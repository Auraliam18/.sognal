"""UT Bot — استراتژی جدید از بخش ایده‌های TradingView (دستور حمید، ۱۸ اوت).

## منبع و اعتبار

«UT Bot Alerts» (نویسندهٔ اصلی: QuantNomad) از پرکاربردترین اسکریپت‌های
متن‌بازِ TradingView است و ده‌ها ایده/استراتژی منتشرشده دور همان هسته
ساخته شده. هسته‌اش **تریلینگ‌استاپ ATR با فلیپ جهت** است — چیزی که ما تا
امروز فقط برای *خروج* داشتیم (نردبان تریل حمید)، نه به‌عنوان *انجین ورود*.
همین «مکانیزم متفاوت» دلیل انتخابش است: با ibs/smc هم‌پوشانی ندارد و
قانون ۷ (استراتژی‌ها مخلوط نمی‌شوند) راحت رعایت می‌شود.

## منطق، مو به مو (همان تعریف اسکریپت اصلی)

خطِ استاپ متحرک `xATRTrailingStop` با فاصلهٔ `nLoss = key × ATR(period)`
از قیمت بسته می‌شود و فقط به نفع پوزیشن می‌خزد:

    اگر src و srcقبلی هر دو بالای استاپ قبلی‌اند:
        stop = max(stopقبلی, src − nLoss)          # لانگ‌مود، فقط بالا می‌رود
    اگر src و srcقبلی هر دو زیر استاپ قبلی‌اند:
        stop = min(stopقبلی, src + nLoss)          # شورت‌مود، فقط پایین می‌آید
    وگرنه (عبور):  stop = src − nLoss  یا  src + nLoss

**فلیپ** یعنی بسته‌شدنِ قیمت آن‌طرفِ خط: فلیپِ رو به بالا = سیگنال خرید،
رو به پایین = فروش. ATR با هموارسازی وایلدر (RMA) است، مثل خود Pine.

## فیلترهایی که ایده‌های منتشرشده کنارش می‌گذارند (و ما هم)

- **EMA200**: لانگ فقط بالای EMA200، شورت فقط زیرش — فیلتر روند بلندمدت،
  هم‌راستا با قانون ۲ خودمان (تایم بالا حاکم است).
- **RSI(14) غیراشباع**: لانگ وقتی RSI < ۷۰، شورت وقتی RSI > ۳۰ — ورود در
  اشباع، دم‌بریدهٔ حرکت است (توصیهٔ خود ایده‌ها).

پیش‌فرض‌ها همان توصیهٔ مستندشده برای کریپتو/۱۵د: key=2، ATR=10.

## خروج — این استراتژی تریل خودش را دارد

استاپ همان خط UT است و هر کندل جابه‌جا می‌شود؛ خروج یا با برخورد به خط
(به قیمتِ خود خط) یا با فلیپِ مخالف (به قیمت بسته). R نسبت به ریسکِ
لحظهٔ ورود (فاصلهٔ ورود تا خطِ همان لحظه) سنجیده می‌شود. تریل داخلی یعنی
ضررِ کامل نادر است ولی بردها هم پله‌ای‌اند — دقیقاً باید اندازه‌گیری شود،
نه فرض (قانون ۰۳: فقط دفتر آزمایش تا وقتی CI حکم بدهد).

## جایگاه در سیستم (قانون ۱۲)

فقط Backtest — به تولید، رتبه‌بندی یا سیگنال هیچ راهی ندارد. رانرش
`hamid/backtest_utbot.py` است و خروجی‌اش در `brain/backtests/utbot-*.json`.
"""
from __future__ import annotations

from dataclasses import dataclass

KEY = 2.0            # ضریب فاصلهٔ استاپ (a در اسکریپت اصلی)
ATR_PERIOD = 10
EMA_PERIOD = 200
RSI_PERIOD = 14
RSI_HI, RSI_LO = 70.0, 30.0


def _wilder(series, period, seed_avg=True):
    """هموارسازی وایلدر (RMA) — همان تعریفی که ATR و RSI پاین استفاده می‌کند."""
    out, avg = [], None
    for i, v in enumerate(series):
        if avg is None:
            if seed_avg and i + 1 >= period:
                avg = sum(series[i + 1 - period:i + 1]) / period
            out.append(avg)
            continue
        avg = (avg * (period - 1) + v) / period
        out.append(avg)
    return out


def atr_series(cd, period=ATR_PERIOD):
    trs = []
    for i, c in enumerate(cd):
        if i == 0:
            trs.append(c["h"] - c["l"])
            continue
        pc = cd[i - 1]["c"]
        trs.append(max(c["h"] - c["l"], abs(c["h"] - pc), abs(c["l"] - pc)))
    return _wilder(trs, period)


def ema_series(cd, period=EMA_PERIOD):
    out, k, e = [], 2 / (period + 1), None
    for i, c in enumerate(cd):
        px = c["c"]
        if e is None:
            if i + 1 >= period:
                e = sum(x["c"] for x in cd[i + 1 - period:i + 1]) / period
            out.append(e)
            continue
        e = px * k + e * (1 - k)
        out.append(e)
    return out


def rsi_series(cd, period=RSI_PERIOD):
    gains, losses = [0.0], [0.0]
    for i in range(1, len(cd)):
        d = cd[i]["c"] - cd[i - 1]["c"]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = _wilder(gains, period)
    al = _wilder(losses, period)
    out = []
    for g, l in zip(ag, al):
        if g is None or l is None:
            out.append(None)
        elif l == 0:
            out.append(100.0)
        else:
            out.append(100 - 100 / (1 + g / l))
    return out


def trail_series(cd, key=KEY, atr_period=ATR_PERIOD):
    """خط UT و جهت هر کندل. dir: +1 قیمت بالای خط، -1 زیر خط، None هنوز داده کم."""
    atrs = atr_series(cd, atr_period)
    stops, dirs = [], []
    prev_stop = None
    for i, c in enumerate(cd):
        a = atrs[i]
        if a is None:
            stops.append(None)
            dirs.append(None)
            continue
        n_loss = key * a
        src, psrc = c["c"], cd[i - 1]["c"] if i else c["c"]
        if prev_stop is None:
            stop = src - n_loss
        elif src > prev_stop and psrc > prev_stop:
            stop = max(prev_stop, src - n_loss)
        elif src < prev_stop and psrc < prev_stop:
            stop = min(prev_stop, src + n_loss)
        elif src > prev_stop:
            stop = src - n_loss
        else:
            stop = src + n_loss
        stops.append(stop)
        dirs.append(1 if src > stop else -1)
        prev_stop = stop
    return stops, dirs


@dataclass
class Setup:
    dir: str
    entry: float
    sl: float
    i: int               # اندیس کندل سیگنال داخل پنجره
    why: dict


def signal(window, key=KEY, atr_period=ATR_PERIOD, use_filters=True):
    """سیگنال روی **آخرین** کندل پنجره، فقط با گذشته. None یعنی هیچ.

    بدون look-ahead به معنای دقیق: خروجی فقط تابع window است؛ آزمونش در
    test_strat_utbot ثابت می‌کند افزودن آینده، گذشته را عوض نمی‌کند.
    """
    n = len(window)
    if n < max(EMA_PERIOD + 5, atr_period + 5):
        return None
    stops, dirs = trail_series(window, key, atr_period)
    i = n - 1
    if dirs[i] is None or dirs[i - 1] is None:
        return None
    if dirs[i] == dirs[i - 1]:
        return None                                   # فلیپ نیست
    long = dirs[i] > 0
    px, sl = window[i]["c"], stops[i]
    if (long and sl >= px) or (not long and sl <= px):
        return None
    why = {"stage": "utbot", "strategy": "utbot", "key": key,
           "atr_period": atr_period}
    if use_filters:
        ema = ema_series(window)[i]
        rsi = rsi_series(window)[i]
        if ema is None or rsi is None:
            return None                               # قانون ۱: دادهٔ ناقص = هیچ
        if long and (px < ema or rsi >= RSI_HI):
            return None
        if not long and (px > ema or rsi <= RSI_LO):
            return None
        why.update(ema200_side="above" if px > ema else "below",
                   rsi=round(rsi, 1))
    return Setup("LONG" if long else "SHORT", px, sl, i, why)


def walk(cd, key=KEY, atr_period=ATR_PERIOD, use_filters=True, max_hold=192):
    """بازپخش کل سری: ورود روی فلیپ، خروجِ خودِ استراتژی (خط UT یا فلیپ مخالف).

    قواعد سخت:
    - تصمیمِ کندل i فقط پنجرهٔ [0..i] را می‌بیند (signal روی برش).
    - برخورد به خط داخل کندل = خروج به قیمت خط؛ اگر کندل هم خط را زده
      باشد هم فلیپ داده باشد، **بدخیم‌ترین فرض**: خروجِ خط.
    - R نسبت به ریسک لحظهٔ ورود.
    """
    # بازگشتِ خط UT «علّی» است: مقدار هر کندل فقط از گذشته می‌آید، پس
    # محاسبهٔ یک‌بار روی کل سری با محاسبهٔ برش‌به‌برش هم‌ارز است — آزمون
    # «تک‌گذر = برش‌به‌برش» در test_strat_utbot همین را اثبات می‌کند و
    # بازپخش را از O(n²) به O(n) می‌رساند (لازمهٔ بک‌تست ۲۰۰۰کندلی×۴۰ ارز).
    stops_full, dirs_full = trail_series(cd, key, atr_period)
    emas = ema_series(cd) if use_filters else None
    rsis = rsi_series(cd) if use_filters else None
    trades = []
    warm = max(EMA_PERIOD + 5, atr_period + 5)
    i = warm
    while i < len(cd) - 2:
        d_now, d_prev = dirs_full[i], dirs_full[i - 1]
        if d_now is None or d_prev is None or d_now == d_prev:
            i += 1
            continue
        long = d_now > 0
        px, sl = cd[i]["c"], stops_full[i]
        if (long and sl >= px) or (not long and sl <= px):
            i += 1
            continue
        if use_filters:
            ema, rsi = emas[i], rsis[i]
            if (ema is None or rsi is None
                    or (long and (px < ema or rsi >= RSI_HI))
                    or (not long and (px > ema or rsi <= RSI_LO))):
                i += 1
                continue
        s = Setup("LONG" if long else "SHORT", px, sl, i,
                  {"stage": "utbot", "strategy": "utbot", "key": key,
                   "atr_period": atr_period})
        entry, risk = s.entry, abs(s.entry - s.sl)
        exit_px, why_exit, j = None, None, i
        for j in range(i + 1, min(i + 1 + max_hold, len(cd))):
            line = stops_full[j - 1]                  # خطِ بستهٔ کندل قبل
            c = cd[j]
            hit = (c["l"] <= line) if long else (c["h"] >= line)
            if hit:
                exit_px, why_exit = line, "trail_line"
                break
            if dirs_full[j] is not None and dirs_full[j] != (1 if long else -1):
                exit_px, why_exit = c["c"], "flip"
                break
        if exit_px is None:
            j = min(i + max_hold, len(cd) - 1)
            exit_px, why_exit = cd[j]["c"], "timeout"
        r = ((exit_px - entry) if long else (entry - exit_px)) / risk
        trades.append({"sym": None, "dir": s.dir, "entry": entry, "sl": s.sl,
                       "exit": exit_px, "R": round(r, 3), "outcome": why_exit,
                       "opened": cd[i]["t"], "closed": cd[j]["t"],
                       "hold_bars": j - i, "why": s.why})
        i = j + 1
    return trades
