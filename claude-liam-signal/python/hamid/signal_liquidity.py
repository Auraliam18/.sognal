"""Eligibility for a trade signal on the Bitunix USDT futures market."""
import json
import math
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import fees, sizing
from .execution_gate import REF_EQUITY
from .market_quotes import BITUNIX, MAX_AGE_MS, URLS, now_ms

LIMIT = 50
RANK_AGE = 60_000
_lock = threading.Lock()
_cached = {}
_retry_at = 0


def _get(resource, age, **params):
    url = URLS[BITUNIX].rsplit("/", 1)[0] + "/" + resource
    if params:
        url += "?" + urlencode(params)
    with urlopen(Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "LiamTerminal/1.0"}), timeout=5) as response:
        at = int(parsedate_to_datetime(response.headers["Date"]).timestamp() * 1000)
        packet = json.load(response)
    if not -2000 <= now_ms() - at <= age:
        raise ValueError("stale_" + resource)
    if str(packet["code"]) != "0":
        raise ValueError("unavailable_" + resource)
    return packet["data"], at


def _number(value):
    if isinstance(value, bool):
        raise ValueError("invalid_number")
    n = float(value)
    if not math.isfinite(n) or n < 0:
        raise ValueError("invalid_number")
    return n


def _rank(directory, tickers):
    active = {r["symbol"] for r in directory if r["symbolStatus"] == "OPEN" and r["quote"] == "USDT"}
    volumes = {}
    for row in tickers:
        sym = row["symbol"]
        if sym in active:
            if sym in volumes:
                raise ValueError("duplicate_ticker")
            volumes[sym] = _number(row["quoteVol"])
    if volumes.keys() != active:
        raise ValueError("incomplete_ticker_coverage")
    ordered = sorted((s for s in volumes if volumes[s] > 0), key=lambda s: (-volumes[s], s))
    if len(ordered) < LIMIT:
        raise ValueError("incomplete_ranking")
    return {s: {"rank": i, "volume_usdt": volumes[s]} for i, s in enumerate(ordered[:LIMIT], 1)}


def policy():
    global _cached, _retry_at
    with _lock:
        if _cached.get("members") and -2000 <= now_ms() - _cached["at"] <= RANK_AGE:
            return _cached
        if not _cached.get("members") and time.monotonic() < _retry_at:
            return _cached
        p = {"venue": BITUNIX, "metric": "quoteVol_24h_USDT", "limit": LIMIT, "members": {}}
        try:
            directory, da = _get("trading_pairs", RANK_AGE)
            tickers, ta = _get("tickers", RANK_AGE)
            p["members"] = _rank(directory, tickers)
            p["at"] = min(da, ta)
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
            p["error"] = str(error)[:160]
            _retry_at = time.monotonic() + 5
        _cached = p
        return p


def prioritize(symbols, limit, ranking):
    return list(dict.fromkeys([*ranking["members"], *symbols]))[:limit]


def _book_cost(book, notional):
    sides = []
    for side in ("bids", "asks"):
        levels = [(_number(price), _number(qty)) for price, qty in book[side]]
        if not levels or any(p <= 0 or q <= 0 for p, q in levels):
            raise ValueError("invalid_depth")
        prices = [p for p, _ in levels]
        if len(set(prices)) != len(prices) or sorted(prices, reverse=side == "bids") != prices:
            raise ValueError("unsorted_depth")
        sides.append(levels)
    bid, ask = sides[0][0][0], sides[1][0][0]
    if bid >= ask:
        raise ValueError("crossed_depth")
    mid = (bid + ask) / 2
    impacts = []
    # Fill the same base position on both sides, including the spread.
    quantity = notional / mid
    for levels in sides:
        left, value = quantity, 0.0
        for price, qty in levels:
            fill = min(left, qty)
            value += fill * price
            left -= fill
            if left <= 0:
                break
        if left > quantity * 1e-12:
            raise ValueError("insufficient_depth")
        impacts.append(abs(value / quantity / mid - 1) * 100)
    return max(impacts)


def assess(signal, ranking=None):
    ranking = policy() if ranking is None else ranking
    sym = signal.get("sym") or signal.get("symbol")
    evidence = {"ok": False, "venue": BITUNIX, "rank_at": ranking.get("at")}
    if not ranking["members"] or not -2000 <= now_ms() - ranking["at"] <= RANK_AGE:
        return dict(evidence, reason="unverified_ranking")
    if sym not in ranking["members"]:
        return dict(evidence, reason="outside_top50")
    evidence.update(ranking["members"][sym])
    try:
        if signal.get("notional_usd") is not None:
            size = _number(signal["notional_usd"])
        else:
            entry, stop = _number(signal["entry"]), _number(signal["sl"])
            if not entry or not stop:
                raise ValueError("invalid_position_size")
            size = sizing.position(REF_EQUITY, entry, stop, leverage=5)["notional_usd"]
        if size <= 0:
            raise ValueError("invalid_position_size")
        limit = _number(fees.config()["slippage_pct_per_leg"])
        evidence.update(notional_usdt=size, limit_pct=limit)
        book, at = _get("depth", MAX_AGE_MS, symbol=sym, limit=50)
        evidence["book_at"] = at
        cost = _book_cost(book, size)
        evidence["slippage_pct"] = round(cost, 8)
        if now_ms() - ranking["at"] > RANK_AGE:
            return dict(evidence, reason="unverified_ranking")
        if cost > limit:
            return dict(evidence, reason="slippage_limit")
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        return dict(evidence, reason=str(error)[:120])
    return dict(evidence, ok=True, reason="eligible")


def screen(candidates):
    accepted, held = [], []
    for row in candidates:
        check = row["liquidity_check"] = assess(row)
        (accepted if check["ok"] else held).append(row)
    accepted.sort(key=lambda row: row["liquidity_check"]["rank"])
    return accepted, held
