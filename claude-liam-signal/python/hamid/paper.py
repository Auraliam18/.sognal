#!/usr/bin/env python3
"""دفتر ترید کاغذی، و یاد گرفتن از دلیل درست.

Hamid: «مهم اینه بعدش بتونی درست نتیجه گیری کنی و بر اساس دلایل درست یاد بگیری».

That second half is the hard part, and it is where this kind of system usually
lies to itself. Recording trades is bookkeeping. Deciding *why* they won is
statistics, and with a dozen recorded conditions and a few dozen trades, several
conditions will look predictive purely by chance. A loop that acts on those
gets worse every cycle while appearing to learn.

So there are two halves here.

**The book.** Signals become pending limit orders, exactly as they would be
placed. A pending order that is never touched expires and is not a trade — the
same rule the backtest enforces, and the one whose absence once turned
34.1% / +0.103R into 58.8% / +0.873R. Filled orders are tracked to their stop or
target and closed with the full context that was true when they were opened.

**The attribution.** Every closed trade carries the conditions at entry. For
each condition the difference in expectancy between trades that had it and
trades that did not is measured with a bootstrap interval — and then corrected
for the fact that many conditions were tested at once. A condition is only
reported as a *reason* if its interval still clears zero after that correction.
Everything else is reported as "not yet distinguishable from luck", which is
usually the honest answer and always the safe one.

    python3 -m hamid.paper --mark          # update open positions
    python3 -m hamid.paper --reasons       # what actually separated winners
"""
import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import brain                                                  # noqa: E402
import sources                                                # noqa: E402

ROOT = HERE.parent.parent.parent
BOOK = ROOT / "brain" / "paper"
OPEN = BOOK / "open.jsonl"
CLOSED = BOOK / "closed.jsonl"
EQUITY = BOOK / "equity.json"

START_BALANCE = 1000.0
RISK_FRACTION = 0.01          # 1% of balance per trade
FILL_HOURS = 6                # a limit untouched this long is cancelled
HOLD_HOURS = 24               # then closed at market


def _read(p):
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _write(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
                 if rows else "")


def _append(p, row):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ── the book ───────────────────────────────────────────────────────────────

def open_from(setups, context):
    """Place the signals as pending limit orders, with their reasons attached.

    The context is snapshotted now, not looked up later. A trade that closes
    tomorrow must be judged against the market that existed when it was opened,
    and re-deriving it afterwards would quietly attribute the outcome to
    conditions that arrived after the decision.
    """
    have = {(p["sym"], p["entry"]) for p in _read(OPEN)}
    added = 0
    for s in setups:
        key = (s["symbol"], float(s["entry"]))
        if key in have:
            continue
        _append(OPEN, {
            "sym": s["symbol"], "dir": s["dir"],
            "entry": float(s["entry"]), "sl": float(s["sl"]),
            "tp1": float(s["tp1"]), "tp2": float(s.get("tp2") or 0) or None,
            "opened": int(time.time() * 1000),
            "filled": None,
            "why": {
                "trend_4h": s.get("trend_4h"),
                "returns": (s.get("block") or {}).get("returns"),
                "impulse": (s.get("block") or {}).get("impulse"),
                "reactions": (s.get("on_level") or {}).get("reactions"),
                "flipped": (s.get("on_level") or {}).get("flipped"),
                "stop_pct": s.get("stop_pct"),
                "dir": s["dir"],
                "stage": s.get("stage_tag") or ("second" if not s.get("waiting") else "first"),
                **context,
            },
        })
        have.add(key)
        added += 1
    if added:
        brain.room_log("paper", f"{added} سفارش لیمیت جدید در دفتر کاغذی", "open")
    return added


def _candles_since(sym, since_ms):
    try:
        rows = sources.klines(sym, "15m", 200)
    except Exception:                                # noqa: BLE001 - skip this one
        return []
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4]}
            for k in rows if k[0] >= since_ms]


def mark():
    """Walk every open position forward and close what has resolved."""
    positions = _read(OPEN)
    if not positions:
        print("دفتر باز خالی است")
        return 0, 0
    still, closed = [], 0
    now = time.time() * 1000

    for p in positions:
        cd = _candles_since(p["sym"], p["opened"])
        if not cd:
            still.append(p)
            continue
        long = p["dir"] == "LONG"
        risk = abs(p["entry"] - p["sl"])

        if p["filled"] is None:
            for c in cd:
                if c["l"] <= p["entry"] <= c["h"]:
                    p["filled"] = c["t"]
                    break
            if p["filled"] is None:
                if now - p["opened"] > FILL_HOURS * 3600_000:
                    # never touched: not a trade, and must not be scored as one
                    p["outcome"] = "expired"
                    p["R"] = None
                    p["closed"] = int(now)
                    _append(CLOSED, p)
                    closed += 1
                else:
                    still.append(p)
                continue

        after = [c for c in cd if c["t"] >= p["filled"]]
        done = None
        for c in after:
            hit_sl = (c["l"] <= p["sl"]) if long else (c["h"] >= p["sl"])
            hit_tp = (c["h"] >= p["tp1"]) if long else (c["l"] <= p["tp1"])
            if hit_sl and hit_tp:
                done = ("stop", -1.0)    # cannot order them within a bar
                break
            if hit_sl:
                done = ("stop", -1.0)
                break
            if hit_tp:
                done = ("target", abs(p["tp1"] - p["entry"]) / risk)
                break
        if done is None and now - p["filled"] > HOLD_HOURS * 3600_000:
            last = after[-1]["c"] if after else p["entry"]
            R = ((last - p["entry"]) if long else (p["entry"] - last)) / risk
            done = ("timeout", R)
        if done is None:
            still.append(p)
            continue

        p["outcome"], p["R"] = done[0], round(done[1], 4)
        p["closed"] = int(now)
        _append(CLOSED, p)
        closed += 1
        brain.room_log("paper", f"{p['sym']} {p['dir']} بسته شد: "
                                f"{p['outcome']} {p['R']:+.2f}R", "close")

    _write(OPEN, still)
    _equity()
    print(f"{len(still)} پوزیشن باز، {closed} بسته شد")
    return len(still), closed


def _equity():
    """Fixed-fractional balance from the closed book. Expired orders contribute
    nothing, because they were never trades.

    Two lines, kept apart on purpose. The book now also records first-pullback
    entries as experiments so the learning loop can measure Hamid's own rule
    («منتظر پولبک دومش می‌مانم») instead of assuming it — but those were never
    signalled to him, and mixing them into the headline balance would make the
    signalled strategy's record unreadable. `balance` is the signalled trades
    only; the experiments get their own line.
    """
    def run_book(trades):
        bal, peak, dd, n, wins = START_BALANCE, START_BALANCE, 0.0, 0, 0
        for t in trades:
            if t.get("R") is None:
                continue
            bal += bal * RISK_FRACTION * t["R"]
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
            n += 1
            wins += 1 if t["R"] > 0 else 0
        return {"balance": round(bal, 2), "trades": n,
                "win_pct": round(wins / n * 100, 1) if n else None,
                "return_pct": round((bal / START_BALANCE - 1) * 100, 2),
                "max_drawdown_pct": round(dd * 100, 2)}

    closed = _read(CLOSED)
    signalled = [t for t in closed if (t.get("why") or {}).get("stage") != "first"]
    experiments = [t for t in closed if (t.get("why") or {}).get("stage") == "first"]
    j = {**run_book(signalled),
         "start": START_BALANCE, "risk_per_trade_pct": RISK_FRACTION * 100,
         "experiments_first_pullback": run_book(experiments),
         "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    EQUITY.parent.mkdir(parents=True, exist_ok=True)
    EQUITY.write_text(json.dumps(j, ensure_ascii=False, indent=1))
    return j


# ── learning from the right reasons ────────────────────────────────────────

def _boot_diff(a, b, n=3000, alpha=0.05):
    """Interval around mean(a) − mean(b), at the given alpha."""
    if len(a) < 8 or len(b) < 8:
        return None
    diffs = []
    for _ in range(n):
        ma = sum(random.choice(a) for _ in range(len(a))) / len(a)
        mb = sum(random.choice(b) for _ in range(len(b))) / len(b)
        diffs.append(ma - mb)
    diffs.sort()
    return diffs[int(n * alpha / 2)], diffs[int(n * (1 - alpha / 2))]


CONDITIONS = [
    ("لانگ بود", lambda w: w.get("dir") == "LONG"),
    # قانون خود حمید، بالاخره قابل اندازه‌گیری: آیا صبر برای پولبک دوم واقعاً
    # نتیجه را بهتر می‌کند؟ تا حالا فرض بود؛ حالا هر دو مرحله در دفتر ثبت
    # می‌شوند و این شرط جوابش را با داده می‌دهد.
    ("پولبک دوم بود", lambda w: w.get("stage") == "second"),
    ("روند ۴ساعته صعودی", lambda w: w.get("trend_4h") == "up"),
    ("ضربهٔ بلاک ≥ ۶", lambda w: (w.get("impulse") or 0) >= 6),
    ("ضربهٔ بلاک ≥ ۱۰", lambda w: (w.get("impulse") or 0) >= 10),
    ("بلاک ۱ بار برگشت خورده", lambda w: (w.get("returns") or 0) <= 1),
    ("بلاک ۳ بار یا بیشتر", lambda w: (w.get("returns") or 0) >= 3),
    ("سطح با ≥ ۵ واکنش", lambda w: (w.get("reactions") or 0) >= 5),
    ("سطح نقش‌عوض‌کرده", lambda w: bool(w.get("flipped"))),
    ("استاپ < ۲٪", lambda w: (w.get("stop_pct") or 99) < 2),
    ("ترس شدید (<۳۰)", lambda w: (w.get("fear") or 50) < 30),
    ("فاندینگ مثبت", lambda w: (w.get("funding") or 0) > 0),
    ("دامیننس تتر بالای ۸٪", lambda w: (w.get("usdt_dom") or 0) > 8),
]


def reasons(verbose=True):
    """Which conditions actually separated winners from losers?

    The correction is the whole point. Twelve conditions tested at 95% means
    roughly one will clear zero by chance even if none of them matter — and that
    one would then be written into the rules and start steering real signals. So
    the interval is widened by the number of conditions tested (Bonferroni), and
    only a condition surviving *that* is called a reason.

    Both numbers are printed, because the uncorrected one is what a naive
    version of this would have believed, and seeing the gap is the point.
    """
    trades = [t for t in _read(CLOSED) if t.get("R") is not None]
    if len(trades) < 20:
        if verbose:
            print(f"\nفقط {len(trades)} معاملهٔ بسته‌شده — برای نتیجه‌گیری کم است.")
            print("هیچ دلیلی گزارش نمی‌شود تا نمونه بزرگ‌تر شود.")
        return []

    k = len(CONDITIONS)
    alpha_adj = 0.05 / k
    out = []
    if verbose:
        print(f"\n{len(trades)} معاملهٔ بسته‌شده · {k} شرط آزموده شد")
        print(f"سطح تصحیح‌شده: {alpha_adj:.4f} (بونفرونی) — چون آزمودن ۱۲ شرط "
              f"با ۹۵٪ یعنی تقریباً یکی‌شان الکی رد می‌شود\n")
        print(f"{'شرط':<26}{'با':>10}{'بدون':>10}{'تفاوت':>10}   تصحیح‌شده")
        print("─" * 84)

    for name, fn in CONDITIONS:
        a = [t["R"] for t in trades if fn(t.get("why") or {})]
        b = [t["R"] for t in trades if not fn(t.get("why") or {})]
        if len(a) < 8 or len(b) < 8:
            if verbose:
                print(f"{name:<26}{len(a):>10}{len(b):>10}       نمونهٔ کم")
            continue
        ea, eb = statistics.fmean(a), statistics.fmean(b)
        raw = _boot_diff(a, b, alpha=0.05)
        adj = _boot_diff(a, b, alpha=alpha_adj)
        survives = adj and (adj[0] > 0 or adj[1] < 0)
        raw_only = raw and (raw[0] > 0 or raw[1] < 0) and not survives
        mark_s = "✓ دلیل واقعی" if survives else \
                 "— بعد از تصحیح از بین رفت" if raw_only else "— شانسی"
        if verbose:
            print(f"{name:<26}{ea:>+10.3f}{eb:>+10.3f}{ea-eb:>+10.3f}   {mark_s}")
        if survives:
            out.append({"condition": name, "n_with": len(a), "n_without": len(b),
                        "ev_with": ea, "ev_without": eb, "diff": ea - eb,
                        "interval": adj})

    if verbose:
        print("─" * 84)
        if out:
            print(f"{len(out)} دلیل واقعی پیدا شد — این‌ها بعد از تصحیح هم زنده ماندند.")
        else:
            print("هیچ شرطی بعد از تصحیح زنده نماند. یعنی هنوز نمی‌دانیم چرا "
                  "بعضی بردند — و ادعای دانستنش بدتر از ندانستن است.")
    for r in out:
        brain.save_pattern(f"hamid-reason-{r['condition']}", r)
    # خروجی کامل در فایل، تا چرخه بتواند بخواند و روی رتبه‌بندی اعمال کند.
    # فقط تأییدشده‌ها عمل می‌شوند — قانون ثابت پروژه: یافته تا بازه‌اش از صفر
    # رد نشده، عمل نمی‌شود. بقیه فقط برای شفافیت ثبت می‌شوند.
    (BOOK / "reasons.json").write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_trades": len(trades),
        # امضا: مسیر دفتری که این قوانین از آن آمده. چرخه فقط فایلی را اعمال
        # می‌کند که از دفتر واقعی آمده باشد — دفاعِ دوم بعد از ایزوله شدن تست.
        "book": str(CLOSED),
        "confirmed": out,
    }, ensure_ascii=False, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--reasons", action="store_true")
    a = ap.parse_args()
    if a.mark or not (a.mark or a.reasons):
        mark()
    eq = _equity()
    print(f"\nموجودی کاغذی: ${eq['balance']} از ${eq['start']} "
          f"({eq['return_pct']:+.2f}٪) · {eq['trades']} معامله · "
          f"بیشترین افت {eq['max_drawdown_pct']}٪")
    if a.reasons or not (a.mark or a.reasons):
        reasons()
    return 0


if __name__ == "__main__":
    sys.exit(main())
