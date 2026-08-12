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


def _bars(points, key, bar_ms=3_600_000):
    """کندل از نقاط سری دامیننس — o/h/l/c واقعی هر سطل، فقط سطل‌های بسته.

    سری ما نقطه‌ای است (هر ~۵ دقیقه یک سطح)؛ برای موتور ساختار حمید باید
    کندل شود. سطل آخر هنوز باز است و کندل نیست — حذف می‌شود، همان قاعدهٔ
    «سقف تا شکست نخورده سقف نیست»."""
    bucket = {}
    for p in points:
        bucket.setdefault(p["t"] // bar_ms, []).append(p[key])
    out = []
    for b in sorted(bucket)[:-1]:
        vs = bucket[b]
        out.append({"t": b * bar_ms, "o": vs[0], "h": max(vs), "l": min(vs),
                    "c": vs[-1], "v": float(len(vs))})
    return out


MIN_BARS_1H = 60      # زیر این، حکم ساختاری صادر نمی‌شود — دروازهٔ صداقت
MIN_BARS_4H = 60


def structural(points, macro=None):
    """فاز ۲ معماری AuraLiam369 — تحلیل ساختاری مستقل USDT.D و BTC.D.

    همان موتور ساختار حمید (سوینگ/روند/سطح معتبر) روی سری دامیننسِ خودمان،
    نه فقط دلتای عددی. رژیم از دید آلت‌هاست: USDT.D ساختاراً نزولی = پول
    وارد ریسک = BULLISH؛ صعودی = BEARISH؛ بدون جهت = RANGE؛ تعارض ۴س با
    ۱س = TRANSITION؛ رویداد کلان تا ۲ ساعت = UNSAFE (شلاق قیمت، حکم جهتی
    معلق). زیر MIN_BARS داده، جواب INSUFFICIENT است با شمارش صریح — حدس
    جای اندازه‌گیری نمی‌نشیند."""
    from hamid import structure as st

    bu, bb = _bars(points, "u"), _bars(points, "b")
    bu4 = _bars(points, "u", 4 * 3_600_000)
    out = {"bars_1h": len(bu), "bars_4h": len(bu4), "regime": "INSUFFICIENT"}
    if len(bu) < MIN_BARS_1H:
        out["note"] = (f"دادهٔ ساختاری کافی نیست ({len(bu)} کندل ۱س از حداقل "
                       f"{MIN_BARS_1H}) — تا آن موقع فقط دلتای عددی معتبر است")
        return out

    tu1, tb1 = st.trend(bu), st.trend(bb)
    # سطوح معتبر USDT.D: نزدیک‌ترین سطح بالا/پایین = مسیر و ابطال رژیم
    px = bu[-1]["c"]
    lv = st.levels(bu)
    above = min((l.price for l in lv if l.price > px), default=None)
    below = max((l.price for l in lv if l.price < px), default=None)
    out["usdt"] = {"trend_1h": tu1, "px": round(px, 3),
                   "level_above": round(above, 3) if above else None,
                   "level_below": round(below, 3) if below else None}
    out["btc_d"] = {"trend_1h": tb1}

    tu4 = None
    if len(bu4) >= MIN_BARS_4H:
        tu4 = st.trend(bu4)
        out["usdt"]["trend_4h"] = tu4
    else:
        out["usdt"]["trend_4h"] = f"INSUFFICIENT ({len(bu4)}/{MIN_BARS_4H})"

    if tu1 == "down":
        reg = "BULLISH"
    elif tu1 == "up":
        reg = "BEARISH"
    else:
        reg = "RANGE"
    if tu4 in ("up", "down") and tu1 in ("up", "down") and tu4 != tu1:
        reg = "TRANSITION"                # تایم بالا مخالف است — قطعیت ممنوع
    near_macro = [m for m in (macro or [])
                  if 0 <= (m.get("in_hours") if m.get("in_hours") is not None else 99) <= 2]
    if near_macro:
        reg = "UNSAFE"
        out["unsafe_reason"] = f"رویداد کلان تا ۲ ساعت: {near_macro[0].get('title')}"

    out["regime"] = reg
    why = f"USDT.D ساختار ۱س {tu1}"
    if tu4:
        why += f" · ۴س {tu4}"
    if tb1 in ("up", "down"):
        why += f" · BTC.D ۱س {tb1}"
    out["why"] = why
    if reg == "BULLISH" and above is not None:
        out["invalidation"] = f"ابطال رژیم: بازگشت USDT.D بالای {above:.3f}"
    elif reg == "BEARISH" and below is not None:
        out["invalidation"] = f"ابطال رژیم: شکست USDT.D زیر {below:.3f}"
    return out


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
    try:
        struct = structural(series, mac)
    except Exception as e:                       # noqa: BLE001 - ساختار، سری را نمی‌کشد
        struct = {"regime": "INSUFFICIENT", "note": f"خطای ساختار: {e}"}
    if struct.get("regime") not in (None, "INSUFFICIENT"):
        verdict += f"؛ رژیم ساختاری: {struct['regime']} ({struct.get('why', '')})"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": int(time.time() * 1000),
        "usdt_dominance": u, "btc_dominance": b,
        "chg_1h": {"usdt": u1, "btc": b1}, "chg_4h": {"usdt": u4, "btc": b4},
        "points": len(series), "verdict": verdict, "macro": mac,
        "structure": struct,
    }, ensure_ascii=False, indent=1))
    print(f"USDT.D {u} ({'+' if (u1 or 0) >= 0 else ''}{u1}/1h) · "
          f"BTC.D {b} · {verdict}")


if __name__ == "__main__":
    run()
