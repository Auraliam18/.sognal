"""آزمون دیتابیس خطوط و دفتر پایداری قانون — دستور حمید ۱۶ اوت.

سه چیزی که باید تضمین شود:

  ۱. **مبدأ زمانی خط.** `trendline` روی ۱۲۰ کندل آخر برازش می‌کند. اگر
     ایندکس صفر را کندل اولِ سری بگیریم، خط روی سری ۲۴۰تایی ۱۲۰ کندل
     جابه‌جا کشیده می‌شود. این باگ واقعی بود و روی چارت سیگنال می‌رفت.
  ۲. **انباشتگی.** همان خط در اجراهای بعد باید *همان* خط شمرده شود و
     برخوردهایش جمع شود، نه اینکه هر بار خط تازه ساخته شود.
  ۳. **پاک نشدن.** خط شکسته یا کهنه وضعیتش عوض می‌شود، حذف نمی‌شود.
"""
from __future__ import annotations

import math
import pathlib
import random
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import levels_db as L                      # noqa: E402
from hamid import rule_ledger as RL                   # noqa: E402
from hamid import structure as st                     # noqa: E402

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


def series(n=320, seed=7, drift=0.0018, step=3_600_000):
    r = random.Random(seed)
    out, p = [], 100.0
    for i in range(n):
        p *= (1 + drift + math.sin(i / 11) * 0.004 + r.gauss(0, 0.0016))
        hi = p * (1 + abs(r.gauss(0, 0.002)))
        lo = p * (1 - abs(r.gauss(0, 0.002)))
        out.append({"t": 1_700_000_000_000 + i * step, "o": p,
                    "h": max(hi, p), "l": min(lo, p), "c": p, "v": 10})
    return out


print("── دیتابیس خطوط · دفتر پایداری قانون ──")

# همان پنجره‌ای که بقیهٔ آزمون از آن استفاده می‌کند — روی ۳۲۰ کندل این
# سریِ مصنوعی خط معتبری پیدا نمی‌شود و آن هم جواب درستی است، ولی آن‌وقت
# آزمونِ مبدأ چیزی برای سنجیدن ندارد.
cd = series()[:300]

# ── ۱. مبدأ زمانی ─────────────────────────────────────────────────────────
tl = st.trendline(cd)
check("خط روند پیدا شد", tl is not None)
if tl:
    check("مبدأ = کندل صفرِ پنجرهٔ برازش، نه کندل اول سری",
          tl.t0 == cd[len(cd) - 120]["t"])
    check("گام زمانی ذخیره شده", tl.step_ms == cd[1]["t"] - cd[0]["t"])
    v = tl.at_t(cd[-1]["t"])
    px = cd[-1]["c"]
    check(f"خط نزدیک قیمت می‌افتد نه صدها درصد دورتر ({abs(v-px)/px*100:.1f}٪)",
          v is not None and abs(v - px) / px < 0.35)
    # همان مقدار باید بدون پاس دادن cd هم بیاید
    check("at_t بدون cd هم کار می‌کند (گام از خودِ خط)",
          abs(tl.at_t(cd[-1]["t"]) - v) < 1e-9)
    # مقایسه با فرمول غلط قدیمی: باید تفاوت معنادار باشد
    old = tl.at((cd[-1]["t"] - cd[0]["t"]) / tl.step_ms)
    check("فرمول قدیمی واقعاً جواب دیگری می‌داد (باگ واقعی بود)",
          abs(old - v) > abs(v) * 0.01)

# ── ۲. انباشتگی ──────────────────────────────────────────────────────────
L.DB = pathlib.Path(tempfile.mkdtemp()) / "levels"
w = cd
j1 = L.update("TUSDT", "1h", w)
check("اجرای اول خط ذخیره کرد", j1 and len(j1["lines"]) == 1)
t1 = j1["lines"][0]["touches_total"]
j2 = L.update("TUSDT", "1h", w)
check("اجرای دوم خط تازه **نساخت** (تطبیق خورد)", len(j2["lines"]) == 1)
check("برخوردها انباشته شد", j2["lines"][0]["touches_total"] > t1)
check("شمار اجراهای مستقل بالا رفت", j2["lines"][0]["seen_runs"] == 2)
j3 = L.update("TUSDT", "1h", series()[5:305])
check("پنجرهٔ کمی جابه‌جا هم همان خط شمرده می‌شود",
      len(j3["lines"]) == 1 and j3["lines"][0]["seen_runs"] == 3)

# ── ۳. تأیید مستقل قبل از استفاده ────────────────────────────────────────
check("خطِ چنداجرایی به‌عنوان معتبرترین برگردانده می‌شود",
      L.best_line("TUSDT", "1h", w) is not None)
L.DB = pathlib.Path(tempfile.mkdtemp()) / "levels2"
L.update("TUSDT", "1h", w)
check("خطی که فقط یک بار دیده شده هنوز تأیید مستقل ندارد",
      L.best_line("TUSDT", "1h", w, min_runs=2) is None)

# ── ۴. رکورد ذخیره‌شده جای خط لحظه‌ای می‌نشیند ──────────────────────────
L.DB = pathlib.Path(tempfile.mkdtemp()) / "levels3"
L.update("TUSDT", "1h", w)
L.update("TUSDT", "1h", w)
rec = L.best_line("TUSDT", "1h", w)
adapted = L.as_trendline(rec)
check("رکورد به شکل Trendline درمی‌آید", hasattr(adapted, "at_t"))
check("و قیمتش با رکورد می‌خواند",
      abs(adapted.at_t(w[-1]["t"])
          - (rec["slope"] * ((w[-1]["t"] - rec["t0"]) / rec["step_ms"])
             + rec["intercept"])) < 1e-6)

# ── ۵. خط پاک نمی‌شود ────────────────────────────────────────────────────
j = L.load("TUSDT", "1h")
allowed = {"ACTIVE", "BROKEN", "FLIPPED", "HISTORICAL"}
check("هر خط یکی از چهار وضعیت مجاز را دارد",
      all(r.get("status") in allowed for r in j["lines"]))

# ── ۶. دفتر پایداری قانون ────────────────────────────────────────────────
hist = ([{"day": f"2026-08-{d:02d}", "strategy": "ibs",
          "condition": "داخل اردر بلاک", "verdict": "مثبت",
          "n": 700, "delta": 0.2, "ci": [0.09, 0.35]} for d in range(1, 8)]
        + [{"day": "2026-08-01", "strategy": "smc", "condition": "شانسی",
            "verdict": "مثبت", "n": 20, "delta": 0.4, "ci": [0.01, 0.8]}]
        + [{"day": f"2026-08-0{d}", "strategy": "smc", "condition": "متناقض",
            "verdict": "مثبت" if d % 2 else "منفی", "n": 50, "delta": 0.1,
            "ci": [0.01, 0.2]} for d in range(1, 7)])
j = RL.stable(window=10, min_days=5, hist=hist)
names = {r["condition"] for r in j["rules"]}
check("قانونِ تکرارشونده پایدار می‌شود", "داخل اردر بلاک" in names)
check("قانونِ یک‌روزه پایدار نمی‌شود", "شانسی" not in names)
check("قانونِ علامت‌متناقض حذف می‌شود، هرچقدر هم تکرار شده باشد",
      "متناقض" not in names)
r0 = [r for r in j["rules"] if r["condition"] == "داخل اردر بلاک"][0]
check("تعداد روزهای تأیید ثبت می‌شود", r0["days_confirmed"] == 7)
check("دلتای میانگین محاسبه می‌شود", abs(r0["mean_delta"] - 0.2) < 1e-6)
check("دفتر خالی کرش نمی‌کند", RL.stable(hist=[])["rules"] == [])

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون دیتابیس خطوط و پایداری گذشت")
