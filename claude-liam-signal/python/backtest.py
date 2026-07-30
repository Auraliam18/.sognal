#!/usr/bin/env python3
"""Historical backtest of both strategies on real 15m and 5m candles.

Simulated markets answer whether the engine has an edge against a hard model.
They cannot answer what it did on the actual tape, and they cannot test the
rules about thin structure at all — the simulator gives every bar a full range
and ordinary volume, so its inside-candle ratio never passes 0.45. This script
runs the same engine over candles that really traded.

Layout of the work:
  * Python pulls the symbol list and paginates real klines from Binance, in
    parallel, and caches them so a re-run costs nothing.
  * Node replays them through the engine lifted out of index.html, one worker
    per core, so both strategies are measured on identical candles.
  * Python aggregates, with 95% bootstrap intervals, because a difference that
    does not clear zero is not a finding.

  python3 backtest.py --symbols 60 --bars 5000 --tf 15m,5m

Binance is unreachable from some networks; this is built to run on a GitHub
runner, where it is not.
"""
import argparse, json, os, random, statistics, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / ".klines-cache"
OUT = ROOT / "claude-liam-signal" / "backtests"
HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api1.binance.com"]
STABLE = ("USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "EURUSDT", "DAIUSDT", "USDPUSDT")
MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000}


def get(path, tries=4):
    last = None
    for attempt in range(tries):
        host = HOSTS[attempt % len(HOSTS)]
        try:
            req = urllib.request.Request(host + path, headers={"User-Agent": "hamid-signal-backtest"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:                       # noqa: BLE001 - any failure is retryable
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{path}: {last}")


def top_symbols(n):
    """Most-traded USDT pairs, stablecoin pairs dropped — they have no structure."""
    rows = get("/api/v3/ticker/24hr")
    usdt = [r for r in rows if r["symbol"].endswith("USDT") and r["symbol"] not in STABLE
            and not any(k in r["symbol"] for k in ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT"))]
    usdt.sort(key=lambda r: float(r["quoteVolume"]), reverse=True)
    return [r["symbol"] for r in usdt[:n]]


def klines(sym, tf, bars):
    """Paginate backwards until `bars` candles are in hand. Cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sym}-{tf}-{bars}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:                            # noqa: BLE001 - a torn cache file is just a miss
            pass
    step, out, end = MS[tf], [], None
    while len(out) < bars:
        q = f"/api/v3/klines?symbol={sym}&interval={tf}&limit=1000"
        if end:
            q += f"&endTime={end}"
        page = get(q)
        if not page:
            break
        out = page + out
        end = page[0][0] - step
        if len(page) < 1000:
            break
    cd = [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
           "c": float(k[4]), "v": float(k[5])} for k in out[-bars:]]
    f.write_text(json.dumps(cd))
    return cd


def boot(vals, n=5000):
    """95% interval around the mean, by resampling. Nothing is acted on until
    this clears zero."""
    if len(vals) < 20:
        return None
    k, means = len(vals), []
    for _ in range(n):
        means.append(sum(random.choice(vals) for _ in range(k)) / k)
    means.sort()
    return means[int(n * 0.025)], means[int(n * 0.975)]


def boot_diff(a, b, n=5000):
    if len(a) < 20 or len(b) < 20:
        return None
    d = []
    for _ in range(n):
        ma = sum(random.choice(a) for _ in range(len(a))) / len(a)
        mb = sum(random.choice(b) for _ in range(len(b))) / len(b)
        d.append(ma - mb)
    d.sort()
    return d[int(n * 0.025)], d[int(n * 0.975)]


def run_variant(variant, jobs, cores, tmp):
    """One Node worker per core, each given a slice of the symbol/timeframe list."""
    shards = [jobs[i::cores] for i in range(cores)]
    procs = []
    for i, shard in enumerate(shards):
        if not shard:
            continue
        p = tmp / f"{variant}-{i}.json"
        p.write_text(json.dumps(shard))
        procs.append(subprocess.Popen(
            ["node", str(HERE / "bt_worker.js"), variant, str(p)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    trades = []
    for p in procs:
        so, se = p.communicate()
        if p.returncode != 0:
            raise RuntimeError(f"{variant} worker failed: {se.decode()[:600]}")
        trades += json.loads(so.decode() or "[]")
    return trades


def describe(name, trades):
    if not trades:
        return {"name": name, "n": 0}
    rs = [t["r"] for t in trades]
    ci = boot(rs)
    return {
        "name": name, "n": len(trades),
        "win": round(100 * sum(t["w"] for t in trades) / len(trades), 1),
        "exp": round(statistics.fmean(rs), 3),
        "ci": [round(ci[0], 3), round(ci[1], 3)] if ci else None,
        "median_bars": statistics.median([t["bars"] for t in trades]),
        "by_exit": {w: sum(1 for t in trades if t["why"] == w)
                    for w in sorted({t["why"] for t in trades})},
    }


def line(d):
    if not d["n"]:
        return f"  {d['name']:<34} no trades"
    ci = f"[{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}]" if d["ci"] else "—"
    mark = ""
    if d["ci"]:
        mark = "  ✓ above zero" if d["ci"][0] > 0 else ("  ✗ below zero" if d["ci"][1] < 0 else "  — spans zero")
    return f"  {d['name']:<34} n={d['n']:>5}  win={d['win']:>5.1f}%  E={d['exp']:+.3f}R  {ci}{mark}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=60)
    ap.add_argument("--bars", type=int, default=5000)
    ap.add_argument("--tf", default="15m,5m")
    ap.add_argument("--cores", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()
    tfs = [t.strip() for t in args.tf.split(",") if t.strip()]

    t0 = time.time()
    print(f"symbols: fetching the {args.symbols} most-traded USDT pairs", flush=True)
    syms = top_symbols(args.symbols)
    print(f"  {', '.join(syms[:12])}{' …' if len(syms) > 12 else ''}", flush=True)

    pairs = [(s, tf) for tf in tfs for s in syms]
    print(f"candles: {len(pairs)} series × {args.bars} bars", flush=True)
    jobs, failed = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(klines, s, tf, args.bars): (s, tf) for s, tf in pairs}
        for f, (s, tf) in futs.items():
            try:
                cd = f.result()
                if len(cd) >= 400:
                    jobs.append({"sym": s, "tf": tf, "candles": cd})
                else:
                    failed.append(f"{s} {tf} (only {len(cd)} bars)")
            except Exception as e:                   # noqa: BLE001 - one bad series must not sink the run
                failed.append(f"{s} {tf}: {e}")
    if failed:
        print(f"  skipped {len(failed)}: {'; '.join(failed[:5])}", flush=True)
    if not jobs:
        sys.exit("no candles fetched — check network reachability to Binance")

    span_days = args.bars * MS[tfs[0]] / 86_400_000
    print(f"  {len(jobs)} series in hand, ≈{span_days:.0f} days of {tfs[0]} history each", flush=True)

    tmp = HERE / ".bt-tmp"
    tmp.mkdir(exist_ok=True)
    results = {}
    for variant, label in (("base", "استراتژی اصلی — کانال + اردر بلاک + پولبک"),
                           ("channel", "استراتژی کانالی — با سه قانون جدید")):
        print(f"replay: {variant} on {args.cores} cores", flush=True)
        results[variant] = run_variant(variant, jobs, args.cores, tmp)
        print(f"  {len(results[variant])} trades", flush=True)

    report = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
              "source": "real Binance candles", "symbols": len(syms), "bars": args.bars,
              "timeframes": tfs, "series": len(jobs), "strategies": {}}

    print("\n" + "=" * 78)
    print("HISTORICAL BACKTEST — real candles, not simulated")
    print("=" * 78)
    for variant, label in (("base", "base — as shipped"), ("channel", "channel — three rules required")):
        tr = results[variant]
        print(f"\n{label}")
        overall = describe("overall", tr)
        print(line(overall))
        per_tf = {}
        for tf in tfs:
            d = describe(f"{tf} only", [t for t in tr if t["tf"] == tf])
            per_tf[tf] = d
            print(line(d))
        longs = describe("long", [t for t in tr if t["dir"] == "LONG"])
        shorts = describe("short", [t for t in tr if t["dir"] == "SHORT"])
        print(line(longs)); print(line(shorts))
        if overall["n"]:
            print(f"  exits: {overall['by_exit']}")
        report["strategies"][variant] = {"overall": overall, "by_tf": per_tf,
                                         "long": longs, "short": shorts}

    a = [t["r"] for t in results["base"]]
    b = [t["r"] for t in results["channel"]]
    print("\nchannel versus base")
    if a and b:
        d = boot_diff(b, a)
        gap = statistics.fmean(b) - statistics.fmean(a)
        verdict = "spans zero — the rules did not earn a gate"
        if d and d[0] > 0:
            verdict = "clears zero — the rules earned a gate"
        elif d and d[1] < 0:
            verdict = "below zero — the rules cost expectancy"
        print(f"  Δ = {gap:+.3f}R  " + (f"[{d[0]:+.3f}, {d[1]:+.3f}]  {verdict}" if d else "too few trades"))
        print(f"  trades kept: {len(b)} of {len(a)}  ({100*len(b)/max(1,len(a)):.0f}%)")
        report["comparison"] = {"delta": round(gap, 3), "ci": [round(d[0], 3), round(d[1], 3)] if d else None,
                                "verdict": verdict, "kept": len(b), "of": len(a)}

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M", time.gmtime())
    (OUT / f"backtest-{stamp}.json").write_text(json.dumps(
        {**report, "trades": {k: v for k, v in results.items()}}, indent=1))
    (OUT / "latest.json").write_text(json.dumps(report, indent=1))
    print(f"\nwritten to claude-liam-signal/backtests/backtest-{stamp}.json")
    print(f"took {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
