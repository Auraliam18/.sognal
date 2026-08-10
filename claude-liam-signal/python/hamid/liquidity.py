"""نقشهٔ نقدینگی — تخمین هیت‌مپ لیکوییدیتی از خود کندل، بدون سرویس پولی.

درسی که ایجنت باید بلد باشد (خواستهٔ حمید — خلاصهٔ آموزش):

هیت‌مپ لیکوییدیتی جایی را نشان می‌دهد که استاپ‌ها و لیکوییدها جمع شده‌اند:
بالای سقف‌های برابر، استاپِ شورت‌ها و بای‌استاپ‌ها خوابیده؛ زیر کف‌های
برابر، استاپ لانگ‌ها. بازار این استخرها را «می‌بیند» و قیمت مثل آهن‌ربا
به سمت استخر بزرگ‌تر کشیده می‌شود؛ بعد از برداشتن نقدینگی هم اغلب
برمی‌گردد (همان سوییپ که در استراتژی ایندوسمنت کد شده). سرویس‌های پولی
این را از دفتر سفارش می‌کشند؛ تخمین صادقانهٔ ما از کندل: اکسترمم‌هایی
که چند بار در همان حوالی لمس شده‌اند = استخر؛ هرچه برخورد بیشتر و
تازه‌تر، استخر سنگین‌تر.

این نقشه فعلاً «سیگنال» را رد یا تأیید نمی‌کند — روی هر معامله ثبت
می‌شود و بک‌تست شبانه می‌سنجد آیا هم‌جهتی با آهن‌ربا واقعاً انتظار را
بالا می‌برد؛ اگر بازهٔ اطمینانش صفر را رد کرد، قانون می‌شود. همان
قاعدهٔ همیشگی: اول اندازه، بعد عمل.
"""
from hamid.structure import swings


def pools(c15, tol=0.0015, lookback=240):
    """استخرهای نقدینگی: خوشه‌های سقف‌ها و کف‌های سوینگ در تلورانس ±tol."""
    cd = c15[-lookback:]
    if len(cd) < 30:
        return {"above": [], "below": []}
    sw = swings(cd)
    highs = [s.price for s in sw if s.kind == "high"]
    lows = [s.price for s in sw if s.kind == "low"]

    def cluster(vals):
        out = []
        for v in sorted(vals):
            if out and abs(v - out[-1]["price"]) <= out[-1]["price"] * tol:
                g = out[-1]
                g["touches"] += 1
                g["price"] = (g["price"] * (g["touches"] - 1) + v) / g["touches"]
            else:
                out.append({"price": v, "touches": 1})
        return [g for g in out if g["touches"] >= 2]

    px = cd[-1]["c"]
    above = [dict(g, price=round(g["price"], 10),
                  dist_pct=round((g["price"] / px - 1) * 100, 2))
             for g in cluster(highs) if g["price"] > px]
    below = [dict(g, price=round(g["price"], 10),
                  dist_pct=round((1 - g["price"] / px) * 100, 2))
             for g in cluster(lows) if g["price"] < px]
    above.sort(key=lambda g: (-g["touches"], g["dist_pct"]))
    below.sort(key=lambda g: (-g["touches"], g["dist_pct"]))
    return {"above": above[:3], "below": below[:3]}


def read(c15, direction=None):
    """خوانش نقشه: آهن‌ربا کدام سمت است، و نسبت به جهت معامله چه حکمی دارد."""
    p = pools(c15)
    near_above = [g for g in p["above"] if g["dist_pct"] <= 2.5]
    near_below = [g for g in p["below"] if g["dist_pct"] <= 2.5]
    wa = sum(g["touches"] for g in near_above)
    wb = sum(g["touches"] for g in near_below)
    if wa > wb and wa >= 3:
        magnet = "above"
    elif wb > wa and wb >= 3:
        magnet = "below"
    else:
        magnet = "balanced"
    side = None
    if direction and magnet != "balanced":
        side = "with" if ((direction == "LONG" and magnet == "above") or
                          (direction == "SHORT" and magnet == "below")) else "against"
    note = None
    if magnet == "above" and near_above:
        g = near_above[0]
        note = (f"نقدینگی سنگین بالای سر: {g['price']:.10g} "
                f"({g['touches']} برخورد، +{g['dist_pct']}٪) — آهن‌ربای قیمت")
    elif magnet == "below" and near_below:
        g = near_below[0]
        note = (f"نقدینگی سنگین زیر پا: {g['price']:.10g} "
                f"({g['touches']} برخورد، −{g['dist_pct']}٪) — آهن‌ربای قیمت")
    return {"above": p["above"], "below": p["below"], "magnet": magnet,
            "side": side, "note": note}
