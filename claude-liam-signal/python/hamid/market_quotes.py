"""Public, venue-qualified quotes. Candles/strategy levels are never current quotes."""
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
import json
import math
import time
from urllib.request import Request, urlopen

BITUNIX = "Bitunix futures"
URLS = {
    BITUNIX: "https://fapi.bitunix.com/api/v1/futures/market/tickers",
    "OKX swap": "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
    "Bitget spot": "https://api.bitget.com/api/v2/spot/market/tickers",
    "MEXC spot": "https://api.mexc.com/api/v3/ticker/24hr",
    "Binance spot": "https://data-api.binance.vision/api/v3/ticker/24hr?type=MINI",
}
MAX_AGE_MS = 15000


def now_ms():
    return int(time.time() * 1000)


def parse_quote(source, row, response_time, now):
    if source == "OKX swap":
        instrument = row.get("instId", "")
        if not instrument.endswith("-USDT-SWAP"):
            return None
        symbol = instrument[:-10] + "USDT"
        last, at = row.get("last"), row.get("ts")
    else:
        symbol = row.get("symbol")
        if source == BITUNIX:
            last, at = row.get("last"), response_time
        elif source == "Bitget spot":
            last, at = row.get("lastPr"), row.get("ts")
        else:
            last, at = row.get("lastPrice"), row.get("closeTime")
    if not isinstance(symbol, str) or not symbol.endswith("USDT"):
        return None
    if isinstance(last, bool) or isinstance(at, bool):
        return None
    try:
        price, at = float(last), int(at)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(price) or price <= 0 or not -2000 <= now - at <= MAX_AGE_MS:
        return None
    return {"symbol":symbol, "price":price, "venue":source, "observed_at":at,
            "clock":"http_date" if source == BITUNIX else "exchange_timestamp"}


def fetch(source):
    request = Request(URLS[source], headers={"User-Agent":"LiamTerminal/1.0", "Cache-Control":"no-cache"})
    with urlopen(request, timeout=5) as response:
        packet = json.load(response)
        at = int(parsedate_to_datetime(response.headers["Date"]).timestamp()*1000) if source == BITUNIX else None
    if source in ("MEXC spot", "Binance spot"):
        rows = packet
    else:
        if str(packet.get("code")) not in ("0", "00000"):
            raise ValueError("exchange rejected ticker request")
        rows = packet["data"]
    if not isinstance(rows, list):
        raise ValueError("invalid ticker rows")
    now = now_ms()
    quotes = {}
    for row in rows:
        if isinstance(row, dict):
            quote = parse_quote(source, row, at, now)
            if quote:
                quotes[quote["symbol"]] = quote
    if not quotes:
        raise ValueError("no fresh quotes")
    return quotes


_execution_cache = {}
_cached_at = 0


def execution_quote(symbol):
    global _execution_cache, _cached_at
    now = now_ms()
    if not 0 <= now-_cached_at <= 3000:
        _execution_cache = fetch(BITUNIX)
        _cached_at = now_ms()
    q = _execution_cache.get(symbol)
    if not q or not -2000 <= now_ms()-q["observed_at"] <= MAX_AGE_MS:
        raise ValueError("no fresh Bitunix futures quote")
    return dict(q)


def snapshot(symbols):
    """At scan time only. Other venues support research, never the delivery gate."""
    requested = set(symbols)
    quotes, errors = {}, {}
    with ThreadPoolExecutor(max_workers=len(URLS)) as pool:
        jobs = {source:pool.submit(fetch, source) for source in URLS}
        for source, job in jobs.items():
            try:
                batch = job.result()
            except (ValueError, TypeError, KeyError, OSError) as error:
                errors[source] = type(error).__name__
                continue
            for symbol in requested.intersection(batch):
                if now_ms()-batch[symbol]["observed_at"] <= MAX_AGE_MS:
                    quotes.setdefault(symbol, batch[symbol])
    return {"captured_at":now_ms(), "quotes":quotes, "requested":len(requested),
            "missing":sorted(requested-quotes.keys()), "source_errors":errors}


def entry_check(signal, quote):
    """Apply the existing entry-distance bounds against the execution venue only."""
    if (not quote or quote.get("venue") != BITUNIX or quote.get("symbol") != (signal.get("sym") or signal.get("symbol"))
            or not -2000 <= now_ms()-quote["observed_at"] <= MAX_AGE_MS):
        return "no_execution_quote", None
    entry, stop = signal.get("entry"), signal.get("sl")
    if not entry or not stop or signal.get("dir") not in ("LONG","SHORT"):
        return "invalid_levels", None
    signed = (quote["price"]-entry)/entry * (1 if signal["dir"] == "LONG" else -1)
    if signed < -0.5 * abs(entry-stop)/entry:
        return "passed_entry", signed
    if signed > 0.025:
        return "far_from_entry", signed
    return "within_entry_window", signed

