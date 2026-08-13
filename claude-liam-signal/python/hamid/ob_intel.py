"""هوش اردر بلاک LIAM — لایهٔ عددیِ قطعی ایجنت ORDER-BLOCK-INTELLIGENCE.

مأموریت (سند حمید، ۱۳ اوت): DETECT → VALIDATE → CLASSIFY → SCORE → TRACK
→ INVALIDATE → LEARN. هدف «کمترین و باکیفیت‌ترین اردر بلاک‌های ساختاری،
قبل از رسیدن قیمت» است — نه برچسب‌زدن هر کندل مخالف.

روی بدنهٔ hamid/orderblocks (روش خود حمید: کندل بدنه>شدو قبل از حرکت،
امتداد باکس، شمارش واکنش/هانت/شکست) این لایه‌ها اضافه می‌شود:

  · اعتبارسنجی ساختاری: displacement واقعی، BOS معنادار، ساخت FVG،
    سوییپ نقدینگی قبل از باکس، مکان (premium/discount)، حجم
  · ماشین وضعیت: CANDIDATE/FRESH/TOUCHED/REACTION_CONFIRMED/WEAKENED/
    PARTIALLY_MITIGATED/MITIGATED/CONSUMED/BREAKER/INVALIDATED
  · کیفیت میتیگیشن هر بازدید: WICK/SHALLOW/MIDPOINT/DEEP/BODY_INSIDE/FULL
  · امتیاز مدرک‌محور + گرید A_PLUS/A/B/C/REJECT + «چرا معتبر است» فارسی
  · بریکر: باکسِ شکسته‌ای که از سمت مقابل واکنش گرفته
  · رادار چند-تایم‌فریم (4H راهبردی > 1H عملیاتی > 15M ستاپ) + تودرتو
  · رویداد داخلی OB_APPROACHING برای ارکستراتور — سیگنال معاملاتی نیست
  · ثبت مشاهدات append-only برای یادگیری آماری (بدون نتیجه‌گیری زودهنگام)

وزن‌های امتیاز عمداً «اکتشافی و موقت»اند (بند ۱۳ سند): قانونِ عمل
نمی‌شوند تا ماشین بونفرونی/بک‌تست تأییدشان کند. هیچ قانون تست‌نشده‌ای
مستقیم وارد تولید نمی‌شود — این فایل فقط اندازه می‌گیرد و گزارش می‌دهد.

    python3 -m hamid.ob_intel --symbols 40      # رادار → signals/ob-radar.json
    python3 -m hamid.test_ob_intel              # آزمون آفلاین
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import orderblocks as obm                          # noqa: E402
from hamid.structure import atr                               # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "ob-radar.json"
OBS = ROOT / "brain" / "ob" / "observations.jsonl"

GRADE_ORDER = ["A_PLUS", "A", "B", "C", "REJECT"]


# ── شواهد ساختاری ──────────────────────────────────────────────────────────

def fvg_after(cd, i, direction, span=6):
    """آیا حرکتِ بعد از باکس، گپ سه‌کندلی (FVG) هم‌جهت ساخته؟

    کف اندازه: گپ ≥ ۰.۳×ATR — گپ مویی، ناکارایی نیست؛ نویزِ ویک است."""
    amin = 0.3 * (_full_atr_local(cd) or 1e-12)
    for j in range(i + 1, min(len(cd) - 1, i + span)):
        a, c = cd[j - 1], cd[j + 1]
        if direction == "down" and a["l"] - c["h"] >= amin:
            return {"low": round(c["h"], 10), "high": round(a["l"], 10), "i": j}
        if direction == "up" and c["l"] - a["h"] >= amin:
            return {"low": round(a["h"], 10), "high": round(c["l"], 10), "i": j}
    return None


def swept_before(cd, i, direction, look=12, prior_n=20):
    """قبل از باکس، نقدینگیِ سوینگ قبلی با ویک برداشته شده و قیمت برگشته؟

    برای OB نزولی (سقف): ویکِ بالای سقفِ قبلی + بستنِ زیر آن (سوییپ خرید)؛
    قرینه برای صعودی. قید صداقت (از کنترل نویز): نفوذ باید ≥۰.۴×ATR از
    اکسترمم قبلی رد شود و بسته‌شدن ≥۰.۲×ATR برگشته باشد — لمسِ مویی
    اکسترمم در نویز هم مدام رخ می‌دهد و «سوییپ» نیست."""
    lo_w = max(0, i - look)
    win = cd[lo_w:i + 1]
    prior = cd[max(0, lo_w - prior_n):lo_w]
    if len(prior) < 5 or not win:
        return False
    a = _full_atr_local(cd) or 1e-12
    if direction == "down":
        ph = max(x["h"] for x in prior)
        return any(x["h"] > ph + 0.4 * a and x["c"] < ph - 0.2 * a for x in win)
    pl = min(x["l"] for x in prior)
    return any(x["l"] < pl - 0.4 * a and x["c"] > pl + 0.2 * a for x in win)


def _full_atr_local(cd):
    trs = [max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - cd[i - 1]["c"]),
               abs(cd[i]["l"] - cd[i - 1]["c"])) for i in range(1, len(cd))]
    return sum(trs) / len(trs) if trs else 0.0


def bos_after(cd, i, direction, span=15, prior_n=30):
    """حرکتِ برخاسته از باکس، سوینگ معنادار قبلی را با «بستن» شکسته؟"""
    prior = cd[max(0, i - prior_n):i]
    aft = cd[i + 1:min(len(cd), i + 1 + span)]
    if len(prior) < 5 or not aft:
        return False
    if direction == "down":
        pl = min(x["l"] for x in prior)
        return min(x["c"] for x in aft) < pl
    ph = max(x["h"] for x in prior)
    return max(x["c"] for x in aft) > ph


def location_of(cd, b):
    """مکان باکس در رنج پنجره — OB وسطِ رنج بی‌معنا کم‌ارزش است (بند ۷)."""
    lo = min(c["l"] for c in cd)
    hi = max(c["h"] for c in cd)
    mid = (b["low"] + b["high"]) / 2
    pos = (mid - lo) / max(hi - lo, 1e-12)
    zone = "discount" if pos < 0.4 else ("premium" if pos > 0.6 else "equilibrium")
    good = (b["move"] == "up" and zone == "discount") or \
           (b["move"] == "down" and zone == "premium")
    return zone, good, round(pos, 2)


def vol_z_at(cd, i, look=20):
    lo = max(0, i - look)
    vols = [c["v"] for c in cd[lo:i]]
    if len(vols) < 5:
        return 0.0
    mv = sum(vols) / len(vols)
    sd = (sum((v - mv) ** 2 for v in vols) / len(vols)) ** 0.5
    if sd:
        return round((cd[i]["v"] - mv) / sd, 1)
    # حجم پایهٔ کاملاً ثابت: نسبت، جای z — جهش واقعی نباید نامرئی شود
    return 9.9 if mv > 0 and cd[i]["v"] >= 2 * mv else 0.0


# ── کیفیت میتیگیشن (بند ۱۱) ────────────────────────────────────────────────

def mitigation_visits(cd, b):
    """هر بازدید از باکس، بر اساس عمق نفوذ و نوع بسته‌شدن طبقه‌بندی می‌شود."""
    lo, hi = b["low"], b["high"]
    h = max(hi - lo, 1e-12)
    out, in_visit = [], False
    deepest, closed_in, closed_through = 0.0, False, False
    for c in cd[b["i"] + 3:]:
        touching = not (c["l"] > hi or c["h"] < lo)
        if touching:
            if b["move"] == "down":                   # باکس بالا — نفوذ از پایین
                depth = (c["h"] - lo) / h
                if c["c"] > hi:
                    closed_through = True
            else:
                depth = (hi - c["l"]) / h
                if c["c"] < lo:
                    closed_through = True
            deepest = max(deepest, min(depth, 1.0))
            if lo <= c["c"] <= hi:
                closed_in = True
            in_visit = True
        elif in_visit:
            out.append(_classify_visit(deepest, closed_in, closed_through))
            in_visit, deepest, closed_in, closed_through = False, 0.0, False, False
    if in_visit:
        out.append(_classify_visit(deepest, closed_in, closed_through))
    return out


def _classify_visit(depth, closed_in, closed_through):
    if closed_through:
        return "FULL_CONSUMPTION"
    if closed_in:
        return "BODY_CLOSE_INSIDE"
    if depth >= 0.75:
        return "DEEP_MITIGATION"
    if depth >= 0.4:
        return "MIDPOINT_TOUCH"
    if depth >= 0.15:
        return "SHALLOW_TOUCH"
    return "WICK_PENETRATION"


# ── ماشین وضعیت (بند ۵) ────────────────────────────────────────────────────

def _breaker_check(cd, b):
    """باکس شکسته که از سمت مقابل برگشت گرفته = BREAKER (بند ۱۹)."""
    if not b.get("broken"):
        return False
    role2 = "up" if b["move"] == "down" else "down"
    start = b.get("broken_at") or b["i"]
    _, r2, _, _ = obm._score_box(cd, b["low"], b["high"], start, role=role2)
    return r2 >= 1


def state_of(cd, b, visits):
    if b.get("broken"):
        if _breaker_check(cd, b):
            return "BREAKER"
        return "INVALIDATED"
    if "FULL_CONSUMPTION" in visits or visits.count("BODY_CLOSE_INSIDE") >= 2:
        return "CONSUMED"
    if b["touches"] >= 4 or (b["hunts"] >= 2 and b["reactions"] <= 1):
        return "WEAKENED"
    if any(v in ("DEEP_MITIGATION", "BODY_CLOSE_INSIDE") for v in visits):
        return "MITIGATED" if b["reactions"] == 0 else "REACTION_CONFIRMED"
    if any(v in ("MIDPOINT_TOUCH", "SHALLOW_TOUCH") for v in visits):
        return "PARTIALLY_MITIGATED" if b["reactions"] == 0 else "REACTION_CONFIRMED"
    if b["reactions"] >= 1:
        return "REACTION_CONFIRMED"
    if b["touches"] >= 1:
        return "TOUCHED"
    if b["fresh"]:
        return "FRESH"
    return "CANDIDATE"


# ── امتیاز و گرید (بند ۱۳-۱۴) — وزن‌ها اکتشافی، نه قانون ───────────────────

def score(cd, b):
    """امتیاز مدرک‌محور + دلایل فارسی — بند ۱۴ سند: «باکس باکیفیت باید چند
    عامل مستقل داشته باشد؛ کندلِ چشم‌گیرِ بدون تأیید ساختاری، رد».

    گرید از «تعداد گروه‌های مدرک مستقل» می‌آید، نه جمع خام امتیاز — نسخهٔ
    جمع خام روی گشت تصادفی ۹۵٪ گرید A داد (اندازه‌گیری در تست): ایمپالس +
    BOS + مکان به‌تنهایی روی نویز هم فراوان‌اند. A فقط با ≥۴ گروه که
    دست‌کم یکی‌شان رخداد نقدینگی/ناکارایی (سوییپ یا FVG) باشد."""
    why, s = [], 0.0
    has_disp = b["mag_atr"] >= 4.5
    if b["mag_atr"] >= 6:
        s += 2; why.append(f"دیسپلیسمنت قوی ({b['mag_atr']}×ATR)")
    elif has_disp:
        s += 1; why.append(f"دیسپلیسمنت کافی ({b['mag_atr']}×ATR)")
    has_bos = bos_after(cd, b["i"], b["move"])
    if has_bos:
        s += 2; why.append("حرکتش سوینگ قبلی را با بستن شکست (BOS)")
    fvg = fvg_after(cd, b["i"], b["move"])
    if fvg:
        s += 1.5; why.append("پشت سرش FVG ساخته")
    has_sweep = swept_before(cd, b["i"], b["move"])
    if has_sweep:
        s += 1.5; why.append("قبلش نقدینگی سوینگ قبلی سوییپ شده")
    zone, loc_ok, pos = location_of(cd, b)
    if loc_ok:
        s += 1; why.append(f"مکان درست ({zone})")
    elif zone == "equilibrium":
        why.append("وسط رنج — مکان بی‌مزیت")
    vz = vol_z_at(cd, b["i"])
    if vz >= 1.5:
        s += 1; why.append(f"حجم کندل مبدأ جهش داشت (z={vz})")
    if b["fresh"]:
        s += 1; why.append("تازه — هنوز لمس نشده")
    elif b["reactions"] >= 2:
        s += 1; why.append(f"{b['reactions']} واکنش شمرده‌شده")
    if b["hunts"] >= 2:
        s -= 1; why.append(f"{b['hunts']} بار هانت — فرسوده")
    groups = sum([has_disp, has_bos, bool(fvg), has_sweep, loc_ok, vz >= 1.5])
    if groups <= 1 or s < 2.5:
        grade = "REJECT"
    elif groups >= 5 and bool(fvg) and has_sweep and has_bos:
        grade = "A_PLUS"
    elif groups >= 4 and bool(fvg) and has_sweep:
        # A فقط با «هر دو» رخداد: سوییپ نقدینگی + FVG — ترجیح صریح سند
        # (بند ۳-۴) و تنها ترکیبی که در کنترل نویز کمیاب ماند
        grade = "A"
    elif groups >= 3:
        grade = "B"
    else:
        grade = "C"
    if b["hunts"] >= 2 and grade in ("A_PLUS", "A"):
        grade = "B"                                  # فرسوده، هر قدر خوش‌مدرک
    return {"score": round(s, 1), "grade": grade, "groups": groups,
            "why_fa": why, "fvg": fvg, "zone": zone, "pos": pos, "vol_z": vz}


# ── تحلیل کامل یک سری ──────────────────────────────────────────────────────

def analyze(cd, tf):
    """باکس‌های orderblocks + شکسته‌ها (برای بریکر)، با وضعیت/گرید/شواهد."""
    if len(cd) < 60:
        return []
    px = cd[-1]["c"]
    a = atr(cd) or px * 0.005
    boxes = []
    seen_spans = []
    for imp in obm._impulses(cd):
        j = obm._ob_candle(cd, imp["i"])
        if j is None:
            continue
        lo, hi = cd[j]["l"], cd[j]["h"]
        if hi <= lo:
            continue
        if any(not (hi < s0 or lo > s1) and abs(j - si) < 6
               for s0, s1, si in seen_spans):
            continue
        seen_spans.append((lo, hi, j))
        t, r, hnt, broken_at = obm._score_box(cd, lo, hi, j, role=imp["dir"])
        b = {"tf": tf, "i": j, "t": cd[j]["t"], "low": round(lo, 10),
             "high": round(hi, 10), "move": imp["dir"],
             "mag_atr": imp["mag_atr"], "touches": t, "reactions": r,
             "hunts": hnt, "broken": broken_at is not None,
             "broken_at": broken_at, "fresh": t == 0 and broken_at is None,
             "age": len(cd) - 1 - j}
        visits = mitigation_visits(cd, b)
        b["mitigation"] = visits
        b["state"] = state_of(cd, b, visits)
        b.update(score(cd, b))
        b["mid"] = round((lo + hi) / 2, 10)
        b["dist_atr"] = round(min(abs(px - lo), abs(px - hi)) / a, 2) \
            if not (lo <= px <= hi) else 0.0
        b["inside_now"] = lo <= px <= hi
        boxes.append(b)
    boxes.sort(key=lambda x: (GRADE_ORDER.index(x["grade"]), x["dist_atr"]))
    return boxes


# ── رادار (بند ۱۵-۱۷) ──────────────────────────────────────────────────────

def _nested(maps):
    """باکس‌های تودرتو بین تایم‌فریم‌ها — فقط اگر هم‌پوشان و هم‌مبدأ باشند."""
    out = []
    order = [("4h", "1h"), ("1h", "15m"), ("4h", "15m")]
    for hi_tf, lo_tf in order:
        for H in maps.get(hi_tf, []):
            for L in maps.get(lo_tf, []):
                if H["move"] != L["move"] or H["grade"] == "REJECT" \
                        or L["grade"] == "REJECT":
                    continue
                overlap = min(H["high"], L["high"]) - max(H["low"], L["low"])
                if overlap <= 0:
                    continue
                # هم‌مبدأ: کندل باکس پایینی داخل بازهٔ زمانی کندل بالایی ± یک کندل
                tf_ms = {"4h": 14_400_000, "1h": 3_600_000, "15m": 900_000}
                if abs(L["t"] - H["t"]) <= tf_ms[hi_tf] * 1.5:
                    out.append({"kind": "NESTED_OB_CONFLUENCE",
                                "htf": hi_tf, "ltf": lo_tf, "move": H["move"],
                                "low": max(H["low"], L["low"]),
                                "high": min(H["high"], L["high"])})
    return out


def radar_for(sym, fetch):
    """نقشهٔ اردر بلاک یک نماد — همان ده قلمی که سند بند ۱۶ می‌خواهد.

    fetch(sym, tf, n) -> کندل dict — تزریق‌پذیر برای تست آفلاین."""
    from hamid.lagcorr import _to4h
    c15 = fetch(sym, "15m", 320)
    c1h = fetch(sym, "1h", 320)
    maps = {}
    if len(c15) >= 60:
        maps["15m"] = analyze(c15, "15m")
    if len(c1h) >= 60:
        maps["1h"] = analyze(c1h, "1h")
        c4h = _to4h(c1h)
        if len(c4h) >= 60:
            maps["4h"] = analyze(c4h, "4h")
    px = (c15 or c1h)[-1]["c"]
    allb = [b for tf in maps for b in maps[tf] if b["grade"] != "REJECT"
            and b["state"] not in ("INVALIDATED", "CONSUMED")]
    bull = [b for b in allb if b["move"] == "up" and b["high"] <= px]
    bear = [b for b in allb if b["move"] == "down" and b["low"] >= px]
    htf = [b for b in allb if b["tf"] in ("4h", "1h")]
    fresh = [b for b in allb if b["state"] == "FRESH"]

    def _n(xs):
        return min(xs, key=lambda b: b["dist_atr"]) if xs else None

    def _s(xs):
        return min(xs, key=lambda b: GRADE_ORDER.index(b["grade"])) if xs else None
    nested = _nested(maps)
    near_strong = _n([b for b in allb if b["grade"] in ("A_PLUS", "A")])
    approaching = bool(near_strong and 0 < near_strong["dist_atr"] <= 1.5)
    return {"px": px,
            "nearest_bull_below": _n(bull), "nearest_bear_above": _n(bear),
            "strongest_bull": _s([b for b in allb if b["move"] == "up"]),
            "strongest_bear": _s([b for b in allb if b["move"] == "down"]),
            "nearest_fresh": _n(fresh), "nearest_htf": _n(htf),
            "nested": nested[:3], "n_valid": len(allb),
            "approaching": near_strong if approaching else None}


# ── ثبت مشاهدات برای یادگیری (بند ۲۰-۲۱) — append-only، بدون حکم ──────────

def observe(prev, sym, tf, b):
    """گذار وضعیت نسبت به اجرای قبل → یک ردیف داده. حکم با ماشین آماری است."""
    key = f"{sym}|{tf}|{b['t']}|{b['move']}"
    old = (prev or {}).get(key)
    if old == b["state"]:
        return None
    OBS.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": int(time.time() * 1000), "sym": sym, "tf": tf,
           "low": b["low"], "high": b["high"], "move": b["move"],
           "from": old, "to": b["state"], "grade": b["grade"],
           "score": b["score"], "mag_atr": b["mag_atr"],
           "mitigation": b["mitigation"][-1:] or None}
    with open(OBS, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=40)
    a = ap.parse_args()
    import sources
    from scan import top_by_48h

    def fetch(sym, tf, n):
        try:
            return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4],
                     "v": k[5]} for k in sources.klines(sym, tf, n)]
        except Exception:                            # noqa: BLE001
            return []

    try:
        prev_doc = json.loads(OUT.read_text())
        prev_states = prev_doc.get("states") or {}
    except Exception:                                # noqa: BLE001
        prev_states = {}
    out, states, events = {}, {}, []
    for sym in top_by_48h(a.symbols):
        try:
            r = radar_for(sym, fetch)
        except Exception as e:                       # noqa: BLE001
            print(f"  {sym}: {type(e).__name__}")
            continue
        out[sym] = r
        for slot in ("nearest_bull_below", "nearest_bear_above",
                     "nearest_fresh", "nearest_htf", "approaching"):
            b = r.get(slot)
            if b:
                states[f"{sym}|{b['tf']}|{b['t']}|{b['move']}"] = b["state"]
                observe(prev_states, sym, b["tf"], b)
        if r.get("approaching"):
            b = r["approaching"]
            events.append({"kind": "OB_APPROACHING", "sym": sym,
                           "tf": b["tf"], "grade": b["grade"],
                           "dist_atr": b["dist_atr"],
                           "zone": [b["low"], b["high"]], "move": b["move"]})
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generated": int(time.time() * 1000),
                               "symbols": out, "events": events,
                               "states": states}, ensure_ascii=False))
    print(f"رادار OB: {len(out)} نماد، {len(events)} رویداد OB_APPROACHING")
    # رویداد داخلی برای ارکستراتور — عمداً بدون تلگرام (بند ۱۷: سیگنال نیست)
    if events:
        try:
            import brain
            for e in events[:6]:
                brain.room_log("orchestrator",
                               f"OB_APPROACHING {e['sym']} {e['tf']} "
                               f"{e['grade']} ({e['dist_atr']}×ATR)", "ob")
        except Exception:                            # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
