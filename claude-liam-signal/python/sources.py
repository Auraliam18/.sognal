#!/usr/bin/env python3
"""The venues the panel reads, available to the Python side.

The browser stopped depending on Binance a while ago. Everything that runs on a
GitHub runner — the live scan, the miner, the backtest — did not, and still
asked api.binance.com and nothing else. That held only because the runners
happen to be somewhere Binance answers, and it already stopped being true once:
a runner got HTTP 451 from api.binance.com, and every scheduled job that hour
produced nothing. One venue deciding to refuse should not stop the pipeline any
more than it stops the panel.

So this is the panel's SOURCES table, in Python — ten of the twelve. Bitunix
is not here because its kline endpoint is futures-only and lists a different
set of symbols than the backtest ranks; Coinbase is not here because it quotes
USD, not USDT, and a USD close is not the same number. Both stay in the panel,
where one symbol is charted at a time and that does not matter. The field orders below are not
copied from documentation — they are the rows probe_sources.py actually
received, the same ones tests/sources-parse.mjs checks the JavaScript against,
and test_sources.py re-checks these against the identical rows. That matters
because a wrong field index still parses as a number: it just is not the price.

Two shapes come back out, both in Binance's own shape so no caller changes:

    klines(sym, tf, limit) -> [[open_ms, o, h, l, c, v, close_ms], ...]  oldest first
    tickers()             -> [{"symbol": "BTCUSDT", "quoteVolume": "..."}, ...]

A venue that answers with fewer candles than asked for is skipped rather than
used short. A scan run on 180 candles when the engine wants 420 is not a
degraded scan, it is a different one, and it would not announce itself.
"""
import json
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; hamid-signal)"}
TIMEOUT = 12          # a venue slower than this is not usable at this cadence

# A venue that has just refused three times will refuse the fourth. Walking the
# full list for every one of a hundred-odd requests turns one rate-limited
# exchange into a cycle that takes minutes instead of seconds — which is exactly
# what happened: a run that normally finishes in forty seconds sat for over ten.
# So a failing venue is stood down briefly rather than asked again immediately.
_STOOD_DOWN = {}
_FAILS = {}
STAND_DOWN_SECONDS = 300
FAILS_BEFORE_STAND_DOWN = 3


def _available(vid):
    until = _STOOD_DOWN.get(vid, 0)
    return time.time() >= until


def _note_failure(vid):
    _FAILS[vid] = _FAILS.get(vid, 0) + 1
    if _FAILS[vid] >= FAILS_BEFORE_STAND_DOWN:
        _STOOD_DOWN[vid] = time.time() + STAND_DOWN_SECONDS
        _FAILS[vid] = 0


def _note_success(vid):
    _FAILS[vid] = 0
    _STOOD_DOWN.pop(vid, None)


def _json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _rows(payload, *keys):
    """Dig the array out of whichever envelope this venue wrapped it in."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for k in keys or ("data", "result"):
        v = payload.get(k)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ("list", "klines", "candles", "ticker", "data"):
                if isinstance(v.get(k2), list):
                    return v[k2]
    return None


def _n(x):
    return float(x)


# ── candle adapters ────────────────────────────────────────────────────────
# Each returns rows oldest-first in Binance's shape. The comment on each is the
# row as observed, because that is the only thing that decides these indices.

def _dash(sym):      # BTCUSDT -> BTC-USDT
    return sym[:-4] + "-USDT" if sym.endswith("USDT") else sym


def _under(sym):     # BTCUSDT -> BTC_USDT
    return sym[:-4] + "_USDT" if sym.endswith("USDT") else sym


def _k(t, o, h, l, c, v):
    return [int(t), _n(o), _n(h), _n(l), _n(c), _n(v), int(t)]


VENUES = []


def venue(vid, label, url):
    """Register a venue. `url` builds the request, the decorated function turns
    whatever came back into Binance-shaped rows, oldest first. They are kept
    apart so test_sources.py can hand the parser a recorded reply and check the
    field order without touching the network."""
    def deco(fn):
        VENUES.append({"id": vid, "label": label, "url": url, "parse": fn})
        return fn
    return deco


@venue("mexc", "MEXC",
       lambda s, tf, n: f"https://api.mexc.com/api/v3/klines?symbol={s}"
                        f"&interval={ {'5m':'5m','15m':'15m','1h':'60m','1d':'1d'}[tf] }&limit={n}")
def _mexc(r):
    # [openTime_ms, o, h, l, c, vol, closeTime] — oldest first, Binance's own shape
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@venue("kucoin", "KuCoin",
       lambda s, tf, n: f"https://api.kucoin.com/api/v1/market/candles"
                        f"?type={ {'5m':'5min','15m':'15min','1h':'1hour','1d':'1day'}[tf] }"
                        f"&symbol={_dash(s)}")
def _kucoin(r):
    # [t_s, open, CLOSE, HIGH, LOW, vol, turnover] — newest first, seconds.
    # Close and high swap places against Binance; that is the trap here.
    return [_k(int(x[0]) * 1000, x[1], x[3], x[4], x[2], x[5]) for x in reversed(_rows(r))]


@venue("okx", "OKX",
       lambda s, tf, n: f"https://www.okx.com/api/v5/market/candles?instId={_dash(s)}"
                        f"&bar={ {'5m':'5m','15m':'15m','1h':'1H','1d':'1D'}[tf] }&limit=300")
def _okx(r):
    # [t_ms, o, h, l, c, vol, volCcy] — newest first
    return [_k(int(x[0]), x[1], x[2], x[3], x[4], x[5]) for x in reversed(_rows(r))]


@venue("bitget", "Bitget",
       lambda s, tf, n: f"https://api.bitget.com/api/v2/spot/market/candles?symbol={s}"
                        f"&granularity={ {'5m':'5min','15m':'15min','1h':'1h','1d':'1day'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _bitget(r):
    # [t_ms, o, h, l, c, baseVol, quoteVol] — oldest first
    return [_k(int(x[0]), x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@venue("gate", "Gate.io",
       lambda s, tf, n: f"https://api.gateio.ws/api/v4/spot/candlesticks"
                        f"?currency_pair={_under(s)}"
                        f"&interval={ {'5m':'5m','15m':'15m','1h':'1h','1d':'1d'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _gate(r):
    # [t_s, QUOTEVOL, close, high, low, open, baseVol] — oldest first, seconds.
    # Volume is second and open is last; nothing else lays it out this way.
    return [_k(int(x[0]) * 1000, x[5], x[3], x[4], x[2],
               x[6] if len(x) > 6 else x[1]) for x in _rows(r)]


@venue("bingx", "BingX",
       lambda s, tf, n: f"https://open-api.bingx.com/openApi/spot/v2/market/kline"
                        f"?symbol={_dash(s)}"
                        f"&interval={ {'5m':'5m','15m':'15m','1h':'1h','1d':'1d'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _bingx(r):
    # [t_ms, o, h, l, c, vol, closeTime] — newest first
    return [_k(int(x[0]), x[1], x[2], x[3], x[4], x[5]) for x in reversed(_rows(r))]


@venue("bitmart", "BitMart",
       lambda s, tf, n: f"https://api-cloud.bitmart.com/spot/quotation/v3/klines"
                        f"?symbol={_under(s)}"
                        f"&step={ {'5m':5,'15m':15,'1h':60,'1d':1440}[tf] }&limit={min(n, 500)}")
def _bitmart(r):
    # [t_s, o, h, l, c, baseVol, quoteVol] — oldest first, seconds
    return [_k(int(x[0]) * 1000, x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@venue("htx", "HTX",
       lambda s, tf, n: f"https://api.huobi.pro/market/history/kline?symbol={s.lower()}"
                        f"&period={ {'5m':'5min','15m':'15min','1h':'60min','1d':'1day'}[tf] }"
                        f"&size={min(n, 2000)}")
def _htx(r):
    # {id_s, open, close, low, high, amount} — newest first, seconds
    return [_k(int(x["id"]) * 1000, x["open"], x["high"], x["low"], x["close"],
               x.get("amount", 0)) for x in reversed(_rows(r))]


@venue("coinex", "CoinEx",
       lambda s, tf, n: f"https://api.coinex.com/v2/spot/kline?market={s}"
                        f"&period={ {'5m':'5min','15m':'15min','1h':'1hour','1d':'1day'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _coinex(r):
    # {created_at_ms, open, close, high, low, volume} — oldest first, already ms
    return [_k(int(x["created_at"]), x["open"], x["high"], x["low"], x["close"],
               x.get("volume", 0)) for x in _rows(r)]


@venue("binance", "Binance",
       lambda s, tf, n: f"https://data-api.binance.vision/api/v3/klines?symbol={s}"
                        f"&interval={tf}&limit={n}")
def _binance(r):
    # Last, not first. It is the reference shape and it still answers from a
    # runner most days — but it is the one venue already observed to refuse,
    # with HTTP 451, which is why nothing depends on it any more.
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


# ── the guard ──────────────────────────────────────────────────────────────

def sane(rows, want):
    """Same test the panel applies before it charts anything.

    A reply can be well-formed JSON, parse without error, and still be useless:
    reversed, short, or with two fields swapped. Each of those has happened.
    """
    if not rows or len(rows) < min(want, 10):
        return False
    if len(rows) < want * 0.9:
        return False                                 # short is a different scan
    if rows[0][0] >= rows[-1][0]:
        return False                                 # must run oldest -> newest
    for k in rows:
        o, h, l, c = k[1], k[2], k[3], k[4]
        if not all(x == x for x in (o, h, l, c)):    # NaN
            return False
        if h < l or min(o, h, l, c) <= 0:
            return False
        if h < max(o, c) or l > min(o, c):
            return False
    return True


# ── tickers ────────────────────────────────────────────────────────────────

def _t_mexc():
    r = _json("https://api.mexc.com/api/v3/ticker/24hr")
    return [{"symbol": x["symbol"], "quoteVolume": x.get("quoteVolume", 0)} for x in r]


def _t_okx():
    r = _rows(_json("https://www.okx.com/api/v5/market/tickers?instType=SPOT"))
    return [{"symbol": x["instId"].replace("-", ""), "quoteVolume": x.get("volCcy24h", 0)}
            for x in r]


def _t_gate():
    r = _json("https://api.gateio.ws/api/v4/spot/tickers")
    return [{"symbol": x["currency_pair"].replace("_", ""), "quoteVolume": x.get("quote_volume", 0)}
            for x in r]


def _t_bitget():
    r = _rows(_json("https://api.bitget.com/api/v2/spot/market/tickers"))
    return [{"symbol": x["symbol"], "quoteVolume": x.get("quoteVolume", 0)} for x in r]


def _t_kucoin():
    r = _rows(_json("https://api.kucoin.com/api/v1/market/allTickers"), "data")
    return [{"symbol": x["symbol"].replace("-", ""), "quoteVolume": x.get("volValue", 0)}
            for x in r]


def _t_binance():
    r = _json("https://api.binance.com/api/v3/ticker/24hr")
    return [{"symbol": x["symbol"], "quoteVolume": x.get("quoteVolume", 0)} for x in r]


TICKERS = [("mexc", _t_mexc), ("okx", _t_okx), ("gate", _t_gate),
           ("bitget", _t_bitget), ("kucoin", _t_kucoin), ("binance", _t_binance)]

_used = {"klines": None, "tickers": None}


def used():
    """Which venue actually served, so a report can say where its numbers came from."""
    return dict(_used)


def klines(sym, tf, limit, quiet=True):
    """Candles from the first venue that gives a full, sane series."""
    errs = []
    order = [v for v in VENUES if _available(v["id"])] or VENUES
    for v in order:
        try:
            rows = v["parse"](_json(v["url"](sym, tf, limit)))[-limit:]
        except Exception as e:                       # noqa: BLE001 - next venue
            errs.append(f"{v['id']}: {type(e).__name__}")
            _note_failure(v["id"])
            continue
        if not sane(rows, limit):
            errs.append(f"{v['id']}: {len(rows)} rows, rejected")
            _note_failure(v["id"])
            continue
        _note_success(v["id"])
        if _used["klines"] != v["id"]:
            _used["klines"] = v["id"]
            if not quiet:
                print(f"candles from {v['label']}")
        return rows
    raise RuntimeError(f"{sym} {tf}: no venue answered — {'; '.join(errs[:8])}")


def tickers(quiet=True):
    """24h volume per pair, from the first venue that answers."""
    errs = []
    for vid, fn in TICKERS:
        try:
            rows = fn()
        except Exception as e:                       # noqa: BLE001 - next venue
            errs.append(f"{vid}: {type(e).__name__}")
            continue
        rows = [r for r in rows if r["symbol"].endswith("USDT")]
        if len(rows) < 50:
            errs.append(f"{vid}: only {len(rows)} pairs")
            continue
        if _used["tickers"] != vid:
            _used["tickers"] = vid
            if not quiet:
                print(f"tickers from {vid}")
        return rows
    raise RuntimeError("no venue served tickers — " + "; ".join(errs[:6]))


if __name__ == "__main__":
    t0 = time.time()
    ts = tickers(quiet=False)
    print(f"{len(ts)} USDT pairs")
    kl = klines("BTCUSDT", "15m", 420, quiet=False)
    print(f"{len(kl)} candles, last close {kl[-1][4]}, "
          f"{'oldest→newest' if kl[0][0] < kl[-1][0] else 'REVERSED'}")
    print(f"venues used: {used()}  in {time.time() - t0:.1f}s")
