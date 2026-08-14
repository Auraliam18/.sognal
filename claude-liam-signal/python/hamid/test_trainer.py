"""آزمون میز تمرین ۲۰۰تایی — بدون شبکه، کندل ساختگی، دفتر موقت.

  ۱. بدون look-ahead: تصمیم کندل i فقط پنجرهٔ گذشته را می‌بیند (اثبات مکانیکی)
  ۲. برخورد استاپ+تارگت در یک کندل = استاپ (بدخیم‌ترین فرض)
  ۳. قانون تریل: ⅓ مسیر رفت و برگشت → سود کارمزددار، نه ضرر کامل
  ۴. روی ۱۰۰ ارز ساختگی، کف ۲۰۰ معامله در می‌آید
  ۵. ضدتکرار: اجرای دوم روی همان داده صفر معامله می‌سازد
  ۶. ردیف دفتر شکل درست دارد و stage=practice است (ترازوی سیگنال آلوده نشود)
  ۷. درس‌ها با digest به حافظه می‌روند
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

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


def synth15(n=800, seed=1, start=10.0):
    rnd = random.Random(seed)
    out, px, t = [], start, 1_750_000_000_000
    for i in range(n):
        drift = 0.0006 + (0.006 if i % 120 == 0 else 0)
        r = rnd.gauss(drift, 0.004)
        o = px
        c = max(1e-9, o * (1 + r))
        hi = max(o, c) * (1 + abs(rnd.gauss(0, 0.002)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, 0.002)))
        out.append({"t": t + i * 900_000, "o": o, "h": hi, "l": lo, "c": c,
                    "v": abs(rnd.gauss(1000, 200)) * (3 if i % 120 == 0 else 1)})
        px = c
    return out


print("── میز تمرین ۲۰۰تایی ──")

from hamid import trainer, paper, memory                        # noqa: E402
import brain                                                    # noqa: E402

TMP = Path(tempfile.mkdtemp())
trainer.STATE = TMP / "trainer-state.json"
paper.CLOSED = TMP / "closed.jsonl"
paper.OPEN = TMP / "open.jsonl"
memory.LESSONS = TMP / "lessons.json"
brain.learn = lambda *a, **k: None                # ایندکس آماری در تست لازم نیست
brain.build_index = lambda *a, **k: None

# ── ۱. بدون look-ahead — decide فقط پنجره را می‌بیند ───────────────────────
c15 = synth15(500, seed=7)
windows_seen = []
orig_decide = trainer.decide


def spy_decide(window, tf="15m"):
    windows_seen.append(len(window))
    return orig_decide(window, tf=tf)


trainer.decide = spy_decide
tr = trainer.replay_symbol("SPYUSDT", c15)
check("تصمیم هرگز کل سری را ندید (پنجره < کل)",
      windows_seen and max(windows_seen) < len(c15))
check("پنجره‌ها صعودی جلو می‌روند (بازپخش واقعی)",
      windows_seen == sorted(windows_seen))
trainer.decide = orig_decide

# ── ۲. برخورد هم‌زمان = استاپ ──────────────────────────────────────────────
flat = [{"t": i * 900_000, "o": 100.0, "h": 100.0, "l": 100.0, "c": 100.0, "v": 1}
        for i in range(210)]
s = {"dir": "LONG", "entry": 100.0, "sl": 99.0, "tp1": 102.0}
flat.append({"t": 210 * 900_000, "o": 100.0, "h": 103.0, "l": 98.0, "c": 100.0, "v": 1})
j, outcome, r, exc = trainer.resolve(flat, 209, s)   # ورود در ۲۰۹؛ کندل بحرانی ۲۱۰
check("کندلی که هم استاپ زد هم تارگت → استاپ (بدون خوش‌بینی)",
      outcome == "stop" and r == -1.0)

# ── ۳. قانون تریل ──────────────────────────────────────────────────────────
base = [{"t": i * 900_000, "o": 100.0, "h": 100.1, "l": 99.9, "c": 100.0, "v": 1}
        for i in range(210)]
# ⅓ مسیر (۱۰۰.۶۷) لمس می‌شود، بعد برگشت کامل به ورود — بدون لمس استاپ
base.append({"t": 210 * 900_000, "o": 100.0, "h": 100.8, "l": 99.95, "c": 100.7, "v": 1})
base.append({"t": 211 * 900_000, "o": 100.7, "h": 100.75, "l": 99.9, "c": 99.95, "v": 1})
base += [{"t": (212 + i) * 900_000, "o": 99.95, "h": 100.0, "l": 99.9, "c": 99.95, "v": 1}
         for i in range(10)]
s3 = {"dir": "LONG", "entry": 100.0, "sl": 99.0, "tp1": 102.0}
j3, out3, r3, exc3 = trainer.resolve(base, 210, s3)
check("⅓ مسیر رفت و برگشت → تریل با سود کارمزددار (نه ضرر کامل)",
      out3 == "trail" and r3 > 0)

# ── ۴. کف ۲۰۰ معامله روی ۱۰۰ ارز ───────────────────────────────────────────
syms = [f"C{i:03d}USDT" for i in range(100)]
data = {s: synth15(800, seed=i + 10) for i, s in enumerate(syms)}
trades = trainer.run(symbols=syms, fetch_c15=lambda s: data[s], quiet=True)
check(f"کف ۲۰۰ معامله در یک نوبت ({len(trades)} ساخته شد)", len(trades) >= 200)
check("همه در دفتر ثبت شدند",
      len(paper.CLOSED.read_text().strip().split("\n")) == len(trades))

# ── ۵. ضدتکرار بین اجراها ──────────────────────────────────────────────────
trades2 = trainer.run(symbols=syms, fetch_c15=lambda s: data[s], quiet=True)
check(f"اجرای دوم روی همان داده تکرار نمی‌سازد ({len(trades2)})",
      len(trades2) == 0)

# ── ۶. شکل ردیف دفتر ───────────────────────────────────────────────────────
t0 = trades[0]
check("ردیف شکل دفتر واقعی را دارد",
      all(k in t0 for k in ("sym", "dir", "entry", "sl", "tp1", "opened",
                            "why", "outcome", "R", "closed")))
check("stage=practice — ترازوی سیگنال‌شده آلوده نمی‌شود",
      all(t["why"]["stage"] == "practice" for t in trades))
check("هر معامله دلیل ساختاری دارد (setup/stop_pct)",
      all(t["why"].get("setup") in ("ob_pullback", "bos_continuation")
          and "stop_pct" in t["why"] for t in trades))
check("نتیجه‌ها فقط از چهار نوع مجازند",
      all(t["outcome"] in ("stop", "target", "trail", "timeout") for t in trades))

# ── عمق (دستور «عمیق‌ترش کن») ─────────────────────────────────────────────
check("MFE/MAE روی هر پرونده هست",
      all("mfe" in t["why"] and "mae" in t["why"] for t in trades))
check("MFE نامنفی و MAE نامثبت است (تعریف درست excursion)",
      all(t["why"]["mfe"] >= 0 and t["why"]["mae"] <= 0 for t in trades))
check("مدت نگهداری (hold_bars) ثبت می‌شود",
      all(t.get("hold_bars", 0) > 0 for t in trades))
check("عمق تاریخ ≥ ۲۰۰۰ کندل شد", trainer.BARS >= 2000)
stopped_with_profit = [t for t in trades
                       if t["outcome"] == "stop" and t["why"]["mfe"] >= 1.0]
print(f"    (نمونهٔ درس تریل: {len(stopped_with_profit)} استاپ که اول ۱R+ سود بودند)")

# ── ۷. درس‌ها به حافظه رفتند ───────────────────────────────────────────────
lessons = json.loads(memory.LESSONS.read_text()).get("lessons", [])
check(f"درس در حافظه نشست ({len(lessons)})", len(lessons) > 0)

# ── ۸. مغز واقعی دست نخورد ─────────────────────────────────────────────────
# عیب‌یابی ۱۴ اوت: نسخهٔ اول این آزمون شرط می‌کرد فایل واقعی «وجود نداشته
# باشد» — ولی وقتی ورک‌فلوی ساعتی trainer یک بار واقعاً اجرا شود، همان
# فایل درست و به‌جا ساخته و کامیت می‌شود؛ آن‌وقت این آزمون سرخ می‌شد و
# **کل چرخهٔ حمید را می‌کشت** (خودآزمایی قبل از تولید سیگنال است). شرط
# درست این است: آزمون به مسیر واقعی ننوشته باشد، نه اینکه تولید ننویسد.
real = Path(__file__).resolve().parents[3] / "brain" / "paper" / "trainer-state.json"
check("مسیر state آزمون از مغز واقعی جداست", trainer.STATE != real)
check("آزمون در پوشهٔ موقت نوشت", trainer.STATE.exists()
      and str(trainer.STATE).startswith(str(TMP)))
check("دفتر آزمون هم جدا بود", paper.CLOSED != (
    Path(__file__).resolve().parents[3] / "brain" / "paper" / "closed.jsonl"))

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون میز تمرین گذشت")
