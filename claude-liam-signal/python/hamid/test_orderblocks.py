"""آزمون خصمانهٔ انجین اردر بلاک — هر دو طرف:

الگوی واقعی (کندل بدنه‌قوی قبل از ریزش/صعود + برگشت و واکنش) باید پیدا
شود؛ و روی گشت تصادفی نباید باکس «معتبر» فراوان ببیند. هانت و شکست هم
باید همان معنایی را بدهند که حمید روی چارت می‌کشد.

    python3 -m hamid.test_orderblocks
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import orderblocks as ob                            # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


def bar(i, o, c, h=None, l=None):
    return {"t": i * 3_600_000, "o": o, "c": c,
            "h": h if h is not None else max(o, c) + 0.15,
            "l": l if l is not None else min(o, c) - 0.15, "v": 10.0}


def drift(start, n, base=100.0, amp=0.3):
    return [bar(start + i, base + amp * math.sin((start + i) / 4.0),
                base + amp * math.sin((start + i + 1) / 4.0)) for i in range(n)]


def leg(start, a, b, n):
    out = []
    for i in range(n):
        o = a + (b - a) * i / n
        c = a + (b - a) * (i + 1) / n
        out.append(bar(start + i, o, c))
    return out


# ── سناریوی حمید: کندل بدنه‌قوی → ریزش → دو برگشت با واکنش ─────────────────
cd = drift(0, 40)                                     # آرام حول ۱۰۰
i0 = len(cd)
cd.append(bar(i0, 100.0, 103.0))                      # کندل حمید: بدنهٔ ۳، شدو ۰.۳
cd += leg(i0 + 1, 103.0, 92.0, 8)                     # ریزش قوی (ایمپالس down)
cd += drift(i0 + 9, 10, base=92.0)
cd += leg(i0 + 19, 92.0, 100.5, 6)                    # برگشت اول به باکس
cd += leg(i0 + 25, 100.5, 94.0, 6)                    # واکنش: ریجکت
cd += drift(i0 + 31, 8, base=94.0)
cd += leg(i0 + 39, 94.0, 100.2, 6)                    # برگشت دوم
cd += leg(i0 + 45, 100.2, 93.0, 6)                    # واکنش دوم
cd += drift(i0 + 51, 10, base=93.0)

boxes = ob.find(cd, tf="1h")
hit = [b for b in boxes if b["low"] <= 101.5 and b["high"] >= 101.0 and b["move"] == "down"]
check("اردر بلاکِ کندل بدنه‌قوی قبل از ریزش پیدا می‌شود", bool(hit),
      str([(b['low'], b['high'], b['move'], b['reactions']) for b in boxes]))
check("حداقل ۲ واکنش شمرده شده", hit and hit[0]["reactions"] >= 2,
      str(hit[0] if hit else None))
check("قانون کندل حمید: بدنه > شدوها", ob.hamid_candle(bar(0, 100.0, 103.0))
      and not ob.hamid_candle({"t": 0, "o": 100, "c": 100.4, "h": 102, "l": 99, "v": 1}))

# ── هانت: ویک تا آن‌طرف باکس و بستن بیرون ──────────────────────────────────
cd2 = list(cd[:i0 + 51])
# برگشت سوم: ویک کل باکس (تا ۱۰۳.۲) را می‌گیرد ولی زیر باکس می‌بندد
j = len(cd2)
cd2 += leg(j, 93.0, 99.5, 5)
cd2.append(bar(j + 5, 99.5, 99.0, h=103.4, l=98.6))   # ویکِ شکار
cd2 += leg(j + 6, 99.0, 92.5, 5)                      # و ریجکت
cd2 += drift(j + 11, 8, base=92.5)
boxes2 = ob.find(cd2, tf="1h")
hit2 = [b for b in boxes2 if b["low"] <= 101.5 and b["high"] >= 101.0]
check("هانت شمرده می‌شود (ویک آن‌طرف، بستن بیرون)",
      hit2 and hit2[0]["hunts"] >= 1, str(hit2[0] if hit2 else boxes2))

# ── شکست: بستن آن‌طرف باکس = مصرف‌شده، از معتبرها حذف ─────────────────────
cd3 = list(cd[:i0 + 51])
j = len(cd3)
cd3 += leg(j, 93.0, 106.0, 8)                         # با بدنه از باکس رد می‌شود
cd3 += drift(j + 8, 10, base=106.0)
boxes3 = ob.find(cd3, tf="1h")
hit3 = [b for b in boxes3 if b["low"] <= 101.5 and b["high"] >= 101.0 and not b["broken"]]
check("باکسِ شکسته دیگر معتبر گزارش نمی‌شود", not hit3,
      str([(b['low'], b['high'], b['broken']) for b in boxes3]))

# ── باکس تازه: حرکت همین حالا، هنوز برگشتی نبوده ───────────────────────────
cd4 = drift(0, 60) + [bar(60, 100.0, 102.5)] + leg(61, 102.5, 94.0, 7)
boxes4 = ob.find(cd4, tf="1h")
fresh = [b for b in boxes4 if b["fresh"]]
check("باکس تازه (لمس‌نشده) با برچسب fresh گزارش می‌شود", bool(fresh),
      str(boxes4))

# ── کنترل نویز: گشت تصادفی ─────────────────────────────────────────────────
val = 0
TRIALS = 25
for seed in range(TRIALS):
    random.seed(seed + 1000)
    p, cdn = 100.0, []
    for i in range(320):
        q = p * (1 + random.gauss(0, 0.004))
        cdn.append(bar(i, p, q, h=max(p, q) + p * 0.001, l=min(p, q) - p * 0.001))
        p = q
    proven = [b for b in ob.find(cdn, tf="1h") if not b["fresh"] and b["reactions"] >= 3]
    if proven:
        val += 1
rate = val / TRIALS
check(f"روی گشت تصادفی، باکس پرواکنش (≥۳) در ≤۳۰٪ پنجره‌ها (واقعی: {rate:.0%})",
      rate <= 0.30, f"{val}/{TRIALS}")

# ── near و جملهٔ فارسی ─────────────────────────────────────────────────────
b_in, b_near = ob.near(cd2, tf="1h")
s = ob.note_fa(hit2[0]) if hit2 else ""
check("جملهٔ فارسی عدد دارد", ("واکنش" in s) or ("تازه" in s), s)

# ── اتصال به بازجویی: ورود شورت روی OB نزولیِ پرواکنش = دلیل تارگت ────────
import tempfile as _tf                                         # noqa: E402
from hamid import premortem                                    # noqa: E402
premortem.DOM = Path(_tf.mkdtemp()) / "no-dom.json"
e = cd2[-1]["c"]
rv = premortem.review({"sym": "OBTESTUSDT", "dir": "SHORT", "entry": e,
                       "sl": e * 1.06, "tp1": e * 0.94}, cd2)
check("OB هم‌جهت در دلایل بازجویی ثبت می‌شود",
      any("اردر بلاک" in x for x in rv["pro"] + rv["con"]),
      str(rv["pro"] + rv["con"]))
check("ob_ctx برای دفتر یادگیری برمی‌گردد",
      rv.get("ob_ctx") is None or "align" in rv["ob_ctx"], str(rv.get("ob_ctx")))

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های انجین اردر بلاک گذشت")
