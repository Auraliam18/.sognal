"""لگ-کورولیشن — منظور واقعی حمید از «همبستگی ارزهای پامپ‌شده».

نه شمارش رخداد، بلکه همبستگیِ خودِ سری بازده‌ها با تأخیر زمانی: بازدهٔ
سردسته در لحظهٔ t با بازدهٔ کاندیدا در t+k مقایسه می‌شود، برای kهای
مختلف و در دو تایم‌فریم (۱ساعته و ۱۵دقیقه). دنباله‌روی واقعی یعنی:

  · بهترین همبستگی در تأخیر مثبت (کاندیدا بعد از سردسته حرکت می‌کند)
  · و همان همبستگی در تأخیر منفی وجود ندارد (کاندیدا خودش جلوتر نیست)

صداقت آماری: چون روی چند تأخیر × چند ارز جستجو می‌کنیم، آستانه سخت است —
r≥۰.۲ با حداقل ۲۰۰ نقطهٔ هم‌زمان، و برتری روشن بر جهت معکوس. زیر این،
«رابطه» گزارش نمی‌شود؛ نویز با جستجوی کافی همیشه یک عدد قشنگ می‌سازد.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

MS = {"15m": 900_000, "1h": 3_600_000}


def _rets(cd):
    """بازدهٔ هر کندل، کلید = زمان همان کندل."""
    return {cd[i]["t"]: cd[i]["c"] / cd[i - 1]["c"] - 1
            for i in range(1, len(cd)) if cd[i - 1]["c"]}


def _corr(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    if not vx or not vy:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (vx * vy)


def lag_profile(lead_cd, fol_cd, bar_ms, max_lag):
    """r برای هر تأخیر از -max_lag تا +max_lag (مثبت = دنباله‌رو دیرتر)."""
    lr, fr = _rets(lead_cd), _rets(fol_cd)
    prof = {}
    for k in range(-max_lag, max_lag + 1):
        xs, ys = [], []
        for t, r in lr.items():
            f = fr.get(t + k * bar_ms)
            if f is not None:
                xs.append(r)
                ys.append(f)
        if len(xs) >= 200:
            prof[k] = {"r": _corr(xs, ys), "n": len(xs)}
    return prof


def follow_score(lead_cd, fol_cd, tf, max_lag):
    """بهترین شواهد «دنباله‌روی» در یک تایم‌فریم — یا None اگر قانع‌کننده نیست."""
    prof = lag_profile(lead_cd, fol_cd, MS[tf], max_lag)
    if not prof:
        return None
    pos = [(k, v) for k, v in prof.items() if k >= 1]
    neg = [(k, v) for k, v in prof.items() if k <= -1]
    if not pos:
        return None
    bk, bv = max(pos, key=lambda kv: kv[1]["r"])
    best_neg = max((v["r"] for _, v in neg), default=0.0)
    same = prof.get(0, {}).get("r", 0.0)
    # آستانهٔ سخت: r کافی، برتری روشن بر جهت معکوس (خودش سردسته نباشد)
    if bv["r"] < 0.2 or bv["r"] < best_neg + 0.05:
        return None
    return {"tf": tf, "lag_bars": bk, "lag_h": round(bk * MS[tf] / 3600e3, 2),
            "r": round(bv["r"], 3), "n": bv["n"],
            "r_reverse": round(best_neg, 3), "r_same_time": round(same, 3)}


def followers_of(kc, sym, universe, top=5):
    """ارزهایی که طبق لگ-کورولیشنِ گذشته، با تأخیر دنبال sym حرکت می‌کنند.

    دو تایم‌فریم جدا بررسی می‌شود؛ اگر هر دو رابطه را ببینند اعتماد بیشتر
    است و صریح گفته می‌شود."""
    lead_1h = kc.get(sym, "1h", 1000)
    lead_15 = kc.get(sym, "15m", 600)
    out = []
    for other in universe:
        if other == sym:
            continue
        ev = {}
        if len(lead_1h) >= 220:
            s = follow_score(lead_1h, kc.get(other, "1h", 1000), "1h", 12)
            if s:
                ev["1h"] = s
        if len(lead_15) >= 220:
            s = follow_score(lead_15, kc.get(other, "15m", 600), "15m", 16)
            if s:
                ev["15m"] = s
        if not ev:
            continue
        best = max(ev.values(), key=lambda s: s["r"])
        out.append({"symbol": other, "best": best, "both_tf": len(ev) == 2,
                    "evidence": ev})
    out.sort(key=lambda x: -(x["best"]["r"] + (0.1 if x["both_tf"] else 0)))
    return out[:top]


def reason_fa(leader, f):
    """جملهٔ فارسی با عدد برای پیام/دلیل پیک."""
    b = f["best"]
    s = (f"لگ-کورولیشن با {leader}: r={b['r']:+.2f} در {b['tf']} با تأخیر "
         f"~{b['lag_h']}س (n={b['n']})")
    if f["both_tf"]:
        s += " — هر دو تایم‌فریم تأیید می‌کنند"
    return s
