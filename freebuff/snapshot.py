#!/usr/bin/env python3
"""اسنپ‌شات فیوچرز برای پنل فری‌باف ۱ — یک فایل، همهٔ نمودارها.

کندل ۱۵د BTC/ETH/SOL + ضربان OI + فاندینگ + لانگ/شورت، همه در
signals/freebuff/futures.json. پنل همین را می‌خواند؛ اگر این فایل کهنه
شد، پنل «کهنه» می‌گوید — دادهٔ ساختگی هیچ‌وقت وارد نمی‌شود.

    python3 freebuff/snapshot.py
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freebuff import futures                              # noqa: E402

OUT = HERE.parent / "signals" / "freebuff" / "futures.json"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def build(max_candles=96):
    """هر بخش مستقل — خرابی یکی، بقیه را نمی‌کشد؛ خطا صریح در فایل می‌آید."""
    out = {"panel": "پنل فری‌باف ۱", "generated": int(time.time() * 1000),
           "charts": {}, "oi": None, "funding": None, "longshort": None,
           "errors": []}
    for sym in SYMBOLS:
        try:
            kl = futures.klines(sym, "15m", max_candles)
            out["charts"][sym] = kl
        except Exception as e:                       # noqa: BLE001
            out["errors"].append(f"{sym}: {type(e).__name__}")
    try:
        h = futures.oi_history("BTCUSDT")
        out["oi"] = {"history": h[-48:], "pulse": futures.oi_pulse(h)}
    except Exception:
        # بایننس رد شد — سطح لحظه‌ای OKX جایگزین تاریخچه می‌شود؛ برند صادق
        try:
            s = futures.oi_snapshot_okx()
            out["oi"] = {"snapshot": s,
                         "pulse": {"verdict": "سطح لحظه‌ای OKX (تاریخچهٔ بایننس از این شبکه در دسترس نیست)",
                                    "chg_pct": None}}
        except Exception as e:                       # noqa: BLE001
            out["errors"].append(f"oi: {type(e).__name__}")
    try:
        f = futures.funding(40)
        out["funding"] = futures.funding_verdict(f)
        out["funding"]["rows"] = f[:20]
    except Exception as e:                           # noqa: BLE001
        out["errors"].append(f"funding: {type(e).__name__}")
    try:
        out["longshort"] = futures.longshort_verdict(futures.longshort())
    except Exception:                                # noqa: BLE001 — صادقانه: از این شبکه در دسترس نیست
        out["longshort"] = "نسبت لانگ/شورت از این شبکه در دسترس نیست — در اجرای رانر گیت‌هاب معمولاً می‌آید"
    out["venues"] = futures.used()
    return out


def main():
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")))
    tmp.replace(OUT)
    n_charts = len(data["charts"])
    print(f"اسنپ‌شات: {n_charts}/۳ نمودار، "
          f"{len(data['errors'])} خطا — {OUT.name}")
    return data


if __name__ == "__main__":
    main()
