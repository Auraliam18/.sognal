#!/usr/bin/env python3
"""آیا روش حمید روی کندل واقعی سود می‌دهد؟

Selectivity was measured in hamid/control.py: the method fires on 29% of real
coins and 5% of random walks. That says it is finding something. It does not say
that something is worth trading, and until this runs the daily signal count is a
count, not a claim.

    python3 -m hamid.backtest --symbols 25 --bars 1000

What this is careful about, because every one of these has produced a flattering
wrong answer in this repository before:

  **No lookahead.** At each evaluation the slices end at the bar being evaluated.
  The 1H series is cut by timestamp against the 15m bar, not by index, so a 1H
  candle that had not closed yet cannot leak in.

  **The limit has to fill.** These are limit orders at an order block. An unfilled
  order is not a trade. Counting them once turned 34.1% / +0.103R into
  58.8% / +0.873R — the single largest false result this project has produced —
  so a setup whose entry price is never touched within the window is discarded,
  not scored.

  **Same candle, both levels: it loses.** If a bar's range covers the stop and the
  target, 15m data cannot say which came first, and assuming the good one is how
  a backtest quietly earns its edge.

  **One trade at a time per symbol.** The same block produces a setup on every
  bar it is valid for. Without this the same idea is counted twenty times and the
  interval around the result becomes fiction.

  **The interval has to clear zero.** Reported as a bootstrap CI, per this
  project's standing rule. A mean of +0.09R with an interval spanning zero is not
  an edge, it is a hope.
"""
import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                                # noqa: E402
from hamid import stack                                       # noqa: E402
from hamid.replay_execution import replay, BAR_MS
from hamid import fees
from hamid.cycle import resample                              # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "claude-liam-signal" / "backtests"
LEDGER = ROOT / "brain" / "backtest" / "hamid-trades-v2.jsonl"

FILL_WINDOW = 96          # 24 hours of 15m bars for the limit to be touched
HOLD_WINDOW = 96          # 24 hours before the position is closed at market
STEP = 2                  # every half hour. `busy_until` already prevents the
                          # same idea being counted twice, so a finer step finds
                          # setups a coarse one stepped straight over rather than
                          # duplicating the ones it found.


def rows_to_candles(rows):
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def fetch(sym, bars):
    """15m and 1H for one symbol. Both are needed: the 4H comes from resampling
    the 1H, and cutting 1H by timestamp is what keeps an unclosed candle out."""
    import backtest as historical
    c15 = historical.klines(sym, "15m", bars)
    c1h = historical.klines(sym, "1h", max(1000, bars // 4 + 800))
    return c15, c1h


def simulate(c15, i, setup):
    """Compatibility API: gross R; detailed, net results use replay()."""
    return replay(c15[i+1:], setup, c15[i]["t"] + BAR_MS)["R"]


def closed_4h(c1h, asof):
    """UTC-aligned complete groups only, including the last fully closed group."""
    groups = {}
    for c in c1h:
        if c["t"] + 3_600_000 <= asof:
            groups.setdefault(c["t"] // 14_400_000, []).append(c)
    result = []
    for bucket, rows in sorted(groups.items()):
        expected = [bucket*14_400_000 + j*3_600_000 for j in range(4)]
        if [x["t"] for x in rows] != expected:
            continue
        result.append(dict(t=expected[0], o=rows[0]["o"], h=max(x["h"] for x in rows),
                           l=min(x["l"] for x in rows), c=rows[-1]["c"], v=sum(x["v"] for x in rows)))
    return result


def walk(sym, c15, c1h, bars_needed=140):
    # 140, not 260. The binding constraint is the 1H history checked below —
    # levels() needs about thirty bars and the 15m series is only used for trend
    # and ATR — so a larger 15m warm-up was discarding evaluable bars for
    # nothing, and with only ten days of 15m available that is most of the
    # sample.
    trades = []
    busy_until = -1
    for i in range(bars_needed, len(c15) - FILL_WINDOW - 2, STEP):
        if i <= busy_until:
            continue
        now = c15[i]["t"] + BAR_MS
        # 1H bars that had actually closed by this 15m bar. Index-based slicing
        # here would hand the engine a candle from the future.
        h = [c for c in c1h if c["t"] + 3_600_000 <= now]
        if len(h) < 200:
            continue
        c4 = closed_4h(h, now)
        if len(c4) < 200:
            continue
        r = stack.read(sym, c4[-200:], h[-300:], c15[max(0, i-299):i + 1])
        if not r.setup or r.setup.get("waiting"):
            continue
        cost = fees.cost_in_r(r.setup["entry"], r.setup["sl"], sym)
        if cost is None or cost >= 0.25:
            continue  # same existing signal-grade paper fee gate
        result = replay(c15[i+1:], r.setup, now, symbol=sym)
        busy_until = max(i, next((j-1 for j in range(i+1, len(c15)) if c15[j]["t"] >= result["end"]), len(c15)-1))
        if result["R"] is None:
            continue
        trades.append({"sym": sym, "t": now, "dir": r.setup["dir"], **result,
                       "engine_version": "hamid-stack-paper-v2",
                       "stop_pct": r.setup.get("stop_pct"),
                       "trend_4h": r.trend_4h,
                       "returns": r.setup["block"]["returns"],
                       "impulse": r.setup["block"]["impulse"],
                       "reactions": r.setup["on_level"]["reactions"]})
    return trades


def accumulate(trades):
    """Keep every trade ever measured, so the sample grows instead of resetting.

    The venues serve a thousand 15m candles, which is about ten days. One run
    over 120 coins found 43 filled trades, and 43 is not enough to say anything —
    every interval in that run spanned zero. Re-running daily on the same ten-day
    window would just re-measure the same trades and produce the same
    uninformative answer forever.

    A trade is identified by symbol and entry time, so overlapping windows merge
    rather than double-count. That deduplication is the whole point: without it a
    daily run would inflate the sample by a factor of ten and shrink the interval
    around a number that had not actually been measured any better.
    """
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    seen, kept = set(), []
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if not line.strip():
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (t.get("sym"), t.get("t"))
            if key in seen:
                continue
            seen.add(key)
            kept.append(t)
    added = 0
    for t in trades:
        key = (t["sym"], t["t"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(t)
        added += 1
    kept.sort(key=lambda x: x.get("t") or 0)
    LEDGER.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in kept) + "\n")
    return kept, added


def boot(vals, n=4000):
    """95% interval around the mean. Nothing is acted on until it clears zero."""
    if len(vals) < 20:
        return None
    k, means = len(vals), []
    rng = random.Random(20261105)
    for _ in range(n):
        means.append(sum(rng.choice(vals) for _ in range(k)) / k)
    means.sort()
    return means[int(n * 0.025)], means[int(n * 0.975)]


def report(trades, label="همه"):
    if not trades:
        print(f"  {label:<22} هیچ معامله‌ای تشکیل نشد")
        return None
    rs = [t["R_net"] for t in trades]
    wins = [r for r in rs if r > 0]
    ev = statistics.fmean(rs)
    ci = boot(rs)
    ci_s = f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "نمونه کم"
    clear = "✓ فاصله از صفر رد شده" if ci and ci[0] > 0 else \
            "✗ صفر داخل بازه" if ci else "—"
    print(f"  {label:<22} n={len(rs):<5} برد {len(wins)/len(rs)*100:5.1f}%  "
          f"E={ev:+.3f}R  {ci_s}  {clear}")
    return {"label": label, "n": len(rs), "win": len(wins) / len(rs),
            "ev": ev, "ci": ci}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=25)
    ap.add_argument("--bars", type=int, default=1000)
    ap.add_argument("--isolated", action="store_true", help="Never read or write the accumulated ledger")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    t0 = time.time()
    import backtest as historical
    from hamid.universe import STABLES, WRAPPED
    syms = [s for s in historical.top_symbols(a.symbols + 20)
            if s[:-4] not in STABLES | WRAPPED][:a.symbols]
    print(f"{len(syms)} ارز، {a.bars} کندل ۱۵ دقیقه\n")

    coverage = []
    cutoff = int(time.time()*1000)
    a.out.mkdir(parents=True, exist_ok=True)
    def one(sym):
        try:
            c15, c1h = fetch(sym, a.bars)
            c15 = [c for c in c15 if c["t"] + BAR_MS <= cutoff]
            c1h = [c for c in c1h if c["t"] + 3_600_000 <= cutoff]
            for series, step in ((c15, BAR_MS), (c1h, 3_600_000)):
                if len(series) < 140 or any(b["t"]-a["t"] != step for a,b in zip(series, series[1:])):
                    raise ValueError("insufficient or non-contiguous candles")
            payload = json.dumps({"15m": c15, "1h": c1h}, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            (a.out / f"candles-{sym}.json").write_text(payload, encoding="utf-8")
            coverage.append(dict(symbol=sym, ok=True, bars15=len(c15), bars1h=len(c1h),
                                 first=c15[0]["t"], last=c15[-1]["t"], sha256=digest))
            return walk(sym, c15, c1h)
        except Exception as e:                       # noqa: BLE001 - one symbol is not the run
            coverage.append(dict(symbol=sym, ok=False, error=str(e)))
            print(f"  {sym}: {type(e).__name__}: {e}")
            return []

    trades = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(one, syms):
            trades += res

    all_trades, added = (trades, len(trades)) if a.isolated else accumulate(trades)
    print(f"\n{len(trades)} معاملهٔ پرشده در {time.time()-t0:.0f} ثانیه "
          f"({added} تای جدید)")
    print(f"مجموع انباشته تا امروز: {len(all_trades)} معامله\n")
    print("Component replay — real candles, filled limits, trailing, NET R; no promotion")
    print("─" * 92)
    overall = report(all_trades, "همه (انباشته)")
    if len(all_trades) != len(trades):
        report(trades, "فقط این اجرا")
    trades = all_trades
    cuts = {
        "لانگ": [t for t in trades if t["dir"] == "LONG"],
        "شورت": [t for t in trades if t["dir"] == "SHORT"],
        "ضربهٔ بلاک ≥ ۸": [t for t in trades if t["impulse"] >= 8],
        "برگشت بلاک ≥ ۳": [t for t in trades if t["returns"] >= 3],
        "واکنش سطح ≥ ۵": [t for t in trades if t["reactions"] >= 5],
        "استاپ < ۳٪": [t for t in trades if (t["stop_pct"] or 99) < 3],
    }
    for k, v in cuts.items():
        report(v, k)
    print("─" * 92)

    a.out.mkdir(parents=True, exist_ok=True)
    p = a.out / f"hamid-method-{datetime.now(timezone.utc):%Y-%m-%d-%H-%M}.json"
    p.write_text(json.dumps({
        "run": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "engine_version": "hamid-stack-paper-v2",
        "scope": "Component replay: stack second pullback + paper viability/trailing/costs; not full live pipeline",
        "limitations": ["current universe, not historical membership", "no historical dominance/news/committee", "funding unmodelled", "spot candles; not Bitunix execution", "trade bootstrap does not correct cross-symbol dependence"],
        "costs": fees.config(), "metrics_basis": "R_net", "promotion_allowed": False,
        "symbols": syms, "bars": a.bars, "trades": len(trades),
        "coverage": sorted(coverage, key=lambda c: c["symbol"]),
        "overall": overall, "sample": trades,
    }, ensure_ascii=False, indent=1, default=str))
    print(f"\nنوشته شد در {p}")

    if overall and overall["ci"] and overall["ci"][0] > 0:
        print("\nبازهٔ اطمینان از صفر رد شده — این روش روی این نمونه لبه دارد.")
    else:
        print("\nبازهٔ اطمینان صفر را در بر می‌گیرد. طبق قانون خودمان، این "
              "هنوز لبه نیست و نباید به‌عنوان سود اعلام شود.")
    return 0 if syms and all(c["ok"] for c in coverage) else 1


if __name__ == "__main__":
    sys.exit(main())
