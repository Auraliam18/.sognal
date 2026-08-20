# -*- coding: utf-8 -*-
"""AURA IBS META v1.0 — استراتژی IBS + پولبک به‌صورت پایتونِ خوداتکا (متا).

═══════════════════════════════════════════════════════════════════════════
چرا IBS؟ (انتخاب با اندازه‌گیری، نه سلیقه — ۲۰ اوت ۲۰۲۶)
═══════════════════════════════════════════════════════════════════════════
از همهٔ استراتژی‌های پنل، تنها موردی که روی **کندل واقعی** با بازهٔ
اطمینان از صفر رد شده IBS است:

  بک‌تست ۷۰ ارز × ۳۰ روز × ۱۵د:  n=۲۰۹۱ · E=+0.105R · CI [+0.046, +0.171]
  سیگنال‌های زندهٔ ارسالی (sig-ibs، بدون ردیف تکراری):
                                  n=۱۰۴  · E=+0.165R · CI [+0.005, +0.327]

(همان روز کشف شد دفتر معامله ۴۲٪ ردیف تکراری داشت؛ اعداد بالا بعد از
پاک‌سازی‌اند. smc زنده فقط n=۲۱ دارد — نمونه کم، حکم ممنوع.)

═══════════════════════════════════════════════════════════════════════════
منطق ورود — مو به مو همان انجین پنل (index.html → ibsPullback)
═══════════════════════════════════════════════════════════════════════════
۱. سوینگ‌ها: فرکتال ۴کندله (سقفی که از ۴ کندلِ هر طرفش بالاتر است).
۲. BOS: از ۱۲ سوینگ آخر، اولین کلوزِ آن‌سوی هر سوینگ؛ فقط BOSِ
   حداکثر ۶۰ کندل پیش معتبر است؛ آخرین BOS ملاک است.
۳. اردر بلاک: آخرین کندلِ مخالف قبل از سوینگِ BOS (تا ۲۵ کندل عقب‌تر).
۴. CHoCH: اولین سوینگِ بعد از BOS (اختیاری — فقط امتیاز).
۵. امتیاز کیفیت: BOS=۲۸ · CHoCH=۲۲ · OB=۲۰ · داخل OB=۲۰ (نزدیک=۸) ·
   کندل رد=۱۰ · تازگی≤۲۰کندل=۸ (≤۴۰=۴). حد صدور: quality ≥ ۵۵.
۶. ورود: داخل OB = قیمت فعلی، وگرنه میانهٔ OB. استاپ: آن‌سوی OB با
   حاشیهٔ ۰.۳٪. TP1 = ورود ± ۱.۵×ریسک · TP2 = ورود ± ۲.۵×ریسک.
   (ریسک و ریوارد هر دو از **ورود** سنجیده می‌شوند — درسِ باگِ R:R=12.92.)

═══════════════════════════════════════════════════════════════════════════
مدیریت پوزیشن — نردبان تریل حمید + قانون جدید نزدیکِ TP2 (دستور ۲۰ اوت)
═══════════════════════════════════════════════════════════════════════════
- ⅓ مسیر تا TP1 رفت → استاپ به سودِ کارمزددار (ورود ± ۰.۱۵٪).
- ⅔ مسیر → استاپ به سطح ⅓.
- TP1 خورد → استاپ به TP1؛ پوزیشن به سمت TP2 ادامه می‌دهد.
- **نزدیک TP2** (پیش‌فرض: ۸۵٪ مسیرِ ورود→TP2) → TP2 برداشته می‌شود و
  استاپ با فاصلهٔ خیلی کم (پیش‌فرض ۰.۳٪) پشت اکسترممِ کندل‌های بسته
  تریل می‌شود — شاید بازار بیشتر از 2.5R بدهد. حالت کلاسیک (خروج روی
  TP2) هم در walk() هست تا این فرضیه **اندازه‌گیری** شود، نه فرض.
- تریل از اکسترمم کندل‌های «قبلی» محاسبه می‌شود — بدون خوش‌بینی
  درون-کندلی. کندلی که هم استاپ هم تارگت را زده = استاپ (بدخیم‌ترین فرض).

═══════════════════════════════════════════════════════════════════════════
ایزوله — قرارداد اجرا برای داشبورد
═══════════════════════════════════════════════════════════════════════════
فقط کتابخانهٔ استاندارد پایتون ۳٫۸+. هیچ import بیرونی، هیچ شبکه،
هیچ فایلِ خانگی. کندل را داشبورد می‌دهد، تصمیم را JSON می‌گیرد:

  کندل: [{"t":ms,"o":..,"h":..,"l":..,"c":..,"v":..}, ...]  (قدیم→جدید، ۱۵د)

  python3 aura_ibs_meta.py signal   --klines candles.json
      → {"signal": {...entry/sl/tp1/tp2/quality...}}  یا  {"signal": null}

  python3 aura_ibs_meta.py step     --klines candles.json --state state.json
      → وضعیت جدید + رویدادها؛ state را خود داشبورد نگه می‌دارد
        (فراخوانی بعد از بسته‌شدن هر کندل — حلقهٔ زندهٔ داشبورد)

  python3 aura_ibs_meta.py backtest --klines candles.json
      → مقایسهٔ دو حالت خروج (کلاسیک TP2 در برابر تریلِ نزدیک-TP2)

  import: from aura_ibs_meta import signal, step, walk

این فایل سفارش واقعی نمی‌فرستد — LIVE_EXECUTION جای دیگری و با تأیید
جداگانه است. خروجی فقط تصمیم است.
"""
from __future__ import annotations

import json
import sys

VERSION = "aura-ibs-meta-1.0"

# ── پارامترها (همه از انجین اصلی؛ تغییرشان یعنی استراتژیِ دیگر) ─────────
SWING_K = 4              # فرکتال ۴کندله
BOS_MAX_AGE = 60         # BOS کهنه‌تر از این تعداد کندل بی‌اعتبار است
OB_LOOKBACK = 25         # جست‌وجوی کندل مخالف قبل از سوینگ
NEAR_OB_PCT = 0.006      # «نزدیک OB» = فاصله از میانه < ۰.۶٪
SL_PAD = 0.003           # حاشیهٔ استاپ آن‌سوی باکس
TP1_R, TP2_R = 1.5, 2.5
QUALITY_MIN = 55         # حد صدور پنل (ibs_qmin)
FEE_PCT = 0.0015         # کارمزد دو سر + لغزش (~۰.۱۵٪) — قانون تریل
FILL_BARS = 48           # مهلت پر شدن سفارش (۱۲ ساعت در ۱۵د)
HOLD_BARS = 192          # حداکثر نگهداری (۴۸ ساعت در ۱۵د)
NEAR_TP2_FRAC = 0.85     # «نزدیک TP2» = این کسر از مسیر ورود→TP2
TIGHT_GAP_PCT = 0.003    # فاصلهٔ تریلِ تنگ پشت اکسترمم (۰.۳٪)


# ── تشخیص ساختار (پورت وفادار ibsDetect* از index.html) ──────────────────

def swings(cd, k=SWING_K):
    out = []
    for i in range(k, len(cd) - k):
        hi = all(cd[i]["h"] > cd[i - j]["h"] and cd[i]["h"] > cd[i + j]["h"]
                 for j in range(1, k + 1))
        lo = all(cd[i]["l"] < cd[i - j]["l"] and cd[i]["l"] < cd[i + j]["l"]
                 for j in range(1, k + 1))
        if hi:
            out.append({"type": "high", "i": i, "price": cd[i]["h"]})
        if lo:
            out.append({"type": "low", "i": i, "price": cd[i]["l"]})
    return out


def last_bos(cd, sw):
    events = []
    for s in sw[-12:]:
        for i in range(s["i"] + 1, len(cd)):
            if s["type"] == "high" and cd[i]["c"] > s["price"]:
                events.append({"type": "bullish_bos", "level": s["price"],
                               "bar": i, "swing": s})
                break
            if s["type"] == "low" and cd[i]["c"] < s["price"]:
                events.append({"type": "bearish_bos", "level": s["price"],
                               "bar": i, "swing": s})
                break
    valid = [e for e in events if len(cd) - 1 - e["bar"] <= BOS_MAX_AGE]
    return valid[-1] if valid else None


def order_block(cd, bos):
    if not bos:
        return None
    lo, hi = max(0, bos["swing"]["i"] - OB_LOOKBACK), bos["swing"]["i"]
    rng = range(hi, lo - 1, -1)
    if bos["type"] == "bearish_bos":                  # آخرین کندل صعودی = عرضه
        for i in rng:
            if cd[i]["c"] > cd[i]["o"]:
                return {"type": "supply", "high": cd[i]["h"], "low": cd[i]["o"],
                        "mid": (cd[i]["h"] + cd[i]["o"]) / 2, "bar": i}
    else:                                             # آخرین کندل نزولی = تقاضا
        for i in rng:
            if cd[i]["c"] < cd[i]["o"]:
                return {"type": "demand", "high": cd[i]["o"], "low": cd[i]["l"],
                        "mid": (cd[i]["o"] + cd[i]["l"]) / 2, "bar": i}
    return None


def choch(cd, bos, sw):
    if not bos:
        return None
    post = [s for s in sw if s["i"] > bos["bar"]]
    want = "high" if bos["type"] == "bearish_bos" else "low"
    for s in post:
        if s["type"] == want:
            return {"type": f"{'bearish' if want == 'high' else 'bullish'}_choch",
                    "level": s["price"], "bar": s["i"]}
    return None


def ibs_value(c):
    """IBS کندل = (کلوز − کف) / (سقف − کف). تأیید است، نه سیگنال مستقل."""
    rng = c["h"] - c["l"]
    return None if rng <= 0 else (c["c"] - c["l"]) / rng


def signal(cd, qmin=QUALITY_MIN):
    """سیگنال روی آخرین کندلِ بسته. None یعنی NO_SIGNAL — تصمیم معتبر.

    فقط تابعِ پنجرهٔ ورودی است (بدون نگاه به آینده)؛ آزمونِ همراهش ثابت
    می‌کند برشِ [0..i] همان جواب لحظهٔ i را می‌دهد."""
    if not cd or len(cd) < 60:
        return None
    sw = swings(cd)
    if len(sw) < 4:
        return None
    bos = last_bos(cd, sw)
    if not bos:
        return None
    ob = order_block(cd, bos)
    if not ob:
        return None
    ch = choch(cd, bos, sw)
    cur, last = cd[-1]["c"], cd[-1]
    in_ob = ob["low"] <= cur <= ob["high"]
    near_ob = (not in_ob) and abs(cur - ob["mid"]) / ob["mid"] < NEAR_OB_PCT
    bars_ago = len(cd) - 1 - bos["bar"]
    direction = "SHORT" if bos["type"] == "bearish_bos" else "LONG"
    rej = in_ob and ((direction == "SHORT" and last["c"] < last["o"])
                     or (direction == "LONG" and last["c"] > last["o"]))
    q = (28 + (22 if ch else 0) + 20
         + (20 if in_ob else 8 if near_ob else 0)
         + (10 if rej else 0)
         + (8 if bars_ago <= 20 else 4 if bars_ago <= 40 else 0))
    if q < qmin:
        return None
    entry = cur if in_ob else ob["mid"]
    sl = ob["high"] * (1 + SL_PAD) if direction == "SHORT" else ob["low"] * (1 - SL_PAD)
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    sgn = -1 if direction == "SHORT" else 1
    iv = ibs_value(last)
    return {"strategy": VERSION, "dir": direction,
            "entry": entry, "sl": sl,
            "tp1": entry + sgn * risk * TP1_R,       # تارگت اجباری
            "tp2": entry + sgn * risk * TP2_R,       # تارگت اجباری
            "quality": min(100, q), "in_ob": in_ob, "near_ob": near_ob,
            "choch": bool(ch), "rej_candle": rej, "bars_since_bos": bars_ago,
            "ibs": round(iv, 3) if iv is not None else None,
            "ibs_confirms": (iv is not None
                             and ((direction == "LONG" and iv <= 0.30)
                                  or (direction == "SHORT" and iv >= 0.70))),
            "t": cd[-1]["t"]}


# ── مدیریت پوزیشن — ماشین وضعیت خالص (state داخل داشبورد می‌ماند) ────────

def _new_state():
    return {"version": VERSION, "phase": "flat", "position": None}


def step(state, candle, exit_mode="trail_after_tp2"):
    """یک کندلِ بسته را به ماشین وضعیت بده؛ (state جدید، رویدادها) بگیر.

    phase ∈ flat | pending | open. داشبورد بعد از هر کندلِ بسته صدا می‌زند؛
    ترتیب بررسی داخل کندل بدخیم‌ترین است: اول استاپ، بعد تارگت."""
    st = dict(state or _new_state())
    ev = []
    p = dict(st.get("position") or {})

    if st.get("phase") == "pending" and p:
        p["age"] = (p.get("age") or 0) + 1
        if candle["l"] <= p["entry"] <= candle["h"]:
            st["phase"] = "open"
            p.update(filled_t=candle["t"], extremum=p["entry"], age=0)
            ev.append({"event": "FILLED", "entry": p["entry"]})
        elif p["age"] > FILL_BARS:
            st, p = _new_state(), None
            ev.append({"event": "EXPIRED"})
        st["position"] = p
        return st, ev

    if st.get("phase") != "open" or not p:
        return st, ev

    long = p["dir"] == "LONG"
    sgn = 1 if long else -1
    entry, risk = p["entry"], abs(p["entry"] - p["sl0"])

    # ۱) استاپ/تریل با همین کندل؟ (اول استاپ — بدون خوش‌بینی)
    hit_sl = candle["l"] <= p["sl"] if long else candle["h"] >= p["sl"]
    if hit_sl:
        r = (p["sl"] - entry) * sgn / risk
        ev.append({"event": "CLOSED", "outcome": "stop" if r < 0 else "trail",
                   "exit": p["sl"], "R": round(r, 3)})
        return _new_state(), ev

    # ۲) خروج کلاسیک روی TP2 (فقط در حالت مقایسه؛ TP هنوز برداشته نشده)
    if exit_mode == "tp2" and not p.get("tp_removed"):
        hit_tp2 = candle["h"] >= p["tp2"] if long else candle["l"] <= p["tp2"]
        if hit_tp2:
            ev.append({"event": "CLOSED", "outcome": "tp2", "exit": p["tp2"],
                       "R": round((p["tp2"] - entry) * sgn / risk, 3)})
            return _new_state(), ev

    # ۳) مهلت نگهداری
    p["age"] = (p.get("age") or 0) + 1
    if p["age"] > HOLD_BARS:
        r = (candle["c"] - entry) * sgn / risk
        ev.append({"event": "CLOSED", "outcome": "timeout", "exit": candle["c"],
                   "R": round(r, 3)})
        return _new_state(), ev

    # ۴) به‌روزرسانی اکسترمم و نردبان — از کندلِ همین لحظه، برای کندل بعد
    p["extremum"] = (max(p["extremum"], candle["h"]) if long
                     else min(p["extremum"], candle["l"]))
    prog = (p["extremum"] - entry) * sgn / risk       # پیشروی بر حسب R
    tp1_r, tp2_r = TP1_R, TP2_R

    def lift(new_sl, tag):
        if (new_sl - p["sl"]) * sgn > 0:              # استاپ فقط جلو می‌رود
            p["sl"] = new_sl
            ev.append({"event": "SL_MOVED", "to": new_sl, "rule": tag})

    if p.get("tp_removed"):
        # قانون جدید: تریل تنگ پشت اکسترمم — TP دیگر وجود ندارد
        lift(p["extremum"] * (1 - sgn * TIGHT_GAP_PCT), "tight_trail")
    else:
        if prog >= tp2_r * NEAR_TP2_FRAC:
            # دستور حمید ۲۰ اوت: نزدیک TP2 → TP برداشته، تریل تنگ و سریع
            p["tp_removed"] = True
            ev.append({"event": "TP_REMOVED",
                       "rule": f"نزدیک TP2 (≥{NEAR_TP2_FRAC:.0%} مسیر)"})
            lift(p["extremum"] * (1 - sgn * TIGHT_GAP_PCT), "tight_trail")
        elif prog >= tp1_r:
            lift(entry + sgn * risk * tp1_r, "tp1_lock")
        elif prog >= (2 / 3) * tp1_r:
            lift(entry + sgn * risk * tp1_r / 3, "ladder_2_3")
        elif prog >= tp1_r / 3:
            lift(entry * (1 + sgn * FEE_PCT), "ladder_1_3")

    st["position"] = p
    return st, ev


def open_position(setup):
    """از خروجی signal() یک state آمادهٔ step() بساز (سفارش لیمیت pending)."""
    return {"version": VERSION, "phase": "pending",
            "position": {"dir": setup["dir"], "entry": setup["entry"],
                         "sl": setup["sl"], "sl0": setup["sl"],
                         "tp1": setup["tp1"], "tp2": setup["tp2"],
                         "opened_t": setup["t"], "age": 0,
                         "extremum": setup["entry"], "tp_removed": False}}


# ── بک‌تست — همان ماشین وضعیت، روی تاریخ؛ بدون نگاه به آینده ─────────────

def walk(cd, exit_mode="trail_after_tp2", qmin=QUALITY_MIN, step_bars=4):
    """بازپخش: هر step_bars کندل یک بار سیگنال، بعد مدیریت با step().

    همان کد مسیرِ زنده اجرا می‌شود — بک‌تستی که کدِ دیگری را می‌سنجد،
    چیزی را اثبات نمی‌کند."""
    trades, st, i = [], _new_state(), 60
    opened_i = None
    while i < len(cd) - 1:
        if st["phase"] == "flat":
            if (i - 60) % step_bars == 0:
                s = signal(cd[:i + 1], qmin=qmin)
                if s:
                    st = open_position(s)
                    opened_i = i
            i += 1
            continue
        st, evs = step(st, cd[i], exit_mode=exit_mode)
        done = next((e for e in evs if e["event"] in ("CLOSED", "EXPIRED")), None)
        if done:
            if done["event"] == "CLOSED":
                trades.append({"opened": cd[opened_i]["t"], "closed": cd[i]["t"],
                               "R": done["R"], "outcome": done["outcome"],
                               "exit_mode": exit_mode})
            st, opened_i = _new_state(), None
        i += 1
    return trades


def compare(cd, qmin=QUALITY_MIN):
    """فرضیهٔ حمید، اندازه‌گیری‌شده: تریلِ نزدیک-TP2 در برابر خروج کلاسیک TP2."""
    a = walk(cd, "trail_after_tp2", qmin)
    b = walk(cd, "tp2", qmin)

    def agg(ts):
        rs = [t["R"] for t in ts]
        return {"n": len(rs),
                "win_pct": round(100 * sum(1 for r in rs if r > 0) / len(rs), 1) if rs else None,
                "ev_r": round(sum(rs) / len(rs), 3) if rs else None,
                "sum_r": round(sum(rs), 2)}
    return {"trail_after_tp2": agg(a), "classic_tp2": agg(b),
            "note": "حکم فقط با CI روی نمونهٔ بزرگِ چندارزی — این خروجی تک‌سری است"}


# ── CLI برای داشبورد ──────────────────────────────────────────────────────

def main(argv):
    if len(argv) < 2 or argv[1] not in ("signal", "step", "backtest"):
        print(json.dumps({"error": "usage: signal|step|backtest --klines f.json"
                                   " [--state s.json] [--exit-mode m]"}))
        return 2
    args = dict(zip(argv[2::2], argv[3::2]))
    cd = json.load(open(args["--klines"]))
    if argv[1] == "signal":
        print(json.dumps({"signal": signal(cd)}, ensure_ascii=False))
        return 0
    if argv[1] == "backtest":
        print(json.dumps(compare(cd), ensure_ascii=False, indent=1))
        return 0
    state = json.load(open(args["--state"])) if args.get("--state") else _new_state()
    mode = args.get("--exit-mode", "trail_after_tp2")
    if state.get("phase") == "flat":
        s = signal(cd)
        if s:
            state = open_position(s)
            print(json.dumps({"state": state, "events": [
                {"event": "ORDER_PLACED", **{k: s[k] for k in
                 ("dir", "entry", "sl", "tp1", "tp2", "quality")}}]},
                ensure_ascii=False))
            return 0
        print(json.dumps({"state": state, "events": []}, ensure_ascii=False))
        return 0
    state, evs = step(state, cd[-1], exit_mode=mode)
    print(json.dumps({"state": state, "events": evs}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
