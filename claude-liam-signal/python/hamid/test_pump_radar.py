"""آزمون آفلاین رادار پامپ — بدون شبکه، روی دادهٔ ساختگی و ردیف‌های ضبط‌شده.

    python3 -m hamid.test_pump_radar
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import pump_radar as pr                            # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


# ── پارس تیکر بیتیونیکس، با همان شکل‌هایی که پنل مشاهده کرده ───────────────
rows = [
    {"symbol": "BTCUSDT", "lastPrice": "63000", "priceChangePercent": "2.5", "baseVol": "42.8"},
    {"symbol": "TUTUSDT", "last": "0.19", "change": "0.31", "quoteVol": "9000"},
    {"symbol": "BTCUSDT_UMCBL", "lastPrice": "1"},              # پسوند غیر USDT — حذف
    {"symbol": "XUSDT", "lastPrice": "0", "priceChangePercent": "9"},   # قیمت صفر — حذف
    {"symbol": "YUSDT", "lastPrice": "1", "priceChangePercent": "9999"},  # بی‌معنا — حذف
]
g = pr._parse_bitunix(rows)
check("پارس بیتیونیکس: فقط ردیف‌های سالم USDT", [x["symbol"] for x in g] == ["BTCUSDT", "TUTUSDT"])
check("priceChangePercent مستقیم خوانده شد", g[0]["change_pct"] == 2.5)
check("change کسری در ۱۰۰ ضرب شد", g[1]["change_pct"] == 31.0)

# ── همبستگی ────────────────────────────────────────────────────────────────
a = [math.sin(i / 5) + 2 for i in range(48)]
check("همبستگی سری با خودش = ۱", abs(pr._corr(a, a) - 1) < 1e-9)
check("همبستگی سری با قرینه = -۱", abs(pr._corr(a, [4 - x for x in a]) + 1) < 1e-9)

# ── شبیه‌ترین پامپ قبلی ────────────────────────────────────────────────────
random.seed(7)


def bar(t, c, v=100.0):
    return {"t": t, "o": c, "h": c * 1.004, "l": c * 0.996, "c": c, "v": v}


cd = []
px = 1.0
for i in range(400):
    px *= 1 + random.gauss(0, 0.004)
    cd.append(bar(i * 3600_000, px))
# یک پامپ واقعی در i=200 بساز: ۴ کندل +۱۵٪ با حجم ۱۰ برابر
for k in range(4):
    i = 197 + k
    cd[i] = bar(i * 3600_000, cd[196]["c"] * (1 + 0.05 * (k + 1)), v=1000.0)
for i in range(201, 400):
    cd[i] = bar(i * 3600_000, cd[200]["c"] * (1 + random.gauss(0, 0.003)))
eps = pr.pumps(cd)
check("پامپ ساختگی پیدا شد", len(eps) >= 1 and any(195 <= e["i"] <= 203 for e in eps))
m = pr.best_match(cd, eps)
check("شبیه‌ترین پامپ برمی‌گردد", m is not None and -100 <= m["corr_pct"] <= 100)

# ── نقش خوشه‌ای ────────────────────────────────────────────────────────────
rel = {"LEADUSDT": {"n": 3, "pre_24h_pct": 30.0, "post_24h_pct": 2.0},
       "TAILUSDT": {"n": 3, "pre_24h_pct": 1.0, "post_24h_pct": 12.0}}
role, leaders, followers = pr.role_of(rel)
check("سردسته‌ی قوی قبلش → این ارز دنباله‌رو", role == "دنباله‌رو" and leaders[0]["symbol"] == "LEADUSDT")
rel2 = {"TAILUSDT": {"n": 3, "pre_24h_pct": 1.0, "post_24h_pct": 15.0}}
role2, _, f2 = pr.role_of(rel2)
check("فقط دنباله‌رو دارد → خودش سردسته", role2 == "سردسته" and f2[0]["symbol"] == "TAILUSDT")

# ── پیشنهاد و دلایلش ───────────────────────────────────────────────────────
blocks = [
    {"symbol": "AUSDT", "price": 1.0, "role": "دنباله‌رو",
     "leaders": [{"symbol": "LEADUSDT", "pre_24h_pct": 30.0}], "followers": [],
     "pumps": [1, 2, 3, 4], "match": {"corr_pct": 80, "then_24h_pct": 20.0},
     "now": {"rsi_1h": 45.0}, "alarm": {"entry": 0.99, "sl": 0.95}},
    {"symbol": "HOTUSDT", "price": 2.0, "role": "سردسته", "leaders": [], "followers": [],
     "pumps": [1], "match": None,
     "now": {"rsi_1h": 88.0}, "alarm": {"entry": 1.6, "sl": 1.5}},
    {"symbol": "NOENTRYUSDT", "price": 3.0, "role": "سردسته", "leaders": [], "followers": [],
     "pumps": [], "match": None, "now": {"rsi_1h": 50.0}, "alarm": None},
]
picks = pr.recommend(blocks)
check("بدون نقطهٔ ورود پیشنهاد نمی‌شود", all(p["symbol"] != "NOENTRYUSDT" for p in picks))
check("دنباله‌روی نزدیک‌به‌ورود بالاتر از ارزِ اشباع", picks[0]["symbol"] == "AUSDT")
check("هر امتیاز دلیل نوشته دارد", all(p["reasons"] for p in picks))
check("ارز اشباع‌خرید امتیاز منفی خورد", next(p for p in picks if p["symbol"] == "HOTUSDT")["score"] < picks[0]["score"])

# ── متن تلگرام ─────────────────────────────────────────────────────────────
msg = pr.tg_message("بیتیونیکس (فیوچرز)", picks[:1], blocks)
check("سرتیتر پنل + گزینه‌های پامپ", "حمید کلود مکس پنل" in msg and "گزینه‌های پامپ" in msg)
check("دلایل داخل پیام‌اند", "دنباله‌رو" in msg and "ورود" in msg)

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های رادار پامپ گذشتند")
