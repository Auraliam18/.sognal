"""آزمون اولویت صرافی — بدون شبکه، با پاسخ‌های تزریقی.

کانتینر به بیت‌یونیکس/XT/KCEX دسترسی ندارد (پراکسی ۴۰۳ می‌دهد)، پس شکل
واقعی پاسخ این‌جا قابل تأیید نیست. برای همین پارس عمداً شکل‌ناشناس است و
این آزمون همان را می‌سنجد: هر شکلی که نماد داشته باشد باید کار کند، و هر
پاسخی که نماد کافی نداشته باشد باید **رد** شود نه این‌که نصفه قبول شود.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import venues                              # noqa: E402

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


print("── اولویت صرافی (بیت‌یونیکس / XT / KCEX) ──")

# ── ۱. برداشت نماد از شکل‌های مختلف ────────────────────────────────────────
flat = json.dumps([{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}])
nested = json.dumps({"code": 0, "data": {"list": [
    {"s": "SOL_USDT", "p": "1"}, {"s": "ARB-USDT", "p": "2"}]}})
perp = json.dumps([{"symbol": "PEPEUSDT_PERP"}, {"symbol": "WIF/USDT"}])

check("شکل تخت پارس می‌شود", venues.harvest(flat) == {"BTCUSDT", "ETHUSDT"})
check("شکل تودرتو با جداکنندهٔ _ و - پارس می‌شود",
      venues.harvest(nested) == {"SOLUSDT", "ARBUSDT"})
check("پسوند PERP و جداکنندهٔ / پارس می‌شود",
      venues.harvest(perp) == {"PEPEUSDT", "WIFUSDT"})
check("بدنهٔ خالی نماد نمی‌سازد", venues.harvest("") == set())
check("متن بدون نماد چیزی نمی‌سازد",
      venues.harvest('{"error":"forbidden","code":403}') == set())

# قیمت‌ها و اعداد نباید تصادفاً نماد شوند — همان دلیلی که پارس این‌جا امن است
noise = json.dumps({"price": "12345.678", "vol": 9999, "t": 1755200000000})
check("اعداد/قیمت‌ها نماد تولید نمی‌کنند", venues.harvest(noise) == set())


# ── ۲. گاردِ پاسخ ناقص ─────────────────────────────────────────────────────
def _fake(mapping):
    def f(url):
        if url in mapping:
            v = mapping[url]
            if isinstance(v, Exception):
                raise v
            return v
        raise OSError("no route")
    return f


big = json.dumps([{"symbol": f"S{i}USDT"} for i in range(50)])
small = json.dumps([{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}])

u_bit = venues.ENDPOINTS["bitunix"][0]
u_bit2 = venues.ENDPOINTS["bitunix"][1]

# کش را برای آزمون از مسیر واقعی جدا کن — نباید فایل تولید را دست بزند
real_cache = venues.CACHE
venues.CACHE = Path("/tmp/claude-0/-home-user--sognal/venues-test.json")
venues.CACHE.parent.mkdir(parents=True, exist_ok=True)
if venues.CACHE.exists():
    venues.CACHE.unlink()
check("آزمون به کش تولید دست نمی‌زند", venues.CACHE != real_cache)

ls = venues.listings(force=True, fetch=_fake({u_bit: small, u_bit2: big}))
check("پاسخ کم‌نماد رد می‌شود و نقطهٔ بعدی امتحان می‌شود",
      len(ls["bitunix"]["symbols"]) == 50 and ls["bitunix"]["url"] == u_bit2)
check("صرافی بی‌پاسخ خطایش را ثبت می‌کند و خالی می‌ماند",
      ls["xt"]["symbols"] == [] and ls["xt"].get("error"))

# ── ۳. کش کهنه از هیچ بهتر است ─────────────────────────────────────────────
ls2 = venues.listings(force=True, fetch=_fake({}))          # هیچ‌کس جواب نمی‌دهد
check("فهرست کهنه نگه داشته می‌شود وقتی صرافی نمی‌آید",
      len(ls2["bitunix"]["symbols"]) == 50 and ls2["bitunix"].get("stale"))

# ── ۴. ترتیب‌دهی ───────────────────────────────────────────────────────────
idx = {"AUSDT": ["bitunix"], "CUSDT": ["xt", "kcex"]}
order, note = venues.prioritize(["AUSDT", "BUSDT", "CUSDT", "DUSDT"], idx=idx)
check("نماد قابل‌معامله جلو می‌افتد", order[:2] == ["AUSDT", "CUSDT"])
check("هیچ نمادی حذف نمی‌شود (تحقیق/لید-لگ کور نمی‌شود)",
      sorted(order) == ["AUSDT", "BUSDT", "CUSDT", "DUSDT"])
check("ترتیب حجمی درون هر گروه حفظ می‌شود", order[2:] == ["BUSDT", "DUSDT"])
check("گزارش شمارش درست می‌دهد", "2 از 4" in note)

order0, note0 = venues.prioritize(["AUSDT", "BUSDT"], idx={})
check("صرافی نیامد → ترتیب دست‌نخورده و صادقانه گزارش می‌شود",
      order0 == ["AUSDT", "BUSDT"] and "جواب ندادند" in note0)

check("keep_all=False فقط قابل‌معامله‌ها را می‌دهد",
      venues.prioritize(["AUSDT", "BUSDT"], idx=idx, keep_all=False)[0] == ["AUSDT"])

# ── ۵. برچسب صرافی برای کپشن ───────────────────────────────────────────────
check("برچسب فارسی صرافی ساخته می‌شود",
      venues.where("CUSDT", idx=idx) == "XT · KCEX")
check("نماد بیرون از صرافی‌های هدف برچسب ندارد",
      venues.where("ZUSDT", idx=idx) == "")

# ── ۶. index از listings ───────────────────────────────────────────────────
i2 = venues.index({"bitunix": {"symbols": ["XUSDT"]},
                   "xt": {"symbols": ["XUSDT", "YUSDT"]},
                   "kcex": {"symbols": []}})
check("index صرافی‌ها را جمع می‌کند", i2 == {"XUSDT": ["bitunix", "xt"],
                                              "YUSDT": ["xt"]})

if venues.CACHE.exists():
    venues.CACHE.unlink()

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون اولویت صرافی گذشت")
