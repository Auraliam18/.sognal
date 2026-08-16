"""خودآزمایی موتور کارمزد — python3 -m hamid.test_fees"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import fees                               # noqa: E402


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def run():
    # تیکر دو سر + لغزش: 0.06×2 + 0.015×2 = 0.15٪ — همان «~۰.۱۵٪» قانون تریل
    rt = fees.round_trip_pct()
    assert close(rt, 0.15), rt
    print(f"۱ ✅ رفت‌وبرگشت تیکر+لغزش = {rt}٪ — منطبق با قانون تریل trading-core")

    # میکر دو سر ارزان‌تر است — مزیتی که حمید گفت
    rt_m = fees.round_trip_pct(entry_maker=True, exit_maker=True)
    assert close(rt_m, 0.07) and rt_m < rt
    print(f"۲ ✅ میکر دو سر = {rt_m}٪ < تیکر {rt}٪")

    # استاپ ۱٪ → کارمزد 0.15R؛ استاپ تنگ ۰.۳٪ → 0.5R (دام اسکالپ)
    r1 = fees.cost_in_r(100.0, 99.0)
    r2 = fees.cost_in_r(100.0, 99.7)
    assert close(r1, 0.15, 0.001) and r2 >= 0.5, (r1, r2)
    print(f"۳ ✅ کارمزد بر R: استاپ ۱٪ → {r1}R · استاپ ۰.۳٪ → {r2}R (دام اسکالپ آشکار)")

    # دروازه: RR اسمی 2.0 با استاپ تنگ رد می‌شود، با استاپ عادی می‌گذرد
    g_bad = fees.gate(100.0, 99.7, 100.6)            # RR اسمی 2.0، استاپ ۰.۳٪
    g_ok = fees.gate(100.0, 99.0, 102.0)             # RR اسمی 2.0، استاپ ۱٪
    assert not g_bad["ok"] and g_ok["ok"], (g_bad, g_ok)
    assert "کارمزد" in g_bad["reason"]
    print(f"۴ ✅ دروازه: تنگ رد ({g_bad['net_rr']}R خالص) · عادی قبول ({g_ok['net_rr']}R)")

    # صفر-کارمزدِ تأییدنشده اثر ندارد (بی‌منبع = بی‌اعتبار)
    fees.DEFAULTS["zero_fee_symbols"] = ["XUSDT"]
    assert fees.round_trip_pct("XUSDT") == fees.round_trip_pct("YUSDT")
    fees.DEFAULTS["zero_fee_status"] = "VERIFIED"
    assert fees.round_trip_pct("XUSDT") < fees.round_trip_pct("YUSDT")
    fees.DEFAULTS["zero_fee_symbols"] = []
    fees.DEFAULTS["zero_fee_status"] = "UNVERIFIED"
    print("۵ ✅ صفر-کارمزد فقط با وضعیت VERIFIED اثر می‌کند")

    print("\nهمهٔ ۵ آزمون کارمزد گذشت")


if __name__ == "__main__":
    run()
