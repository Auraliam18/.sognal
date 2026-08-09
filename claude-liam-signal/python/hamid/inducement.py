"""استراتژی «ایندوسمنت» — از معاملهٔ NEAR خود حمید، ۱۵ دقیقه، ۹ اوت ۲۰۲۶.

قانون، به زبان خودش: «فقط با یک ایندوسمنت، خلاف جهت، عرضه دور، زیر پولبک
اضافی، ورود نوک شدو.» یعنی برای لانگ:

  ۱. روند ۱۵ دقیقه نزولی است — معامله خلاف جهت است.
  ۲. یک اردر بلاک خرید در کف (همان تعریف همیشگی: بدنه بزرگ‌تر از جمع شدوها).
  ۳. بعد از دور شدن قیمت، یک کف پولبک ساخته می‌شود.
  ۴. دقیقاً «یک» پولبک اضافی آن کف را می‌شکند و شدویش وارد باکس می‌شود ولی
     بدنه بیرون می‌ماند — شکار نقدینگی زیر کف، نه شکست باکس. دو بار سوییپ؟
     ستاپ باطل — نقدینگی قبلاً خورده شده.
  ۵. ورود روی نوک همان شدو؛ استاپ کمی زیرش.
  ۶. «عرضه دور»: نزدیک‌ترین سطح مقاومت معتبر بالای ورود باید دست‌کم دو برابر
     ریسک فاصله داشته باشد — وگرنه جای حرکت نیست و ستاپ رد می‌شود.

برای شورت همه‌چیز آینه است. این استراتژی تا وقتی رکوردش در دفتر کاغذی با
بازهٔ اطمینان بالای صفر تأیید نشود، «سیگنال» نمی‌شود — فقط اندازه گرفته
می‌شود؛ همان قانونی که یک بار جلوی نتیجه‌گیری از تاپه دوستانه را گرفت.
"""
from dataclasses import dataclass

from hamid import orderblock
from hamid.structure import atr, levels, swings, trend


@dataclass
class Inducement:
    dir: str           # "LONG" | "SHORT"
    entry: float       # نوک شدو
    sl: float
    tp1: float
    tp2: float
    ob_low: float
    ob_high: float
    sweep_i: int       # کندل ایندوسمنت
    room_r: float      # فاصلهٔ عرضه/تقاضا به واحد ریسک
    note: str


def _one_sweep_long(cd, ob):
    """دقیقاً یک سوییپ بعد از بلاک: شدو کفِ قبلی را می‌شکند و تا باکس می‌رسد،
    بدنه بیرونِ باکس می‌ماند. «کف قبلی» = پایین‌ترین کفِ بعد از ترک باکس تا
    قبل از همان کندل — همین است که سوییپ‌شدنش یعنی شکار نقدینگی پولبک."""
    start = ob.i + 1
    sweeps = []
    for j in range(start + 3, len(cd)):
        prior_low = min(c["l"] for c in cd[start:j])
        c = cd[j]
        if c["l"] < prior_low and c["l"] <= ob.high and min(c["o"], c["c"]) > ob.mid:
            sweeps.append(j)
    if len(sweeps) != 1:               # «فقط با یک ایندوسمنت»
        return None
    return sweeps[0]


def _one_sweep_short(cd, ob):
    start = ob.i + 1
    sweeps = []
    for j in range(start + 3, len(cd)):
        prior_high = max(c["h"] for c in cd[start:j])
        c = cd[j]
        if c["h"] > prior_high and c["h"] >= ob.low and max(c["o"], c["c"]) < ob.mid:
            sweeps.append(j)
    if len(sweeps) != 1:
        return None
    return sweeps[0]


def _context_dir(c15, a, lookback=96):
    """«خلاف جهت» یعنی زمینهٔ بزرگ، نه سه چرخش آخر — ورودِ این الگو همیشه بعد
    از شروع برگشت است و چرخش‌های آخر به‌طبع «بالا» می‌خوانند. پس زمینه با
    ترکیب trend و رانش خالص پنجرهٔ بلند تعیین می‌شود."""
    t = trend(c15)
    if t in ("up", "down"):
        return t
    span = c15[-lookback:] if len(c15) > lookback else c15
    net = span[-1]["c"] - span[0]["c"]
    if a and abs(net) > 3 * a:
        return "down" if net < 0 else "up"
    return "range"


def find(c15, max_age_bars=8, min_room_r=2.0):
    """ستاپ ایندوسمنت روی ۱۵ دقیقه، اگر همین حالا زنده باشد."""
    if len(c15) < 120:
        return None
    a = atr(c15)
    if not a:
        return None
    t15 = _context_dir(c15, a)
    out = []
    if t15 == "down":                  # خلاف جهت → لانگ
        for ob in orderblock.find(c15, "bullish"):
            if ob.consumed:
                continue
            i = _one_sweep_long(c15, ob)
            if i is None or len(c15) - 1 - i > max_age_bars:
                continue
            sweep = c15[i]
            entry = sweep["l"] + 0.25 * (min(sweep["o"], sweep["c"]) - sweep["l"])
            sl = sweep["l"] - 0.3 * a
            risk = entry - sl
            if risk <= 0:
                continue
            # «عرضه دور» — نزدیک‌ترین مقاومت معتبر بالای ورود
            res = [l for l in levels(c15) if l.valid and l.price > entry * 1.001]
            res.sort(key=lambda l: l.price)
            if res:
                room = (res[0].price - entry) / risk
                tp1, tp2 = res[0].price, (res[1].price if len(res) > 1 else res[0].price)
            else:
                room, tp1, tp2 = 99.0, entry + 2 * risk, entry + 3 * risk
            if room < min_room_r:
                continue               # عرضه نزدیک است — جای حرکت نیست
            out.append(Inducement("LONG", round(entry, 10), round(sl, 10),
                                  round(tp1, 10), round(tp2, 10),
                                  ob.low, ob.high, i, round(room, 2),
                                  "ایندوسمنت خلاف روند نزولی — سوییپ تکی زیر کف پولبک"))
    elif t15 == "up":                  # آینه: شورت
        for ob in orderblock.find(c15, "bearish"):
            if ob.consumed:
                continue
            i = _one_sweep_short(c15, ob)
            if i is None or len(c15) - 1 - i > max_age_bars:
                continue
            sweep = c15[i]
            entry = sweep["h"] - 0.25 * (sweep["h"] - max(sweep["o"], sweep["c"]))
            sl = sweep["h"] + 0.3 * a
            risk = sl - entry
            if risk <= 0:
                continue
            sup = [l for l in levels(c15) if l.valid and l.price < entry * 0.999]
            sup.sort(key=lambda l: -l.price)
            if sup:
                room = (entry - sup[0].price) / risk
                tp1, tp2 = sup[0].price, (sup[1].price if len(sup) > 1 else sup[0].price)
            else:
                room, tp1, tp2 = 99.0, entry - 2 * risk, entry - 3 * risk
            if room < min_room_r:
                continue
            out.append(Inducement("SHORT", round(entry, 10), round(sl, 10),
                                  round(tp1, 10), round(tp2, 10),
                                  ob.low, ob.high, i, round(room, 2),
                                  "ایندوسمنت خلاف روند صعودی — سوییپ تکی بالای سقف پولبک"))
    # بهترین: نزدیک‌ترین سوییپ به الان
    out.sort(key=lambda x: -x.sweep_i)
    return out[0] if out else None
