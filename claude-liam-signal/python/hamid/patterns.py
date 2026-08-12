"""انجین الگوهای کلاسیک — دستور حمید (۱۲ اوت ۲۰۲۶):

    «در صدور سیگنال یکی از انجین‌ها می‌تواند الگوهای شکل‌گرفته را بررسی
    کند و الگوها هم جزو شروط تأثیرگذار باشند؛ ایجنت تمام الگوها را در
    تمام تایم‌فریم‌ها یاد بگیرد و همه را به جدیدترین شکل.»

کشف کاملاً قطعی است (سوینگ‌های فرکتالی همان hamid/structure.py — هیچ
حدسی، هیچ LLMی) و «یادگیری» همان ماشین همیشگی است، نه ادعا: نام الگو و
هم‌جهت/خلاف‌بودنش روی هر معاملهٔ دفتر ثبت می‌شود و شب‌ها paper.reasons با
بوت‌استرپ + تصحیح بونفرونی می‌سنجد که کدام الگو واقعاً برنده از بازنده
جدا می‌کند. الگویی که تیپ پاداشش را قطع کند، در بازسنجی بعدی خودش
می‌افتد — «جدیدترین شکل» یعنی همین: هر شب از نو اندازه‌گیری می‌شود.

صداقت: تلورانس‌ها از ATR خودِ سری‌اند؛ الگوی کهنه (قله/کفِ آخرش دورتر از
FRESH کندل) گزارش نمی‌شود؛ و اگر تایم‌فریم‌ها الگوی متضاد بدهند، جواب
«تعارض» است نه انتخابِ دلبخواه یکی‌شان.

    python3 -m hamid.test_patterns
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid.structure import swings, atr, _fit                 # noqa: E402

FRESH = 24            # قله/کف پایانی الگو حداکثر این تعداد کندل قبل


def _tol(cd):
    return max(atr(cd) * 0.6, cd[-1]["c"] * 0.001)


def _valley(cd, i1, i2):
    return min(c["l"] for c in cd[i1:i2 + 1])


def _peak(cd, i1, i2):
    return max(c["h"] for c in cd[i1:i2 + 1])


def _mk(name, fa, bias, last_i, n, key, confirmed):
    return {"name": name, "fa": fa, "bias": bias,
            "age": n - 1 - last_i, "key": round(key, 10),
            "status": "confirmed" if confirmed else "forming"}


def _double(cd, sw, tol, n, px):
    """سقف/کف دوقلو — دو قلهٔ هم‌قد با درهٔ معنادار بینشان.

    قید صداقت (از کنترل نویز): قله‌ها باید اکسترممِ پنجرهٔ اخیر باشند.
    گشت تصادفی وسطِ رنج مدام «دو قلهٔ هم‌قد» می‌سازد؛ سقف دوقلوی واقعی
    سقفِ خودِ بازار است، نه دو تپهٔ اتفاقی در میانه."""
    out = []
    hi = [s for s in sw if s.kind == "high"]
    lo = [s for s in sw if s.kind == "low"]
    win = cd[-70:]
    wh, wl = max(c["h"] for c in win), min(c["l"] for c in win)
    if len(hi) >= 2:
        a, b = hi[-2], hi[-1]
        if (abs(a.price - b.price) <= tol * 0.9 and b.i - a.i >= 5
                and n - 1 - b.i <= FRESH
                and max(a.price, b.price) >= wh - tol):
            neck = _valley(cd, a.i, b.i)
            if min(a.price, b.price) - neck >= 3 * tol and px > neck - 3 * tol:
                out.append(_mk("double_top", "سقف دوقلو", "bear", b.i, n,
                               neck, px < neck))
    if len(lo) >= 2:
        a, b = lo[-2], lo[-1]
        if (abs(a.price - b.price) <= tol * 0.9 and b.i - a.i >= 5
                and n - 1 - b.i <= FRESH
                and min(a.price, b.price) <= wl + tol):
            neck = _peak(cd, a.i, b.i)
            if neck - max(a.price, b.price) >= 3 * tol and px < neck + 3 * tol:
                out.append(_mk("double_bottom", "کف دوقلو", "bull", b.i, n,
                               neck, px > neck))
    return out


def _hns(cd, sw, tol, n, px):
    """سر و شانه و معکوسش — سرِ بلندتر بین دو شانهٔ هم‌قد.

    همان قید صداقت دوقلوها: سر باید اکسترمم پنجرهٔ اخیر باشد."""
    out = []
    hi = [s for s in sw if s.kind == "high"]
    lo = [s for s in sw if s.kind == "low"]
    win = cd[-70:]
    wh, wl = max(c["h"] for c in win), min(c["l"] for c in win)
    if len(hi) >= 3:
        a, h, b = hi[-3], hi[-2], hi[-1]
        if (h.price > a.price + tol and h.price > b.price + tol
                and abs(a.price - b.price) <= 2 * tol and n - 1 - b.i <= FRESH
                and h.price >= wh - tol):
            neck = _valley(cd, a.i, b.i)
            out.append(_mk("head_shoulders", "سر و شانه", "bear", b.i, n,
                           neck, px < neck))
    if len(lo) >= 3:
        a, h, b = lo[-3], lo[-2], lo[-1]
        if (h.price < a.price - tol and h.price < b.price - tol
                and abs(a.price - b.price) <= 2 * tol and n - 1 - b.i <= FRESH
                and h.price <= wl + tol):
            neck = _peak(cd, a.i, b.i)
            out.append(_mk("inv_head_shoulders", "سر و شانهٔ معکوس", "bull",
                           b.i, n, neck, px > neck))
    return out


def _triangles(cd, sw, tol, n, px):
    """مثلث صعودی/نزولی و فشردگی متقارن — از شیب خطوط سوینگ‌های اخیر."""
    start = max(0, n - 70)
    hi = [(s.i, s.price) for s in sw if s.kind == "high" and s.i >= start]
    lo = [(s.i, s.price) for s in sw if s.kind == "low" and s.i >= start]
    if len(hi) < 2 or len(lo) < 2:
        return []
    last_i = max(hi[-1][0], lo[-1][0])
    if n - 1 - last_i > FRESH:
        return []
    fh, fl = _fit(hi), _fit(lo)
    if not fh or not fl:
        return []
    span = max(last_i - min(hi[0][0], lo[0][0]), 1)
    dh, dl = fh[0] * span, fl[0] * span          # جابه‌جایی هر خط در طول الگو
    flat_h, flat_l = abs(dh) <= tol, abs(dl) <= tol
    up_l, dn_h = dl >= 2 * tol, dh <= -2 * tol
    u, l = fh[0] * (n - 1) + fh[1], fl[0] * (n - 1) + fl[1]
    inside = (l - tol) <= px <= (u + tol)
    if not inside:
        return []
    if flat_h and up_l:
        return [_mk("asc_triangle", "مثلث صعودی", "bull", last_i, n, u, False)]
    if flat_l and dn_h:
        return [_mk("desc_triangle", "مثلث نزولی", "bear", last_i, n, l, False)]
    if dn_h and up_l:
        return [_mk("squeeze", "فشردگی متقارن", None, last_i, n, (u + l) / 2,
                    False)]
    return []


def _flag(cd, tol, n, px):
    """پرچم — ضربهٔ قوی و بعد استراحت کم‌عمقِ خلاف جهت."""
    if n < 20:
        return []
    a = atr(cd)
    if not a:
        return []
    imp = cd[-5]["c"] - cd[-13]["c"]
    if abs(imp) < 3.5 * a:
        return []
    pull = px - cd[-5]["c"]
    if imp * pull > 0:                            # استراحت باید خلاف ضربه باشد
        return []
    r = abs(pull) / abs(imp)
    if not (0.05 <= r <= 0.5):
        return []
    bias = "bull" if imp > 0 else "bear"
    return [_mk("flag", "پرچم صعودی" if imp > 0 else "پرچم نزولی", bias,
                n - 1, n, cd[-5]["c"], False)]


def detect(cd):
    """همهٔ الگوهای زندهٔ این سری — لیست خالی یعنی «الگویی نیست»، که جواب
    معتبر و پرتکراری است."""
    n = len(cd)
    if n < 40:
        return []
    sw = swings(cd)
    tol = _tol(cd)
    px = cd[-1]["c"]
    out = []
    out += _double(cd, sw, tol, n, px)
    out += _hns(cd, sw, tol, n, px)
    out += _triangles(cd, sw, tol, n, px)
    out += _flag(cd, tol, n, px)
    return out


def align(pats, direction):
    """نسبت الگوهای جهت‌دار با جهت سیگنال.

    خروجی: ("with"/"against"/None, بهترین الگو یا None). الگوهای متضاد در
    همان تایم‌فریم = None — تعارض را گزارش می‌کنیم، انتخاب نمی‌کنیم."""
    want = "bull" if direction == "LONG" else "bear"
    biased = [p for p in pats if p["bias"] in ("bull", "bear")]
    if not biased:
        return None, None
    rank = lambda p: (p["status"] == "confirmed", -p["age"])   # noqa: E731
    withs = sorted([p for p in biased if p["bias"] == want], key=rank, reverse=True)
    against = sorted([p for p in biased if p["bias"] != want], key=rank, reverse=True)
    if withs and not against:
        return "with", withs[0]
    if against and not withs:
        return "against", against[0]
    return None, None
