#!/usr/bin/env python3
"""Fast screener: which symbols are worth the engine's attention right now.

The engine's full evaluation is expensive and runs on every closed candle for
every symbol. Most of those symbols have nothing happening. This narrows the
field first, cheaply, using only what one bulk request already gives us plus a
short candle pull — so the expensive work lands where a setup is plausible.

Multiprocessing because the laptop has cores and the network waits are what
actually cost time.

    python3 screener.py                  # top 100 by volume, ranked
    python3 screener.py --top 200 --json # more symbols, machine-readable
"""
import argparse, json, math, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import URLError

HOSTS = ["https://fapi.binance.com", "https://fapi1.binance.com",
         "https://fapi2.binance.com", "https://fapi3.binance.com"]
UA = {"User-Agent": "claude-liam-signal/screener"}


def get(path, tries=3):
    """Binance geo-blocks some regions; walk the mirrors before giving up."""
    last = None
    for attempt in range(tries):
        for host in HOSTS:
            try:
                with urlopen(Request(host + path, headers=UA), timeout=15) as r:
                    return json.loads(r.read())
            except Exception as e:          # noqa: BLE001 — any failure means try the next host
                last = e
        time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"no host answered for {path}: {last}")


def klines(symbol, interval, limit):
    raw = get(f"/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in raw]


def atr(c, period=14):
    if len(c) < period + 1:
        return 0.0
    trs = [max(c[i]["h"] - c[i]["l"],
               abs(c[i]["h"] - c[i - 1]["c"]),
               abs(c[i]["l"] - c[i - 1]["c"]))
           for i in range(len(c) - period, len(c))]
    return sum(trs) / period


def swings(c, k=4):
    """Pivot highs and lows. Ties are allowed — real tape is full of them, and
    disqualifying a pivot for an equal neighbour throws away most of them."""
    out = []
    for i in range(k, len(c) - k):
        hi = all(c[j]["h"] <= c[i]["h"] for j in range(i - k, i + k + 1) if j != i)
        lo = all(c[j]["l"] >= c[i]["l"] for j in range(i - k, i + k + 1) if j != i)
        if hi:
            out.append((i, c[i]["h"], "H"))
        if lo:
            out.append((i, c[i]["l"], "L"))
    return out


def score(symbol, quote_vol, change):
    """Cheap proxies for 'a setup could be forming here', in the engine's terms.

    Deliberately not the engine: this decides where to look, not what to trade.
    """
    try:
        c = klines(symbol, "15m", 120)
    except Exception:
        return None
    if len(c) < 60:
        return None

    a = atr(c) or 1e-9
    last = c[-1]["c"]
    sw = swings(c)
    if not sw:
        return None

    # A recent structure break is the single thing that mattered most in
    # measurement — expectancy fell monotonically with how long ago it happened.
    recent_break, bars_since = False, 999
    for idx, price, kind in reversed(sw[-8:]):
        for j in range(idx + 1, len(c)):
            broke = (c[j]["c"] < price) if kind == "L" else (c[j]["c"] > price)
            if broke and abs(c[j]["c"] - price) >= a * 0.35:
                recent_break = True
                bars_since = min(bars_since, len(c) - 1 - j)
                break
        if recent_break:
            break

    span = max(x["h"] for x in c[-60:]) - min(x["l"] for x in c[-60:])
    vol_now = sum(x["v"] for x in c[-6:]) / 6
    vol_base = sum(x["v"] for x in c[-60:-6]) / 54 or 1e-9

    pts = 0.0
    if recent_break:
        pts += 40 if bars_since <= 10 else 25 if bars_since <= 20 else 8
    pts += min(20, (a / last) * 4000)                 # room to move, relative to price
    pts += min(15, (vol_now / vol_base - 1) * 20)     # participation picking up
    pts += min(15, (span / last) * 300)               # a range worth targeting
    pts += min(10, math.log10(max(quote_vol, 1) / 1e6) * 3)

    return {"symbol": symbol, "score": round(pts, 1), "bars_since_break": bars_since,
            "atr_pct": round(a / last * 100, 3),
            "vol_ratio": round(vol_now / vol_base, 2),
            "range_pct": round(span / last * 100, 2),
            "quote_vol_m": round(quote_vol / 1e6),
            "change_24h": round(change, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=100, help="symbols to screen, by volume")
    ap.add_argument("--show", type=int, default=25, help="rows to print")
    ap.add_argument("--workers", type=int, default=min(16, (os.cpu_count() or 4) * 4))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="write full ranking to this path")
    args = ap.parse_args()

    t0 = time.time()
    try:
        tickers = get("/fapi/v1/ticker/24hr")
    except RuntimeError as e:
        print(f"No Binance host answered. If you are behind a geo-block, a VPN "
              f"is what fixes this.\n  {e}", file=sys.stderr)
        return 2

    universe = sorted(
        (t for t in tickers
         if t["symbol"].endswith("USDT")
         and not any(t["symbol"].endswith(x + "USDT") for x in ("UP", "DOWN", "BULL", "BEAR"))),
        key=lambda t: float(t["quoteVolume"]), reverse=True)[:args.top]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(
            lambda t: score(t["symbol"], float(t["quoteVolume"]), float(t["priceChangePercent"])),
            universe))
    rows = sorted((r for r in rows if r), key=lambda r: r["score"], reverse=True)
    secs = time.time() - t0

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "screened": len(universe), "seconds": round(secs, 1),
                       "rows": rows}, f, indent=1)

    if args.json:
        print(json.dumps(rows, indent=1))
        return 0

    print(f"{len(universe)} symbols screened in {secs:.1f}s on {args.workers} workers\n")
    print(f"{'symbol':<14}{'score':>7}{'break':>8}{'atr%':>8}{'vol×':>7}{'range%':>8}{'vol $m':>9}")
    print("-" * 61)
    for r in rows[:args.show]:
        b = r["bars_since_break"]
        print(f"{r['symbol']:<14}{r['score']:>7}{(str(b) if b < 999 else '—'):>8}"
              f"{r['atr_pct']:>8}{r['vol_ratio']:>7}{r['range_pct']:>8}{r['quote_vol_m']:>9}")
    fresh = [r for r in rows if r["bars_since_break"] <= 10]
    print(f"\n{len(fresh)} broke structure within the last 10 candles — "
          f"the band where expectancy was measured positive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
