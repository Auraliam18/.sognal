"""اتاق مستقل دامیننس — هر چند دقیقه نظر خودش را می‌دهد، همان که حمید خواست.

USDT.D و BTC.D سری زمانی رسمی رایگان ندارند؛ این اتاق خودش می‌سازد: هر
اجرا سطح لحظه‌ای را می‌خواند و به سری ذخیره‌شده می‌چسباند — بالاخره
می‌شود روی دامیننس روند و تغییر واقعی سنجید، نه فقط یک عدد لحظه‌ای.

نظر اتاق سه جزء دارد و هر سه با عدد:
  ۱. جهت USDT.D در ۱ و ۴ ساعت اخیر (از سری خودمان) — بالا = پول به حاشیه.
  ۲. جهت BTC.D — بالا = پول از آلت به بیت‌کوین.
  ۳. رویدادهای کلان پیشِ رو (تورم/بیکاری/فدرال از تقویم رسمی) — عامل
     سیاسی/تورمی که حمید گفت، تا جایی که منبع قابل‌اتکا دارد.

خروجی signals/dominance.json است؛ چرخه و پنل همین را می‌خوانند.
    python3 -m hamid.dominance
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import research, intel                             # noqa: E402

ROOT = HERE.parent.parent.parent
SERIES = ROOT / "brain" / "dominance-series.json"
OUT = ROOT / "signals" / "dominance.json"
CAP = 4000                                    # ~۲ هفته با گام ۵ دقیقه

MACRO_KEYS = ("cpi", "inflation", "unemployment", "nonfarm", "payroll",
              "fomc", "fed", "rate", "gdp", "ppi")


def _chg(points, minutes):
    """تغییر واحد درصدِ دامیننس نسبت به نزدیک‌ترین نقطهٔ minutes دقیقه قبل."""
    if len(points) < 2:
        return None, None
    t0 = points[-1]["t"] - minutes * 60000
    past = min(points, key=lambda p: abs(p["t"] - t0))
    if abs(past["t"] - t0) > minutes * 60000:    # سری هنوز آن‌قدر عقب نمی‌رود
        return None, None
    return (round(points[-1]["u"] - past["u"], 3),
            round(points[-1]["b"] - past["b"], 3))


def opinion(u1, b1, u4):
    """نظر اتاق، به فارسی و بدون طفره — آستانهٔ ۰.۰۵ واحد در ساعت یعنی حرکت
    واقعی، نه لرزش."""
    if u1 is None:
        return "سری هنوز کوتاه است — نظر قطعی بعد از یک ساعت دادهٔ خودمان"
    parts = []
    if u1 >= 0.05 or (u4 is not None and u4 >= 0.15):
        parts.append("USDT.D بالا می‌رود: پول به حاشیه — در لانگ آلت‌ها احتیاط")
    elif u1 <= -0.05 or (u4 is not None and u4 <= -0.15):
        parts.append("USDT.D پایین می‌آید: پول وارد ریسک می‌شود — به نفع لانگ")
    else:
        parts.append("USDT.D خنثی است")
    if b1 is not None:
        if b1 >= 0.05:
            parts.append("BTC.D بالا: پول از آلت به بیت‌کوین")
        elif b1 <= -0.05:
            parts.append("BTC.D پایین: فصل آلت‌ها محتمل‌تر")
    return "؛ ".join(parts)


def macro_events():
    """رویدادهای کلان (تورم/بیکاری/فدرال) ۴۸ ساعت پیش رو از تقویم رسمی."""
    try:
        cal = intel.calendar()
    except Exception:                            # noqa: BLE001
        return []
    evs = (cal.get("next_48h") if isinstance(cal, dict) else cal) or []
    out = []
    for e in evs:
        t = (str(e.get("title") or "")).lower()
        if any(k in t for k in MACRO_KEYS):
            out.append({"title": e.get("title"), "in_hours": e.get("in_hours"),
                        "country": e.get("country")})
    return out[:6]


def run():
    g = research.global_market()
    u, b = round(g["usdt_dominance"], 3), round(g["btc_dominance"], 3)
    try:
        series = json.loads(SERIES.read_text()).get("points") or []
    except Exception:                            # noqa: BLE001
        series = []
    series.append({"t": int(time.time() * 1000), "u": u, "b": b})
    series = series[-CAP:]
    SERIES.parent.mkdir(parents=True, exist_ok=True)
    SERIES.write_text(json.dumps({"points": series}))

    u1, b1 = _chg(series, 60)
    u4, b4 = _chg(series, 240)
    mac = macro_events()
    verdict = opinion(u1, b1, u4)
    if mac:
        nearest = min(mac, key=lambda e: e.get("in_hours") or 99)
        verdict += (f"؛ رویداد کلان پیش رو: {nearest['title']}"
                    f" ({nearest.get('in_hours', '؟')} ساعت دیگر) — نزدیکش سایز کوچک")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": int(time.time() * 1000),
        "usdt_dominance": u, "btc_dominance": b,
        "chg_1h": {"usdt": u1, "btc": b1}, "chg_4h": {"usdt": u4, "btc": b4},
        "points": len(series), "verdict": verdict, "macro": mac,
    }, ensure_ascii=False, indent=1))
    print(f"USDT.D {u} ({'+' if (u1 or 0) >= 0 else ''}{u1}/1h) · "
          f"BTC.D {b} · {verdict}")


if __name__ == "__main__":
    run()
