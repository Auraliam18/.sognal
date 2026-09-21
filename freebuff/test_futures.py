#!/usr/bin/env python3
"""آزمون آفلاین لایهٔ فیوچرز — هیچ شبکه‌ای صدا زده نمی‌شود.

    python3 freebuff/test_futures.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freebuff import futures                              # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'OK' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


# ── sane روی ردیف‌های جعلی — همان تله‌هایی که sources.py دید ────────────────
OK_ROWS = [[1_000, 100.0, 110.0, 95.0, 105.0, 10.0, 1_500],
           [2_000, 105.0, 120.0, 100.0, 118.0, 12.0, 2_500]]

check("sane: ردیف سالم قبول", futures.sane(OK_ROWS, 2))
check("sane: برعکس رد", not futures.sane(list(reversed(OK_ROWS)), 2))
check("sane: کوتاه رد", not futures.sane(OK_ROWS[:1], 2))
check("sane: high<low رد", not futures.sane(
    [[1_000, 100.0, 90.0, 95.0, 105.0, 1.0, 1_500]], 1))
check("sane: body بیرون range رد", not futures.sane(
    [[1_000, 120.0, 110.0, 95.0, 105.0, 1.0, 1_500]], 1))
check("sane: NaN رد", not futures.sane(
    [[1_000, float("nan"), 110.0, 95.0, 105.0, 1.0, 1_500]], 1))

# ── آداپتورها: ترتیب و جهت ────────────────────────────────────────────────
BYB = {"result": {"list": [["3000", "104", "108", "100", "106", "10", "1e6"],
                           ["2000", "102", "106", "98", "104", "9", "9e5"],
                           ["1000", "100", "104", "96", "102", "8", "8e5"]]}}
rows = futures._k_bybit(BYB)
check("bybit: قدیم→جدید", rows[0][0] == 1000 and rows[-1][0] == 3000)
check("bybit: فیلدها o,h,l,c", rows[-1][1] == 104.0 and rows[-1][2] == 108.0
      and rows[-1][3] == 100.0 and rows[-1][4] == 106.0)

OKX = {"data": [["3000", "104", "108", "100", "106", "10", "1"],
                ["2000", "102", "106", "98", "104", "9", "1"],
                ["1000", "100", "104", "96", "102", "8", "1"]]}
rows = futures._k_okx(OKX)
check("okx: قدیم→جدید", rows[0][0] == 1000 and rows[-1][0] == 3000)
check("okx: بسته آخر = 106", rows[-1][4] == 106.0)

BIN = [[1000, "100", "104", "96", "102", "8", 1500]]
rows = futures._k_binance(BIN)
check("binance: شکل مرجع حفظ", rows[0][0] == 1000 and rows[0][4] == 102.0)

# ── oi_pulse — ضربان OI ───────────────────────────────────────────────────
def mk_hist(pct_series):
    return [{"t": 1000 + i * 300_000, "oi": v, "oi_usd": v * 60_000}
            for i, v in enumerate(pct_series)]

rising = mk_hist([100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5,
                  104.0, 104.5, 105.0, 105.5, 106.0, 106.5])
p = futures.oi_pulse(rising, window=12)
check("oi_pulse: رشد مثبت دیده می‌شود", p["chg_pct"] is not None and p["chg_pct"] > 1.0,
      str(p))
check("oi_pulse: حکم پول تازه", "تازه" in p["verdict"])

falling = mk_hist([106.0, 105.5, 105.0, 104.5, 104.0, 103.5, 103.0, 102.5,
                   102.0, 101.5, 101.0, 100.5, 100.0, 99.5])
p = futures.oi_pulse(falling, window=12)
check("oi_pulse: خروج پول دیده می‌شود", p["chg_pct"] is not None and p["chg_pct"] < -1.0,
      str(p))

flat = mk_hist([100.0 + (0.01 if i % 2 else -0.01) for i in range(14)])
p = futures.oi_pulse(flat, window=12)
check("oi_pulse: خنثی", "خنثی" in p["verdict"], str(p))
check("oi_pulse: سری کوتاه صادق", futures.oi_pulse(mk_hist([100.0] * 5))["chg_pct"] is None)

# ── funding_verdict ───────────────────────────────────────────────────────
def fr(sym, rate):
    return {"symbol": sym, "rate": rate, "mark": 100.0, "at": 1}

v = futures.funding_verdict([fr("BTCUSDT", 0.02), fr("ETHUSDT", 0.01),
                             fr("SOLUSDT", 0.015), fr("AAAUSDT", 0.9)])
check("funding: مثبت → جمعیت لانگ سنگین", "لانگ‌ها پول می‌دهند" in v["verdict"])
check("funding: اکسترم جدا شده", any(r["symbol"] == "AAAUSDT" for r in v["extremes"]))

v = futures.funding_verdict([fr("BTCUSDT", -0.02), fr("ETHUSDT", -0.01),
                             fr("SOLUSDT", -0.015)])
check("funding: منفی → جمعیت شورت سنگین", "شورت‌ها پول می‌دهند" in v["verdict"])
check("funding: خالی صادق", futures.funding_verdict([])["avg"] is None)

# ── longshort_verdict ─────────────────────────────────────────────────────
hot = [{"symbol": "XUSDT", "ratio": 2.4, "long_pct": 70.0},
       {"symbol": "BTCUSDT", "ratio": 1.1, "long_pct": 52.0}]
check("longshort: جمعیت لانگ هشدار", "سوخت لیکویید برای شورت" in
      futures.longshort_verdict(hot))
short_side = [{"symbol": "BTCUSDT", "ratio": 0.8, "long_pct": 44.0},
              {"symbol": "ETHUSDT", "ratio": 0.9, "long_pct": 47.0}]
check("longshort: شورت سنگین هشدار", "سوخت لیکویید برای لانگ" in
      futures.longshort_verdict(short_side))
check("longshort: متعادل", futures.longshort_verdict(
    [{"symbol": "BTCUSDT", "ratio": 1.2, "long_pct": 54.0}]) == "نسبت لانگ/شورت متعادل")
check("longshort: خالی صادق", "نیامد" in futures.longshort_verdict([]))

print(f"\n{'همهٔ آزمون‌ها سبز' if FAIL == 0 else f'{FAIL} آزمون قرمز'}")
sys.exit(1 if FAIL else 0)
