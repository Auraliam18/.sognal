"""خودآزمایی دروازهٔ روند — python3 -m hamid.test_trend_gate"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import trend_gate as tg                   # noqa: E402


def candles(direction, n=240, base=100.0):
    """کندل مصنوعی با سوینگ واضح. موج ۹تایی (i%9-4) جمعِ صفر دارد، پس
    «رنج» دریفت پنهان نمی‌گیرد — عیب نسخهٔ اول همین بود و trend آن را
    به‌درستی down می‌خواند. down = آینهٔ up حول base."""
    out = []
    p = base
    for i in range(n):
        wave = ((i % 9) - 4) * 0.6                   # جمع هر ۹ گام = صفر
        drift = {"up": 0.35, "down": 0.35, "range": 0.0}[direction] * i
        level = base + drift + wave if direction != "down" else                 base - drift + wave
        level = max(1.0, level)
        out.append({"t": i, "o": level, "h": level + 0.5,
                    "l": level - 0.5, "c": level, "v": 100})
        p = level
    return out


def kget_for(t4, t1):
    def kget(sym, tf, n):
        return candles(t4 if tf == "4h" else t1, n)
    return kget


FULL_EV = {"inOB": True, "swept": True, "choch": True, "fvg": True, "quality": 75}


def run():
    # ۱ — چارت صعودی، سیگنال شورت، بدون تأییدیه → بلاک (عین شکایت حمید)
    a = tg.assess("XUSDT", "SHORT", kget_for("up", "up"), {})
    assert not a["ok"] and a["mode"] == "hard-veto", a
    print("۱ ✅ چارت صعودی + سیگنال SHORT → وتوی مطلق (عین شکایت حمید)")

    # ۲ — چارت نزولی، سیگنال لانگ، حتی با تأییدیهٔ کامل → باز هم وتو
    a = tg.assess("XUSDT", "LONG", kget_for("down", "down"), FULL_EV)
    assert not a["ok"] and a["mode"] == "hard-veto"
    print("۲ ✅ هر دو تایم مخالف: حتی تأییدیهٔ کامل هم عبور نمی‌دهد")

    # ۳ — یک تایم مخالف + تأییدیهٔ ناقص → بلاک با فهرست غایب‌ها
    a = tg.assess("XUSDT", "LONG", kget_for("down", "up"),
                  {"inOB": True, "swept": True, "quality": 75})
    assert not a["ok"] and a["mode"] == "counter-blocked"
    assert "choch" in a["missing"] and "fvg" in a["missing"]
    print(f"۳ ✅ خلاف روند ۴س + تأییدیه ناقص → NO_SIGNAL (غایب: {a['missing']})")

    # ۴ — یک تایم مخالف + تمام تأییدیه‌ها → عبور با برچسب
    a = tg.assess("XUSDT", "LONG", kget_for("down", "up"), FULL_EV)
    assert a["ok"] and a["mode"] == "counter-confirmed"
    assert tg.caption_line(a) and "خلاف روند" in tg.caption_line(a)
    print("۴ ✅ خلاف روند با تمام تأییدیه‌ها → عبور + برچسب روی پیام")

    # ۵ — هم‌راستا → عبور عادی بدون برچسب
    a = tg.assess("XUSDT", "LONG", kget_for("up", "up"), {})
    assert a["ok"] and a["mode"] == "with-trend" and tg.caption_line(a) is None
    print("۵ ✅ هم‌راستا: عبور عادی")

    # ۶ — رنج: مخالفت نیست → عبور (رنج جهت ندارد که نقض شود)
    a = tg.assess("XUSDT", "SHORT", kget_for("range", "range"), {})
    assert a["ok"] and a["mode"] == "with-trend"
    print("۶ ✅ رنج ۴س/۱س: عبور (مخالفتی نیست)")

    # ۷ — دادهٔ ناقص → NO_SIGNAL نه عبور کور (قانون ۱)
    def dead(sym, tf, n): raise TimeoutError
    a = tg.assess("XUSDT", "LONG", dead, {})
    assert not a["ok"] and a["mode"] == "no-data"
    print("۷ ✅ دادهٔ روند در دسترس نیست → NO_SIGNAL (قانون ۱)")

    print("\nهمهٔ ۷ آزمون دروازهٔ روند گذشت")


if __name__ == "__main__":
    run()
