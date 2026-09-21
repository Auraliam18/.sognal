#!/usr/bin/env python3
"""آزمون آفلاین اسنپ‌شات — با آداپتورهای جعلی، بدون شبکه.

    python3 freebuff/test_snapshot.py
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freebuff import snapshot, futures                    # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'OK' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


def fake_kl(sym, tf, limit):
    return [[1000 + i * 900_000, 100.0 + i, 105.0 + i, 99.0 + i,
             102.0 + i, 10.0] for i in range(limit)]


real_kl, real_oi = futures.klines, futures.oi_history
real_fu, real_ls = futures.funding, futures.longshort

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    snapshot.OUT = tmp / "futures.json"

    # همه سالم
    futures.klines = fake_kl
    futures.oi_history = lambda s="BTCUSDT", p="5m", l=48: [
        {"t": i, "oi": 100.0 + i, "oi_usd": 1e6} for i in range(50)]
    futures.funding = lambda l=60: [{"symbol": "BTCUSDT", "rate": 0.01,
                                     "mark": 1.0, "at": 1}]
    futures.longshort = lambda: [{"symbol": "BTCUSDT", "ratio": 1.2,
                                  "long_pct": 55.0}]
    d = snapshot.build()
    check("سه نمودار ساخته شد", set(d["charts"]) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"})
    check("ضربان OI داخل اسنپ‌شات", d["oi"]["pulse"]["verdict"] is not None)
    check("فاندینگ داخل اسنپ‌شات", d["funding"]["verdict"] is not None)
    check("بدون خطا در حالت سالم", d["errors"] == [])

    # یکی می‌میرد — بقیه زنده می‌مانند
    def boom(sym, tf, limit):
        raise RuntimeError("HTTP 418")
    futures.klines = boom
    d = snapshot.build()
    check("نمودار مرده در errors صریح است", any("418" not in e and "RuntimeError" in e for e in d["errors"]),
          str(d["errors"]))
    check("بقیهٔ بخش‌ها زنده ماندند", d["oi"] is not None and d["funding"] is not None)
    check("نمودار خالی، نه ساختگی", d["charts"] == {})

    # نوشتن اتمیک
    futures.klines = fake_kl
    import time as _t
    _t.sleep(0.01)
    data = snapshot.main()
    saved = json.loads((tmp / "futures.json").read_text())
    check("فایل ذخیره شد و خوانا", saved["panel"] == "پنل فری‌باف ۱")
    leftovers = list(tmp.glob("*.tmp"))
    check("فایل موقتی باقی نماند", not leftovers)

futures.klines, futures.oi_history = real_kl, real_oi
futures.funding, futures.longshort = real_fu, real_ls

print(f"\n{'همهٔ آزمون‌ها سبز' if FAIL == 0 else f'{FAIL} آزمون قرمز'}")
sys.exit(1 if FAIL else 0)
