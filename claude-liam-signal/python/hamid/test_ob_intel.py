"""آزمون خصمانهٔ هوش اردر بلاک — شواهد، وضعیت، گرید، بریکر، رادار.

هر دو طرف: سناریوی ساختاریِ تمیز باید مدرک و گرید بالا بگیرد؛ باکسِ
بی‌مدرک و گشت تصادفی نباید A بگیرند («کندل چشم‌گیر بدون تأیید، رد»).

    python3 -m hamid.test_ob_intel
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import ob_intel as ob                               # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


def bar(i, o, c, h=None, l=None, v=10.0):
    return {"t": i * 3_600_000, "o": o, "c": c,
            "h": h if h is not None else max(o, c) + 0.15,
            "l": l if l is not None else min(o, c) - 0.15, "v": v}


def drift(st, n, base=100.0, amp=0.3):
    return [bar(st + i, base + amp * math.sin((st + i) / 4.0),
                base + amp * math.sin((st + i + 1) / 4.0)) for i in range(n)]


def leg(st, a, b, n, v=10.0):
    return [bar(st + i, a + (b - a) * i / n, a + (b - a) * (i + 1) / n, v=v)
            for i in range(n)]


def rich_scenario():
    """سناریوی پرمدرک: سوییپ سقف قبلی → کندل حمید پرحجم → ریزش با FVG و BOS
    → دو برگشت با واکنش. باید گرید بالا بگیرد."""
    cd = drift(0, 20, base=100.0)                    # سقف قبلی ~۱۰۰.۳
    cd += drift(20, 14, base=99.0)                   # عقب‌نشینی
    cd.append(bar(34, 99.0, 99.4, h=100.9, l=98.9))  # سوییپِ سقف قبلی، بستن زیر
    cd.append(bar(35, 99.4, 102.4, v=40.0))          # کندل حمید — بدنه‌قوی پرحجم
    # ریزش با گپ (FVG): کندل ۳۷ از ۳۶ فاصلهٔ گپ می‌سازد
    cd.append(bar(36, 102.4, 100.8, h=102.55, l=100.6))
    cd.append(bar(37, 99.6, 97.8, h=99.9, l=97.6))   # h(37)=99.9 < l(35)=99.25? نه — گپ بین ۳۶ و ۳۸
    cd.append(bar(38, 97.8, 95.6, h=97.9, l=95.4))
    cd += leg(39, 95.6, 92.0, 5)                     # BOS: زیر کف ۳۰ کندل قبل می‌بندد
    cd += drift(44, 8, base=92.0)
    cd += leg(52, 92.0, 101.0, 6) + leg(58, 101.0, 93.5, 6)   # برگشت ۱ + واکنش
    cd += drift(64, 6, base=93.5)
    cd += leg(70, 93.5, 100.8, 6) + leg(76, 100.8, 93.0, 6)   # برگشت ۲ + واکنش
    cd += drift(82, 10, base=93.0)
    return cd


CD = rich_scenario()
BOXES = ob.analyze(CD, "1h")
# شواهد را مستقیم روی کندل مبدأ شناخته‌شده می‌سنجیم (ایندکس ۳۵: کندل حمید
# پرحجم ۹۹.۴→۱۰۲.۴)، نه با حدس دربارهٔ هندسهٔ لنگر انجین
I0 = 35
check("سوییپ قبل از مبدأ دیده می‌شود", ob.swept_before(CD, I0, "down"))
check("BOS بعد از مبدأ دیده می‌شود", ob.bos_after(CD, I0, "down"))
_fake = {"low": CD[I0]["l"], "high": CD[I0]["h"], "move": "down"}
check("مکان: باکس نزولی در premium", ob.location_of(CD, _fake)[0] == "premium",
      str(ob.location_of(CD, _fake)))
check("حجم کندل مبدأ جهش دارد", ob.vol_z_at(CD, I0) >= 1.5,
      str(ob.vol_z_at(CD, I0)))
# و در سطح analyze: باکس نزولی در ناحیهٔ عرضه با واکنش و گرید غیر-REJECT
TOP = [b for b in BOXES if b["move"] == "down" and b["high"] >= 100.5
       and b["grade"] != "REJECT"]
check("باکس ناحیهٔ عرضه با گرید معتبر پیدا می‌شود", bool(TOP),
      str([(b["low"], b["high"], b["grade"], b["state"]) for b in BOXES]))
B = TOP[0] if TOP else None
if B:
    check("چرایی فارسی با مدرک", len(B["why_fa"]) >= 2, str(B["why_fa"]))
    check("وضعیت: لمس/واکنش ثبت شده",
          B["state"] in ("REACTION_CONFIRMED", "TOUCHED", "PARTIALLY_MITIGATED",
                         "MITIGATED", "WEAKENED"), B["state"])
    check("کیفیت میتیگیشن ثبت شده", len(B["mitigation"]) >= 1, str(B["mitigation"]))

# ── FVG آشکارساز مستقل ─────────────────────────────────────────────────────
g = [bar(0, 100, 100.2), bar(1, 100.2, 99.0, h=100.4, l=98.8),
     bar(2, 99.0, 97.0, h=99.2, l=96.8), bar(3, 96.5, 95.0, h=96.6, l=94.8)]
check("FVG نزولی: l کندل قبل > h کندل بعد", ob.fvg_after(g, 0, "down") is not None)

# ── باکس بی‌مدرک: ایمپالس وسطِ رنج، بدون سوییپ/BOS/گپ → گرید پایین ───────
def bare_scenario():
    # رنج بزرگ ۹۰-۱۱۰ از قبل جا افتاده؛ ایمپالس وسط رنج بدون سوییپ/FVG
    cd = leg(0, 100, 110, 8) + leg(8, 110, 90, 10) + leg(18, 90, 100, 8)
    cd += drift(26, 24, base=100.0, amp=0.2)
    cd.append(bar(50, 100.0, 101.6))                 # کندل حمید، ولی بی‌بستر
    cd += leg(51, 101.6, 94.5, 11)                   # قدم ~۰.۶ بی‌گپ (ویک ۰.۱۵)
    cd += drift(62, 40, base=94.5, amp=0.2)
    return cd


bb = ob.analyze(bare_scenario(), "1h")
bare = [b for b in bb if b["move"] == "down" and b["i"] >= 45]
check("باکس بی‌مدرک گرید بالا نمی‌گیرد",
      bool(bare) and all(b["grade"] not in ("A_PLUS", "A") for b in bare),
      str([(b["grade"], b["score"], b.get("groups"), b["why_fa"]) for b in bare]))

# ── بریکر: باکس شکسته + برگشت از سمت مقابل ────────────────────────────────
def breaker_scenario():
    cd = rich_scenario()
    n = len(cd)
    cd += leg(n, 93.0, 106.0, 8)                     # شکست باکس با بدنه
    cd += drift(n + 8, 6, base=106.0)
    cd += leg(n + 14, 106.0, 100.2, 5)               # برگشت به داخل باکس از بالا
    cd += leg(n + 19, 100.2, 108.0, 6)               # واکنش صعودی — بریکر
    cd += drift(n + 25, 8, base=108.0)
    return cd


bk = ob.analyze(breaker_scenario(), "1h")
bkr = [b for b in bk if b["high"] >= 100.5 and b["move"] == "down" and b["broken"]]
check("باکس شکسته با برگشتِ مقابل → BREAKER",
      bkr and bkr[0]["state"] == "BREAKER",
      str([(b["state"], b["low"], b["high"]) for b in bkr]))

# ── رادار با فچ تزریقی ─────────────────────────────────────────────────────
def fetch(sym, tf, n):
    if tf == "15m":
        cd = rich_scenario()
        return [{**c, "t": i * 900_000} for i, c in enumerate(cd)]
    if tf == "1h":
        # ۴×۹۰ کندل ۱س هم‌تراز تا _to4h هم چیزی بسازد
        cd = rich_scenario() + drift(len(rich_scenario()), 260, base=93.0)
        return [{**c, "t": i * 3_600_000} for i, c in enumerate(cd)]
    return []


r = ob.radar_for("TESTUSDT", fetch)
check("رادار همهٔ قلم‌ها را دارد",
      all(k in r for k in ("nearest_bull_below", "nearest_bear_above",
                           "strongest_bull", "strongest_bear", "nearest_fresh",
                           "nearest_htf", "nested", "approaching", "n_valid")))
check("رادار باکس معتبر دیده", r["n_valid"] >= 1, str(r["n_valid"]))

# ── کنترل نویز: گشت تصادفی نباید A بدهد ────────────────────────────────────
hiA = 0
TR = 20
for seed in range(TR):
    random.seed(seed + 500)
    p, cdn = 100.0, []
    for i in range(300):
        q = p * (1 + random.gauss(0, 0.004))
        w = p * 0.002 * (0.5 + random.random())      # ویک واقع‌گرایانه ~۰.۲٪
        cdn.append(bar(i, p, q, h=max(p, q) + w, l=min(p, q) - w,
                       v=10 * (1 + abs(random.gauss(0, 0.3)))))
        p = q
    if any(b["grade"] in ("A_PLUS", "A") for b in ob.analyze(cdn, "1h")):
        hiA += 1
rate = hiA / TR
check(f"روی گشت تصادفی، گرید A در ≤۲۵٪ پنجره‌ها (واقعی: {rate:.0%})",
      rate <= 0.25, f"{hiA}/{TR}")

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های هوش اردر بلاک گذشت")
