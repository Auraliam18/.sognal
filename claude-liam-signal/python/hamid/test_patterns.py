"""آزمون خصمانهٔ انجین الگوها — دو طرفه:

۱. الگوی واقعیِ تمیز باید پیدا شود (وگرنه انجین کور است).
۲. روی گشت تصادفی خالص نباید همه‌جا الگو ببیند (وگرنه انجین خیال‌باف است
   و «شرط تأثیرگذار» یعنی نویزِ وزن‌دار). سقف نرخ شلیک اندازه‌گیری می‌شود.

    python3 -m hamid.test_patterns
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import patterns, premortem                          # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


def bar(i, o, h, l, c):
    return {"t": i * 900_000, "o": o, "h": h, "l": l, "c": c, "v": 10.0}


def path(vals, wick=0.15):
    """کندل از مسیر قیمتی — ویک کوچک دو طرف."""
    out = []
    for i in range(1, len(vals)):
        o, c = vals[i - 1], vals[i]
        hi, lo = max(o, c) + wick, min(o, c) - wick
        out.append(bar(i, o, hi, lo, c))
    return out


def leg(a, b, n):
    return [a + (b - a) * i / n for i in range(n)]


PAD = [100 + 0.2 * math.sin(i / 3) for i in range(20)]        # پیش‌زمینهٔ آرام

# ── سقف دوقلو ───────────────────────────────────────────────────────────────
v = (PAD + leg(100, 110, 12) + leg(110, 104, 8) + leg(104, 110.2, 8)
     + leg(110.2, 105, 6))
ps = patterns.detect(path(v))
dt = [p for p in ps if p["name"] == "double_top"]
check("سقف دوقلو پیدا می‌شود و خرسی است",
      dt and dt[0]["bias"] == "bear", str([p["name"] for p in ps]))

# ── کف دوقلو ────────────────────────────────────────────────────────────────
v = (PAD + leg(100, 90, 12) + leg(90, 96, 8) + leg(96, 89.9, 8)
     + leg(89.9, 95, 6))
ps = patterns.detect(path(v))
db = [p for p in ps if p["name"] == "double_bottom"]
check("کف دوقلو پیدا می‌شود و گاوی است",
      db and db[0]["bias"] == "bull", str([p["name"] for p in ps]))

# ── سر و شانه ───────────────────────────────────────────────────────────────
v = (PAD + leg(100, 108, 8) + leg(108, 103, 5) + leg(103, 113, 8)
     + leg(113, 103, 5) + leg(103, 108.3, 6) + leg(108.3, 102, 5))
ps = patterns.detect(path(v))
hs = [p for p in ps if p["name"] == "head_shoulders"]
check("سر و شانه پیدا می‌شود و خرسی است",
      hs and hs[0]["bias"] == "bear", str([p["name"] for p in ps]))

# ── سر و شانهٔ معکوس ────────────────────────────────────────────────────────
v = (PAD + leg(100, 92, 8) + leg(92, 97, 5) + leg(97, 87, 8)
     + leg(87, 97, 5) + leg(97, 91.8, 6) + leg(91.8, 98, 5))
ps = patterns.detect(path(v))
ihs = [p for p in ps if p["name"] == "inv_head_shoulders"]
check("سر و شانهٔ معکوس پیدا می‌شود و گاوی است",
      ihs and ihs[0]["bias"] == "bull", str([p["name"] for p in ps]))

# ── مثلث صعودی: سقف تخت، کف‌های بالا رونده ──────────────────────────────────
v = [100]
lows = [96, 97.2, 98.2, 99.0]
for lo_ in lows:
    v += leg(v[-1], 102, 6) + leg(102, lo_, 6)
v += leg(v[-1], 101, 4)
ps = patterns.detect(path(v, wick=0.05))
tri = [p for p in ps if p["name"] == "asc_triangle"]
check("مثلث صعودی پیدا می‌شود و گاوی است",
      tri and tri[0]["bias"] == "bull", str([p["name"] for p in ps]))

# ── پرچم صعودی: ضربهٔ قوی + استراحت کم‌عمق ─────────────────────────────────
v = [100 + 0.1 * math.sin(i) for i in range(30)] + leg(100, 112, 9) + leg(112, 110, 5)
ps = patterns.detect(path(v, wick=0.1))
fl = [p for p in ps if p["name"] == "flag"]
check("پرچم صعودی پیدا می‌شود و گاوی است",
      fl and fl[0]["bias"] == "bull", str([p["name"] for p in ps]))

# ── کنترل نویز: گشت تصادفی خالص ────────────────────────────────────────────
fired = biased = 0
TRIALS = 40
for seed in range(TRIALS):
    random.seed(seed)
    p, vals = 100.0, [100.0]
    for _ in range(119):
        p *= 1 + random.gauss(0, 0.004)
        vals.append(p)
    got = patterns.detect(path(vals, wick=p * 0.001))
    if got:
        fired += 1
    if any(g["bias"] in ("bull", "bear") for g in got):
        biased += 1
rate = biased / TRIALS
check(f"روی گشت تصادفی، الگوی جهت‌دار در ≤۴۰٪ پنجره‌ها (واقعی: {rate:.0%})",
      rate <= 0.40, f"{biased}/{TRIALS}")

# ── align: تعارض انتخاب نمی‌شود ─────────────────────────────────────────────
a, b = patterns.align([{"name": "x", "fa": "x", "bias": "bull",
                        "age": 1, "status": "forming", "key": 1}], "LONG")
check("الگوی گاوی برای لانگ = with", a == "with")
a, _ = patterns.align([{"name": "x", "fa": "x", "bias": "bull", "age": 1,
                        "status": "forming", "key": 1},
                       {"name": "y", "fa": "y", "bias": "bear", "age": 0,
                        "status": "confirmed", "key": 1}], "LONG")
check("الگوهای متضاد → تعارض (None)، انتخاب دلبخواه ممنوع", a is None)
a, _ = patterns.align([{"name": "s", "fa": "s", "bias": None, "age": 1,
                        "status": "forming", "key": 1}], "LONG")
check("الگوی بی‌جهت (فشردگی) با/خلاف نمی‌سازد", a is None)

# ── اتصال به بازجویی: کف دوقلوی هم‌جهت باید دلیل تارگت لانگ شود ────────────
import json as _json                                           # noqa: E402
import tempfile as _tf                                         # noqa: E402
premortem.DOM = Path(_tf.mkdtemp()) / "no-dom.json"
v = ([100] + leg(100, 90, 12) + leg(90, 96, 8) + leg(96, 89.9, 8)
     + leg(89.9, 95, 20))
c15 = path(v)
e = c15[-1]["c"]
rv = premortem.review({"sym": "PATUSDT", "dir": "LONG", "entry": e,
                       "sl": e * 0.96, "tp1": e * 1.05}, c15)
check("الگوی هم‌جهت در دلایل تارگت بازجویی است",
      any("الگوی کلاسیک هم‌جهت" in x for x in rv["pro"]), str(rv["pro"]))
check("الگو در خروجی بازجویی برای پرونده ثبت می‌شود",
      (rv.get("patterns") or {}).get("align") == "with"
      and "15m" in (rv["patterns"].get("by_tf") or {}), str(rv.get("patterns")))
rv2 = premortem.review({"sym": "PATUSDT", "dir": "SHORT", "entry": e,
                        "sl": e * 1.04, "tp1": e * 0.95}, c15)
check("همان الگو برای شورت دلیل استاپ است",
      any("الگوی کلاسیک خلاف" in x for x in rv2["con"]), str(rv2["con"]))

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های انجین الگو گذشت")
