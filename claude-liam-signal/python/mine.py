#!/usr/bin/env python3
"""Mines the past of the top coins with both strategies and stores what it learns.

This is what paper trading means here. Not a made-up account: go back through
candles that really traded, find every place the strategy fired, see what
actually happened next, and keep it — with enough of the surrounding conditions
that the reason can be found later.

For each coin, on 15m, up to 15 long setups and 15 short setups per strategy, so
neither side can dominate the sample by accident and both strategies are judged
on the same coins over the same days.

Dominance is recorded at the moment each setup fired. Binance lists BTCDOMUSDT
as a perpetual, which is real BTC dominance rather than a proxy, and BTCUSDT
gives the market's own direction. Both are fetched on the same 15m grid and
looked up by timestamp, so a stored experience says not only what happened but
what the market looked like while it happened.

Then the part that matters: `reasons` asks which conditions keep showing up on
the winners and which keep showing up on the losers. A reason invented per trade
would be a story. A condition that survives a few hundred repetitions, with a
confidence interval that clears zero, is a finding — and only those get written
down as patterns.

    python3 mine.py --symbols 70 --days 30
"""
import argparse, json, os, random, statistics, subprocess, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import brain
from backtest import get, STABLE

MS15 = 900_000
CTX = {"btc": "BTCUSDT", "btcdom": "BTCDOMUSDT"}


def top_symbols_by_volume(n):
    rows = get("/api/v3/ticker/24hr")
    usdt = [r for r in rows if r["symbol"].endswith("USDT") and r["symbol"] not in STABLE
            and not any(k in r["symbol"] for k in ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT"))]
    usdt.sort(key=lambda r: float(r["quoteVolume"]), reverse=True)
    return [r["symbol"] for r in usdt[:n]]


def klines(sym, tf, bars, futures=False):
    """Paginate back until `bars` candles are in hand."""
    step = MS15 if tf == "15m" else 300_000
    out, end = [], None
    base = "/fapi/v1/klines" if futures else "/api/v3/klines"
    while len(out) < bars:
        q = f"{base}?symbol={sym}&interval={tf}&limit=1500"
        if end:
            q += f"&endTime={end}"
        page = get(q, futures=futures)
        if not page:
            break
        out = page + out
        end = page[0][0] - step
        if len(page) < 1000:
            break
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
             "c": float(k[4]), "v": float(k[5])} for k in out[-bars:]]


def boot_ci(vals, n=3000):
    if len(vals) < 25:
        return None
    k = len(vals)
    m = sorted(sum(random.choice(vals) for _ in range(k)) / k for _ in range(n))
    return m[int(n * 0.025)], m[int(n * 0.975)]


CONDITIONS = [
    ("کانال هم‌جهت با ستاپ", lambda e: e.get("channelAligned") == 1),
    ("کانال خلاف ستاپ", lambda e: e.get("channelAligned") == 0),
    ("FVG هم‌جهت دارد", lambda e: e.get("fvg") == 1),
    ("روی سطح کلیدی", lambda e: e.get("level") == 1),
    ("ADX بالای ۲۵", lambda e: (e.get("adx") or 0) >= 25),
    ("ADX زیر ۲۰", lambda e: (e.get("adx") or 99) < 20),
    ("پولبک دوم یا بیشتر", lambda e: (e.get("visits") or 0) >= 2),
    ("نقدینگی جمع شده", lambda e: e.get("swept") == 1),
    ("جای حرکت بیش از ۱.۵ برابر", lambda e: (e.get("room") or 0) >= 1.5),
    ("جای حرکت کمتر از ۱ برابر", lambda e: (e.get("room") or 99) < 1),
    ("R:R بالای ۲.۵", lambda e: (e.get("rr") or 0) >= 2.5),
    ("CHOCH دارد", lambda e: e.get("choch") == 1),
    ("داخل اردر بلاک", lambda e: e.get("inOB") == 1),
    ("بیت‌کوین صعودی", lambda e: e.get("btc_dir") == "UP"),
    ("بیت‌کوین نزولی", lambda e: e.get("btc_dir") == "DOWN"),
    ("دامیننس بیت‌کوین صعودی", lambda e: e.get("btcdom_dir") == "UP"),
    ("دامیننس بیت‌کوین نزولی", lambda e: e.get("btcdom_dir") == "DOWN"),
    ("لانگ همسو با بیت‌کوین", lambda e: e.get("dir") == "LONG" and e.get("btc_dir") == "UP"),
    ("شورت همسو با بیت‌کوین", lambda e: e.get("dir") == "SHORT" and e.get("btc_dir") == "DOWN"),
    ("لانگ خلاف بیت‌کوین", lambda e: e.get("dir") == "LONG" and e.get("btc_dir") == "DOWN"),
    ("شورت خلاف بیت‌کوین", lambda e: e.get("dir") == "SHORT" and e.get("btc_dir") == "UP"),
]


def reasons(exps, strategy):
    """Which conditions keep showing up on winners, and which on losers.

    The comparison is against the same strategy's own baseline, so a condition
    is only credited with the difference it makes — not with the strategy's
    overall performance, which it would otherwise inherit for free.
    """
    pool = [e for e in exps if e["strategy"] == strategy]
    if len(pool) < 40:
        return []
    base = statistics.fmean(e["r"] for e in pool)
    out = []
    for label, test in CONDITIONS:
        hit = [e["r"] for e in pool if test(e)]
        miss = [e["r"] for e in pool if not test(e)]
        if len(hit) < 25 or len(miss) < 25:
            continue
        d = statistics.fmean(hit) - statistics.fmean(miss)
        n = 3000
        diffs = sorted(
            sum(random.choice(hit) for _ in range(len(hit))) / len(hit) -
            sum(random.choice(miss) for _ in range(len(miss))) / len(miss)
            for _ in range(n))
        lo, hi = diffs[int(n * 0.025)], diffs[int(n * 0.975)]
        out.append({
            "condition": label, "strategy": strategy, "n": len(hit),
            "hit_rate": round(100 * sum(1 for e in pool if test(e) and e["r"] > 0) / len(hit), 1),
            "ev": round(statistics.fmean(hit), 3), "baseline": round(base, 3),
            "delta": round(d, 3), "ci": [round(lo, 3), round(hi, 3)],
            "verdict": "مثبت" if lo > 0 else "منفی" if hi < 0 else "بی‌اثر",
        })
    out.sort(key=lambda x: -abs(x["delta"]))
    return out


def summarise(exps, strategy):
    pool = [e for e in exps if e["strategy"] == strategy]
    if not pool:
        return {"strategy": strategy, "n": 0}
    rs = [e["r"] for e in pool]
    ci = boot_ci(rs)
    longs = [e["r"] for e in pool if e["dir"] == "LONG"]
    shorts = [e["r"] for e in pool if e["dir"] == "SHORT"]
    return {
        "strategy": strategy, "n": len(pool),
        "win": round(100 * sum(e["win"] for e in pool) / len(pool), 1),
        "ev": round(statistics.fmean(rs), 3),
        "ci": [round(ci[0], 3), round(ci[1], 3)] if ci else None,
        "long": {"n": len(longs), "ev": round(statistics.fmean(longs), 3) if longs else None,
                 "win": round(100 * sum(1 for r in longs if r > 0) / len(longs), 1) if longs else None},
        "short": {"n": len(shorts), "ev": round(statistics.fmean(shorts), 3) if shorts else None,
                  "win": round(100 * sum(1 for r in shorts if r > 0) / len(shorts), 1) if shorts else None},
        "exits": {k: sum(1 for e in pool if e["outcome"] == k)
                  for k in sorted({e["outcome"] for e in pool})},
        "symbols": len({e["sym"] for e in pool}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=70)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--per-side", type=int, default=15)
    ap.add_argument("--tf", default="15m")
    ap.add_argument("--cores", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    t0 = time.time()
    bars = int(args.days * 24 * 60 / (15 if args.tf == "15m" else 5))
    print(f"mining {args.symbols} symbols × {args.days} days on {args.tf} "
          f"({bars} bars each), up to {args.per_side} per side per strategy", flush=True)

    syms = top_symbols_by_volume(args.symbols)
    print(f"  {', '.join(syms[:10])} …", flush=True)

    print("context: BTCUSDT and BTCDOMUSDT on the same grid", flush=True)
    context = {}
    for name, sym in CTX.items():
        try:
            context[name] = klines(sym, args.tf, bars, futures=(name == "btcdom"))
            print(f"  {name}: {len(context[name])} bars", flush=True)
        except Exception as e:                       # noqa: BLE001 - context is not worth failing over
            print(f"  {name}: unavailable ({e})", flush=True)

    jobs, failed = [], 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(klines, s, args.tf, bars): s for s in syms}
        for f, s in futs.items():
            try:
                cd = f.result()
                if len(cd) >= 400:
                    jobs.append({"sym": s, "tf": args.tf, "candles": cd,
                                 "context": context, "perSide": args.per_side})
            except Exception:                        # noqa: BLE001 - one bad series is not fatal
                failed += 1
    print(f"  {len(jobs)} series in hand, {failed} failed", flush=True)
    if not jobs:
        sys.exit("no candles — is Binance reachable from here?")

    tmp = HERE / ".mine-tmp"
    tmp.mkdir(exist_ok=True)
    procs = []
    for i in range(args.cores):
        shard = jobs[i::args.cores]
        if not shard:
            continue
        p = tmp / f"mine-{i}.json"
        p.write_text(json.dumps(shard))
        procs.append(subprocess.Popen(["node", str(HERE / "mine_worker.js"), str(p)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    print(f"mining on {len(procs)} cores…", flush=True)
    exps = []
    for p in procs:
        so, se = p.communicate()
        if p.returncode != 0:
            sys.exit(f"mine worker failed: {se.decode()[:800]}")
        exps += json.loads(so.decode() or "[]")
    for f in tmp.glob("*.json"):
        f.unlink()

    print(f"  {len(exps)} setups mined in {time.time()-t0:.0f}s", flush=True)
    if not exps:
        sys.exit("no setups found — that is a result, but check the fire conditions")

    for e in exps:
        brain.learn(e)
    brain.event("mine", symbols=len(jobs), days=args.days, tf=args.tf,
                found=len(exps),
                by_strategy={s: sum(1 for e in exps if e["strategy"] == s)
                             for s in ("ibs", "smc")})
    idx = brain.build_index()

    report = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
              "symbols": len(jobs), "days": args.days, "tf": args.tf,
              "total": len(exps), "strategies": {}, "reasons": {}}

    print("\n" + "=" * 74)
    print(f"MINED THE PAST — {len(jobs)} symbols, {args.days} days, real candles")
    print("=" * 74)
    for strat, label in (("ibs", "استراتژی ۱ — IBS + پولبک"),
                         ("smc", "استراتژی ۲ — کانال + اردر بلاک")):
        s = summarise(exps, strat)
        report["strategies"][strat] = s
        print(f"\n{label}  ({strat})")
        if not s["n"]:
            print("   no setups"); continue
        ci = f"[{s['ci'][0]:+.3f}, {s['ci'][1]:+.3f}]" if s["ci"] else "—"
        mark = "" if not s["ci"] else ("  ✓" if s["ci"][0] > 0 else "  ✗" if s["ci"][1] < 0 else "  —")
        print(f"   {s['n']:>5} setups on {s['symbols']} coins · win {s['win']}% · EV {s['ev']:+.3f}R  {ci}{mark}")
        if s["long"]["n"]:
            print(f"   long  {s['long']['n']:>5} · win {s['long']['win']}% · EV {s['long']['ev']:+.3f}R")
        if s["short"]["n"]:
            print(f"   short {s['short']['n']:>5} · win {s['short']['win']}% · EV {s['short']['ev']:+.3f}R")
        print(f"   exits: {s['exits']}")

        rs = reasons(exps, strat)
        report["reasons"][strat] = rs
        acted = [r for r in rs if r["verdict"] != "بی‌اثر"]
        print(f"\n   شرایطی که واقعاً فرق می‌کنند ({len(acted)} از {len(rs)} آزموده‌شده):")
        for r in acted[:10]:
            print(f"     {r['verdict']:<5} {r['condition']:<32} n={r['n']:>4} "
                  f"win {r['hit_rate']:>5.1f}%  Δ{r['delta']:+.3f}R  "
                  f"[{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]")
        if not acted:
            print("     هیچ‌کدام بازه‌اش از صفر عبور نکرد — یعنی هنوز چیزی برای عمل کردن نیست.")
        for r in acted:
            brain.save_pattern(f"{strat}-{abs(hash(r['condition']))%10**8}", r)

    out = brain.BRAIN / "backtests" / f"mine-{time.strftime('%Y-%m-%d-%H%M', time.gmtime())}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    (brain.BRAIN / "backtests" / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nbrain: {json.dumps(brain.stats(), ensure_ascii=False)}")
    print(f"written to brain/backtests/ · took {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
