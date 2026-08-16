#!/usr/bin/env python3
"""دفتر ترید کاغذی، و یاد گرفتن از دلیل درست.

Hamid: «مهم اینه بعدش بتونی درست نتیجه گیری کنی و بر اساس دلایل درست یاد بگیری».

That second half is the hard part, and it is where this kind of system usually
lies to itself. Recording trades is bookkeeping. Deciding *why* they won is
statistics, and with a dozen recorded conditions and a few dozen trades, several
conditions will look predictive purely by chance. A loop that acts on those
gets worse every cycle while appearing to learn.

So there are two halves here.

**The book.** Signals become pending limit orders, exactly as they would be
placed. A pending order that is never touched expires and is not a trade — the
same rule the backtest enforces, and the one whose absence once turned
34.1% / +0.103R into 58.8% / +0.873R. Filled orders are tracked to their stop or
target and closed with the full context that was true when they were opened.

**The attribution.** Every closed trade carries the conditions at entry. For
each condition the difference in expectancy between trades that had it and
trades that did not is measured with a bootstrap interval — and then corrected
for the fact that many conditions were tested at once. A condition is only
reported as a *reason* if its interval still clears zero after that correction.
Everything else is reported as "not yet distinguishable from luck", which is
usually the honest answer and always the safe one.

    python3 -m hamid.paper --mark          # update open positions
    python3 -m hamid.paper --reasons       # what actually separated winners
"""
import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import brain                                                  # noqa: E402
import sources                                                # noqa: E402

ROOT = HERE.parent.parent.parent
BOOK = ROOT / "brain" / "paper"
OPEN = BOOK / "open.jsonl"
CLOSED = BOOK / "closed.jsonl"
EQUITY = BOOK / "equity.json"

START_BALANCE = 1000.0
RISK_FRACTION = 0.01          # 1% of balance per trade
# تغییر کنترل‌شدهٔ این چرخه، با اندازه‌گیری نه حدس: از ۴۵ سفارش پرشده، میانهٔ
# زمان تا پر شدن ۱٫۷ ساعت بود ولی ۳۸٪ در بازهٔ ۳ تا ۶ ساعت پر شدند و هیچ‌چیز
# بعد از ۶ ساعت «دیده نشد» — چون خود سقف ۶ ساعته مشاهده را می‌بُرید (دادهٔ
# سانسورشده). ستاپ‌های حمید از ساختار ۱ساعته/۴ساعته می‌آیند و ۸۴٪ سفارش‌ها
# منقضی می‌شدند. پنجره ۲۴ ساعت شد؛ پر شدنِ بعد از ۶ ساعت با برچسب late_fill
# ثبت می‌شود تا بازبینی بعدی بسنجد معامله‌های دیرپرشده واقعاً می‌ارزند یا نه —
# اگر EVشان منفی بود، برمی‌گردیم.
FILL_HOURS = 24               # a limit untouched this long is cancelled
HOLD_HOURS = 24               # then closed at market


def _read(p):
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _write(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
                 if rows else "")


def _append(p, row):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def experience_index(min_n=12):
    """کارنامهٔ بسته به تفکیک (ارز، جهت) — ناظرِ چرخه قبل از صدور هر سیگنال
    همین را می‌پرسد. سفارش‌های منقضی معامله نیستند و حساب نمی‌شوند. زیر min_n
    معامله «تاریخچهٔ نازک» است: گزارش می‌شود ولی حق وتو ندارد — قضاوت با
    نمونهٔ کوچک همان اشتباهی است که یک بار ۵۵۷ معامله را نتیجه خواند."""
    idx = {}
    for t in _read(CLOSED):
        if t.get("R") is None or t.get("outcome") == "expired":
            continue
        # داور بیرونی: وتو فقط از دفترهای هم‌جنسِ سیگنال واقعی — تمرینِ
        # دروازه‌شل و آزمایش‌ها (پولبک اول/ایندوسمنت) و وتوشده‌ها معیار
        # منصفانه‌ای برای رد سیگنال واقعی همان ارز نیستند.
        if (t.get("why") or {}).get("stage") in ("practice", "first",
                                                 "inducement", "vetoed", "v2"):
            continue
        idx.setdefault((t["sym"], t["dir"]), []).append(t["R"])
    out = {}
    for k, rs in idx.items():
        n = len(rs)
        out[k] = {"n": n, "mean_r": round(sum(rs) / n, 3),
                  "win_pct": round(100 * sum(1 for r in rs if r > 0) / n, 1),
                  "thin": n < min_n}
    return out


# ── the book ───────────────────────────────────────────────────────────────

def open_from(setups, context):
    """Place the signals as pending limit orders, with their reasons attached.

    The context is snapshotted now, not looked up later. A trade that closes
    tomorrow must be judged against the market that existed when it was opened,
    and re-deriving it afterwards would quietly attribute the outcome to
    conditions that arrived after the decision.
    """
    # کلید یکتایی شامل دفتر (stage) — دفتر v2 همان ستاپ دفتر اصلی را با
    # همان ورود جدا ثبت می‌کند؛ بدون این، v2 هیچ‌وقت پر نمی‌شد.
    have = {(p["sym"], p["entry"], (p.get("why") or {}).get("stage"))
            for p in _read(OPEN)}
    added = 0
    from hamid.universe import STABLES, WRAPPED
    for s in setups:
        # استیبل/رپد وارد هیچ دفتری نمی‌شود — کشف ۱۲ اوت: USD1/USDE با استاپ
        # ذره‌ای، R نجومی قلابی ساختند (+58R) و آمار دفتر را بی‌معنا کردند.
        base = s["symbol"][:-4] if s["symbol"].endswith("USDT") else s["symbol"]
        if base in STABLES or base in WRAPPED:
            continue
        key = (s["symbol"], float(s["entry"]),
               s.get("stage_tag") or ("second" if not s.get("waiting") else "first"))
        if key in have:
            continue
        _append(OPEN, {
            "sym": s["symbol"], "dir": s["dir"],
            "entry": float(s["entry"]), "sl": float(s["sl"]),
            "tp1": float(s["tp1"]), "tp2": float(s.get("tp2") or 0) or None,
            "opened": int(time.time() * 1000),
            "filled": None,
            "why": {
                "trend_4h": s.get("trend_4h"),
                "returns": (s.get("block") or {}).get("returns"),
                "impulse": (s.get("block") or {}).get("impulse"),
                "reactions": (s.get("on_level") or {}).get("reactions"),
                "flipped": (s.get("on_level") or {}).get("flipped"),
                "stop_pct": s.get("stop_pct"),
                "liq": s.get("liq"),
                "tg_msg_id": s.get("tg_msg_id"),
                "dir": s["dir"],
                "stage": s.get("stage_tag") or ("second" if not s.get("waiting") else "first"),
                **context,
            },
        })
        have.add(key)
        added += 1
    if added:
        brain.room_log("paper", f"{added} سفارش لیمیت جدید در دفتر کاغذی", "open")
    return added


def _candles_since(sym, since_ms):
    # پنجرهٔ ثابت ۲۰۰تایی (~۵۰ ساعت) بعد از قطعی رانر تاریخچه را گم می‌کرد و
    # معاملهٔ پرشدهٔ برنده «منقضی» ثبت می‌شد — بازبینی کد. حالا عمق فچ از سنِ
    # خود سفارش می‌آید، با سقف ۱۰۰۰ کندل.
    n = min(1000, max(200, int((time.time() * 1000 - since_ms) / 900000) + 20))
    try:
        rows = sources.klines(sym, "15m", n)
    except Exception:                                # noqa: BLE001 - skip this one
        return []
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4]}
            for k in rows if k[0] >= since_ms]


def mark():
    """Walk every open position forward and close what has resolved."""
    positions = _read(OPEN)
    if not positions:
        print("دفتر باز خالی است")
        return 0, 0
    still, closed = [], 0
    now = time.time() * 1000

    for p in positions:
        cd = _candles_since(p["sym"], p["opened"])
        if not cd:
            # عیب‌یابی ۱۳ اوت: نماد بی‌کندل (دیلیست‌شده یا غایب از منبع) تا
            # ابد در دفتر باز می‌ماند و هر دور دوباره فچ می‌شود — ۲۷ اردر با
            # عمر ۸۴ ساعت پیدا شد. حالا بعد از مهلت، بدون داده هم بسته
            # می‌شود: پرنشده = expired؛ پرشده = no_data با R=None تا آمار را
            # آلوده نکند. اجازهٔ ماندن فقط داخل مهلت است، نه برای همیشه.
            age = now - (p.get("opened") or now)
            if p.get("filled") is None and age > FILL_HOURS * 3600_000:
                p["outcome"] = "expired"
                p["R"] = None
                p["closed"] = int(now)
                _append(CLOSED, p)
                closed += 1
            elif p.get("filled") and now - p["filled"] > 2 * HOLD_HOURS * 3600_000:
                p["outcome"] = "no_data"
                p["R"] = None
                p["closed"] = int(now)
                _append(CLOSED, p)
                closed += 1
            else:
                still.append(p)
            continue
        long = p["dir"] == "LONG"
        risk = abs(p["entry"] - p["sl"])

        if p["filled"] is None:
            for c in cd:
                if c["l"] <= p["entry"] <= c["h"]:
                    p["filled"] = c["t"]
                    # برچسب برای بازبینی: پر شدن بعد از ۶ ساعت — تا اثر باز
                    # کردن پنجره جدا سنجیده شود، نه قاطی کل دفتر.
                    if c["t"] - p["opened"] > 6 * 3600_000:
                        p["late_fill"] = True
                    break
            if p["filled"] is None:
                if now - p["opened"] > FILL_HOURS * 3600_000:
                    # never touched: not a trade, and must not be scored as one
                    p["outcome"] = "expired"
                    p["R"] = None
                    p["closed"] = int(now)
                    _append(CLOSED, p)
                    closed += 1
                else:
                    still.append(p)
                continue

        after = [c for c in cd if c["t"] >= p["filled"]]
        done = None
        # MFE/MAE — منشور LIAM بند ۲۲: هر معامله باید بگوید تا کجا به نفعش
        # رفت و تا کجا علیه‌اش، تا بازبینی بفهمد «جهت درست بود و تایم غلط» یا
        # ورود زود بود — نه فقط برد/باخت خام.
        mfe = mae = 0.0
        end_t = p["filled"]
        # تریل — قانون حمید (EURI درس شد): «هر ارزی که یک‌سوم مسیر تارگت را
        # رفت، استاپ بیاید در سود با حساب کارمزد؛ سود که بالاتر رفت، استاپ هم
        # در سود بیشتر.» نردبان: ⅓ مسیر → استاپ = ورود + کارمزد دو سر؛
        # ⅔ مسیر → استاپ = ⅓ مسیر. تریل از اکسترمم کندل‌های *قبلی* حساب
        # می‌شود، نه همان کندل — محافظه‌کار، بدون خوش‌بینی درون-کندلی.
        tp_dist = abs(p["tp1"] - p["entry"])
        fee_px = p["entry"] * 0.0015              # ~۰.۱٪ کارمزد دو سر + لغزش
        sgn = 1 if long else -1
        sl_eff = p["sl"]
        best = p["entry"]
        for c in after:
            if tp_dist > 0:
                prog = sgn * (best - p["entry"]) / tp_dist
                if prog >= 2 / 3:
                    lvl = p["entry"] + sgn * tp_dist / 3
                elif prog >= 1 / 3:
                    lvl = p["entry"] + sgn * fee_px
                else:
                    lvl = None
                if lvl is not None:
                    sl_eff = max(sl_eff, lvl) if long else min(sl_eff, lvl)
            fav = ((c["h"] - p["entry"]) if long else (p["entry"] - c["l"])) / risk
            adv = ((p["entry"] - c["l"]) if long else (c["h"] - p["entry"])) / risk
            mfe, mae = max(mfe, fav), max(mae, adv)
            end_t = c["t"]
            hit_sl = (c["l"] <= sl_eff) if long else (c["h"] >= sl_eff)
            hit_tp = (c["h"] >= p["tp1"]) if long else (c["l"] <= p["tp1"])
            trailed = (sl_eff > p["sl"]) if long else (sl_eff < p["sl"])
            if hit_sl:                                # هم‌زمانی با تارگت → محافظه‌کار: استاپ اول
                R = sgn * (sl_eff - p["entry"]) / risk if trailed else -1.0
                done = ("trail" if trailed else "stop", R)
                break
            if hit_tp:
                done = ("target", abs(p["tp1"] - p["entry"]) / risk)
                break
            best = max(best, c["h"]) if long else min(best, c["l"])
        if done is None and now - p["filled"] > HOLD_HOURS * 3600_000:
            last = after[-1]["c"] if after else p["entry"]
            R = ((last - p["entry"]) if long else (p["entry"] - last)) / risk
            done = ("timeout", R)
        if done is None:
            if sl_eff != p["sl"]:
                p["sl_eff"] = round(sl_eff, 10)       # تریلِ تا این لحظه، ثبت‌شده
            still.append(p)
            continue

        p["outcome"], p["R"] = done[0], round(done[1], 4)
        if sl_eff != p["sl"]:
            p["sl_eff"] = round(sl_eff, 10)
        p["mfe_r"], p["mae_r"] = round(mfe, 3), round(mae, 3)
        p["held_h"] = round((end_t - p["filled"]) / 3600e3, 1)
        # R خالص با کارمزد+لغزش ~۰.۰۵٪ هر طرف — روی استاپ تنگ چند دهم R است
        try:
            fee_r = 0.001 * p["entry"] / abs(p["entry"] - p["sl"])
            p["fee_r"] = round(fee_r, 4)
            p["R_net"] = round(p["R"] - fee_r, 4)
        except Exception:                            # noqa: BLE001
            pass
        p["closed"] = int(now)
        _append(CLOSED, p)
        closed += 1
        brain.room_log("paper", f"{p['sym']} {p['dir']} بسته شد: "
                                f"{p['outcome']} {p['R']:+.2f}R", "close")

    _write(OPEN, still)
    _equity()
    print(f"{len(still)} پوزیشن باز، {closed} بسته شد")
    return len(still), closed


def _equity():
    """Fixed-fractional balance from the closed book. Expired orders contribute
    nothing, because they were never trades.

    Two lines, kept apart on purpose. The book now also records first-pullback
    entries as experiments so the learning loop can measure Hamid's own rule
    («منتظر پولبک دومش می‌مانم») instead of assuming it — but those were never
    signalled to him, and mixing them into the headline balance would make the
    signalled strategy's record unreadable. `balance` is the signalled trades
    only; the experiments get their own line.
    """
    def run_book(trades):
        bal, peak, dd, n, wins = START_BALANCE, START_BALANCE, 0.0, 0, 0
        for t in trades:
            if t.get("R") is None:
                continue
            bal += bal * RISK_FRACTION * t["R"]
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak)
            n += 1
            wins += 1 if t["R"] > 0 else 0
        return {"balance": round(bal, 2), "trades": n,
                "win_pct": round(wins / n * 100, 1) if n else None,
                "return_pct": round((bal / START_BALANCE - 1) * 100, 2),
                "max_drawdown_pct": round(dd * 100, 2)}

    closed = _read(CLOSED)
    # چهار دفتر جدا: سیگنال‌شده (رکورد اصلی)، دو آزمایش، میز تمرین (دروازهٔ
    # شل برای چندبرابر کردن نمونهٔ یادگیری) و سیگنال‌های آلارم. قاطی کردنشان
    # رکورد استراتژی سیگنال‌شده را ناخوانا می‌کند.
    _aside = ("first", "inducement", "practice", "alarm", "vetoed")

    def _stage(t):
        return (t.get("why") or {}).get("stage") or ""

    signalled = [t for t in closed
                 if _stage(t) not in _aside and not _stage(t).startswith("sig-")]
    experiments = [t for t in closed if (t.get("why") or {}).get("stage") == "first"]
    inducements = [t for t in closed if (t.get("why") or {}).get("stage") == "inducement"]
    practices = [t for t in closed if (t.get("why") or {}).get("stage") == "practice"]
    alarm_trades = [t for t in closed if (t.get("why") or {}).get("stage") == "alarm"]
    # سیگنال‌های ارسالی اسکن (IBS/SMC) — بعد از استاپ زاما اضافه شد: هر چه به
    # تلگرام می‌رود باید تا نتیجه دنبال شود وگرنه ضررِ واقعی درس نمی‌شود.
    sent_scan = [t for t in closed if _stage(t).startswith("sig-")]

    # شفافیت یعنی خود لیست، نه فقط جمع‌بندی — آخرین نتیجه‌ها تک‌به‌تک به پنل
    # می‌روند تا حمید ببیند دقیقاً کدام معامله چه شد. سفارش منقضی هم می‌آید،
    # با برچسب خودش، چون پنهان کردنش همان «عقب‌نشینی از شفافیت» است.
    def public(t):
        return {"sym": t.get("sym"), "dir": t.get("dir"),
                "entry": t.get("entry"), "sl": t.get("sl"), "tp1": t.get("tp1"),
                "outcome": t.get("outcome"), "R": t.get("R"),
                "closed": t.get("closed"),
                "kind": ("سیگنال ارسالی اسکن"
                         if str((t.get("why") or {}).get("stage") or "").startswith("sig-")
                         else {"first": "آزمایش پولبک اول",
                               "inducement": "آزمایش ایندوسمنت",
                               "practice": "میز تمرین",
                               "vetoed": "وتوشدهٔ ناظر",
                               "alarm": "سیگنال آلارم"}.get(
                             (t.get("why") or {}).get("stage"), "سیگنال‌شده"))}
    recent = sorted([t for t in closed if t.get("closed")],
                    key=lambda t: t["closed"], reverse=True)[:40]

    j = {**run_book(signalled),
         "start": START_BALANCE, "risk_per_trade_pct": RISK_FRACTION * 100,
         "experiments_first_pullback": run_book(experiments),
         "experiments_inducement": run_book(inducements),
         "practice_desk": run_book(practices),
         "alarm_signals": run_book(alarm_trades),
         "sent_scan_signals": run_book(sent_scan),
         # نگرانی حمید (۱۴ اوت): «اطلاعات پنل مجدد صفر شده بود». صفر نشده
         # بود — سرتیتر فقط دفتر سیگنال‌شده را می‌گفت و ۴ دفتر دیگر پنهان
         # بودند. از حالا جمع کل انباشته صریح صادر می‌شود تا پنل همیشه
         # نشانش دهد: این عدد فقط بالا می‌رود؛ اگر روزی پایین رفت، خرابی
         # واقعی است و باید داد بزند.
         "total_closed": len(closed),
         # «تعداد برد و استاپا برام مهمه» (حمید، ۱۴ اوت) — کارنامهٔ همیشگیِ
         # همهٔ دفترها روی هم. این اعداد هرگز ریست نمی‌شوند.
         "lifetime": (lambda real: {
             "trades": len(real),
             "wins": sum(1 for t in real if t["R"] > 0),
             "stops": sum(1 for t in real if t["R"] <= 0),
             "win_pct": round(sum(1 for t in real if t["R"] > 0) / len(real) * 100, 1)
             if real else None,
             "mean_r": round(sum(t["R"] for t in real) / len(real), 3) if real else None,
             "sum_r": round(sum(t["R"] for t in real), 1) if real else None,
             "expired_not_trades": sum(1 for t in closed if t.get("outcome") == "expired"),
             "by_outcome": {k: sum(1 for t in real if t.get("outcome") == k)
                            for k in ("target", "trail", "stop", "timeout")},
         })([t for t in closed
             if t.get("R") is not None and t.get("outcome") != "expired"]),
         "books_breakdown": {
             k: {"n": len(v),
                 "wins": sum(1 for t in v if (t.get("R") or 0) > 0),
                 "stops": sum(1 for t in v
                              if t.get("R") is not None and t["R"] <= 0
                              and t.get("outcome") != "expired")}
             for k, v in (("signalled", signalled), ("first_pullback", experiments),
                          ("inducement", inducements), ("practice", practices),
                          ("alarm", alarm_trades), ("sent_scan", sent_scan))},
         "recent": [public(t) for t in recent],
         "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    EQUITY.parent.mkdir(parents=True, exist_ok=True)
    EQUITY.write_text(json.dumps(j, ensure_ascii=False, indent=1))
    return j


# ── learning from the right reasons ────────────────────────────────────────

def _boot_diff(a, b, n=3000, alpha=0.05, days_a=None, days_b=None):
    """Interval around mean(a) − mean(b), at the given alpha.

    داور بیرونی: معامله‌های یک روز هم‌حرکت‌اند (بتای BTC، ستاپ تکراری) و
    بوت‌استرپ i.i.d نمونهٔ متورم می‌سازد. وقتی روزها داده شوند، بلوکی
    (به‌روز) نمونه‌گیری می‌شود؛ بدون روز، همان رفتار قبلی می‌ماند."""
    if len(a) < 8 or len(b) < 8:
        return None

    def draw(vals, days):
        if not days or len(set(days)) < 3:
            return [random.choice(vals) for _ in range(len(vals))]
        byday = {}
        for v, d in zip(vals, days):
            byday.setdefault(d, []).append(v)
        keys = list(byday)
        out = []
        while len(out) < len(vals):
            out += byday[random.choice(keys)]
        return out[:len(vals)]

    diffs = []
    for _ in range(n):
        sa = draw(a, days_a)
        sb = draw(b, days_b)
        diffs.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    diffs.sort()
    return diffs[int(n * alpha / 2)], diffs[int(n * (1 - alpha / 2))]


CONDITIONS = [
    ("لانگ بود", lambda w: w.get("dir") == "LONG"),
    # قانون خود حمید، بالاخره قابل اندازه‌گیری: آیا صبر برای پولبک دوم واقعاً
    # نتیجه را بهتر می‌کند؟ تا حالا فرض بود؛ حالا هر دو مرحله در دفتر ثبت
    # می‌شوند و این شرط جوابش را با داده می‌دهد.
    ("پولبک دوم بود", lambda w: w.get("stage") == "second"),
    ("روند ۴ساعته صعودی", lambda w: w.get("trend_4h") == "up"),
    ("ضربهٔ بلاک ≥ ۶", lambda w: (w.get("impulse") or 0) >= 6),
    ("ضربهٔ بلاک ≥ ۱۰", lambda w: (w.get("impulse") or 0) >= 10),
    ("بلاک ۱ بار برگشت خورده", lambda w: (w.get("returns") or 0) <= 1),
    ("بلاک ۳ بار یا بیشتر", lambda w: (w.get("returns") or 0) >= 3),
    ("سطح با ≥ ۵ واکنش", lambda w: (w.get("reactions") or 0) >= 5),
    ("سطح نقش‌عوض‌کرده", lambda w: bool(w.get("flipped"))),
    # نقشهٔ نقدینگی (درخواست حمید): معامله در جهت آهن‌ربای نقدینگی بهتر است؟
    # فرض نمی‌کنیم — همین شرط با بوت‌استرپ و تصحیح بونفرونی جواب می‌دهد.
    ("نقدینگی هم‌جهت بود", lambda w: w.get("liq") == "with"),
    ("نقدینگی خلاف جهت بود", lambda w: w.get("liq") == "against"),
    # انجین الگوهای کلاسیک (دستور حمید ۱۲ اوت): الگوی هم‌جهت/خلاف واقعاً در
    # نتیجه فرق می‌سازد؟ ادعا نمی‌کنیم — همین دو شرط با بوت‌استرپ و تصحیح
    # بونفرونی هر شب جواب می‌دهند، و این یعنی «یادگیری همهٔ الگوها به
    # جدیدترین شکل»: هر شب از نو.
    ("الگوی کلاسیک هم‌جهت", lambda w: w.get("pattern_align") == "with"),
    ("الگوی کلاسیک خلاف جهت", lambda w: w.get("pattern_align") == "against"),
    # انجین اردر بلاک (دستور حمید ۱۳ اوت): ورود روی OB معتبر هم‌جهت واقعاً
    # بهتر است؟ و باکس چندبار-هانت‌شده تله است یا سکو؟ حکم با ماشین شبانه.
    ("روی OB معتبر هم‌جهت", lambda w: w.get("ob_align") == "with"),
    ("روی OB خلاف جهت", lambda w: w.get("ob_align") == "against"),
    ("OB با ۲+ هانت", lambda w: (w.get("ob_hunts") or 0) >= 2),
    # پرسش پروندهٔ زاما: استاپ خیلی تنگ بیشتر استاپ می‌خورد؟
    ("استاپ زیر ۰.۶٪", lambda w: (w.get("stop_pct") or 9) < 0.6),
    # هزینهٔ هدف «۱۵ در روز»: سیگنالی که با آستانهٔ شل‌شده باز شد بدتر است؟
    ("با آستانهٔ شل باز شد", lambda w: (w.get("relax") or 0) >= 0.05),
    ("استاپ < ۲٪", lambda w: (w.get("stop_pct") or 99) < 2),
    ("ترس شدید (<۳۰)", lambda w: (w.get("fear") or 50) < 30),
    ("فاندینگ مثبت", lambda w: (w.get("funding") or 0) > 0),
    ("دامیننس تتر بالای ۸٪", lambda w: (w.get("usdt_dom") or 0) > 8),
    # میز تمرین عمیق (۱۴ اوت): این سه شرط از پرونده‌های تمرینی می‌آیند و
    # سؤال‌هایشان مستقیماً «کشف ضعف/قوت استراتژی» حمید است.
    ("اول ۱R+ سود رفت (تریل دیر؟)", lambda w: (w.get("mfe") or 0) >= 1.0),
    ("ورود نزدیک سقف کانال", lambda w: (w.get("chan_pos") or 0.5) > 0.75),
    ("جهش حجم در ورود (z≥2)", lambda w: (w.get("vol_z") or 0) >= 2),
    # سؤال حمید (۱۴ اوت): «ارزها در بازهٔ زمانی خاصی به پولبک‌ردشون پایان
    # می‌دهند؟» — اگر حرکت اصلی معمولاً در ≤۸ کندل شروع می‌شود، ورودی که
    # ۸ کندل معطل ماند دیگر پولبک نیست، تلهٔ چرخش بین دو OB است.
    ("حرکت اصلی در ≤۸ کندل شروع شد", lambda w: (w.get("mfe") or 0) >= 1.0 and (w.get("mfe_bar") or 99) <= 8),
    ("۸+ کندل معطل ماند (چرخش؟)", lambda w: (w.get("mfe") or 0) < 0.5 and (w.get("mfe_bar") or 0) >= 8),
]


def reasons(verbose=True):
    """Which conditions actually separated winners from losers?

    The correction is the whole point. Twelve conditions tested at 95% means
    roughly one will clear zero by chance even if none of them matter — and that
    one would then be written into the rules and start steering real signals. So
    the interval is widened by the number of conditions tested (Bonferroni), and
    only a condition surviving *that* is called a reason.

    Both numbers are printed, because the uncorrected one is what a naive
    version of this would have believed, and seeing the gap is the point.
    """
    _siggrade = lambda st: (st not in ("practice", "first", "inducement", "vetoed", "v2"))  # noqa: E731
    trades = [t for t in _read(CLOSED)
              if t.get("R") is not None
              and _siggrade((t.get("why") or {}).get("stage") or "")]
    if len(trades) < 20:
        if verbose:
            print(f"\nفقط {len(trades)} معاملهٔ بسته‌شده — برای نتیجه‌گیری کم است.")
            print("هیچ دلیلی گزارش نمی‌شود تا نمونه بزرگ‌تر شود.")
        return []

    def _day(t):
        return int((t.get("closed") or 0) // 86_400_000)

    # آلفا فقط بین شرط‌های **واجدشرایط** تقسیم می‌شود، نه همهٔ ۲۷ تا.
    #
    # اندازه‌گیری ۱۶ اوت: در ۸ روز پیاپی این ماشین **صفر** شرط تأیید کرد،
    # در حالی که دفتر از ۲۳۹ به ۴۳۵۰ معامله رسید. علتش این بود: آلفا بر ۲۷
    # تقسیم می‌شد (۰.۰۰۱۸۵) ولی بخش بزرگی از آن ۲۷ تا چند خط پایین‌تر
    # به‌خاطر «نمونهٔ کم» اصلاً آزموده نمی‌شدند. یعنی جریمهٔ چندآزمونی را
    # می‌دادیم بابت آزمون‌هایی که هرگز انجام نمی‌شدند.
    #
    # این شل‌کردن آستانه نیست؛ تصحیح بونفرونی همچنان کامل اعمال می‌شود —
    # فقط روی تعداد آزمونی که **واقعاً** انجام می‌شود.
    def _eligible(fn):
        na = sum(1 for t in trades if fn(t.get("why") or {}))
        return na >= 8 and (len(trades) - na) >= 8

    k = max(1, sum(1 for _n, fn in CONDITIONS if _eligible(fn)))
    alpha_adj = 0.05 / k
    out = []
    if verbose:
        print(f"\n{len(trades)} معاملهٔ بسته‌شده · {k} شرط آزموده شد")
        print(f"سطح تصحیح‌شده: {alpha_adj:.4f} (بونفرونی روی {k} شرطِ "
              f"واجدشرایط، نه همهٔ {len(CONDITIONS)} تا)\n")
        print(f"{'شرط':<26}{'با':>10}{'بدون':>10}{'تفاوت':>10}   تصحیح‌شده")
        print("─" * 84)

    for name, fn in CONDITIONS:
        ta = [t for t in trades if fn(t.get("why") or {})]
        tb = [t for t in trades if not fn(t.get("why") or {})]
        a, da = [t["R"] for t in ta], [_day(t) for t in ta]
        b, db = [t["R"] for t in tb], [_day(t) for t in tb]
        if len(a) < 8 or len(b) < 8:
            if verbose:
                print(f"{name:<26}{len(a):>10}{len(b):>10}       نمونهٔ کم")
            continue
        ea, eb = statistics.fmean(a), statistics.fmean(b)
        raw = _boot_diff(a, b, alpha=0.05, days_a=da, days_b=db)
        adj = _boot_diff(a, b, alpha=alpha_adj, days_a=da, days_b=db)
        survives = adj and (adj[0] > 0 or adj[1] < 0)
        raw_only = raw and (raw[0] > 0 or raw[1] < 0) and not survives
        mark_s = "✓ دلیل واقعی" if survives else \
                 "— بعد از تصحیح از بین رفت" if raw_only else "— شانسی"
        if verbose:
            print(f"{name:<26}{ea:>+10.3f}{eb:>+10.3f}{ea-eb:>+10.3f}   {mark_s}")
        if survives:
            out.append({"condition": name, "n_with": len(a), "n_without": len(b),
                        "ev_with": ea, "ev_without": eb, "diff": ea - eb,
                        "interval": adj})

    if verbose:
        print("─" * 84)
        if out:
            print(f"{len(out)} دلیل واقعی پیدا شد — این‌ها بعد از تصحیح هم زنده ماندند.")
        else:
            print("هیچ شرطی بعد از تصحیح زنده نماند. یعنی هنوز نمی‌دانیم چرا "
                  "بعضی بردند — و ادعای دانستنش بدتر از ندانستن است.")
    for r in out:
        brain.save_pattern(f"hamid-reason-{r['condition']}", r)
    # خروجی کامل در فایل، تا چرخه بتواند بخواند و روی رتبه‌بندی اعمال کند.
    # فقط تأییدشده‌ها عمل می‌شوند — قانون ثابت پروژه: یافته تا بازه‌اش از صفر
    # رد نشده، عمل نمی‌شود. بقیه فقط برای شفافیت ثبت می‌شوند.
    (BOOK / "reasons.json").write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_trades": len(trades),
        # امضا: مسیر دفتری که این قوانین از آن آمده. چرخه فقط فایلی را اعمال
        # می‌کند که از دفتر واقعی آمده باشد — دفاعِ دوم بعد از ایزوله شدن تست.
        "book": str(CLOSED),
        "confirmed": out,
    }, ensure_ascii=False, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--reasons", action="store_true")
    a = ap.parse_args()
    if a.mark or not (a.mark or a.reasons):
        mark()
    eq = _equity()
    print(f"\nموجودی کاغذی: ${eq['balance']} از ${eq['start']} "
          f"({eq['return_pct']:+.2f}٪) · {eq['trades']} معامله · "
          f"بیشترین افت {eq['max_drawdown_pct']}٪")
    if a.reasons or not (a.mark or a.reasons):
        reasons()
    return 0


if __name__ == "__main__":
    sys.exit(main())
