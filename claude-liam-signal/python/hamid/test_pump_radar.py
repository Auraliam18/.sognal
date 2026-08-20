"""آزمون آفلاین رادار پامپ — بدون شبکه، روی دادهٔ ساختگی و ردیف‌های ضبط‌شده.

    python3 -m hamid.test_pump_radar
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import pump_radar as pr                            # noqa: E402

import subprocess as _sp                              # noqa: E402
_REPO = str(Path(__file__).resolve().parents[3])


def _brain_status():
    return _sp.run(["git", "-C", _REPO, "status", "--short", "brain"],
                   capture_output=True, text=True).stdout


_BRAIN_BEFORE = _brain_status()

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

# محاسبه از «آخرین ÷ باز» وقتی فیلد باز هست — بدون ابهام مقیاس
open_rows = [{"symbol": "OPNUSDT", "lastPrice": "1.2", "open": "1.0"}]
go = pr._parse_bitunix(open_rows)
check("تغییر از last/open حساب شد", go and go[0]["change_pct"] == 20.0)

# تشخیص مقیاس: ۲۵ ردیف که همه priceChangePercent کسری دارند (بیشینه 0.27)
frac_rows = [{"symbol": f"C{i}USDT", "lastPrice": "1",
              "priceChangePercent": str(0.27 - i * 0.01)} for i in range(25)]
gf = pr._parse_bitunix(frac_rows)
check("مقیاس کسری خودکار ×۱۰۰ شد", max(x["change_pct"] for x in gf) == 27.0)
mixed = [{"symbol": f"D{i}USDT", "lastPrice": "1",
          "priceChangePercent": str(3.0 if i == 0 else 0.2)} for i in range(25)]
gm = pr._parse_bitunix(mixed)
check("وقتی درصد واقعی است دست نمی‌خورد", max(x["change_pct"] for x in gm) == 3.0)

# ── پارس توبیت (شکل واقعی از لاگ زنده: pcp کسری + qv) ─────────────────────
tb_rows = ([{"s": f"T{i}USDT", "c": "1", "qv": "500000", "pcp": str(0.01 * i)}
            for i in range(24)]
           + [{"s": "JUNKUSDT", "c": "1", "qv": "5000", "pcp": "29.15"},     # بی‌عمق
              {"s": "WILDUSDT", "c": "1", "qv": "900000", "pcp": "0.31"}])
gt = pr._parse_toobit(tb_rows)
check("pcp کسری ×۱۰۰ شد", any(x["symbol"] == "WILDUSDT" and x["change_pct"] == 31.0 for x in gt))
check("جفت کم‌حجم حذف شد (درس +۲۹۰۰٪)", all(x["symbol"] != "JUNKUSDT" for x in gt))
tb_pct = [{"s": f"P{i}USDT", "c": "1", "qv": "500000", "pcp": str(2.0 + i)}
          for i in range(24)]
gp = pr._parse_toobit(tb_pct)
check("وقتی pcp خودش درصد است دست نمی‌خورد", max(x["change_pct"] for x in gp) == 25.0)

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
     "leaders": [{"symbol": "LEADUSDT", "pre_24h_pct": 30.0, "n": 3}], "followers": [],
     "pumps": [1, 2, 3, 4], "match": {"corr_pct": 80, "then_24h_pct": 20.0},
     "now": {"rsi_1h": 45.0}, "alarm": {"entry": 0.99, "sl": 0.95}},
    {"symbol": "HOTUSDT", "price": 2.0, "role": "دنباله‌رو",
     "leaders": [{"symbol": "LEADUSDT", "pre_24h_pct": 20.0, "n": 2}], "followers": [],
     "pumps": [1], "match": None,
     "now": {"rsi_1h": 88.0}, "alarm": {"entry": 1.6, "sl": 1.5}},
    {"symbol": "LONEUSDT", "price": 2.0, "role": "سردسته", "leaders": [], "followers": [],
     "pumps": [1, 2, 3], "match": None,
     "now": {"rsi_1h": 40.0}, "alarm": {"entry": 1.9, "sl": 1.8}},
    {"symbol": "NOENTRYUSDT", "price": 3.0, "role": "سردسته", "leaders": [], "followers": [],
     "pumps": [], "match": None, "now": {"rsi_1h": 50.0}, "alarm": None},
]
picks = pr.recommend(blocks)
check("بدون نقطهٔ ورود پیشنهاد نمی‌شود", all(p["symbol"] != "NOENTRYUSDT" for p in picks))
check("دنباله‌روی نزدیک‌به‌ورود بالاتر از ارزِ اشباع", picks[0]["symbol"] == "AUSDT")
check("هر امتیاز دلیل نوشته دارد", all(p["reasons"] for p in picks))
check("ارز اشباع‌خرید امتیاز منفی خورد", next(p for p in picks if p["symbol"] == "HOTUSDT")["score"] < picks[0]["score"])
# متن رد ۱۴ اوت عوض شد (مطالعهٔ رویدادی k/N راه سومِ اثبات رابطه شد) —
# آزمون به‌جای متن دقیق، خودِ رفتار را می‌سنجد.
check("بی‌رابطهٔ خوشه‌ای پیشنهاد نمی‌شود (قانون سخت)",
      all(p["symbol"] != "LONEUSDT" for p in picks)
      and "رابطهٔ" in blocks[2].get("skipped", "")
      and "پیشنهاد نمی‌شود" in blocks[2].get("skipped", ""))

# ── قانون حمید: پامپ‌خورده سیگنال نیست ────────────────────────────────────
late30 = {"symbol": "L30USDT", "price": 1.0, "role": "دنباله‌رو",
          "leaders": [{"symbol": "XUSDT", "pre_24h_pct": 30.0, "n": 3}], "followers": [],
          "pumps": [1, 2, 3], "match": None, "change_30m_pct": 12.0, "change_24h_pct": 5.0,
          "now": {"rsi_1h": 50.0}, "alarm": {"entry": 0.99, "sl": 0.95}}
late24 = {**late30, "symbol": "L24USDT", "change_30m_pct": 2.0, "change_24h_pct": 40.0}
ok_coin = {**late30, "symbol": "OKUSDT", "change_30m_pct": 2.0, "change_24h_pct": 4.0}
p2 = pr.recommend([late30, late24, ok_coin])
check("۱۰٪+ در ۳۰ دقیقه → حذف از پیشنهاد", all(p["symbol"] != "L30USDT" for p in p2))
check("۱۰٪+ در ۲۴ ساعت → حذف از پیشنهاد", all(p["symbol"] != "L24USDT" for p in p2))
check("عضو نپریدهٔ خوشه می‌ماند", p2 and p2[0]["symbol"] == "OKUSDT")
# متن دلیلِ رد در ۱۴ اوت عوض شد (آستانه از ۱۰٪ به «هنوز نپریده» سفت شد).
# باز هم درسِ همان روز: آزمون به متن دقیق نچسبد — رفتار را بسنجد؛ این‌جا
# «دلیلی ثبت شد و درصدِ واقعی داخلش هست»، نه یک جملهٔ خاص.
check("دلیل حذف روی خود ارز ثبت شد",
      late30.get("skipped") and "12.0" in late30["skipped"])

# سردستهٔ در حال پریدن → امتیاز اضافه برای عضو نپریده
p3 = pr.recommend([dict(ok_coin)], hot={"XUSDT"})
check("سردستهٔ شعله‌ور امتیاز و دلیل اضافه داد",
      p3 and p3[0]["score"] > p2[0]["score"] and any("در حال پریدن" in w for w in p3[0]["reasons"]))

# ── شعله‌گیری ۳۰ دقیقه‌ای (زودتر از تیکر ۲۴ساعته) ─────────────────────────
class FakeKc:
    def get(self, s, tf, n):
        base = [{"t": i, "o": 1, "h": 1, "l": 1, "c": 1.0, "v": 100.0} for i in range(38)]
        if s == "IGNUSDT":
            base += [{"t": 38, "o": 1, "h": 1.06, "l": 1, "c": 1.03, "v": 900.0},
                     {"t": 39, "o": 1.03, "h": 1.08, "l": 1.02, "c": 1.06, "v": 900.0}]
        else:
            base += [{"t": 38, "o": 1, "h": 1, "l": 1, "c": 1.0, "v": 100.0},
                     {"t": 39, "o": 1, "h": 1, "l": 1, "c": 1.0, "v": 100.0}]
        return base
em = pr.early_movers(FakeKc(), ["IGNUSDT", "FLATUSDT"])
check("شعله‌گیری با حجم پیدا شد و ارز آرام نه",
      [x["symbol"] for x in em] == ["IGNUSDT"] and em[0]["change_pct"] >= 4)


class Spike15Kc(FakeKc):
    """یک کندل ۱۵دقیقه‌ای +۶٪ بدون جهش حجم — ماشهٔ صریح حمید."""
    def get(self, s, tf, n):
        base = [{"t": i, "o": 1, "h": 1, "l": 1, "c": 1.0, "v": 100.0} for i in range(39)]
        if s == "SPKUSDT":
            base.append({"t": 39, "o": 1.0, "h": 1.065, "l": 1.0, "c": 1.06, "v": 110.0})
        else:
            base.append({"t": 39, "o": 1, "h": 1, "l": 1, "c": 1.0, "v": 100.0})
        return base


em15 = pr.early_movers(Spike15Kc(), ["SPKUSDT", "FLATUSDT"])
check("کندل ۱۵د ≥۵٪ به‌تنهایی ماشه است (بدون شرط حجم)",
      [x["symbol"] for x in em15] == ["SPKUSDT"] and em15[0]["chg_15m"] >= 5)

# ── معاینهٔ چارت: الانِ دنباله‌رو در برابر قبل از واکنش‌های قبلی‌اش ───────
H = 3600_000


class ReactKc:
    """دنباله‌رویی که چارت ۲۴ساعت اخیرش عین چارتِ قبل از واکنش قبلی است."""
    def get(self, s, tf, n):
        pat = [1 + 0.1 * math.sin(i / 3) for i in range(24)]
        cs = [1.0] * 300
        cs[100:124] = pat          # پنجرهٔ قبل از واکنشِ i=124
        cs[276:300] = pat          # همین الگو، الان
        return [bar(i * H, c) for i, c in enumerate(cs)]


sim = pr.react_similarity(ReactKc(), "FOLUSDT",
                          fol_eps=[{"t": 124 * H}],
                          leader_eps=[{"t": 120 * H}])
check("الگوی تکراری → شباهت نزدیک ۱۰۰٪", sim is not None and sim["corr_pct"] >= 95)
check("تعداد واکنش‌های شمرده درست است", sim and sim["n_reacts"] == 1)
sim_none = pr.react_similarity(ReactKc(), "FOLUSDT",
                               fol_eps=[{"t": 124 * H}],
                               leader_eps=[{"t": 200 * H}])   # واکنش قبل از سردسته
check("واکنشِ بی‌ربط به سردسته شمرده نمی‌شود", sim_none is None)

# ── آینهٔ ریزش: BTC ریخت → دنباله‌روهای تاریخی ریزش ───────────────────────


class CrashKc:
    def get(self, s, tf, n):
        cs = [100.0] * 100
        if s == "BTCUSDT":
            for i in (30, 50, 70, 99):
                cs[i] = 97.0       # -۳٪ در آن ساعت؛ آخری = ریزش الان
        elif s == "PANICUSDT":
            for i in (31, 51, 71):
                cs[i] = 96.0       # یک ساعت بعد از هر ریزش BTC، -۴٪
        return [bar(i * H, c) for i, c in enumerate(cs)]


cw = pr.crash_watch(CrashKc(), ["BTCUSDT", "PANICUSDT", "CALMUSDT"])
check("ریزش BTC تشخیص داده شد", cw is not None and cw["btc_1h"] <= -2)
check("دنباله‌روی تاریخی ریزش پیدا شد",
      cw and [f["symbol"] for f in cw["followers"]] == ["PANICUSDT"]
      and cw["followers"][0]["hit_pct"] == 100)
check("ارز آرام در فهرست هشدار نیست",
      cw and all(f["symbol"] != "CALMUSDT" for f in cw["followers"]))


class NoCrashKc(CrashKc):
    def get(self, s, tf, n):
        rows = super().get(s, tf, n)
        if s == "BTCUSDT":
            rows[-1] = bar(99 * H, 100.0)   # ساعت آخر آرام
        return rows


check("بدون ریزش الان، هشداری نیست",
      pr.crash_watch(NoCrashKc(), ["BTCUSDT", "PANICUSDT"]) is None)

# ── لگ-کورولیشن — همبستگی با تأخیر، معنی واقعی «همبستگی» از زبان حمید ─────
from hamid import lagcorr                             # noqa: E402
random.seed(11)
lead_rets = [random.gauss(0, 0.01) for _ in range(500)]
LAG = 3


def _mkcd(rets, t0=0, bar=3600_000):
    cd, p = [], 100.0
    for i, r in enumerate(rets):
        p *= 1 + r
        cd.append({"t": t0 + i * bar, "o": p / (1 + r), "h": p, "l": p, "c": p, "v": 1.0})
    return cd


lead_cd = _mkcd(lead_rets)
fol_rets = [0.0] * LAG + [r * 0.8 + random.gauss(0, 0.004) for r in lead_rets[:-LAG]]
fol_cd = _mkcd(fol_rets)
noise_cd = _mkcd([random.gauss(0, 0.01) for _ in range(500)])


class LagKc:
    def get(self, s, tf, n):
        if tf != "1h":
            return []
        return {"LEADUSDT": lead_cd, "FOLUSDT": fol_cd, "NOISEUSDT": noise_cd}.get(s, [])


lf = lagcorr.followers_of(LagKc(), "LEADUSDT", ["FOLUSDT", "NOISEUSDT", "LEADUSDT"])
check("دنباله‌روی ساختگی با تأخیر ۳ کندل پیدا شد",
      lf and lf[0]["symbol"] == "FOLUSDT" and lf[0]["best"]["lag_bars"] == LAG
      and lf[0]["best"]["r"] >= 0.5)
check("نویز مستقل رابطه اعلام نمی‌شود", all(x["symbol"] != "NOISEUSDT" for x in lf))
# جهت معکوس: اگر «دنباله‌رو» جلوتر حرکت کند، دنباله‌رو نیست
rev = lagcorr.follow_score(fol_cd, lead_cd, "1h", 12)
check("رابطهٔ معکوس (خودش سردسته) رد می‌شود", rev is None)
check("جملهٔ فارسی دلیل ساخته می‌شود",
      "لگ-کورولیشن" in lagcorr.reason_fa("LEADUSDT", lf[0]))
# ۴ساعته: دنباله‌رو با تأخیر ۸ کندل ۱س (=۲ کندل ۴س) — از ۱س ساخته می‌شود
LAG8 = 8
fol8_rets = [0.0] * LAG8 + [r * 0.8 + random.gauss(0, 0.002) for r in lead_rets[:-LAG8]]
fol8_cd = _mkcd(fol8_rets)


class Lag4hKc:
    def get(self, s, tf, n):
        if tf == "1h":
            return {"LEADUSDT": lead_cd, "FOL8USDT": fol8_cd}.get(s, [])
        return []


lf4 = lagcorr.followers_of(Lag4hKc(), "LEADUSDT", ["FOL8USDT"])
check("لگ-کورولیشن ۴ساعته هم می‌بیند (تأخیر ۲ کندل ۴س)",
      lf4 and "4h" in lf4[0]["evidence"]
      and lf4[0]["evidence"]["4h"]["lag_bars"] == 2)
check("چند-تایم‌فریمی شمرده می‌شود (n_tf)", lf4[0]["n_tf"] >= 2)

# ── واکنش-بازار: BTC ریخت، این ارز طبق سابقه چه می‌کند؟ (قانون حمید) ──────
# سری آرام (σ=۰.۳٪) تا تنها «حرکت بزرگ»، ریزش تزریقی -۳٪ باشد — سری
# پرنوسان قبلی خودش حرکت‌های ±۳٪ تصادفی داشت و تست را شکننده می‌کرد
random.seed(23)
mr_lead = [random.gauss(0, 0.003) for _ in range(500)]
mr_lead[400] = -0.03          # ریزش بزرگ قبلی BTC
mr_lead[-1] = -0.02           # ریزش جاری
mr_btc = _mkcd(mr_lead)
random.seed(24)
mr_fol = _mkcd([0.0] * LAG + [r * 0.8 + random.gauss(0, 0.001)
                              for r in mr_lead[:-LAG]])
mr = lagcorr.market_reaction(mr_btc, mr_fol)
check("حرکت جاری BTC درست خوانده شد", mr and abs(mr["btc_1h_pct"] - (-2.0)) < 0.1)
check("رابطهٔ لگ-کورولیشنی BTC→ارز پیدا شد",
      mr and mr["follow"] and mr["follow"]["lag_bars"] == LAG)
check("در ریزش بزرگ قبلی BTC، ریزش ارز هم ثبت شد",
      mr and mr["last_move"] and mr["last_move"]["btc_pct"] <= -2.5
      and mr["last_move"]["sym_pct"] < -1.0)
rfa = lagcorr.reaction_fa("LTCUSDT", mr)
check("جملهٔ واکنش فارسی و عددی است", "BTC الان" in rfa and "حرکت بزرگ قبلی" in rfa)

# پیک فقط-لگ‌کورولیشنی از قانون سخت خوشه رد می‌شود
lc_block = {"symbol": "LCUSDT", "price": 1.0, "role": "نامشخص", "leaders": [],
            "followers": [], "pumps": [], "match": None,
            "lag_corr_leaders": [{"symbol": "LEADUSDT", "both_tf": True,
                                  "best": {"r": 0.31, "lag_h": 3.0, "n": 490, "tf": "1h"},
                                  "reason": "لگ-کورولیشن با LEADUSDT: r=+0.31"}],
            "now": {"rsi_1h": 50.0}, "alarm": {"entry": 0.99, "sl": 0.95}}
plc = pr.recommend([dict(lc_block)])
check("لگ-کورولیشن قوی به‌تنهایی نامزدی می‌سازد",
      plc and plc[0]["symbol"] == "LCUSDT"
      and any("لگ-کورولیشن" in w for w in plc[0]["reasons"]))
no_ev = {**dict(lc_block), "symbol": "NOEVUSDT", "lag_corr_leaders": []}
pno = pr.recommend([no_ev])
check("بدون هیچ‌کدام از دو اثبات، پیشنهاد نمی‌شود", not pno)

# ── دفتر ماندگار تاریخچهٔ پامپ‌ها ──────────────────────────────────────────
import json                                           # noqa: E402
import tempfile                                       # noqa: E402
pr.HIST = Path(tempfile.mkdtemp()) / "pump-history.json"
hist_blocks = [
    {"symbol": "LEADUSDT", "pumps": [{"i": 50, "t": 100 * H, "ret_4h_pct": 18.0, "vol_z": 4.1},
                                     {"i": 90, "t": 200 * H, "ret_4h_pct": 25.0, "vol_z": 5.0}],
     "followers": [{"symbol": "FOLUSDT", "n": 3}], "leaders": []},
    {"symbol": "FOLUSDT", "pumps": [{"i": 53, "t": 103 * H, "ret_4h_pct": 9.0, "vol_z": 3.0}],
     "followers": [], "leaders": [{"symbol": "LEADUSDT", "n": 3}]},
]
n1, fresh1 = pr.update_history(hist_blocks)
check("رخدادها ثبت شدند", n1 == 3)
check("رخدادهای تازه برای گزارش به ایجنت برگشتند",
      len(fresh1) == 3 and all(s in ("LEADUSDT", "FOLUSDT") for s, _ in fresh1))
led = json.loads(pr.HIST.read_text())
ev = led["symbols"]["LEADUSDT"]["events"]
check("جدیدترین اول و تاریخ تهران دارد", ev[0]["t"] == 200 * H and ev[0]["date"])
old = next(e for e in ev if e["t"] == 100 * H)
check("واکنش دنباله‌رو با فاصلهٔ ساعتی ثبت شد",
      old["reactions"] and old["reactions"][0]["symbol"] == "FOLUSDT"
      and old["reactions"][0]["lag_h"] == 3.0)
n2, fresh2 = pr.update_history(hist_blocks)
check("اجرای دوباره رخداد تکراری نمی‌سازد", n2 == 3 and not fresh2)
check("خلاصهٔ تاریخچه روی بلوک نشست", hist_blocks[0].get("history"))
# «پاک نشود» — ۶۰ رخداد قدیمی هم بعد از اجرای تازه باید سر جایشان بمانند
many = {"symbols": {"OLDUSDT": {"events": [
    {"t": i * H, "date": "x", "ret_4h_pct": 12.0, "reactions": []}
    for i in range(60)], "updated": 1}}}
pr.HIST.write_text(json.dumps(many))
n3, _ = pr.update_history(hist_blocks)
led3 = json.loads(pr.HIST.read_text())
check("هیچ رخداد قدیمی‌ای پاک نمی‌شود (بدون سقف)",
      len(led3["symbols"]["OLDUSDT"]["events"]) == 60 and n3 == 63)

# ── علت‌یابی حرکت BTC — «ریخت یا پرید، فوری علت اعلام شود» ────────────────


class CauseKc:
    """ریزش ۲٪ که کف برابرِ سه‌برخوردی را جارو کرده."""
    def get(self, s, tf, n):
        if tf == "1h":
            cs = [100.0] * 60
            cs[-1] = 98.0
            return [bar(i * H, c) for i, c in enumerate(cs)]
        cd = []
        for i in range(260):
            # سه کف برابر در ۹۹.۵ — بعد کندل آخر زیرش می‌رود
            lo = 99.5 if i in (200, 215, 230) else 99.8
            c = 100.0 if i < 256 else 99.0
            cd.append({"t": i * 900_000, "o": c, "h": c + 0.3,
                       "l": min(lo, c - 0.3), "c": c, "v": 100.0})
        return cd


mc = pr.btc_move_cause(CauseKc())
check("حرکت بزرگ تشخیص و جهتش درست است", mc and mc["dir"] == "down"
      and abs(mc["btc_1h_pct"] + 2.0) < 0.1)
check("جاروی نقدینگی به‌عنوان عامل تکنیکال ثبت شد",
      mc and any("جاروی نقدینگی" in t for t in mc["tech"]))
txt = pr.move_cause_fa(mc)
check("متن علت‌یابی فارسی و صادق است",
      "ریخت" in txt and ("علت خبری" in txt))


class QuietKc(CauseKc):
    def get(self, s, tf, n):
        rows = super().get(s, tf, n)
        if tf == "1h":
            rows[-1] = bar(59 * H, 100.0)
        return rows


check("حرکت کوچک → علت‌یابی ساکت", pr.btc_move_cause(QuietKc()) is None)

# ── متن تلگرام ─────────────────────────────────────────────────────────────
msg = pr.tg_message("بیتیونیکس (فیوچرز)", picks[:1], blocks)
# نام پنل ثابت در آزمون نمی‌نشیند — برند از telegram.PANEL_NAME می‌آید و
# با دستور «تک پنل» (۱۷ اوت) عوض شد؛ آزمونِ اسم-ثابت با هر تغییر برند
# دروغکی قرمز می‌شود.
import telegram as _tgb                               # noqa: E402
check("سرتیتر پنل + گزینه‌های پامپ",
      _tgb.PANEL_NAME in msg and "گزینه‌های پامپ" in msg)
check("دلایل داخل پیام‌اند", "دنباله‌رو" in msg and "ورود" in msg)
# پیک AUSDT سردسته‌اش LEADUSDT است — سابقهٔ درآورده‌شده باید در پیام باشد
hb = {b["symbol"]: b for b in hist_blocks}
msg_h = pr.tg_message("تست", picks[:1], blocks + hist_blocks)
check("سابقهٔ سردسته با تاریخ و واکنش در پیام است",
      "📜" in msg_h and "پامپ +" in msg_h and "س بعد" in msg_h)

# ── پاسبانِ کلاس: هیچ دفتری نباید از reset --hard جان سالم به در نبرد ──────
#
# این سومین باری است که همین کلاس خطا زد: ۱۷ اوت دفتر انتظار و ضدتکرار ضعف،
# ۲۰ اوت دفتر نمرهٔ پیشنهادها. هر بار «یک فایل جا مانده بود». پس این آزمون
# نمونهٔ منفرد را نمی‌سنجد — کلاس را می‌بندد: هر فایلی که رادار زیر brain/
# می‌نویسد باید یا از reapply جان به در ببرد، یا صریح در PRESERVE_EXEMPT
# نامش آمده باشد. عضو جدیدِ بی‌نام، تست را قرمز می‌کند.
import shutil as _sh                                  # noqa: E402
import tempfile as _tf                                # noqa: E402

# دفترهایی که عمداً نگه داشته نمی‌شوند (بازتولیدشدنی از منبع، نه دانش)
PRESERVE_EXEMPT = set()

_root = Path(_tf.mkdtemp(prefix="pump-preserve-"))
_brain = _root / "brain"
_brain.mkdir(parents=True)
(_brain / "memory").mkdir()

# «نوشتهٔ اجرای فعلی» — هر دفتری که رادار زیر brain/ نگه می‌دارد
_LEDGERS = {
    "pump-picks.jsonl": '{"t": 1, "sym": "AUSDT", "entry": 1.0}\n',
    "pump-radar-sent.json": '{"AUSDT@1.0": 1}',
    "pump-history.json": '{"symbols": {"AUSDT": {"events": [{"t": 1}], "updated": 1}}}',
    "pump-watchlist.json": '{"AUSDT": {"leader": "L", "added_at": 1, "expires_at": 9e12}}',
    "pump-weakness-seen.json": '{"AUSDT": 1}',
}
_bk = _root / "bk"
_bk.mkdir()
for _n, _c in _LEDGERS.items():
    (_bk / _n).write_text(_c)
(_bk / "pump-radar.json").write_text('{"generated": 1}')

_saved = (pr.ROOT, pr.OUT, pr.SENT, pr.PICKS, pr.HIST)
try:
    pr.ROOT, pr.OUT = _root, _root / "signals" / "pump-radar.json"
    pr.SENT = _brain / "pump-radar-sent.json"
    pr.PICKS = _brain / "pump-picks.jsonl"
    pr.HIST = _brain / "pump-history.json"
    # نامِ ثابتِ مسیر در pump_watchlist «WL» است. نسخهٔ اول این آزمون
    # `PATH` را عوض می‌کرد — یعنی هیچ — و در همان اجرا به فایل **تولید**
    # نوشت. گاردِ تفاضلیِ پایین همین را گرفت. حالا اگر روزی نام ثابت عوض
    # شود، assert زیر تست را می‌شکند نه تولید را.
    import hamid.pump_watchlist as _pw2               # noqa: E402
    assert hasattr(_pw2, "WL"), "pump_watchlist.WL نیست — آزمون به تولید می‌نویسد"
    _pw_saved = _pw2.WL
    _pw2.WL = _brain / "pump-watchlist.json"
    # صحنهٔ واقعی: reset --hard درخت را خالی کرده، فقط پشتیبان مانده
    pr.reapply(str(_bk))
    _lost = [n for n in _LEDGERS
             if n not in PRESERVE_EXEMPT
             and not (_brain / n).exists()
             or (n not in PRESERVE_EXEMPT and (_brain / n).exists()
                 and not (_brain / n).read_text().strip())]
    if _lost:
        print("      ↳ گم‌شده پس از reapply: " + "، ".join(_lost))
    check("هر دفتر رادار از reset --hard جان به در می‌برد", not _lost)
    _picks = (_brain / "pump-picks.jsonl").read_text()
    check("دفتر پیشنهادها محتوایش را نگه داشت (نه فقط فایل خالی)",
          "AUSDT" in _picks)
    # اجتماع، نه جایگزینی: ردیف تازهٔ درختِ ریست‌شده هم باید بماند
    (_brain / "pump-picks.jsonl").write_text(
        '{"t": 2, "sym": "BUSDT", "entry": 2.0}\n')
    pr.reapply(str(_bk))
    _both = (_brain / "pump-picks.jsonl").read_text()
    check("اجتماع دو نسخه، نه بازنویسی (append-only)",
          "AUSDT" in _both and "BUSDT" in _both)
    check("اجتماع تکراری نمی‌سازد",
          _both.count("AUSDT") == 1 and _both.count("BUSDT") == 1)
finally:
    pr.ROOT, pr.OUT, pr.SENT, pr.PICKS, pr.HIST = _saved
    _pw2.WL = _pw_saved

# گارد ایزوله‌سازی: خودِ این آزمون نباید به دفتر تولید دست بزند.
# (نسخهٔ اولش زد — به brain/pump-watchlist.json — چون نام ثابت را اشتباه
# عوض کرده بود. آزمونی که تولید را آلوده کند بدتر از نبودنش است.)
# سنجش **تفاضلی** است نه پاکیِ مطلق (همان درسِ ۱۶ اوت در test_fill_books):
# گاردی که بابت تغییرِ عمدیِ کسِ دیگر — مثلاً بازیابی دفتر پیشنهادها —
# قرمز شود، اولین چیزی است که نادیده گرفته می‌شود، و آن‌وقت روزی که
# واقعاً نشتی هست هم نادیده گرفته می‌شود.
_new_dirty = sorted(set(_brain_status().splitlines()) - set(_BRAIN_BEFORE.splitlines()))
if _new_dirty:
    print("      ↳ " + " | ".join(_new_dirty)[:200])
check("آزمون به دفتر تولید دست نزد", not _new_dirty)

# و پاسبانِ ورک‌فلو: پشتیبانِ خودِ yml هم باید همان فهرست را داشته باشد،
# وگرنه reapply چیزی برای بازگرداندن ندارد.
_yml = (Path(__file__).resolve().parents[3] / ".github" / "workflows"
        / "pump-radar.yml").read_text()
_missing = [n for n in _LEDGERS if n not in PRESERVE_EXEMPT and n not in _yml]
if _missing:
    print("      ↳ در backup ورک‌فلو نیست: " + "، ".join(_missing))
check("ورک‌فلو از همهٔ دفترها پشتیبان می‌گیرد", not _missing)

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های رادار پامپ گذشتند")
