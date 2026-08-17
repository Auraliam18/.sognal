"""دروازهٔ هم‌راستایی با روند — دستور حمید (۱۷ اوت).

مشاهدهٔ او، عین جمله: «بارها دیدم چارت کاملاً صعودی است ولی سیگنال شورت
صادر شده، و برعکس.» ریشه: سلسله‌مراتب ۴س/۱س فقط در امتیاز اثر داشت، نه
به‌صورت وتو در گلوگاه ارسال — سیگنال خلاف روند با امتیازِ جمعیِ خوب رد
می‌شد و می‌رفت.

قانون (مکمل قانون ۲ و ۸ غیرقابل‌مذاکره‌ها):
  هر دو تایم بالا (۴س و ۱س) خلاف جهت سیگنال → وتوی مطلق. هیچ استثنایی.
  یک تایم بالا خلاف جهت → «خلاف روند»: فقط با تمام تأییدیه‌ها می‌گذرد و
  روی پیام برچسب می‌خورد؛ حتی یک تأییدیهٔ غایب → NO_SIGNAL.
  هم‌راستا یا رنج → عبور عادی (بقیهٔ دروازه‌ها سر جایشان‌اند).

تأییدیه‌های کامل خلاف روند (همه لازم‌اند — «تمام تاییدیه‌ها»):
  inOB      قیمت داخل ناحیهٔ معتبر OB
  swept     سوییپ نقدینگی رخ داده (شکار استاپ‌ها پیش از برگشت)
  choch     تغییر کاراکتر ثبت‌شده
  fvg       FVG معتبر در جهت سیگنال
  quality   کیفیت ستاپ ≥ ۷۰

روند هر تایم از structure.trend (سوینگ‌محور، قطعی) با ۲۴۰ کندل.
"""
from hamid.structure import trend

COUNTER_NEEDS = ("inOB", "swept", "choch", "fvg", "quality>=70")
_TF_N = 240


def _opposes(t, direction):
    return (direction == "LONG" and t == "down") or \
           (direction == "SHORT" and t == "up")


def assess(sym, direction, kget, evidence=None):
    """kget(sym, tf, n) -> کندل‌ها. خروجی همیشه دلیل نوشته دارد.

    ok=False یعنی ارسال ممنوع — بی‌استثنا (دستور: عدم تأیید = بدون سیگنال).
    """
    ev = evidence or {}
    out = dict(sym=sym, dir=direction, t4=None, t1=None,
               mode="with-trend", ok=True, missing=[], reason="")
    try:
        c4 = kget(sym, "4h", _TF_N)
        c1 = kget(sym, "1h", _TF_N)
    except Exception as e:                           # noqa: BLE001
        out.update(ok=False, mode="no-data",
                   reason=f"روند ۴س/۱س خواندنی نیست ({type(e).__name__}) — "
                          "دادهٔ ناقص = NO_SIGNAL (قانون ۱)")
        return out
    if len(c4) < 60 or len(c1) < 60:
        out.update(ok=False, mode="no-data",
                   reason="کندل کافی برای حکم روند نیست — NO_SIGNAL")
        return out
    t4, t1 = trend(c4), trend(c1)
    out.update(t4=t4, t1=t1)

    opp4, opp1 = _opposes(t4, direction), _opposes(t1, direction)
    if opp4 and opp1:
        out.update(ok=False, mode="hard-veto",
                   reason=f"هر دو تایم بالا خلاف {direction} است "
                          f"(۴س={t4}، ۱س={t1}) — وتوی مطلق؛ تایم پایین حق "
                          "نقض ساختار بالا را ندارد (قانون ۲)")
        return out
    if opp4 or opp1:
        have, missing = [], []
        for need in COUNTER_NEEDS:
            if need == "quality>=70":
                (have if (ev.get("quality") or 0) >= 70 else missing).append(need)
            else:
                (have if ev.get(need) else missing).append(need)
        if missing:
            out.update(ok=False, mode="counter-blocked", missing=missing,
                       reason=f"خلاف روند {'۴س' if opp4 else '۱س'} "
                              f"({t4 if opp4 else t1}) و تأییدیه ناقص است — "
                              f"غایب: {', '.join(missing)} → NO_SIGNAL "
                              "(قانون: خلاف روند فقط با تمام تأییدیه‌ها)")
        else:
            out.update(mode="counter-confirmed",
                       reason=f"خلاف روند {'۴س' if opp4 else '۱س'} ولی هر "
                              f"{len(COUNTER_NEEDS)} تأییدیه کامل است — عبور "
                              "با برچسب خلاف روند")
        return out
    out["reason"] = f"هم‌راستا (۴س={t4}، ۱س={t1})"
    return out


def caption_line(a):
    """خط کپشن — فقط برای عبورِ خلاف روند؛ قانون ۲ حمید: بدون توضیح ناقص است."""
    if a.get("mode") != "counter-confirmed":
        return None
    return (f"⚠️ خلاف روند (۴س={a['t4']}، ۱س={a['t1']}) — مجاز چون تمام "
            f"تأییدیه‌ها کامل بود: {'، '.join(COUNTER_NEEDS)}")
