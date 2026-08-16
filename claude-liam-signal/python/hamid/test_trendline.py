"""آزمون خط روند کتاب، دروازهٔ بیت‌یونیکس، و وضوح چارت — دستور حمید ۱۵ اوت.

سه دستور، سه بخش:

  · «خط روند ۱ساعته و ۴ساعته که بر اساس ترندلاین‌کشیدن یاد گرفتی، در
    تصویر بماند» → `structure.trendline` + کشیدنش روی چارت
  · «ارزهایی باشد که در بیت‌یونیکس موجود باشد» → `venues.tradable`
  · «کندل‌ها را واضح‌تر بکشد» → بدنهٔ پهن‌تر و محوری که خط‌ها آن را نکشند

نکتهٔ صادقانه دربارهٔ گزینش‌گری: این خط‌یاب روی گام تصادفی هم خط پیدا
می‌کند (۶۰/۶۰ اندازه‌گیری شد). یعنی وجودِ خط به‌تنهایی مدرکِ ساختار نیست
— همان‌طور که آدم هم روی نویز خط می‌کشد. چیزی که این‌جا تضمین می‌شود
تعریفِ کتاب است: ≥۳ برخورد مجزا، بدون شکستِ بدنه، شیب هم‌جهت با نوع خط.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import structure as st                     # noqa: E402
from hamid import venues as vn                        # noqa: E402

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


def series(seed, drift, n=160, step=900_000, wob=0.004):
    r = random.Random(seed)
    cd, p = [], 100.0
    for i in range(n):
        p *= (1 + drift + math.sin(i / 11) * wob + r.gauss(0, 0.0016))
        hi = p * (1 + abs(r.gauss(0, 0.0022)))
        lo = p * (1 - abs(r.gauss(0, 0.0022)))
        o = p * (1 + r.gauss(0, 0.0008))
        cd.append({"t": 1_700_000_000_000 + i * step, "o": o,
                   "h": max(hi, o, p), "l": min(lo, o, p), "c": p, "v": 10})
    return cd


print("── خط روند کتاب · دروازهٔ بیت‌یونیکس · وضوح چارت ──")

# ── ۱. جهت خط با نوعش می‌خواند ────────────────────────────────────────────
up = st.trendline(series(7, 0.0022))
dn = st.trendline(series(7, -0.0022))
check("روند صعودی → خط حمایت", up is not None and up.kind == "support")
check("روند نزولی → خط مقاومت", dn is not None and dn.kind == "resistance")
check("خط حمایت شیب مثبت دارد (از کف‌های بالارونده)", up is None or up.slope > 0)
check("خط مقاومت شیب منفی دارد (از سقف‌های پایین‌رونده)",
      dn is None or dn.slope < 0)

# ── ۲. شرط کتاب: دست‌کم سه برخورد مجزا ────────────────────────────────────
check("خط بدون ≥۳ برخورد ساخته نمی‌شود",
      all(t.touches >= 3 for t in (up, dn) if t))
check("برخوردها مجزا شمرده می‌شوند، نه هر کندلِ نزدیک",
      up is None or up.touches < 30)     # نسخهٔ اول ۳۷ می‌داد روی همین سری

# ── ۳. شکستِ بدنه ثبت می‌شود ولی خط پاک نمی‌شود ──────────────────────────
cd = series(3, 0.002)
t = st.trendline(cd)
if t:
    broken_cd = [dict(k) for k in cd]
    for i in range(len(broken_cd) - 12, len(broken_cd)):   # ته سری را بشکن
        line = t.at(i - max(0, len(cd) - 120))
        broken_cd[i]["o"] = broken_cd[i]["c"] = line * 0.90
        broken_cd[i]["l"] = line * 0.89
    t2 = st.trendline(broken_cd)
    check("بعد از شکستِ بدنه، یا خط دیگری پیدا می‌شود یا شکسته علامت می‌خورد",
          t2 is None or t2.broken or abs(t2.slope - t.slope) > 1e-9)
else:
    check("سری آزمون خط داشت", False)

# ── ۴. نگاشت زمانی: خط تایم بالا روی محور تایم پایین ─────────────────────
h1 = series(5, 0.0015, n=200, step=3_600_000)
tl = st.trendline(h1)
check("خط ۱ساعته ساخته شد", tl is not None)
if tl:
    v0 = tl.at_t(h1[0]["t"], h1)
    vn_ = tl.at_t(h1[-1]["t"], h1)
    # این دو شرط قبلاً رفتارِ **باگ‌دار** را تثبیت می‌کردند: فرض می‌شد
    # ایندکس صفرِ خط همان کندل اولِ سری است. ولی `trendline` روی ۱۲۰ کندل
    # آخر برازش می‌کند، پس مبدأ آن‌جاست. حالا شرط درست سنجیده می‌شود.
    check("at_t روی **مبدأ پنجرهٔ برازش** با at(0) هم‌خوان است",
          abs(tl.at_t(tl.t0) - tl.at(0)) < 1e-6)
    check("و روی کندل اول سری با at(0) هم‌خوان **نیست** (چون مبدأ آن نیست)",
          len(h1) <= 120 or abs(v0 - tl.at(0)) > 1e-9)
    check("خط در طول سری حرکت می‌کند (نه ثابت)",
          vn_ is not None and abs(vn_ - v0) > 0)
    check("at_t بدون سری هم جواب می‌دهد — گام را از خودِ خط دارد",
          tl.at_t(h1[-1]["t"]) is not None)

# ── ۵. دروازهٔ بیت‌یونیکس ─────────────────────────────────────────────────
idx = {"BTCUSDT": ["bitunix", "xt"], "FOOUSDT": ["xt"], "BARUSDT": []}
check("نماد روی بیت‌یونیکس مجاز است", vn.tradable("BTCUSDT", idx)[0] is True)
check("نمادِ فقط-XT ارسال نمی‌شود", vn.tradable("FOOUSDT", idx)[0] is False)
check("نمادِ ناشناخته ارسال نمی‌شود", vn.tradable("ZZZUSDT", idx)[0] is False)
check("فهرست خالی = NO_SIGNAL، نه «شاید»",
      vn.tradable("BTCUSDT", {})[0] is False)
check("دلیلِ رد به فارسی و قابل‌چاپ است",
      "بیت‌یونیکس" in vn.tradable("FOOUSDT", idx)[1])
check("صرافی اجرا صریح تعریف شده", vn.EXECUTION_VENUE == "bitunix")

# ── ۶. چارت: خط‌ها محور را نکشند و کندل واضح بماند ───────────────────────
try:
    import matplotlib                                 # noqa: F401
    import tg_batch as tb                             # noqa: E402

    c5 = series(5, 0.0009, n=110, step=300_000)
    px = c5[-1]["c"]

    class FarLine:
        """خطی عمداً بیرون کادر — نباید کشیده شود."""
        broken = False
        touches = 5

        def at_t(self, t, cd):
            return px * 3          # خیلی بالاتر از هر کندل

    buf = tb.chart("TESTUSDT", c5, px * 0.999, px * 0.994, px * 1.006,
                   px * 1.011, "LONG",
                   htf=[("4H", FarLine(), c5, "#f0a92e")])
    check("چارت با خط بیرون‌کادر هم ساخته می‌شود", buf is not None)
    check("چارت خروجی PNG واقعی است", buf.getvalue()[:4] == b"\x89PNG")

    buf2 = tb.chart("TESTUSDT", c5, px * 0.999, px * 0.994, px * 1.006,
                    px * 1.011, "LONG", htf=None)
    check("بدون خط تایم بالا هم چارت سالم است",
          buf2 is not None and buf2.getvalue()[:4] == b"\x89PNG")
    check("خط بیرون‌کادر چارت را بزرگ‌تر نکرد (محور از کندل‌هاست)",
          abs(len(buf.getvalue()) - len(buf2.getvalue()))
          < max(len(buf2.getvalue()) * 0.5, 40_000))
except ImportError:
    print("  ⏭ matplotlib نیست — آزمون چارت رد شد")

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون خط روند/صرافی/چارت گذشت")
