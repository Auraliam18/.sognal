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
from hamid.cycle import resample                              # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "claude-liam-signal" / "backtests"
LEDGER = ROOT / "brain" / "backtest" / "hamid-trades.jsonl"

FILL_WINDOW = 24          # 6 hours of 15m bars for the limit to be touched
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
    c15 = rows_to_candles(sources.klines(sym, "15m", bars))
    c1h = rows_to_candles(sources.klines(sym, "1h", min(bars, 1000)))
    return c15, c1h


def simulate(c15, i, setup, with_exit=False):
    """Place the limit and see what happens. Returns R, or None if never filled.

    `i` is the bar the setup was produced on, so the walk starts at i+1 — the
    setup could not have been acted on any earlier than the bar after the one
    that revealed it.

    With `with_exit=True` the return is `(R, exit_bar_timestamp)`. The callers
    that write ledger rows need the real exit bar: synthesising a close time as
    "entry + the full hold window" dates every replayed row 24h after entry
    whatever actually happened, which shifts every close-time-based window and
    can even land rows in the future. Default stays R-only so existing callers
    are untouched.
    """
    def done(R, j):
        return (R, c15[j]["t"]) if with_exit else R

    entry, sl, tp = setup["entry"], setup["sl"], setup["tp1"]
    risk = abs(entry - sl)
    if risk <= 0:
        return (None, None) if with_exit else None
    long = setup["dir"] == "LONG"

    fill = None
    for j in range(i + 1, min(len(c15), i + 1 + FILL_WINDOW)):
        if c15[j]["l"] <= entry <= c15[j]["h"]:
            fill = j
            break
    if fill is None:                      # never filled: not a trade
        return (None, None) if with_exit else None

    for j in range(fill, min(len(c15), fill + HOLD_WINDOW)):
        c = c15[j]
        hit_sl = (c["l"] <= sl) if long else (c["h"] >= sl)
        hit_tp = (c["h"] >= tp) if long else (c["l"] <= tp)
        if hit_sl and hit_tp:
            return done(-1.0, j)          # cannot tell the order; assume the worse
        if hit_sl:
            return done(-1.0, j)
        if hit_tp:
            return done(abs(tp - entry) / risk, j)
    end = min(len(c15) - 1, fill + HOLD_WINDOW - 1)
    out = c15[end]["c"]
    return done(((out - entry) if long else (entry - out)) / risk, end)


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
        now = c15[i]["t"]
        # 1H bars that had actually closed by this 15m bar. Index-based slicing
        # here would hand the engine a candle from the future.
        h = [c for c in c1h if c["t"] + 3_600_000 <= now]
        if len(h) < 80:
            continue
        c4 = resample(h, 4)
        if len(c4) < 30:
            continue
        r = stack.read(sym, c4, h, c15[:i + 1])
        if not r.setup or r.setup.get("waiting"):
            continue
        R = simulate(c15, i, r.setup)
        if R is None:
            continue
        trades.append({"sym": sym, "t": now, "dir": r.setup["dir"], "R": R,
                       "stop_pct": r.setup.get("stop_pct"),
                       "trend_4h": r.trend_4h,
                       "returns": r.setup["block"]["returns"],
                       "impulse": r.setup["block"]["impulse"],
                       "reactions": r.setup["on_level"]["reactions"]})
        busy_until = i + HOLD_WINDOW
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
    for _ in range(n):
        means.append(sum(random.choice(vals) for _ in range(k)) / k)
    means.sort()
    return means[int(n * 0.025)], means[int(n * 0.975)]


def report(trades, label="همه"):
    if not trades:
        print(f"  {label:<22} هیچ معامله‌ای تشکیل نشد")
        return None
    rs = [t["R"] for t in trades]
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
    a = ap.parse_args()

    t0 = time.time()
    syms = [s["symbol"] for s in
            sorted(sources.tickers(), key=lambda x: -float(x["quoteVolume"] or 0))
            if s["symbol"].endswith("USDT")][:a.symbols]
    print(f"{len(syms)} ارز، {a.bars} کندل ۱۵ دقیقه\n")

    def one(sym):
        try:
            c15, c1h = fetch(sym, a.bars)
            return walk(sym, c15, c1h)
        except Exception as e:                       # noqa: BLE001 - one symbol is not the run
            print(f"  {sym}: {type(e).__name__}")
            return []

    trades = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(one, syms):
            trades += res

    all_trades, added = accumulate(trades)
    print(f"\n{len(trades)} معاملهٔ پرشده در {time.time()-t0:.0f} ثانیه "
          f"({added} تای جدید)")
    print(f"مجموع انباشته تا امروز: {len(all_trades)} معامله\n")
    print("نتیجه — کندل واقعی، با شرط پر شدن سفارش")
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

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"hamid-method-{datetime.now(timezone.utc):%Y-%m-%d-%H-%M}.json"
    p.write_text(json.dumps({
        "run": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "symbols": syms, "bars": a.bars, "trades": len(trades),
        "overall": overall, "sample": trades[:200],
    }, ensure_ascii=False, indent=1, default=str))
    print(f"\nنوشته شد در {p.relative_to(ROOT)}")

    if overall and overall["ci"] and overall["ci"][0] > 0:
        print("\nبازهٔ اطمینان از صفر رد شده — این روش روی این نمونه لبه دارد.")
    else:
        print("\nبازهٔ اطمینان صفر را در بر می‌گیرد. طبق قانون خودمان، این "
              "هنوز لبه نیست و نباید به‌عنوان سود اعلام شود.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
