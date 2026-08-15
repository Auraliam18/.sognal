"""آزمون پرکردن دفتر — بدون شبکه، با انجین تزریقی.

مرز کار روشن است و عمداً این‌طور تقسیم شده:

  · **انجین** (`stack.read` + `backtest.simulate`) از قبل ثابت شده و
    `backtest.py` سنجیده‌اش. این‌جا دوباره سنجیده نمی‌شود.
  · **لوله‌کشی** (چیزی که تازه نوشته شد) این‌جا سنجیده می‌شود: جداکردن
    پولبک اول از دوم، ضدتکرار بین اجراها، مرز پیشروی، شکل ردیف دفتر، و
    این‌که سفارش پرنشده معامله حساب نشود.

روی دادهٔ مصنوعی انجین واقعی هیچ ستاپی نمی‌دهد (خودِ control.py اندازه
گرفته: ۵٪ روی گام تصادفی) — پس تزریق تنها راهِ سنجیدن لوله‌کشی است، نه
یک میان‌بر.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))

from hamid import backtest as bt                      # noqa: E402
from hamid import fill_books as fb                    # noqa: E402
from hamid import stack                               # noqa: E402

ok = 0
fail = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


print("── پرکردن دفترهای نازک ──")


def candles(n, t0=1_700_000_000_000):
    return [{"t": t0 + i * 900_000, "o": 100.0, "h": 101.0, "l": 99.0,
             "c": 100.0, "v": 10.0} for i in range(n)]


c15 = candles(900)
c1h = [{"t": 1_700_000_000_000 + i * 3_600_000, "o": 100.0, "h": 101.0,
        "l": 99.0, "c": 100.0, "v": 10.0} for i in range(400)]


class FakeRead:
    """انجین تزریقی: هر N اُمین کندل یک ستاپ، یکی‌درمیان اول/دوم."""

    def __init__(self, every=40, waiting_cycle=2):
        self.every = every
        self.waiting_cycle = waiting_cycle
        self.calls = 0
        self.longest = 0

    def __call__(self, symbol, c4, c1h_, c15_):
        self.calls += 1
        self.longest = max(self.longest, len(c15_))
        # روی شمارندهٔ فراخوانی، نه روی len(c15_): طول پنجره با گام ۲ همیشه
        # فرد است و «فرد % ۴۰» هرگز صفر نمی‌شود — نسخهٔ اول همین اشتباه را
        # داشت و آزمون صفر ردیف می‌گرفت در حالی که کد سالم بود.
        if self.calls % self.every:
            return type("R", (), {"setup": None, "trend_4h": "up"})()
        waiting = (self.calls // self.every) % self.waiting_cycle == 0
        setup = {"dir": "LONG", "entry": 100.0, "sl": 99.0, "tp1": 101.5,
                 "stop_pct": 1.0, "waiting": waiting,
                 "block": {"returns": 2, "impulse": 3.0},
                 "on_level": {"reactions": 3}}
        return type("R", (), {"setup": setup, "trend_4h": "up"})()


orig_read, orig_sim = stack.read, bt.simulate
fake = FakeRead()
stack.read = fake
bt.simulate = lambda c, i, s: 1.6                      # همیشه پر می‌شود، R=+1.6

rows, frontier = fb.walk_both("XUSDT", c15, c1h)
check(f"ستاپ‌ها به ردیف دفتر تبدیل شدند ({len(rows)})", len(rows) > 0)
stages = {r["why"]["stage"] for r in rows}
check("هر دو دفتر پر می‌شوند — پولبک اول و دوم", stages == {"first", "second"})
check("waiting=True یعنی پولبک اول",
      all(r["why"]["stage"] in ("first", "second") for r in rows))

# ── بدون look-ahead: انجین هرگز کل سری را ندید ────────────────────────────
check("انجین هرگز کل سری را ندید (بدون look-ahead)",
      fake.longest < len(c15))

# ── شکل ردیف باید مو‌به‌مو مثل دفتر واقعی باشد ────────────────────────────
r0 = rows[0]
check("شکل ردیف همان دفتر پیپر است",
      all(k in r0 for k in ("sym", "dir", "entry", "sl", "tp1", "opened",
                            "filled", "why", "outcome", "R", "closed")))
check("برچسب replay دارد — بازپخش تاریخی، نه سیگنال زنده",
      r0["why"]["replay"] == 1)
check("برچسب تایم‌فریم دارد (جدول دسته‌بندی لازمش دارد)",
      r0["why"]["tf"] == "15m" and r0["tf"] == "15m")
check("نتیجه فقط از چهار نوع مجاز است",
      all(r["outcome"] in ("target", "trail", "stop", "timeout") for r in rows))
check("R عددی و گرد شده است", isinstance(r0["R"], float))
check("closed بعد از opened است", r0["closed"] > r0["opened"])

# ── سفارش پرنشده معامله نیست ──────────────────────────────────────────────
bt.simulate = lambda c, i, s: None
none_rows, _ = fb.walk_both("XUSDT", c15, c1h)
check("سفارش پرنشده هیچ ردیفی نمی‌سازد", none_rows == [])
bt.simulate = lambda c, i, s: 1.6

# ── ضدتکرار بین اجراها ────────────────────────────────────────────────────
again, _ = fb.walk_both("XUSDT", c15, c1h, after_ms=frontier)
check(f"اجرای دوم از مرز پیشروی تکرار نمی‌سازد ({len(again)})", len(again) == 0)
half = rows[len(rows) // 2]["opened"]
part, _ = fb.walk_both("XUSDT", c15, c1h, after_ms=half)
check("مرز میانی فقط بخش تازه را می‌دهد", 0 < len(part) < len(rows))
check("هیچ ردیفی قبل از مرز نیست", all(r["opened"] > half for r in part))

# ── سقف هر ارز ────────────────────────────────────────────────────────────
# فِیک متراکم‌تر: با نرخ قبلی فقط ۲ ستاپ ساخته می‌شد و سقف ۳ اصلاً به
# آزمون نمی‌رسید — یعنی آزمونی که هیچ‌وقت چیزی را نمی‌سنجید.
dense = FakeRead(every=1, waiting_cycle=2)
stack.read = dense
capped, fr_cap = fb.walk_both("XUSDT", c15, c1h, cap=3)
check(f"سقف هر ارز رعایت می‌شود ({len(capped)})", len(capped) == 3)
check("وقتی به سقف خوردیم مرز = آخرین معامله (نه ته سری)",
      fr_cap == capped[-1]["opened"])
uncapped, fr_full = fb.walk_both("XUSDT", c15, c1h, cap=999)
check("بدون سقف بیشتر تولید می‌شود", len(uncapped) > 3)
check("وقتی به سقف نخوردیم مرز ته سری است (تاریخ کامل بررسی شد)",
      fr_full >= uncapped[-1]["opened"])
stack.read = fake

# ── معاملهٔ هم‌پوشان ساخته نمی‌شود ────────────────────────────────────────
opens = [r["opened"] for r in rows]
check("ورودها صعودی‌اند", opens == sorted(opens))
check("فاصلهٔ ورودها حداقل پنجرهٔ نگهداری است (بدون هم‌پوشانی)",
      all(b - a >= 96 * 900_000 for a, b in zip(opens, opens[1:])))

# ── run() دفتر واقعی را دست نمی‌زند ───────────────────────────────────────
from hamid import memory, paper                        # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="fill-"))
real_closed, real_state = paper.CLOSED, fb.STATE
paper.CLOSED = tmp / "closed.jsonl"
fb.STATE = tmp / "fill-state.json"

# run() علاوه بر دفتر، memory.digest_closed را هم صدا می‌زند. نسخهٔ اول این
# آزمون فقط paper.CLOSED را جابه‌جا کرد و ۱۴ معاملهٔ ساختگی AUSDT/BUSDT
# مستقیم وارد حافظهٔ تولید شد — یعنی آزمون داشت تجربهٔ ایجنت‌ها را مسموم
# می‌کرد، دقیقاً برعکس کاری که باید بکند. هر مسیر نوشتنی باید منحرف شود،
# نه فقط آنی که اول به ذهن می‌رسد.
real_mem = {k: getattr(memory, k) for k in ("LESSONS",)
            if hasattr(memory, k)}
for k in real_mem:
    setattr(memory, k, tmp / f"{k.lower()}.json")
real_brain_learning = None
try:
    import brain as _brain                            # noqa: PLC0415
    real_brain_learning = _brain.LEARNING
    _brain.LEARNING = tmp / "learning"
    (tmp / "learning").mkdir(exist_ok=True)
except Exception:                                     # noqa: BLE001
    pass

check("مسیر آزمون از دفتر واقعی جداست",
      paper.CLOSED != real_closed and fb.STATE != real_state)
check("مسیر حافظه هم منحرف شد (نه فقط دفتر)",
      all(getattr(memory, k) != v for k, v in real_mem.items()))

got = fb.run(symbols=["AUSDT", "BUSDT"], quiet=True,
             fetch=lambda s, n: (c15, c1h))
check(f"run معامله تولید کرد ({len(got)})", len(got) > 0)
written = [json.loads(l) for l in paper.CLOSED.read_text().splitlines() if l.strip()]
check("همه در دفتر نوشته شدند", len(written) == len(got))
check("هر دو ارز بازپخش شدند", {r["sym"] for r in got} == {"AUSDT", "BUSDT"})
st = json.loads(fb.STATE.read_text())
check("مرز پیشروی هر ارز ذخیره شد", set(st) == {"AUSDT", "BUSDT"})

got2 = fb.run(symbols=["AUSDT", "BUSDT"], quiet=True,
              fetch=lambda s, n: (c15, c1h))
check("اجرای دوم روی همان داده تکراری نمی‌سازد", got2 == [])

# بودجهٔ تمام‌شده باید تمیز تمام کند
got3 = fb.run(symbols=["CUSDT"], quiet=True, budget_s=0,
              fetch=lambda s, n: (c15, c1h))
check("بودجهٔ تمام‌شده کار تازه شروع نمی‌کند", got3 == [])

# ── مهلت باید **داخل** ارز هم ببرد، نه فقط قبل از شروعش ───────────────────
# نسخهٔ اول فقط قبل از شروع هر ارز نگاه می‌کرد؛ ارزی که وارد شده بود تا آخر
# می‌رفت و کل job از timeout رد می‌شد — روی رانر واقعی دیده شد.
import time as _t                                      # noqa: E402


class _Slow:
    def __init__(self):
        self.n = 0

    def __call__(self, *a):
        self.n += 1
        _t.sleep(0.004)
        return type("R", (), {"setup": None, "trend_4h": "up"})()


stack.read = _Slow()
_t0 = _t.time()
fb.walk_both("XUSDT", c15, c1h, deadline=_t.time() + 0.3)
_bounded, _calls_b = _t.time() - _t0, stack.read.n
stack.read = _Slow()
_t1 = _t.time()
fb.walk_both("XUSDT", c15, c1h)
_free, _calls_f = _t.time() - _t1, stack.read.n
check(f"مهلت وسط یک ارز هم می‌برد ({_bounded:.2f}s در برابر {_free:.2f}s)",
      _bounded < _free / 1.5)
check("کار کمتری انجام شد، نه فقط زودتر برگشت", _calls_b < _calls_f)
stack.read = fake

# گارد صریح: هیچ‌کدام از فایل‌های واقعی مغز نباید در این اجرا عوض شده باشند.
# آزمونی که خودش تولید را آلوده کند بدتر از نبودنش است.
import subprocess as _sp                              # noqa: E402

_dirty = _sp.run(["git", "status", "--porcelain", "--",
                  "brain/learning", "brain/memory", "brain/paper"],
                 cwd=REPO, capture_output=True, text=True).stdout.strip()
check("هیچ فایلی در مغز واقعی عوض نشد", not _dirty)
if _dirty:
    print("      ↳ " + _dirty.replace("\n", "\n      ↳ "))

paper.CLOSED, fb.STATE = real_closed, real_state
for k, v in real_mem.items():
    setattr(memory, k, v)
if real_brain_learning is not None:
    import brain as _b2                               # noqa: E402
    _b2.LEARNING = real_brain_learning
stack.read, bt.simulate = orig_read, orig_sim

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون پرکردن دفتر گذشت")
