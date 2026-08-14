"""آزمون مطالعهٔ رویدادی پامپ — مدل دقیق حمید، بدون شبکه.

  ۱. صفحه‌بندی تا روز لانچ کار می‌کند و ترتیب/یکتایی حفظ می‌شود
  ۲. پامپ‌های تاریخچه پیدا می‌شوند و هم‌پوشان‌ها یکی شمرده می‌شوند
  ۳. کاندیدایی که ۳ از ۵ بار دنبال لیدر رشد کرده qualified می‌شود («۳ بار از ۱۰» حمید)
  ۴. کاندیدای بی‌واکنش qualified نمی‌شود
  ۵. پامپ بدون پوشش دادهٔ کاندیدا در N شمرده نمی‌شود (صداقت پوشش)
  ۶. واکنشِ قبل از پامپ (k_before) جدا شمرده می‌شود
  ۷. دفتر ماندگار union است — لیدر قبلی نمی‌پرد
  ۸. جملهٔ فارسی دلیل، k از N و درصد دارد
  ۹. امتیازدهی رادار event_leaders را قوی‌ترین مدرک می‌گیرد
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

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


from hamid import pump_study as ps                              # noqa: E402

TMP = Path(tempfile.mkdtemp())
ps.LEDGER = TMP / "pump-followers.json"

H1 = ps.H1
T0 = 1_700_000_000_000


def flat_series(n, start_t, px=1.0):
    return [{"t": start_t + i * H1, "o": px, "h": px * 1.001, "l": px * 0.999,
             "c": px, "v": 100.0} for i in range(n)]


def inject_pump(cd, at_idx, pct=12.0, cand=False):
    """در at_idx یک موج رشد ۴ساعته بگذار."""
    for k in range(4):
        i = at_idx + k
        if i < len(cd):
            mult = 1 + (pct / 100) * (k + 1) / 4
            base = cd[at_idx - 1]["c"] if at_idx else 1.0
            cd[i] = {**cd[i], "h": base * mult, "c": base * mult * 0.99,
                     "o": cd[i]["o"], "l": cd[i]["l"], "v": 500.0}


print("── مطالعهٔ رویدادی پامپ ──")

# ── ۱. صفحه‌بندی ───────────────────────────────────────────────────────────
full = flat_series(2500, T0)


def fake_page(sym, end_ms):
    rows = [c for c in full if end_ms is None or c["t"] < end_ms]
    return rows[-1000:]


hist = ps.deep_history("XUSDT", fetch_page=fake_page, max_bars=6000)
check("صفحه‌بندی کل تاریخچه را آورد (۲۵۰۰ کندل)", len(hist) == 2500)
ts = [c["t"] for c in hist]
check("ترتیب زمانی و یکتایی حفظ شد", ts == sorted(set(ts)))

short = flat_series(300, T0)
hist2 = ps.deep_history("YUSDT",
                        fetch_page=lambda s, e: [c for c in short
                                                 if e is None or c["t"] < e][-1000:])
check("ارز تازه‌لانچ: در صفحهٔ اول تمام می‌شود", len(hist2) == 300)

# ── ۲. پامپ‌یابی ───────────────────────────────────────────────────────────
lead = flat_series(1200, T0)
pump_idxs = [200, 400, 600, 800, 1000]
for i in pump_idxs:
    inject_pump(lead, i)
pumps = ps.find_pumps(lead)
check(f"۵ پامپ تزریقی پیدا شد ({len(pumps)})", len(pumps) == 5)

dense = flat_series(300, T0)
inject_pump(dense, 100)
inject_pump(dense, 106)                                # همان موج — نباید دو بشود
check("پامپ‌های هم‌پوشان یکی شمرده می‌شوند",
      len(ps.find_pumps(dense)) == 1)

# ── ۳و۴. شمارش k از N ─────────────────────────────────────────────────────
# کاندیدای A: بعد از پامپ‌های ۱و۳و۵ لیدر (با ~۳س تأخیر) می‌پرد → k=3 از N=5
candA = flat_series(1200, T0)
for i in (203, 603, 1003):
    inject_pump(candA, i, pct=8.0)
# کاندیدای B: هیچ واکنشی ندارد
candB = flat_series(1200, T0)
# کاندیدای C: فقط ۴۰۰ کندل آخر داده دارد → پامپ‌های قدیمی لیدر پوشش ندارند
candC = flat_series(400, T0 + 800 * H1)
inject_pump(candC, 203)                                # واکنش به پامپ ۱۰۰۰

res = ps.study("LEADUSDT", lead,
               {"AUSDT": candA, "BUSDT": candB, "CUSDT": candC})
a = res["followers"]["AUSDT"]
check(f"A: سه از پنج ({a['k_after']} از {a['N']})", a["k_after"] == 3 and a["N"] == 5)
check("A: qualified شد (قاعدهٔ ۳تایی و ≥۳۰٪ حمید)", a["qualified"])
check("A: تأخیر میانه ثبت شد", a["med_lag_h"] is not None)
b = res["followers"].get("BUSDT")
check("B: بی‌واکنش qualified نیست", b is not None and not b["qualified"])
c = res["followers"].get("CUSDT")
check("C: فقط پامپ‌های پوشش‌داده در N شمرده شد (N<5)",
      c is not None and c["N"] < 5)

# ── ۶. واکنش قبل از پامپ ───────────────────────────────────────────────────
candD = flat_series(1200, T0)
for i in (180, 380):                                   # قبل از پامپ‌های ۲۰۰ و ۴۰۰
    inject_pump(candD, i, pct=8.0)
resD = ps.study("LEADUSDT", lead, {"DUSDT": candD})
d = resD["followers"]["DUSDT"]
check(f"واکنشِ قبل جدا شمرده می‌شود (k_before={d['k_before']})",
      d["k_before"] >= 2)

# ── ۷. دفتر union ──────────────────────────────────────────────────────────
ps.save_ledger(res)
ps.save_ledger({"leader": "OTHERUSDT", "pumps_n": 2,
                "coverage_from": T0, "followers": {}})
led = json.loads(ps.LEDGER.read_text())
check("دفتر ماندگار union است (هر دو لیدر ماندند)",
      "LEADUSDT" in led and "OTHERUSDT" in led)

# ── ۸. جملهٔ دلیل ──────────────────────────────────────────────────────────
fa = ps.reason_fa("LEADUSDT", "AUSDT", a)
check("دلیل فارسی k از N و درصد دارد",
      "3 از 5" in fa and "60٪" in fa)

# ── ۹. امتیازدهی رادار ─────────────────────────────────────────────────────
from hamid import pump_radar as pr                              # noqa: E402
blocks = [{"symbol": "AUSDT", "role": "نامشخص", "alarm": {"entry": 1.0, "sl": 0.95},
           "now": {"rsi_1h": 50, "rsi_15m": 50, "trend_4h": "up", "trend_1h": "up"},
           "pumps": [], "history": [], "price": 0.99,
           "change_30m_pct": 1.0, "change_24h_pct": 2.0, "change_60m_pct": 1.0,
           "event_leaders": [{"symbol": "LEADUSDT", **a,
                              "reason": fa}]}]
picks = pr.recommend(blocks)
check("کاندیدای مطالعهٔ رویدادی پیشنهاد شد", picks and picks[0]["symbol"] == "AUSDT")
check("دلیلش همان k از N است", picks and any("3 از 5" in w for w in picks[0]["reasons"]))

real = Path(__file__).resolve().parents[3] / "brain" / "pump-followers.json"
check("دفتر واقعی مغز دست نخورد", ps.LEDGER != real)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون مطالعهٔ رویدادی گذشت")
