"""آزمون ماشین تصمیم از نتیجه‌ها — دستور حمید ۱۵ اوت.

چیزی که باید تضمین شود، ترتیبِ اهمیت:

  ۱. این ماژول **هیچ‌وقت** خودش قانون عوض نمی‌کند. خروجی پیشنهاد است.
  ۲. فاصلهٔ اطمینانِ صفرعرض هرگز به‌عنوان شواهد ارائه نمی‌شود — اولین
     اجرای واقعی CI=[0.15, 0.15] داد چون ۱۱۲ معامله دقیقاً روی نردبان
     تریل بسته شده بودند. عددی که شبیه شواهد است ولی نیست.
  ۳. رفتارِ «مشاهده‌ای» هرگز حکم نمی‌گیرد — پیشنهادش آزمایش است.
  ۴. آلفا بین پیشنهادها تقسیم می‌شود (بونفرونی).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import improve as im                       # noqa: E402

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


def tr(sym, r, mfe=None, bar=None, outcome="target"):
    w = {"stage": "practice"}
    if mfe is not None:
        w["mfe"] = mfe
        w["mfe_bar"] = bar if bar is not None else 3
    return {"sym": sym, "dir": "LONG", "R": r, "outcome": outcome, "why": w}


print("── ماشین تصمیم از نتیجه‌ها ──")

# ── ۱. طبقه‌بندی رفتار ─────────────────────────────────────────────────────
check("استاپ بعد از سود = استاپ تنگ",
      im.behaviour(tr("A", -1.0, mfe=0.8, outcome="stop")) == "stop_tight")
check("رسید به ۱R و پس داد = خروج زودهنگام",
      im.behaviour(tr("A", 0.15, mfe=1.6)) == "exit_early")
check("معطل ماند = چرخش",
      im.behaviour(tr("A", -1.0, mfe=0.2, bar=12, outcome="stop")) == "rotation")
check("سریع رسید = سالم",
      im.behaviour(tr("A", 1.5, mfe=1.5, bar=2)) == "clean")
check("بدون MFE هیچ ادعایی نمی‌شود", im.behaviour(tr("A", 1.0)) is None)

# ── ۲. گاردِ فاصلهٔ اطمینانِ صفرعرض ───────────────────────────────────────
rng = random.Random(1)
check("مقدار ثابت → فاصلهٔ اطمینان نمی‌دهد (شواهد قلابی نه)",
      im._boot_ci([0.15] * 40, 0.05, rng) is None)
ci = im._boot_ci([0.1, 0.5, -0.3, 1.2, 0.4, -0.8, 0.9, 0.2, 0.6, -0.1] * 4,
                 0.05, rng)
check("مقدار متغیر → فاصلهٔ اطمینان واقعی می‌دهد",
      ci is not None and ci[1] > ci[0])
check("نمونهٔ خیلی کم → هیچ", im._boot_ci([1.0, 2.0], 0.05, rng) is None)

# ── ۳. پروفایل رفتاری هر ارز ─────────────────────────────────────────────
rows = ([tr("HOTUSDT", -1.0, mfe=0.9, outcome="stop") for _ in range(12)]
        + [tr("HOTUSDT", 1.5, mfe=1.6, bar=2) for _ in range(10)]
        + [tr("THINUSDT", 1.0, mfe=1.1) for _ in range(3)])
prof = im.profile(rows, min_n=20)
check("ارز کم‌نمونه پروفایل نمی‌گیرد", "THINUSDT" not in prof)
check("ارز پرنمونه پروفایل می‌گیرد", "HOTUSDT" in prof)
check("سهم استاپ تنگ درست حساب می‌شود",
      abs(prof["HOTUSDT"]["stop_tight_pct"] - 100 * 12 / 22) < 0.2)
check("مجموع سهم‌ها ۱۰۰ می‌شود",
      abs(sum(prof["HOTUSDT"][f"{k}_pct"] for k in
              ("stop_tight", "exit_early", "rotation", "clean")) - 100) < 0.5)

# ── ۴. پیشنهادها ─────────────────────────────────────────────────────────
j = im.propose(rows=rows, min_n=20)
check("خروجی پیشنهاد است نه تغییر", "proposals" in j and "rule" in j)
check("قانون ۱۲ در خروجی نوشته شده", "دستور صریح حمید" in j["rule"])
p_st = [p for p in j["proposals"] if p["behaviour"] == "stop_tight"]
check("استاپ تنگِ پرتکرار پیشنهاد می‌سازد", len(p_st) == 1)
if p_st:
    check("پیشنهاد نمونه و فاصلهٔ اطمینان دارد",
          p_st[0]["n_with"] == 12 and "ci" in p_st[0])
    check("پیشنهاد وضعیت اعتبارسنجی دارد",
          p_st[0]["validation_status"] in ("BACKTESTED", "UNVERIFIED", "OBSERVED"))
    check("کارِ پیشنهادی به فارسی نوشته شده",
          "استاپ" in p_st[0]["proposed_action"])

# ── ۵. رفتار مشاهده‌ای هرگز حکم نمی‌گیرد ─────────────────────────────────
obs_rows = ([tr("GIVEUSDT", 0.15, mfe=1.6) for _ in range(14)]
            + [tr("GIVEUSDT", 1.5, mfe=1.5, bar=2) for _ in range(12)])
j2 = im.propose(rows=obs_rows, min_n=20)
ee = [p for p in j2["proposals"] if p["behaviour"] == "exit_early"]
check("پس‌دادن پرتکرار دیده می‌شود", len(ee) == 1)
if ee:
    check("ولی حکم نمی‌گیرد (مشاهده است نه آزمون)", ee[0]["decided"] is False)
    check("وضعیتش OBSERVED است", ee[0]["validation_status"] == "OBSERVED")
    check("و پیشنهادش یک آزمایش است، نه تغییر قانون",
          "بازپخش" in ee[0]["proposed_action"])
    check("متریکش پس‌دادن است نه R", ee[0]["metric"] == "giveback")
    check("پس‌دادن مثبت و معنادار گزارش شده", ee[0]["mean_r_with"] > 1.0)

# ── ۶. بونفرونی ──────────────────────────────────────────────────────────
check("آلفا بین پیشنهادها تقسیم شده",
      j2["alpha_adjusted"] <= j2["alpha"])
check("تعداد کاندید گزارش می‌شود", j2["candidates"] >= 1)

# ── ۷. دفتر خالی کرش نمی‌کند ─────────────────────────────────────────────
j3 = im.propose(rows=[], min_n=20)
check("دفتر خالی → صفر پیشنهاد، بدون کرش", j3["proposals"] == [])

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون ماشین تصمیم گذشت")
