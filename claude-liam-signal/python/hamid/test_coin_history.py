"""آزمون جدول تاریخچهٔ ارز — دستور حمید ۱۶ اوت.

مهم‌ترین چیزی که باید تضمین شود: **حرکت مستقل از سواری بازار جدا شود.**
ارزی که ۸٪ رفته وقتی کل بازار ۷٪ رفته، پامپ نکرده. بدون این تفکیک، جدول
پر می‌شود از رویدادهایی که فقط بازار بودند و تاریخچه بی‌ارزش می‌شود.
"""
from __future__ import annotations

import pathlib
import random
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import coin_history as CH                  # noqa: E402

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


def mk(n, seed, runs):
    r = random.Random(seed)
    per = {}
    for st, (ln, pc) in runs.items():
        for k in range(ln):
            per[st + k] = pc
    cd, p = [], 1.0
    for i in range(n):
        mv = per.get(i, 0.0)
        o = p
        p *= (1 + mv + r.gauss(0, 0.0010))
        cd.append({"t": 1_700_000_000_000 + i * 900_000, "o": o,
                   "h": max(o, p) * 1.001, "l": min(o, p) * 0.999, "c": p,
                   "v": (400 if mv else 100) + r.random() * 20})
    return cd


print("── جدول تاریخچهٔ ارز ──")
CH.DB = pathlib.Path(tempfile.mkdtemp()) / "coins"

alt = mk(320, 3, {50: (8, 0.009), 140: (8, 0.008), 220: (8, -0.009)})
btc = mk(320, 9, {140: (8, 0.007)})
j = CH.update("TESTUSDT", alt, btc, [])

check("رویدادها پیدا شدند", len(j["events"]) == 3)
check("پامپ و دامپ از هم جدا شمرده می‌شوند",
      j["summary"]["pumps"] == 2 and j["summary"]["dumps"] == 1)
ev = j["events"]
check("قیمت بیت‌کوین همان لحظه ثبت شد",
      all(e["btc_price"] is not None for e in ev))
check("حرکت بیت‌کوین در همان پنجره ثبت شد",
      all(e["btc_move_pct"] is not None for e in ev))
check("حجم نسبی ثبت شد (پامپ بی‌حجم پامپ نیست)",
      all((e["vol_x"] or 0) > 1.5 for e in ev))
check("پس‌دادن ثبت شد", all(e["retrace_pct"] is not None for e in ev))

solo = [e for e in ev if abs(e["move_pct"]) > abs(e["btc_move_pct"]) * 2]
check("حرکتِ همراه بازار مستقل شمرده نمی‌شود", len(solo) == 2)
check("سهم مستقل در چکیده درست است",
      abs(j["summary"]["solo_pct"] - 66.7) < 0.5)

n1 = len(j["events"])
j2 = CH.update("TESTUSDT", alt, btc, [])
check("اجرای دوم روی همان داده تکراری نمی‌سازد", len(j2["events"]) == n1)
check("مرز پیشروی ثبت شد", j2["frontier"] == alt[-1]["t"])
check("بازهٔ پوشش ثبت شد (تا با «کل عمر ارز» اشتباه نشود)",
      j2["covers_from"] == alt[0]["t"])
# اجرای دوم روی دادهٔ تکراری عمداً کارِ بی‌فایده نمی‌کند و زود برمی‌گردد،
# پس شمارندهٔ اجرا هم بالا نمی‌رود. این درست است: «اجرا» یعنی پردازشِ
# کندل تازه، نه صرفاً صدا زدن تابع.
check("اجرای بی‌فایده کار تازه نمی‌کند (زود برمی‌گردد)", j2["runs"] == 1)

more = alt + mk(40, 11, {10: (8, 0.010)})
for i, c in enumerate(more[len(alt):]):
    c["t"] = alt[-1]["t"] + (i + 1) * 900_000
j3 = CH.update("TESTUSDT", more, btc, [])
check("کندل تازه رویداد تازه اضافه می‌کند", len(j3["events"]) > n1)
check("و شمارندهٔ اجرا فقط با کارِ واقعی بالا می‌رود", j3["runs"] == 2)

b = CH.brief("TESTUSDT")
check("چکیدهٔ فارسی برای ایجنت ساخته می‌شود",
      "نوسان ثبت‌شده" in b and "مستقل از بیت‌کوین" in b)
check("ارز بدون تاریخچه صریح می‌گوید", "ثبت نشده" in CH.brief("NOPEUSDT"))

check("سری خالی کرش نمی‌کند", CH.update("EMPTYUSDT", [], btc, []) is not None)
check("بدون بیت‌کوین هم کار می‌کند (ستون بستر خالی می‌ماند)",
      CH.find_events(alt, None, None) != [])
check("سری کوتاه رویدادی نمی‌سازد", CH.find_events(alt[:5], btc, []) == [])
check("بازار آرام رویداد نمی‌سازد", CH.find_events(mk(200, 5, {}), btc, []) == [])

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون تاریخچهٔ ارز گذشت")
