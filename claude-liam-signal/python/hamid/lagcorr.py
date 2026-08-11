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


def market_reaction(btc_1h, sym_1h, threshold=1.0):
    """واکنش تاریخی یک ارز به حرکت‌های بزرگ بیت‌کوین — قانون حمید:

    «وقتی بیت می‌ریزد و ال‌تی‌سی استاپ می‌خورد، ایجنت باید دلیل‌ها را
    لگ-کورولیشنی بررسی کند و به آخرین ریزش قبلی BTC برگردد ببیند آن موقع
    هم ریخته بود یا نه — بعد تصمیم بگیرد.»

    خروجی: حرکت الان BTC، رابطهٔ لگ-کورولیشنی BTC→sym، و رفتار sym در
    آخرین حرکت بزرگ قبلی BTC (در همان پنجرهٔ تأخیر آماری)."""
    if len(btc_1h) < 60 or len(sym_1h) < 60:
        return None
    chg = (btc_1h[-1]["c"] / btc_1h[-2]["c"] - 1) * 100
    fs = follow_score(btc_1h, sym_1h, "1h", 6)
    idx = {c["t"]: k for k, c in enumerate(sym_1h)}
    last = None
    lagb = max(1, int(round(fs["lag_bars"]))) if fs else 1
    # آخرین حرکت بزرگ قبلی BTC — سه کندل آخر (حرکت جاری) شمرده نمی‌شود
    for i in range(len(btc_1h) - 4, 1, -1):
        c = (btc_1h[i]["c"] / btc_1h[i - 1]["c"] - 1) * 100
        if abs(c) >= threshold:
            k = idx.get(btc_1h[i]["t"])
            if k is not None and k + lagb < len(sym_1h):
                sp = (sym_1h[k + lagb]["c"] / sym_1h[k - 1]["c"] - 1) * 100
                last = {"t": btc_1h[i]["t"], "btc_pct": round(c, 1),
                        "sym_pct": round(sp, 1), "lag_h": lagb}
            break
    return {"btc_1h_pct": round(chg, 2), "follow": fs, "last_move": last}


def reaction_fa(sym, mr):
    """جملهٔ فارسی واکنش-بازار — با عدد، برای پیش از سیگنال و پس از استاپ."""
    if not mr:
        return None
    bits = [f"BTC الان {mr['btc_1h_pct']:+}٪/۱س"]
    if mr["follow"]:
        f = mr["follow"]
        bits.append(f"{sym.replace('USDT','')} طبق لگ-کورولیشن (r={f['r']:+.2f}) "
                    f"~{f['lag_h']}س بعد دنبالش می‌رود")
    else:
        bits.append(f"{sym.replace('USDT','')} رابطهٔ لگ-کورولیشنی قانع‌کننده‌ای "
                    "با BTC ندارد")
    if mr["last_move"]:
        lm = mr["last_move"]
        bits.append(f"در حرکت بزرگ قبلی BTC ({lm['btc_pct']:+}٪) این ارز "
                    f"{lm['sym_pct']:+}٪ شد")
    return "؛ ".join(bits)


def reason_fa(leader, f):
    """جملهٔ فارسی با عدد برای پیام/دلیل پیک."""
    b = f["best"]
    s = (f"لگ-کورولیشن با {leader}: r={b['r']:+.2f} در {b['tf']} با تأخیر "
         f"~{b['lag_h']}س (n={b['n']})")
    if f["both_tf"]:
        s += " — هر دو تایم‌فریم تأیید می‌کنند"
    return s
