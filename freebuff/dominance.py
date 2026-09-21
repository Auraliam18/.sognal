#!/usr/bin/env python3
"""اتاق دامیننس تتر — پنل فری‌باف ۱.

چیزی که این اتاق اضافه می‌کند، «محرک» است: عواملی که روی حرکت USDT.D
اثر می‌گذارند، کنار خود سری. سه منبع مرتبط، همهٔ رایگان:

  ۱. چاپ/سوزاندن تتر (Treasury) — اژدهای اصلی: تترِ تازه چاپ‌شده بالقوه
     پول ورودی به کریپتو است؛ سوزاندن، خروج. endpoint عمومی Tether
     Treasury: totalMinted/totalBurned امروز.
  ۲. شاخص ترس‌وطمع (alternative.me) — سمت ریسک بازار؛ ریسک‌پذیری با
     USDT.D رابطهٔ معکوس دارد.
  ۳. رویداد کلان پیشِ رو (تقویم faireconomy → تریدینگ‌ویو) — CPI/فدرال
     شلاق کل بازار است و اول جریان به حاشیه را تکان می‌دهد.

خروجی: signals/freebuff/dominance.json — سری ۵دقیقه‌ای خودمان + محرک‌ها +
حکم ترکیبی. ساختارِ سوینگ/روند همان موتور hamid.structure است (روش حمید)،
روی سری خودمان.

    python3 freebuff/dominance.py
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "claude-liam-signal" / "python"))

from hamid import intel                                   # noqa: E402

ROOT = HERE.parent
OUT = ROOT / "signals" / "freebuff" / "dominance.json"
SERIES = ROOT / "brain" / "freebuff" / "dominance-series.json"
CAP = 8000                                   # ~۴ هفته با گام ۵ دقیقه
STEP_MS = 5 * 60 * 1000

UA = {"User-Agent": "Mozilla/5.0 (compatible; freebuff1/1.0)"}


def _json(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ── محرک‌ها ────────────────────────────────────────────────────────────────

def tether_treasury():
    """چاپ/سوزاندن تتر امروز — endpoint عمومی Tether Treasury.

    نکتهٔ صداقت: چاپ تتر به‌خودی‌خود «خرید کریپتو» نیست؛ اثرش با تأخیر و
    مسیر چندگانه است. این عدد «فشار پتانسیل» است نه تیک خرید — و در خروجی
    همین‌طور برچسب می‌خورد."""
    try:
        j = _json("https://tether.to/api/v1/treasury", timeout=10)
        minted = float(j.get("totalMinted") or 0)
        burned = float(j.get("totalBurned") or 0)
        return {"minted_usd": minted, "burned_usd": burned,
                "net_usd": round(minted - burned, 2)}
    except Exception:                                # noqa: BLE001
        # شکل ناشناخته یا ناپایدار — بدون عدد، بدون حدس
        return None


def fear_greed():
    try:
        j = _json("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = j["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception:                                # noqa: BLE001
        return None


def macro_window():
    """رویداد کلان در ۴۸ ساعت — از همان تقویم موجود، بدون منبع تازه."""
    try:
        c = intel.calendar()
        return c.get("next_48h") or []
    except Exception:                                # noqa: BLE001
        return []


# ── حکم ترکیبی ────────────────────────────────────────────────────────────

def combined(u1, u4, ttr, fg, macro):
    """حکم اتاق: جهت سری + محرک‌ها، هر جزء با عدد یا «نیست».

    جهت از سری خودمان (دلتای ۱س/۴س)، محرک‌ها فقط وزن تعبیه می‌دهند.
    هیچ جزئی حکم را یکه‌تاز نمی‌کند — تعارض صریح نوشته می‌شود."""
    if u1 is None:
        return "سری کوتاه است — حکم جهتی بعد از ~۱ ساعت داده"
    parts = []
    if u1 > 0.03 or (u4 is not None and u4 > 0.10):
        parts.append("USDT.D صعودی — پول به حاشیه؛ در لانگ آلت احتیاط")
    elif u1 < -0.03 or (u4 is not None and u4 < -0.10):
        parts.append("USDT.D نزولی — پول وارد ریسک؛ به نفع آلت‌کوین‌ها")
    else:
        parts.append("USDT.D خنثی")

    if ttr:
        net = ttr["net_usd"]
        if net >= 20_000_000:
            parts.append(f"تتر {net/1e6:.0f}M$ چاپ خالص امروز — فشار پتانسیل ورود پول (با تأخیر اثر می‌گذارد)")
        elif net <= -20_000_000:
            parts.append(f"تتر {abs(net)/1e6:.0f}M$ سوزاندن خالص — فشار پتانسیل خروج")
        else:
            parts.append("چاپ/سوزاندن تتر امروز در حد معمول")

    if fg:
        if fg["value"] <= 25:
            parts.append(f"ترس شدید ({fg['value']}) — تاریخی‌تر منطقهٔ بازگشت، نه ادامهٔ فروش")
        elif fg["value"] >= 75:
            parts.append(f"طمع شدید ({fg['value']}) — تاریخی‌تر ناحیهٔ خطر لانگ دیرهنگام")
        else:
            parts.append(f"سناریوسازی بازار متعادل ({fg['value']})")

    if macro:
        nxt = macro[0]
        parts.append(f"رویداد کلان پیشِ رو: {nxt['title']} ({nxt['in_hours']}h دیگر) — سقف ریسک پیش از آن پایین بیاید")

    return "؛ ".join(parts)


# ── سری و انتشار ──────────────────────────────────────────────────────────

def load_series():
    try:
        return json.loads(SERIES.read_text())
    except Exception:                                # noqa: BLE001
        return []


def append_point(series, u, b):
    """نقطهٔ ۵دقیقه‌ای — فقط اگر فاصلهٔ زمانی کافی باشد؛ دو نقطهٔ هم‌گام
    یعنی دو اجرا هم‌زمان، و سری نباید دوبرابر پر شود."""
    now = int(time.time() * 1000)
    if series and now - series[-1]["t"] < STEP_MS * 0.75:
        return series, False
    series.append({"t": now, "u": u, "b": b})
    return series[-CAP:], True


def read_level():
    """سطح لحظه‌ای USDT.D و BTC.D از CoinGecko — همان منبع intel، همان شکل."""
    g = intel.research.global_market()
    return round(g["usdt_dominance"], 3), round(g["btc_dominance"], 3)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    SERIES.parent.mkdir(parents=True, exist_ok=True)

    u, b = read_level()
    series = load_series()
    series, added = append_point(series, u, b)

    u1, b1 = _delta(series, 60)
    u4, _ = _delta(series, 240)
    ttr = tether_treasury()
    fg = fear_greed()
    macro = macro_window()
    verdict = combined(u1, u4, ttr, fg, macro)

    out = {
        "panel": "پنل فری‌باف ۱",
        "generated": int(time.time() * 1000),
        "level": {"usdt": u, "btc": b},
        "delta_1h": {"usdt": u1, "btc": b1},
        "delta_4h": {"usdt": u4},
        "drivers": {"tether_treasury": ttr, "fear_greed": fg,
                    "macro_48h": macro},
        "verdict": verdict,
        "series_points": len(series),
        "series_added": added,
        "source": "CoinGecko global + Tether Treasury + alternative.me + faireconomy/TV calendar",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    SERIES.write_text(json.dumps(series, separators=(",", ":")))
    print(f"USDT.D={u} (Δ1h={u1}) — {verdict[:80]}…")
    return out


def _delta(series, minutes, tol_ms=1.5 * STEP_MS):
    """دلتای واحد درصد نسبت به نزدیک‌ترین نقطهٔ minutes دقیقه قبل.

    صداقت: اگر سری به آن عقب نمی‌رسد (نزدیک‌ترین نقطه بیش از یک‌ونیم گام
    با هدف فاصله دارد)، جواب None است — دلتای ساخته‌شده از یک نقطهٔ ۳
    ساعت قبل با عنوان «۱ساخیر» همان دروغ خاموشی است که این پروژه بارها
    ازش ضربه خورده."""
    if len(series) < 2:
        return None, None
    now = series[-1]["t"]
    t0 = now - minutes * 60_000
    past = min(series, key=lambda p: abs(p["t"] - t0))
    if abs(past["t"] - t0) > tol_ms:
        return None, None
    return round(series[-1]["u"] - past["u"], 3), \
           round(series[-1]["b"] - past["b"], 3)


if __name__ == "__main__":
    main()
