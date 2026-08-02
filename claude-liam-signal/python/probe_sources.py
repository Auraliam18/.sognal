#!/usr/bin/env python3
"""Finds out which exchanges actually answer, and in what shape.

Binance is blocked in Iran, which is where this panel is used, so the panel has
to be able to read candles from somewhere else. Picking a replacement off
documentation is guesswork — field orders differ, timestamps are seconds on some
and milliseconds on others, and several of these APIs return newest-first while
Binance returns oldest-first. Getting one of those wrong produces a chart that
looks fine and is reversed.

So this asks each one for real candles and reports what came back: the HTTP
status, how many candles, the raw shape of one row, and whether the series runs
oldest-first. The adapter is then written against what was observed.

It runs on a GitHub runner because the container this was written in cannot
reach any exchange at all.

    python3 probe_sources.py
"""
import json, sys, time, urllib.error, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; hamid-signal-probe)"}
TIMEOUT = 20

# One 15m request for BTC/USDT from each. Several of these are commonly
# reachable where Binance is not, which is the whole point of the list.
SOURCES = [
    # Venues Iranian traders actually reach come first — the point of this list
    # is not completeness, it is finding something that answers from Tehran.
    ("bitunix-futures", "https://fapi.bitunix.com/api/v1/futures/market/kline?symbol=BTCUSDT&interval=15m&limit=10"),
    ("bitunix-openapi", "https://openapi.bitunix.com/api/v1/futures/market/kline?symbol=BTCUSDT&interval=15m&limit=10"),
    ("nobitex",         "https://api.nobitex.ir/market/udf/history?symbol=BTCUSDT&resolution=15&from=1785400000&to=1785600000"),
    ("wallex",          "https://api.wallex.ir/v1/udf/history?symbol=BTCUSDT&resolution=15&from=1785400000&to=1785600000"),
    ("tabdeal",         "https://api.tabdeal.org/r/plots/history/?symbol=BTCUSDT&resolution=15&from=1785400000&to=1785600000"),
    ("ramzinex",        "https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/pairs"),
    ("bingx",           "https://open-api.bingx.com/openApi/spot/v2/market/kline?symbol=BTC-USDT&interval=15m&limit=10"),
    ("bitmart",         "https://api-cloud.bitmart.com/spot/quotation/v3/klines?symbol=BTC_USDT&step=15&limit=10"),
    ("htx",             "https://api.huobi.pro/market/history/kline?symbol=btcusdt&period=15min&size=10"),
    ("phemex",          "https://api.phemex.com/exchange/public/md/v2/kline?symbol=sBTCUSDT&resolution=900&limit=10"),
    ("weex",            "https://api-spot.weex.com/api/v2/market/candles?symbol=BTCUSDT&granularity=900&limit=10"),
    ("cryptocompare",   "https://min-api.cryptocompare.com/data/v2/histominute?fsym=BTC&tsym=USDT&limit=10&aggregate=15"),
    ("coinbase",        "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900"),
    ("kraken",          "https://api.kraken.com/0/public/OHLC?pair=XBTUSDT&interval=15"),
    ("kucoin",          "https://api.kucoin.com/api/v1/market/candles?type=15min&symbol=BTC-USDT"),
    ("okx",             "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=15m&limit=10"),
    ("bybit",           "https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=15&limit=10"),
    ("mexc",            "https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=10"),
    ("gate",            "https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=15m&limit=10"),
    ("bitget",          "https://api.bitget.com/api/v2/spot/market/candles?symbol=BTCUSDT&granularity=15min&limit=10"),
    ("coinex",          "https://api.coinex.com/v2/spot/kline?market=BTCUSDT&period=15min&limit=10"),
    ("lbank",           "https://api.lbkex.com/v2/kline.do?symbol=btc_usdt&size=10&type=minute15&time=1"),
    ("binance",         "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=10"),
]


def rows_of(payload):
    """Dig the candle array out of whatever envelope the exchange used."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("data", "result", "results"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ("list", "klines", "candles", "data"):
                if isinstance(v.get(k2), list):
                    return v[k2]
    return None


def describe(rows):
    """Whatever the row is, say what it looks like and which way time runs."""
    if not rows:
        return {"count": 0}
    first, last = rows[0], rows[-1]
    out = {"count": len(rows), "row_type": type(first).__name__}
    if isinstance(first, dict):
        out["keys"] = sorted(first.keys())[:12]
        out["sample"] = {k: first[k] for k in list(first)[:6]}
        tk = next((k for k in ("time", "ts", "t", "timestamp", "id", "openTime")
                   if k in first), None)
        if tk:
            try:
                a, b = float(first[tk]), float(last[tk])
                out["time_key"] = tk
                out["oldest_first"] = a < b
                out["unit"] = "ms" if a > 1e12 else "s"
            except (TypeError, ValueError):
                pass
    elif isinstance(first, list):
        out["fields"] = len(first)
        out["sample"] = first[:7]
        try:
            a, b = float(first[0]), float(last[0])
            out["time_key"] = "index 0"
            out["oldest_first"] = a < b
            out["unit"] = "ms" if a > 1e12 else "s"
        except (TypeError, ValueError):
            pass
    return out


def probe(name, url):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        return {"name": name, "url": url, "status": e.code,
                "error": e.read()[:180].decode("utf8", "replace")}
    except Exception as e:                          # noqa: BLE001 - unreachable is the answer
        return {"name": name, "url": url, "status": 0, "error": f"{type(e).__name__}: {e}"[:180]}

    ms = int((time.time() - t0) * 1000)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"name": name, "url": url, "status": code, "ms": ms,
                "error": "not JSON: " + raw[:120].decode("utf8", "replace")}

    rows = rows_of(payload)
    d = {"name": name, "url": url, "status": code, "ms": ms}
    if rows is None:
        d["error"] = "no candle array found"
        d["envelope"] = list(payload)[:10] if isinstance(payload, dict) else None
    else:
        d.update(describe(rows))
    return d


def main():
    results = [probe(n, u) for n, u in SOURCES]
    ok = [r for r in results if r.get("count")]

    print(f"\n{'source':<18} {'http':>5} {'ms':>6} {'rows':>5}  shape")
    print("-" * 96)
    for r in results:
        if r.get("count"):
            order = ("oldest→newest" if r.get("oldest_first")
                     else "newest→oldest" if r.get("oldest_first") is False else "order unknown")
            shape = (f"{r['row_type']}"
                     + (f"[{r['fields']}]" if "fields" in r else "")
                     + f"  {order}  time in {r.get('unit','?')}")
            print(f"{r['name']:<18} {r['status']:>5} {r['ms']:>6} {r['count']:>5}  {shape}")
        else:
            print(f"{r['name']:<18} {r.get('status',0):>5} {'':>6} {'':>5}  {r.get('error','')[:60]}")

    print(f"\n{len(ok)} of {len(results)} answered with candles\n")
    for r in ok:
        print(f"── {r['name']}")
        print(f"   {r['url']}")
        print(f"   sample row: {json.dumps(r.get('sample'), ensure_ascii=False)[:220]}")
        if "keys" in r:
            print(f"   keys: {r['keys']}")
        print()

    out = {"probed": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "results": results}
    print(json.dumps(out, ensure_ascii=False, indent=1)[:200] + " …")
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent.parent / "brain" / "sources-probe.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nwritten to brain/sources-probe.json")


if __name__ == "__main__":
    main()
