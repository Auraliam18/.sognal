"""پرکردن سریع دفترهای نازک — دستور حمید: «دیتاهای پیپر تریدینگ سریع به
نتیجه برسند که به تجربهٔ ایجنت‌ها برای تصمیم بهتر برسیم.»

## چرا این لازم شد، با عدد

اندازه‌گیری روی دفتر واقعی (۱۵ اوت) نشان داد هر دفتر چقدر نمونه کم دارد تا
فاصلهٔ اطمینانش از صفر رد کند:

    دفتر            n دارد   n لازم   کمبود
    پولبک اول         ۱۳۲       ۴۸       ۰   ← تمام شد
    ایندوسمنت         ۴۵۰      ۴۶۰      ۱۰
    پولبک دوم          ۶۱      ۴۷۴     ۴۱۳   ← گلوگاه
    v2                 ۲۹      ۱۷۳     ۱۴۴
    sig-ibs            ۳۳      ۲۶۹     ۲۳۶

پولبک دوم — همان قانون اصلی حمید — با ~۸ معامله در روزِ زنده، ۵۰ روز طول
می‌کشید تا حکم بگیرد. تا آن روز، مقایسهٔ «پولبک اول در برابر دوم» بی‌جواب
می‌ماند و ایجنت‌ها بدون تجربه تصمیم می‌گیرند.

## راه‌حل: چیزی که از قبل داشتیم

`hamid/backtest.py:walk()` دقیقاً همین کار را می‌کند — روش حمید را روی
کندل واقعی بازپخش می‌کند و خودش `setup.waiting` را می‌بیند، یعنی پولبک اول
و دوم را از هم جدا می‌کند. فقط خروجی‌اش به `brain/backtests/` می‌رفت و به
دفتر تجربه نمی‌رسید. این ماژول همان بازپخش را به دفتر وصل می‌کند.

پس هیچ موتور تازه‌ای ساخته نشد و هیچ قانونی عوض نشد. همان انجین، همان
گیت‌ها، همان `stack.read` — فقط نتیجه‌اش جایی می‌نشیند که یادگیری می‌بیند.

## چیزهایی که عمداً حفظ شده‌اند

· **بدون look-ahead** — برش‌ها در `walk` سرِ همان کندل تمام می‌شوند و ۱ساعته
  با timestamp بریده می‌شود، نه با ایندکس.
· **سفارش پرنشده معامله نیست** — `simulate` آن را None برمی‌گرداند و کنار
  می‌رود. همین یک قلم یک بار ۳۴٪ را به ۵۹٪ تبدیل کرده بود.
· **یک کندل که هم استاپ هم تارگت را پوشش دهد، باخت است.**
· **ضدتکرار بین اجراها** — مرز پیشروی هر ارز ذخیره می‌شود، مثل میز تمرین.
  بدون این، نمونهٔ متورمِ تکراری می‌سازیم که فقط CI را دروغی باریک می‌کند.
· **برچسب `replay: 1`** روی هر ردیف — این معاملهٔ بازپخشِ تاریخی است، نه
  سیگنال زنده، و در گزارش هم همین‌طور گفته می‌شود.

اجرا:
    python3 -m hamid.fill_books --symbols 40 --bars 1400
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
STATE = ROOT / "brain" / "paper" / "fill-state.json"

BUDGET_S = 15 * 60        # مثل میز تمرین: تمام‌شدن تمیز، نه کشته‌شدن
CAP_PER_SYMBOL = 60


def _load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:                                 # noqa: BLE001 - اولین اجرا
        return {}


def _save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1),
                     encoding="utf-8")


def to_paper(sym, tr, stage):
    """ردیف بازپخش را به شکل دقیق دفتر پیپر دربیاور.

    شکل باید مو‌به‌مو همان باشد که paper.py می‌نویسد، وگرنه classify و
    ماشین بونفرونی این ردیف‌ها را نمی‌بینند و همهٔ این کار هدر است."""
    why = {"stage": stage, "replay": 1, "tf": "15m",
           "trend_4h": tr.get("trend_4h"),
           "stop_pct": tr.get("stop_pct"),
           "returns": tr.get("returns"),
           "impulse": tr.get("impulse"),
           "reactions": tr.get("reactions"),
           "dir": tr.get("dir")}
    r = tr["R"]
    return {"sym": sym, "dir": tr["dir"],
            "entry": tr.get("entry"), "sl": tr.get("sl"), "tp1": tr.get("tp1"),
            "tp2": None,
            "opened": tr["t"], "filled": tr["t"],
            "why": why,
            "outcome": ("target" if r >= 1.5 else
                        "trail" if r > 0 else
                        "stop" if r <= -0.9 else "timeout"),
            "R": round(r, 3), "tf": "15m",
            "closed": tr["t"] + 96 * 900_000}


def walk_both(sym, c15, c1h, after_ms=0, cap=CAP_PER_SYMBOL):
    """مثل backtest.walk ولی هر دو حالت را نگه می‌دارد.

    `walk` اصلی ستاپ waiting را رد می‌کند چون فقط سیگنال‌پذیرها را می‌سنجد.
    این‌جا هر دو لازم‌اند: waiting یعنی پولبک اول، غیر-waiting یعنی پولبک
    دوم — و مقایسهٔ همین دو تا سؤال باز حمید است.

    خروجی: (ردیف‌های دفتر، مرز پیشروی)
    """
    from hamid import stack
    from hamid.backtest import FILL_WINDOW, HOLD_WINDOW, STEP, simulate
    from hamid.cycle import resample

    out = []
    busy_until = -1
    i = 140
    last_t = after_ms
    while i < len(c15) - FILL_WINDOW - 2 and len(out) < cap:
        if i <= busy_until:
            i += STEP
            continue
        now = c15[i]["t"]
        if now <= after_ms:                           # قبلاً بازپخش شده
            i += STEP
            continue
        h = [c for c in c1h if c["t"] + 3_600_000 <= now]
        if len(h) < 80:
            i += STEP
            continue
        c4 = resample(h, 4)
        if len(c4) < 30:
            i += STEP
            continue
        try:
            r = stack.read(sym, c4, h, c15[:i + 1])
        except Exception:                             # noqa: BLE001 - یک بار خراب، بقیه نه
            i += STEP
            continue
        if not r.setup:
            i += STEP
            continue
        R = simulate(c15, i, r.setup)
        if R is None:                                 # سفارش پر نشد = معامله نیست
            i += STEP
            continue
        s = r.setup
        out.append(to_paper(sym, {
            "t": now, "dir": s["dir"], "R": R,
            "entry": s.get("entry"), "sl": s.get("sl"), "tp1": s.get("tp1"),
            "stop_pct": s.get("stop_pct"), "trend_4h": r.trend_4h,
            "returns": (s.get("block") or {}).get("returns"),
            "impulse": (s.get("block") or {}).get("impulse"),
            "reactions": (s.get("on_level") or {}).get("reactions"),
        }, "first" if s.get("waiting") else "second"))
        last_t = now
        busy_until = i + HOLD_WINDOW
        i += STEP
    # مرز = تا کجای تاریخ بررسی شد، نه آخرین معامله. اگر تا ته رفتیم ته سری.
    frontier = c15[min(i, len(c15) - 1)]["t"] if len(out) < cap else last_t
    return out, frontier


def run(symbols=None, bars=1400, budget_s=BUDGET_S, quiet=False, fetch=None):
    from hamid import memory, paper

    if symbols is None:
        from hamid.trainer import top_symbols
        symbols = top_symbols(40)
    if fetch is None:
        from hamid.backtest import fetch as _f

        def fetch(sym, n):
            return _f(sym, n)

    st = _load_state()
    started = time.time()
    deadline = started + budget_s
    skipped = {"n": 0}

    def one(sym):
        if time.time() > deadline:
            skipped["n"] += 1
            return sym, [], None
        try:
            c15, c1h = fetch(sym, bars)
        except Exception:                             # noqa: BLE001
            return sym, [], None
        if len(c15) < 300 or len(c1h) < 120:
            return sym, [], None
        try:
            rows, frontier = walk_both(sym, c15, c1h, after_ms=st.get(sym, 0))
        except Exception as e:                        # noqa: BLE001
            print(f"بازپخش {sym}: {type(e).__name__}: {e}")
            return sym, [], None
        return sym, rows, frontier

    got = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for sym, rows, frontier in pool.map(one, symbols):
            got.extend(rows)
            if frontier:
                st[sym] = max(st.get(sym, 0), frontier)

    for t in got:
        paper._append(paper.CLOSED, t)
    if got:
        try:
            memory.digest_closed(got)
        except Exception as e:                        # noqa: BLE001
            print(f"⚠ digest نشد: {type(e).__name__}")
    _save_state(st)

    if not quiet:
        n1 = sum(1 for t in got if t["why"]["stage"] == "first")
        n2 = len(got) - n1
        took = round(time.time() - started, 1)
        print(f"پرکردن دفتر: {len(got)} معاملهٔ بازپخش از {len(symbols)} ارز "
              f"در {took}s — پولبک اول {n1} · پولبک دوم {n2}")
        if skipped["n"]:
            print(f"⏱ بودجه تمام شد — {skipped['n']} ارز شروع نشد؛ "
                  "مرز پیشروی ذخیره شد و اجرای بعد ادامه می‌دهد")
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=40)
    ap.add_argument("--bars", type=int, default=1400)
    ap.add_argument("--budget", type=int, default=BUDGET_S)
    a = ap.parse_args()
    from hamid.trainer import top_symbols
    run(symbols=top_symbols(a.symbols), bars=a.bars, budget_s=a.budget)


if __name__ == "__main__":
    main()
