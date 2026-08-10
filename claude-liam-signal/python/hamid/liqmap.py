"""نقشهٔ لیکوییدیشن — تخمینِ بازتولیدپذیر از کندل واقعی، به سبک نقشهٔ kCEX.

حمید نقشهٔ لیکوییدیشن اپ kCEX را می‌بیند و می‌خواهد تحلیل هم همان را ببیند.
اپ API عمومی ندارد؛ چیزی که می‌شود صادقانه ساخت همان مدلی است که خود این
نقشه‌ها از آن ساخته می‌شوند: هر ساعتِ پرحجم یعنی ورودِ پوزیشن در آن قیمت؛
اهرم‌های رایج (۱۰×، ۲۵×، ۵۰×، ۱۰۰×) نقطهٔ لیکویید هر پوزیشن را مشخص
می‌کنند — لانگِ بازشده در P حوالی P·(1−1/اهرم) لیکویید می‌شود (پایین قیمت)
و شورت حوالی P·(1+1/اهرم) (بالای قیمت). جمعِ حجم‌وزنی این سطح‌ها روی
سطل‌های قیمتی، همان خوشه‌های نقشه است.

این تخمین است، نه دادهٔ صرافی — و همین را در خروجی می‌گوید. ولی هر عددش
از کندل واقعی همان صرافی‌هاست و re-run همان نتیجه را می‌دهد.
"""
LEVERAGE = (10, 25, 50, 100)
# سهم تقریبی هر اهرم از پوزیشن‌ها — اهرم بالاتر رایج‌تر ولی کم‌حجم‌تر
WEIGHT = {10: 1.0, 25: 0.8, 50: 0.6, 100: 0.4}


def build(c1h, look=48, bins=60, span_pct=6.0):
    """خوشه‌های لیکویید بالا و پایین قیمت الان.

    c1h: کندل ساعتی (dict با c/v). خروجی: above/below (خوشه‌های مرتب به
    شدت، نزدیک‌ترین اول) + magnet (سمتی که خوشهٔ بزرگ‌تر دارد)."""
    if len(c1h) < look + 2:
        return None
    px = c1h[-1]["c"]
    lo, hi = px * (1 - span_pct / 100), px * (1 + span_pct / 100)
    step = (hi - lo) / bins
    if step <= 0:
        return None
    heat = [0.0] * bins
    window = c1h[-look:]
    vmax = max(c["v"] for c in window) or 1.0
    for c in window:
        w_vol = c["v"] / vmax
        for lev in LEVERAGE:
            for liq_px in (c["c"] * (1 - 1 / lev),      # لیکویید لانگ‌ها
                           c["c"] * (1 + 1 / lev)):     # لیکویید شورت‌ها
                k = int((liq_px - lo) / step)
                if 0 <= k < bins:
                    heat[k] += w_vol * WEIGHT[lev]
    peak = max(heat) or 1.0
    clusters = []
    for k, h in enumerate(heat):
        if h < peak * 0.35:                              # فقط خوشه‌های واقعی
            continue
        price = lo + (k + 0.5) * step
        clusters.append({"price": round(price, 10),
                         "pct_away": round((price / px - 1) * 100, 2),
                         "score": round(h / peak * 100)})
    above = sorted([c for c in clusters if c["pct_away"] > 0],
                   key=lambda c: c["pct_away"])[:4]
    below = sorted([c for c in clusters if c["pct_away"] < 0],
                   key=lambda c: -c["pct_away"])[:4]
    magnet = None
    sa, sb = sum(c["score"] for c in above), sum(c["score"] for c in below)
    if sa or sb:
        magnet = "above" if sa > sb * 1.3 else ("below" if sb > sa * 1.3 else "balanced")
    return {"price": px, "above": above, "below": below, "magnet": magnet,
            "note": "تخمین از کندل واقعی (حجم × اهرم‌های رایج) — دادهٔ مستقیم صرافی نیست"}


def note(lm, direction=None):
    """یک جملهٔ فارسی برای کپشن سیگنال — فقط وقتی چیزی برای گفتن هست."""
    if not lm:
        return None
    top_a = lm["above"][0] if lm["above"] else None
    top_b = lm["below"][0] if lm["below"] else None
    bits = []
    if top_a:
        bits.append(f"خوشهٔ لیکویید بالا در {top_a['pct_away']:+}٪ (شدت {top_a['score']})")
    if top_b:
        bits.append(f"پایین در {top_b['pct_away']:+}٪ (شدت {top_b['score']})")
    if not bits:
        return None
    s = "🗺 " + " · ".join(bits)
    if direction == "LONG" and lm["magnet"] == "above":
        s += " — آهن‌ربای لیکویید هم‌جهت خرید"
    elif direction == "SHORT" and lm["magnet"] == "below":
        s += " — آهن‌ربای لیکویید هم‌جهت فروش"
    elif direction and lm["magnet"] in ("above", "below"):
        s += " — آهن‌ربای لیکویید خلاف جهت"
    return s
