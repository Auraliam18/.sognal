#!/usr/bin/env python3
"""یک دستور که اتاق‌ها را فعال می‌کند و چرخه را می‌چرخاند.

    python3 -m hamid.cycle --mode auto --symbols 60

Hamid asked for a schedule that runs in the cloud whether or not the panel is
open, and for one Python command that wakes the rooms. This is that command.
The workflow calls it; nothing else needs to know what a cycle consists of.

`--mode auto` decides for itself what kind of day it is:

  **بازار فعال** — the tape is moving. Full stack on every coin: 4H direction,
  1H channel and order blocks, 15m entry, both existing strategies, live
  signals.

  **آرام / تعطیل** — the tape is not moving. Hamid was explicit that this is not
  a day for forcing entries: «در روزهای تعطیل جمع‌آوری اطلاعات خیلی اولویت
  نیستند و تقویم اقتصادی و خبرهای سیاسی مهم هستند». So the cycle switches to
  the calendar, the news, and a screen of coins whose holder and turnover
  profile looks like something that could be pumped — his اکی-تو example — at
  small size.

Regime is measured, not read off a calendar. A Saturday during a crash is not a
quiet day, and a Tuesday in August often is.

## About the fifteen signals a day

Hamid wants at least fifteen. That is a target the cycle works towards by
relaxing its ranking threshold when the day is behind, and it is honest about
the floor: it will not invent setups the market did not offer. A day that
produces nine says nine, loudly, rather than padding to fifteen with trades
that would lose money — the whole edge measured so far is thin enough that six
forced entries would erase it. The budget is per UTC day and lives in the brain
so a restarted runner does not start counting again.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import brain                                                  # noqa: E402
import sources                                                # noqa: E402
from hamid import research                                    # noqa: E402
from hamid.stack import market_first, read                    # noqa: E402
from hamid import inducement                                  # noqa: E402
from hamid.structure import atr                               # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals"
STATE = ROOT / "brain" / "cycle-state.json"

def _tgname():
    """نام پنل، از همان منبع حقیقتی که تلگرام دارد (telegram.PANEL_NAME)."""
    import telegram as _t
    return _t.PANEL_NAME


def _tgcode():
    import telegram as _t
    return _t.PANEL_CODE


DAILY_TARGET = 15
QUIET_LEARN_N = 40        # جهان روز آرام — فقط برای تمرین، نه سیگنال
ROOMS = ["market", "radar", "scan", "deep", "trade", "paper",
         "chart", "watch", "learn", "calib", "intel", "sup"]

# فعالیت‌های ایجنت، به زبان ساده — پنل همین لیست را در تب «فعالیت‌های ایجنت»
# لحظه‌به‌لحظه نشان می‌دهد تا حمید ببیند الان دقیقاً چه کاری در جریان است.
ACTIVITY = []


def act(text):
    ACTIVITY.append({"t": int(time.time() * 1000), "text": text})
    print(f"⚙ {text}", flush=True)


# ── the day's budget ───────────────────────────────────────────────────────

def _day():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _state():
    try:
        j = json.loads(STATE.read_text())
    except Exception:                                # noqa: BLE001 - fresh day
        j = {}
    if j.get("day") != _day():
        j = {"day": _day(), "signals": 0, "cycles": 0, "modes": {}}
    return j


def _save_state(j):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(j, ensure_ascii=False, indent=1))


def pacing():
    """How far behind the day's target are we, and how much slack does that buy?

    Hours are the denominator, not cycles: being nine short at 22:00 means
    something different from being nine short at 09:00, and a threshold that
    ignores the clock either fires everything at midnight or nothing all day.
    """
    st = _state()
    now = datetime.now(timezone.utc)
    frac = (now.hour * 60 + now.minute) / (24 * 60)
    expected = DAILY_TARGET * frac
    behind = expected - st["signals"]
    # −0.10 relaxes the ranking floor at most; never below the quality floor
    relax = max(0.0, min(0.10, behind * 0.012))
    return {"done": st["signals"], "expected": round(expected, 1),
            "behind": round(behind, 1), "relax": round(relax, 3)}


# ── what kind of day is it ─────────────────────────────────────────────────

def regime(btc_15m):
    """Measured from Bitcoin's own recent range, plus the day of the week.

    The weekend only tips the verdict; it does not decide it. ATR as a fraction
    of price is what actually says whether there is anything to trade.
    """
    now = datetime.now(timezone.utc)
    weekend = now.weekday() >= 5
    if not btc_15m or len(btc_15m) < 40:
        return ("quiet" if weekend else "active"), "کندل کافی نبود، از تقویم تصمیم گرفته شد"
    a = atr(btc_15m)
    px = btc_15m[-1]["c"]
    vol = a / px if px else 0
    # measured on this pipeline's own history: below ~0.12% ATR on 15m the
    # engine's setups stop reaching their first target often enough to matter
    if vol < 0.0012:
        return "quiet", f"نوسان بیت‌کوین کم است ({vol*100:.3f}٪ ATR)"
    if weekend and vol < 0.0020:
        return "quiet", f"تعطیلی و نوسان متوسط ({vol*100:.3f}٪ ATR)"
    return "active", f"بازار در حرکت است ({vol*100:.3f}٪ ATR)"


# ── the active day ─────────────────────────────────────────────────────────

def run_active(symbols, limit_4h=200, limit_1h=300, limit_15m=300, on_ready=None):
    """The full stack, in Hamid's order: market first, then each coin.

    `on_ready(sym, read)` — دستور صریح حمید (۱۴ اوت): «به محض اینکه در
    تحلیل‌ها سیگنالی پیدا شد و شرایطش اوکی بود منتظر نمان که چرخهٔ پایش
    بقیهٔ ارزها تمام شود؛ سیگنال را ارسال کن و بقیهٔ پایش را انجام بده.»
    این قلاب همان‌جا در حلقهٔ ارزها صدا می‌شود — نه بعد از پایان اسکن.
    """
    brain.room_log("market", "شروع چرخهٔ فعال", "cycle")

    def candles(sym, tf, n):
        try:
            rows = sources.klines(sym, tf, n)
        except Exception:                            # noqa: BLE001 - one symbol failing is not fatal
            return []
        return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                for k in rows]

    btc4 = candles("BTCUSDT", "1h", limit_4h)        # 1h stands in for 4h below

    # USDT.D and BTC.D are index series, not pairs — CoinGecko has the level but
    # not the history, so the channel work Hamid does on them needs a series we
    # do not yet store. Reported honestly rather than faked from a proxy.
    try:
        g = research.global_market()
        dom = {"btc_dominance": g["btc_dominance"], "usdt_dominance": g["usdt_dominance"],
               "note": "سطح لحظه‌ای — سری زمانی برای کشیدن کانال هنوز ذخیره نمی‌شود"}
    except Exception as e:                           # noqa: BLE001 - carry on without it
        dom = {"note": f"دامیننس در دسترس نبود: {type(e).__name__}"}

    first = market_first(btc4, None, None)
    first["dominance"] = dom
    brain.room_log("market", f"خوانش بازار: {first.get('verdict')}", "read")

    # Fetched in parallel. Serially this is a hundred-odd round trips, and one
    # slow venue then decides how long the whole cycle takes — a run that
    # normally finished in forty seconds was measured sitting for over ten
    # minutes when a venue started rate-limiting.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {sym: (pool.submit(candles, sym, "1h", limit_1h),
                      pool.submit(candles, sym, "15m", limit_15m))
                for sym in symbols}
        fetched = {sym: (a.result(), b.result()) for sym, (a, b) in jobs.items()}

    reads, setups, inds = [], [], []
    for sym in symbols:
        c1h, c15 = fetched.get(sym, ([], []))
        if len(c1h) < 60 or len(c15) < 60:
            continue
        # 4H is built from 1H by taking every fourth bar's aggregate — the venues
        # that serve this pipeline do not all offer a 4h interval, and resampling
        # from 1H gives the same candles rather than a different vendor's idea
        # of where the 4H boundary falls.
        c4h = resample(c1h, 4)
        r = read(sym, c4h, c1h, c15)
        reads.append(r)
        if r.setup:
            # جای قیمت در کانال ۱ساعته و جهش حجم لحظهٔ ورود.
            #
            # هر دو را میز تمرین از روز اول می‌نوشت و دفتر سیگنال واقعی
            # هرگز — پس شرط‌هایی که به این دو ستون تکیه دارند روی دفتر
            # واقعی همیشه «نمونهٔ کم» می‌خوردند و پل تمرین→سیگنال بی‌صدا
            # بسته می‌ماند. این نبودِ شاهد نبود؛ نبودِ ستون بود.
            # position_1h را stack.read از قبل حساب کرده؛ فقط حمل نمی‌شد.
            if r.position_1h is not None:
                r.setup["chan_pos"] = round(r.position_1h, 2)
            try:
                from hamid.ob_intel import vol_z_at
                r.setup["vol_z"] = round(vol_z_at(c15, len(c15) - 1), 2)
            except Exception:                        # noqa: BLE001 - بستر اختیاری است
                pass
            # نقشهٔ نقدینگی — روی هر ستاپ ثبت می‌شود تا بک‌تست شبانه بسنجد
            # هم‌جهتی با آهن‌ربای نقدینگی واقعاً انتظار را بالا می‌برد یا نه.
            try:
                from hamid import liquidity
                lq = liquidity.read(c15, r.setup.get("dir"))
                r.setup["liq"] = lq["side"]
                if lq["note"]:
                    r.setup["liq_note"] = lq["note"]
            except Exception:                        # noqa: BLE001 - نقشه اختیاری است
                pass
            # نقشهٔ لیکوییدیشن (سبک kCEX، تخمین از کندل واقعی) — خوشه‌های
            # لیکویید بالا/پایین و هم‌جهتی آهن‌ربا با ستاپ
            try:
                from hamid import liqmap
                lm = liqmap.build(c1h)
                if lm:
                    r.setup["liq_map"] = {"magnet": lm["magnet"],
                                          "above": lm["above"][:2],
                                          "below": lm["below"][:2]}
                    ln = liqmap.note(lm, r.setup.get("dir"))
                    if ln:
                        r.setup["liqmap_note"] = ln
            except Exception:                        # noqa: BLE001 - نقشه اختیاری است
                pass
            setups.append((sym, r))
            # ارسال فوری همین ارز — بدون انتظار برای پایان اسکن (دستور حمید)
            if on_ready is not None:
                try:
                    on_ready(sym, r)
                except Exception as e:               # noqa: BLE001 - ارسال نباید اسکن را بکشد
                    print(f"ارسال فوری {sym}: {type(e).__name__}: {e}")
        try:
            ind = inducement.find(c15)
            if ind:
                inds.append((sym, ind))
        except Exception:                            # noqa: BLE001 - آزمایش نباید چرخه را بکشد
            pass
        brain.room_log("scan", f"{sym}: ۴ساعته {r.trend_4h}، "
                               f"{len(r.blocks)} بلاک، ستاپ {'دارد' if r.setup else 'ندارد'}", "read")
    flows = money_flow(fetched)
    return first, reads, setups, flows, inds


def money_flow(fetched, z_gate=2.0, look=4):
    """ورود/خروج پول، با نگاهی به گذشتهٔ خود ارز — نه حدس.

    حجم آخرین کندل بستهٔ یک‌ساعته نسبت به میانگین/انحراف صد کندل قبل سنجیده
    می‌شود؛ جهش یعنی z بالای آستانه. بعد در تاریخچهٔ همان ارز، جهش‌های مشابهِ
    هم‌جهت پیدا و بازدهٔ چهار ساعت بعدشان اندازه گرفته می‌شود — «واکنش
    انتظاری» میانهٔ همان اندازه‌گیری است، با تعداد نمونه کنارش، که معلوم باشد
    حرف از چند مشاهده می‌آید. نمونهٔ کمتر از پنج، بدون پیش‌بینی گزارش می‌شود."""
    out = []
    for sym, (c1h, _) in fetched.items():
        if len(c1h) < 120:
            continue
        vols = [k["v"] for k in c1h[:-1]]            # کندل باز حساب نیست
        base = vols[-101:-1]
        mean = sum(base) / len(base)
        var = sum((v - mean) ** 2 for v in base) / len(base)
        sd = var ** 0.5 or 1e-12
        last = c1h[-2]
        z = (last["v"] - mean) / sd
        if z < z_gate:
            continue
        inflow = last["c"] >= last["o"]
        # جهش‌های مشابهِ گذشته در همین سری
        rets = []
        for i in range(100, len(c1h) - look - 1):
            k = c1h[i]
            b = [x["v"] for x in c1h[max(0, i - 100):i]]
            m = sum(b) / len(b)
            s = (sum((v - m) ** 2 for v in b) / len(b)) ** 0.5 or 1e-12
            if (k["v"] - m) / s >= z_gate and (k["c"] >= k["o"]) == inflow:
                rets.append((c1h[i + look]["c"] - k["c"]) / k["c"] * 100)
        rets.sort()
        n = len(rets)
        med = rets[n // 2] if n else None
        out.append({"symbol": sym, "z": round(z, 1),
                    "flow": "ورود" if inflow else "خروج",
                    "past_n": n,
                    "past_median_pct": round(med, 2) if med is not None else None,
                    "verdict": ("نمونهٔ گذشته کم است — پیش‌بینی نمی‌کنیم" if n < 5 else
                                f"در {n} جهش مشابه، میانهٔ حرکت {look} ساعت بعد {med:+.2f}٪ بود")})
    out.sort(key=lambda x: -x["z"])
    return out[:8]


def resample(cd, k):
    """k one-hour candles into one k-hour candle, anchored to the clock.

    بازبینی کد دو عیب واقعی گرفت: گروه‌بندی از ایندکس صفرِ پنجرهٔ لغزان شروع
    می‌شد، پس مرز کندل ۴ساعته هر ساعت یک ساعت جابه‌جا می‌شد و روند/بلاک‌های
    ۴ساعته بدون هیچ تغییری در بازار بین دو چرخه عوض می‌شدند؛ و وقتی طول
    پنجره مضرب k بود، «کندل بستهٔ» آخر شامل کندل یک‌ساعتهٔ هنوز-باز می‌شد.
    حالا گروه‌ها به ساعت جهانی قفل‌اند، گروه ناقصِ ابتدای پنجره و گروه آخر
    (که کندل باز در آن است) هر دو حذف می‌شوند."""
    ms = k * 3600 * 1000
    buckets, order = {}, []
    for c in cd:
        b = c["t"] // ms
        if b not in buckets:
            buckets[b] = []
            order.append(b)
        buckets[b].append(c)
    if order:
        order.pop()                    # گروه آخر = کندل باز؛ کندل بسته نیست
    out = []
    for b in order:
        g = buckets[b]
        if len(g) < k:                 # گروه ناقص ابتدای پنجره — OHLC ناقص است
            continue
        out.append({"t": g[0]["t"], "o": g[0]["o"],
                    "h": max(x["h"] for x in g), "l": min(x["l"] for x in g),
                    "c": g[-1]["c"], "v": sum(x["v"] for x in g)})
    return out


# ── the quiet day ──────────────────────────────────────────────────────────

def run_quiet():
    """«در روزهای تعطیل … تقویم اقتصادی و خبرهای سیاسی مهم هستند»

    Plus the screen Hamid described: coins listed on the futures venues he can
    reach, whose holders look sensible, worth a small position on the chance of
    a pump. Turnover — volume against market cap — is the part that is
    measurable here; "holders look sensible" in the on-chain sense needs a data
    source none of these free tiers provide, and saying so is better than
    dressing turnover up as holder analysis.
    """
    brain.room_log("intel", "شروع چرخهٔ آرام — تقویم و اخبار", "cycle")
    out = {"mode": "quiet"}

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "hamid-signal"})
        with urllib.request.urlopen(req, timeout=20) as r:
            cal = json.load(r)
        high = [e for e in cal if (e.get("impact") or "").lower() == "high"]
        out["calendar"] = [{"title": e.get("title"), "country": e.get("country"),
                            "date": e.get("date")} for e in high[:12]]
        brain.room_log("intel", f"{len(high)} رویداد مهم اقتصادی این هفته", "calendar")
    except Exception as e:                           # noqa: BLE001 - report, continue
        out["calendar_error"] = f"{type(e).__name__}: {e}"

    try:
        movers = research.coingecko_movers(40)
        # futures-listed and actually traded: turnover is the filter that
        # separates a coin someone could exit from one that only looks alive
        picks = [m for m in movers if m["turnover"] >= 0.08 and m["mcap"] > 5e6]
        picks.sort(key=lambda m: -m["turnover"])
        out["watchlist"] = picks[:12]
        brain.room_log("radar", f"{len(picks)} ارز با گردش معاملاتی بالا برای پایش", "screen")
    except Exception as e:                           # noqa: BLE001
        out["watchlist_error"] = f"{type(e).__name__}: {e}"

    try:
        out["fear_greed"] = research.fear_greed()
    except Exception:                                # noqa: BLE001
        pass
    return out


def practice_candidates(reads, cap=12):
    """میز تمرین سروری — دروازه‌ها عمداً شُل: هر ساختاری با ورود، استاپ و هدف
    واقعی. دلیلش عدد است، نه سلیقه: بعد از چند روز فقط ۴۹ معاملهٔ بسته داریم
    و با این نرخ، یادگیریِ آماری ماه‌ها گرسنه می‌ماند. این میز نمونه را چند
    برابر می‌کند؛ سیگنال نیست، به حمید نمی‌رسد، دفترش جداست."""
    out = []
    for r in reads:
        if getattr(r, "setup", None):        # ستاپ واقعی خودش کاغذی می‌شود
            continue
        bs = getattr(r, "blocks", None) or []
        if not bs:
            continue
        b = bs[0]
        lo, hi = b.get("low"), b.get("high")
        if not lo or not hi or hi <= lo:
            continue
        box = hi - lo
        if b.get("dir") == "bearish":
            entry, sl = lo, hi + 0.3 * box
            tp1, tp2 = entry - 1.5 * (sl - entry), entry - 2.5 * (sl - entry)
            d = "SHORT"
        else:
            entry, sl = hi, lo - 0.3 * box
            tp1, tp2 = entry + 1.5 * (entry - sl), entry + 2.5 * (entry - sl)
            d = "LONG"
        out.append({"symbol": r.symbol, "dir": d, "entry": entry, "sl": sl,
                    "tp1": tp1, "tp2": tp2, "stage_tag": "practice",
                    "trend_4h": getattr(r, "trend_4h", None)})
        if len(out) >= cap:
            break
    return out


def watch_alarms():
    """قولِ «با رسیدن قیمت، بازبینی و سیگنال» — تا امروز آلارم‌ها فقط ثبت
    می‌شدند و هیچ‌کس نگاهشان نمی‌کرد. حالا هر چرخه، هر آلارم مسلح با دو کندل
    ۱۵ دقیقهٔ آخر سنجیده می‌شود: لمس نقطهٔ ورود = فعال؛ بسته‌شدن ۷٪ آن‌طرف
    ورود = ناحیه از دست رفته و آلارم باطل، با دلیلِ نوشته."""
    st = brain.room_load("radar", {}) or {}
    alarms = st.get("alarms") or []
    if not alarms:
        return []
    fired, keep = [], []
    now_ms = int(time.time() * 1000)
    for a in alarms:
        if a.get("stage") != "ARMED":
            keep.append(a)
            continue
        # پنجرهٔ تاریخی — قانون حمید: اگر از فاصلهٔ معمولِ پامپِ دنباله‌رو
        # بگذرد و نپریده باشد، طبق سابقهٔ خودش دیگر احتمالاً نمی‌پرد.
        if a.get("expires_at") and now_ms > a["expires_at"]:
            a["stage"] = "DEAD"
            a["why_dead"] = "پنجرهٔ تاریخی پامپ گذشت — طبق سابقهٔ خودش دیگر بعید است بپرد"
            act(f"آلارم {a['sym']} منقضی شد — {a['why_dead']}")
            keep.append(a)
            continue
        try:
            rows = sources.klines(a["sym"], "15m", 3)
            cs = [{"h": k[2], "l": k[3], "c": k[4]} for k in rows]
        except Exception:                            # noqa: BLE001 - دفعهٔ بعد
            keep.append(a)
            continue
        if len(cs) < 2:
            keep.append(a)
            continue
        px = a.get("price")
        now = cs[-1]["c"]
        a["now"] = now
        a["distancePct"] = round(abs(now - px) / px * 100, 2) if px else None
        d = a.get("dir", "LONG")
        if px and ((d == "LONG" and now < px * 0.93) or
                   (d == "SHORT" and now > px * 1.07)):
            a["stage"] = "DEAD"
            a["why_dead"] = "قیمت ۷٪ آن‌طرف نقطهٔ ورود بسته — ناحیه از دست رفت"
            act(f"آلارم {a['sym']} باطل شد — {a['why_dead']}")
            keep.append(a)
            continue
        touched = px and min(c["l"] for c in cs[-2:]) <= px <= max(c["h"] for c in cs[-2:])
        if touched:
            a["stage"] = "TRIGGERED"
            a["triggered_at"] = int(time.time() * 1000)
            fired.append(a)
            act(f"⏰ قیمت به آلارم {a['sym']} رسید ({px}) — بازبینی شروع شد")
        keep.append(a)
    brain.room_save("radar", {**st, "alarms": keep[:80]})
    return fired


def _stop_reason(t, autopsy=None):
    """دلیل خوانای هر استاپ — خواست حمید: «ایجنت دلیل استاپ‌ها را توضیح بده».

    از دادهٔ ثبت‌شده ساخته می‌شود، نه از حدس: MFE/MAE (مسیر واقعی قیمت بعد
    از ورود)، تنگی استاپ نسبت به نویز، جهت نقدینگی و روند لحظهٔ باز شدن،
    و کالبدشکافی BTC اگر انجام شده. دادهٔ ناقص، صادقانه گفته می‌شود."""
    w = t.get("why") or {}
    bits = []
    if autopsy:
        bits.append(autopsy)
    mfe = t.get("mfe_r")
    if mfe is not None:
        if mfe < 0.15:
            bits.append(f"از لحظهٔ پر شدن تقریباً هیچ‌وقت به نفع نرفت "
                        f"(MFE {mfe:+.2f}R) — ورود دیر یا جهت غلط")
        elif mfe >= 0.8:
            bits.append(f"تا +{mfe:.2f}R به نفع رفت ولی به تارگت نرسید و برگشت "
                        f"— تارگت دور بود یا خروج مدیریت نشد")
    sp = w.get("stop_pct")
    if sp is not None and sp < 0.6:
        bits.append(f"استاپ فقط {sp}٪ — داخل نویز بازار (همان درس ZAMA)")
    if w.get("liq") == "against":
        bits.append("آهن‌ربای نقدینگی از لحظهٔ باز شدن خلاف جهت بود")
    t4 = w.get("trend_4h")
    if t4 in ("up", "down") and (t4 == "down") == (t.get("dir") == "LONG"):
        bits.append(f"روند ۴ساعته مخالف بود ({t4})")
    if not bits:
        bits.append("شرایط لحظهٔ باز شدن این معامله ناقص ثبت شده بود — از این "
                    "چرخه به بعد آلارم‌ها هم نقدینگی و تنگی استاپ را ثبت می‌کنند")
    return "؛ ".join(bits)


def settle_books(report):
    """اول تسویه، بعد تصمیم — یافتهٔ بازبینی معماری: تسویه و یادگیری در انتهای
    چرخه بود، پس هر وتو و مشورتِ حافظه با تجربهٔ یک چرخه کهنه‌تر گرفته می‌شد.
    حالا اول معامله‌های باز علامت می‌خورند، نتیجه به تلگرام می‌رود، حافظه هضم
    و ایندکس دانش تازه می‌شود — بعد چرخه با دانشِ همین لحظه تصمیم می‌گیرد."""
    from hamid import paper
    t_mark = int(time.time() * 1000)
    still, closed = paper.mark()
    try:
        just = [t for t in paper._read(paper.CLOSED)
                if (t.get("closed") or 0) >= t_mark
                and t.get("outcome") in ("target", "stop", "trail")
                and (t.get("why") or {}).get("stage")
                not in ("first", "practice", "inducement")]
        if just:
            import telegram as _tg
            tok, chat = _tg.creds()
            # کالبدشکافی استاپ (قانون حمید): استاپ که خورد، همان لحظه ایجنت
            # وارد شود — BTC چه می‌کرد؟ این ارز طبق لگ-کورولیشن دنبالش
            # می‌ریزد؟ در ریزش بزرگ قبلی BTC هم ریخته بود؟ حکم: استاپ
            # سیستمی بود یا ضعف خود ستاپ — و همین حکم درس می‌شود.
            autopsies = {}
            try:
                from hamid import lagcorr as _lagc
                from hamid import memory as _mem0
                _b1h = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                        for k in sources.klines("BTCUSDT", "1h", 500)]
                for t in [x for x in just if x["outcome"] == "stop"][:4]:
                    try:
                        _s1h = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                                 "c": k[4], "v": k[5]}
                                for k in sources.klines(t["sym"], "1h", 500)]
                        mr = _lagc.market_reaction(_b1h, _s1h)
                    except Exception:                # noqa: BLE001
                        continue
                    if not mr:
                        continue
                    btc_against = ((mr["btc_1h_pct"] <= -1.0 and t["dir"] == "LONG")
                                   or (mr["btc_1h_pct"] >= 1.0 and t["dir"] == "SHORT"))
                    if btc_against and mr["follow"]:
                        verdict = ("استاپ سیستمی بود، نه ضعف ستاپ: "
                                   + _lagc.reaction_fa(t["sym"], mr))
                    elif btc_against:
                        verdict = (f"BTC خلاف جهت بود ({mr['btc_1h_pct']:+}٪/۱س) ولی "
                                   f"رابطهٔ لگ-کورولیشنی این ارز با BTC قانع‌کننده نیست "
                                   "— سهم ستاپ از ضعف خودش است")
                    else:
                        verdict = ("ربطی به حرکت BTC نداشت — ضعف خود ستاپ؛ "
                                   "در بازبینی شرط‌ها دیده شود")
                    autopsies[t["sym"] + t["dir"]] = verdict
                    _mem0.remember("بررسی", t["sym"],
                                   f"کالبدشکافی استاپ {t['sym']} {t['dir']}: {verdict}",
                                   {"R": t.get("R"), "btc_1h": mr["btc_1h_pct"]})
            except Exception as e:                   # noqa: BLE001
                print(f"کالبدشکافی استاپ: {type(e).__name__}")
            # دلیل برای هر استاپ — نه فقط استاپ‌های مرتبط با BTC
            stop_reasons = []
            for t in just:
                if t["outcome"] == "stop":
                    r = _stop_reason(t, autopsies.get(t["sym"] + t["dir"]))
                    stop_reasons.append({"sym": t["sym"], "dir": t["dir"],
                                         "R": t.get("R_net", t.get("R")),
                                         "mfe": t.get("mfe_r"), "mae": t.get("mae_r"),
                                         "reason": r})
            report["stop_reasons"] = stop_reasons[:10]
            if tok:
                rmap = {s["sym"] + s["dir"]: s["reason"] for s in stop_reasons}
                # خواست حمید: نتیجهٔ هر سیگنال «ریپلایِ» پیام خودش باشد تا با
                # سیگنال دیگری اشتباه نشود — فقط معامله‌های دارای شناسهٔ پیام
                # اعلام می‌شوند (ریپلای)؛ پیام جمعی فقط وقتی ریپلای شکست بخورد.
                # یکتاسازی: معاملهٔ آلارمی در دو دفتر (alarm + sig-alarm) ثبت
                # می‌شود؛ برای اعلام فقط یکی — نسخهٔ دارای شناسهٔ پیام مقدم
                dd, seen_k = [], {}
                for t in just:
                    k = (t["sym"], t["dir"], round(float(t["entry"]), 10))
                    has_mid = bool((t.get("why") or {}).get("tg_msg_id"))
                    if k in seen_k:
                        if has_mid and not (dd[seen_k[k]].get("why") or {}).get("tg_msg_id"):
                            dd[seen_k[k]] = t
                        continue
                    seen_k[k] = len(dd)
                    dd.append(t)
                rest = []
                for t in dd[:10]:
                    # شکایت حمید (۱۲ اوت): «بعضی از نتایج اصلاً جزو سیگنال
                    # نبوده‌اند و من در پیام‌ها ندیدم». معامله‌ای که شناسهٔ
                    # پیام تلگرام ندارد یعنی هیچ سیگنالی برایش ارسال نشده
                    # (دفتر داخلی یادگیری: آلارمِ نرفته، وتوشده، v2) —
                    # نتیجه‌اش فقط در حافظه و پنل می‌ماند، به تلگرام نمی‌رود.
                    mid = (t.get("why") or {}).get("tg_msg_id")
                    if not mid:
                        continue
                    won = t["outcome"] == "target"
                    trailed = t["outcome"] == "trail"
                    icon = "✅" if won else ("🟡" if trailed else "❌")
                    verdict = ("تارگت خورد" if won else
                               "تریل شد — سود سیو شد" if trailed else "استاپ خورد")
                    line = (f"{icon} <b>{t['sym']}</b> "
                            f"{'خرید' if t['dir'] == 'LONG' else 'فروش'} — "
                            f"{verdict} (<code>{t['R']:+.2f}R</code>)")
                    if trailed and t.get("mfe_r") is not None:
                        line += (f"\n   <i>قانون تریل اجرا شد: تا +{t['mfe_r']:.2f}R رفت، "
                                 f"استاپِ تریل‌شده در سود بست — برگشتِ کامل دیگر ضرر نمی‌سازد</i>")
                    a = rmap.get(t["sym"] + t["dir"]) if t["outcome"] == "stop" else None
                    if mid:
                        cap = (f"{_tg.BRAND} · 📊 <b>نتیجهٔ همین سیگنال</b>\n" + line
                               + (f"\n🔎 <i>{a}</i>" if a else "")
                               + f"\n🕐 <code>{_tg.tehran()}</code> به وقت ایران")
                        # خواست حمید: ریپلای نتیجه حتماً با عکس چارت باشد —
                        # چارت ۵د لحظهٔ بسته شدن با سطوح ورود/استاپ/تارگت
                        buf = None
                        try:
                            from tg_batch import chart as _c
                            cd5 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                                    "c": k[4], "v": k[5]}
                                   for k in sources.klines(t["sym"], "5m", 120)]
                            if len(cd5) >= 20:
                                buf = _c(t["sym"], cd5, t.get("entry"), t.get("sl"),
                                         t.get("tp1"), t.get("tp2"), t["dir"])
                        except Exception:            # noqa: BLE001 - چارت اختیاری
                            buf = None
                        try:
                            if buf and len(cap) <= 1024:
                                _tg._post(tok, "sendPhoto",
                                          {"chat_id": chat, "parse_mode": "HTML",
                                           "reply_to_message_id": mid,
                                           "allow_sending_without_reply": "true",
                                           "caption": cap},
                                          {"photo": (f"{t['sym']}.png", buf.read())})
                            else:
                                _tg._post(tok, "sendMessage",
                                          {"chat_id": chat, "parse_mode": "HTML",
                                           "reply_to_message_id": mid,
                                           "allow_sending_without_reply": "true",
                                           "text": cap})
                            continue
                        except Exception:            # noqa: BLE001 - ریپلای نشد → جمعی
                            pass
                    rest.append(line + (f"\n   🔎 <i>{a}</i>" if a else ""))
                if rest:
                    _tg._post(tok, "sendMessage",
                              {"chat_id": chat, "parse_mode": "HTML",
                               "text": (f"🏷 <b>{_tg.PANEL_NAME}</b>\n"
                                        f"📊 <b>نتیجهٔ معامله‌ها</b>\n\n" + "\n".join(rest))})
                n_mid = len([t for t in dd if (t.get("why") or {}).get("tg_msg_id")])
                act(f"نتیجهٔ {n_mid} سیگنال ارسالی به تلگرام رفت (ریپلای)؛ "
                    f"{len(just) - n_mid} بستهٔ دفتر داخلی فقط در حافظه/پنل ماند")
                # خواست حمید: اوردرِ فعال‌نشده که منطقی منقضی شد هم ریپلای
                # بگیرد — «به این دلایل منقضی است و ورود ممنوع»
                exp_just = [t for t in paper._read(paper.CLOSED)
                            if (t.get("closed") or 0) >= t_mark
                            and t.get("outcome") == "expired"
                            and (t.get("why") or {}).get("tg_msg_id")]
                for t in exp_just[:6]:
                    hrs = round(((t.get("closed") or 0) - (t.get("opened") or 0)) / 3600e3, 1)
                    try:
                        _tg._post(tok, "sendMessage",
                                  {"chat_id": chat, "parse_mode": "HTML",
                                   "reply_to_message_id": t["why"]["tg_msg_id"],
                                   "allow_sending_without_reply": "true",
                                   "text": (f"{_tg.BRAND} · ⌛️ <b>این سیگنال منقضی شد — ورود ممنوع</b>\n"
                                            f"قیمت در {hrs} ساعت هرگز به ناحیهٔ ورود "
                                            f"<code>{t['entry']:.10g}</code> نرسید؛ ستاپ کهنه "
                                            f"شده و شرایطی که صدورش را توجیه می‌کرد دیگر "
                                            f"برقرار نیست. اگر دوباره معتبر شود، سیگنال "
                                            f"تازه با تحلیل تازه می‌آید.\n"
                                            f"🕐 <code>{_tg.tehran()}</code> به وقت ایران")})
                    except Exception:                # noqa: BLE001
                        pass
                if exp_just:
                    act(f"⌛️ {len(exp_just)} اوردر فعال‌نشده با ریپلای «منقضی — ورود ممنوع» بسته اعلام شد")
    except Exception as e:                           # noqa: BLE001 - اعلان تسویه را نمی‌کشد
        print(f"اعلان نتیجه: {type(e).__name__}")
    # پرونده‌سازی (بند ۲۲ منشور): هر بستهٔ سیگنال‌گرید یک case یکتا —
    # با کالبدشکافی استاپ اگر انجام شده باشد
    try:
        from hamid import cases as _cases
        _cases.write_cases(just, autopsies=locals().get("autopsies") or {})
    except Exception as e:                           # noqa: BLE001
        print(f"پرونده‌سازی: {type(e).__name__}")
    try:
        from hamid import memory as _mem2
        newly = [t for t in paper._read(paper.CLOSED)
                 if (t.get("closed") or 0) >= t_mark]
        fed = _mem2.digest_closed(newly)
        if fed:
            act(f"حافظه: {fed} معاملهٔ بسته هضم شد — تصمیم‌های همین چرخه با دانش تازه گرفته می‌شود")
        report["memory"] = {"fed_now": fed, "lessons": _mem2.lessons(limit=6)}
    except Exception as e:                           # noqa: BLE001
        print(f"هضم حافظه: {type(e).__name__}: {e}")
    try:
        paper.reasons(verbose=False)
    except Exception as e:                           # noqa: BLE001
        print(f"reasons: {type(e).__name__}")
    return still, closed


def review_cycle():
    """مرور دوساعته، خودکار: چه بسته شد و هر دفتر چه کرد. جای قضاوت من نیست —
    ثبتِ قابل‌مقایسه است تا «یک تغییر کنترل‌شده در هر مرور» چیزی برای
    نمره‌گرفتن داشته باشد. بازهٔ بدون معامله صادقانه همین را می‌گوید."""
    rv = brain.room_load("review", {}) or {}
    last = rv.get("at", 0)
    now_ms = int(time.time() * 1000)
    if now_ms - last < 2 * 3600 * 1000:
        return None
    from hamid import paper as _p
    closed = [t for t in _p._read(_p.CLOSED)
              if t.get("R") is not None and t.get("outcome") != "expired"
              and (t.get("closed") or 0) > last]
    books = {}
    for t in closed:
        k = (t.get("why") or {}).get("stage") or "؟"
        books.setdefault(k, []).append(t["R"])
    # شکایت حمید (۱۲ اوت): در اعلام دوساعته نتایجی می‌دید که هیچ‌وقت سیگنال
    # نشده بودند. تفکیک صریح: «سیگنال ارسالی» = معامله‌ای که شناسهٔ پیام
    # تلگرام دارد؛ بقیه دفتر داخلی یادگیری‌اند و با برچسب روشن جمع‌بندی
    # می‌شوند، نه قاطیِ نتایج سیگنال.
    sent_tr = [t for t in closed if (t.get("why") or {}).get("tg_msg_id")]
    intern = [t for t in closed if not (t.get("why") or {}).get("tg_msg_id")]
    if sent_tr:
        parts = []
        for t in sent_tr[:8]:
            ic = {"target": "✅", "trail": "🟡"}.get(t.get("outcome"), "❌")
            parts.append(f"{ic} {t['sym']} {t['R']:+.2f}R")
        sent_line = f"سیگنال‌های ارسالی بسته‌شده ({len(sent_tr)}): " + " · ".join(parts)
    else:
        sent_line = "در این بازه هیچ سیگنال ارسالی‌ای بسته نشد"
    int_line = ""
    if intern:
        mr = sum(t["R"] for t in intern) / len(intern)
        int_line = (f"\nدفترهای یادگیری داخلی (سیگنال نبوده‌اند، ارسال نشده‌اند): "
                    f"{len(intern)} بسته، میانگین {mr:+.2f}R")
    verdict = sent_line + int_line
    if not closed:
        # دستور حمید (۱۴ اوت): «چندین بار شده هیچ موردی نبوده — ایجنت
        # مربوطه باید علت‌یابی کنه که چرا نتیجه حاصل نشده بعد از ۲ ساعت.»
        # پس بازهٔ خالی دیگر یک جمله نیست؛ همان لحظه با دادهٔ همین چرخه
        # جواب می‌دهد: قیف کجا بسته شد؟
        verdict = "در این بازه معامله‌ای بسته نشد — نتیجه‌گیری ممنوع"
        try:
            why = []
            # ۱) چند معامله باز است؟ (باز بودن یعنی کار می‌کند، فقط نتیجه نرسیده)
            n_open = len(_p._read(_p.OPEN))
            if n_open:
                why.append(f"{n_open} معاملهٔ کاغذی باز است — نتیجه هنوز نرسیده، خط تولید زنده است")
            # ۲) آخرین گزارش منتشرشدهٔ خود چرخه: رژیم و شمارش‌ها از همان‌جا
            last_rep = {}
            try:
                last_rep = json.loads(
                    (ROOT / "signals" / "hamid-latest.json").read_text())
            except Exception:                         # noqa: BLE001
                pass
            if last_rep.get("mode") == "quiet":
                why.append("بازار در حالت سکوت بود — چرخه عمداً ستاپ نمی‌سازد"
                           + (f" ({last_rep.get('why')})" if last_rep.get("why") else ""))
            reads_n = last_rep.get("reads")
            setups = last_rep.get("setups")
            if reads_n:
                why.append(f"آخرین چرخه {reads_n} ارز خواند"
                           + (f"، {len(setups)} ستاپ دید" if isinstance(setups, list) else "")
                           + " — ستاپ بود ولی به معاملهٔ بسته نرسید"
                           if isinstance(setups, list) and setups else
                           f"آخرین چرخه {reads_n} ارز خواند و هیچ ستاپی از دروازه‌ها نگذشت")
            # ۳) قیف دروازه‌ها از دفتر ارسال: چند رد
            led = {}
            try:
                import telegram as _tg2
                led = _tg2._load_sent()
            except Exception:                         # noqa: BLE001
                pass
            n_skip = len([k for k in led if str(k).startswith("skip|")])
            if n_skip:
                why.append(f"دروازه‌ها {n_skip} کاندیدا را رد کردند (ضدتکرار/هم‌زمانی/بازجویی)")
            # تشخیص حمید (۱۴ اوت): «دقیقاً بین دو اردر بلاک بازی می‌کند و نه
            # استاپ می‌زند نه تی‌پی — تریدر خسته می‌شود.» دو نشانهٔ قابل‌سنجش:
            # ۱) معامله‌های باز کهنه (>۱۲س نه استاپ نه تارگت = معلق در وسط)
            # ۲) سهم بالای timeout در بسته‌های اخیر میز تمرین
            now0 = int(time.time() * 1000)
            open_rows = _p._read(_p.OPEN)
            stuck = [t for t in open_rows
                     if t.get("filled") and now0 - t["filled"] > 12 * 3600 * 1000]
            if len(stuck) >= 3:
                why.append(f"{len(stuck)} معاملهٔ پرشده {12}+ ساعت است نه استاپ خورده "
                           "نه تارگت — نشانهٔ چرخش بین دو اردر بلاک مخالف (NO_TRADE_ROTATION)")
            recent = [t for t in _p._read(_p.CLOSED)[-120:]
                      if t.get("outcome") in ("stop", "target", "trail", "timeout")]
            n_to = sum(1 for t in recent if t["outcome"] == "timeout")
            if len(recent) >= 20 and n_to / len(recent) > 0.5:
                why.append(f"{n_to} از {len(recent)} بستهٔ اخیر timeout بوده — "
                           "بازار رنجِ بین‌OB است؛ قانون رنج: NO_TRADE_ROTATION معتبر است")
            if not why:
                why.append("هیچ نشانهٔ فعالیتی در بازه نیست — اگر تکرار شد، خودِ چرخه مشکوک است")
            verdict += "\n🔎 علت‌یابی خودکار: " + "؛ ".join(why)
            # تکرار سه‌بارهٔ بازهٔ خالی → درس دائمی، تا الگو گم نشود
            empty_streak = sum(1 for h in (rv.get("history") or [])[:2]
                               if h.get("closed") == 0) + 1
            if empty_streak >= 3:
                from hamid import memory as _mem2
                _mem2.remember("عیب", "SYSTEM",
                               f"سه مرور دوساعتهٔ پیاپی خالی — علت‌یابی آخر: {'؛ '.join(why[:2])}")
        except Exception:                             # noqa: BLE001 - علت‌یابی نباید مرور را بکشد
            pass
    entry = {"at": now_ms, "closed": len(closed), "verdict": verdict,
             "books": {k: {"n": len(v), "mean_r": round(sum(v) / len(v), 3)}
                       for k, v in books.items()}}
    hist = rv.get("history") or []
    hist.insert(0, entry)
    brain.room_save("review", {"at": now_ms, "history": hist[:84]})
    act(f"مرور دوساعته: {verdict}")
    # اعلام کلی دوساعته به تلگرام (دستور حمید) + ریشه‌یابی وتو: اگر ردشده‌ها
    # چند برابر فرستاده‌شده‌ها هستند، پرتکرارترین دلایل رد از دفتر vetoed
    try:
        import telegram as _tg
        tok, chat = _tg.creds()
        if tok:
            led = _tg._load_sent()
            n_sent = len([k for k in led if not k.startswith(("any|", "skip|"))])
            n_skip = len([k for k in led if k.startswith("skip|")])
            veto_line = f"ارسال ۱۲س اخیر: {n_sent} · ردشدهٔ دروازه‌ها: {n_skip}"
            root = ""
            if n_skip >= 4 and n_skip >= 3 * max(n_sent, 1):
                from collections import Counter as _C
                cons = _C()
                for t in _p._read(_p.CLOSED)[-120:]:
                    wv = t.get("why") or {}
                    if wv.get("stage") == "vetoed":
                        for r_ in (wv.get("pm_con") or [])[:2]:
                            cons[r_[:60]] += 1
                top = "؛ ".join(f"«{k}» ×{v}" for k, v in cons.most_common(3))
                root = f"\n🔎 وتو زیاد است — پرتکرارترین دلایل رد: {top or 'ثبت‌نشده'}"
                try:
                    from hamid import memory as _rmem
                    _rmem.remember("بررسی", "-",
                                   f"نرخ وتو بالا ({n_skip} رد / {n_sent} ارسال): {top[:150]}")
                except Exception:                    # noqa: BLE001
                    pass
            opens = len(_p._read(_p.OPEN))
            _tg._post(tok, "sendMessage",
                      {"chat_id": chat, "parse_mode": "HTML",
                       "text": (f"{_tg.BRAND}\n"
                                f"🧾 <b>اعلام کلی دوساعته</b>\n\n{verdict}\n"
                                f"پوزیشن باز: {opens} · {veto_line}{root}\n"
                                f"🕐 <code>{_tg.tehran()}</code> به وقت ایران")})
            act("اعلام کلی دوساعته به تلگرام رفت")
    except Exception as e:                           # noqa: BLE001 - گزارش، مرور را نمی‌کشد
        print(f"اعلام دوساعته: {type(e).__name__}")
    return entry


def _method_record():
    """رکورد روش، زنده از دفتر — عدد هاردکد با رشد دفتر دروغ می‌شد (داور)."""
    try:
        eq = json.loads((ROOT / "brain" / "paper" / "equity.json").read_text())
        n, w = eq.get("trades"), eq.get("win_pct")
        if n:
            return (f"رکورد این روش تا حالا: {n} معاملهٔ واقعی، {w}٪ برد — "
                    "بازهٔ اطمینان هنوز ادعای لبه نمی‌دهد؛ سایز کوچک.")
    except Exception:                                # noqa: BLE001
        pass
    return "رکورد این روش هنوز در حال جمع شدن است — سایز کوچک."


def _tg_chart(s, path):
    """چارت ۵ دقیقه با واترمارک Trade_Osuli برای ارسال لحظه‌ای — اگر matplotlib
    روی رانر نبود، متن خالی می‌رود ولی سیگنال گم نمی‌شود."""
    try:
        from tg_batch import chart as _c
        rows = sources.klines(s["sym"], "5m", 120)
        cd = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
              for k in rows]
        if len(cd) < 20:
            return None
        bp = ((s.get("premortem") or {}).get("patterns") or {}).get("best")
        # OB معتبرِ انجین اردر بلاک مقدم بر باکس خام موتور است
        _obv = (s.get("premortem") or {}).get("ob_ctx") or {}
        _obox = ({"low": _obv["low"], "high": _obv["high"]}
                 if _obv.get("low") is not None else s.get("ob"))
        # خط روند ۱ساعته و ۴ساعته (دستور حمید، ۱۵ اوت). روی کندل تایم
        # بالا محاسبه و با timestamp روی همین چارت ۵دقیقه نگاشت می‌شود.
        # اگر خط معتبری نبود، هیچ کشیده نمی‌شود — خط تزئینی ممنوع.
        _htf = []
        try:
            from hamid import structure as _stl
            for _lbl, _tf, _n, _col in (("4H", "4h", 200, "#f0a92e"),
                                        ("1H", "1h", 240, "#5d8ecb")):
                _rows = sources.klines(s["sym"], _tf, _n)
                _hcd = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                         "c": k[4], "v": k[5]} for k in _rows]
                if len(_hcd) < 40:
                    continue
                # اول از دیتابیس انباشته: خطی که در چند اجرای مستقل
                # دوباره پیدا شده، همان خطی است که حمید دستی هم می‌کشد.
                # اگر هنوز تأیید مستقل ندارد، خط لحظه‌ای کشیده می‌شود.
                _tl = None
                try:
                    from hamid import levels_db as _ldb
                    _ldb.update(s["sym"], _tf, _hcd)
                    _rec = _ldb.best_line(s["sym"], _tf, _hcd)
                    if _rec:
                        _tl = _ldb.as_trendline(_rec)
                        _lbl = f"{_lbl}✦"        # ✦ یعنی از دیتابیس، تأییدشده
                except Exception:                # noqa: BLE001
                    pass
                if _tl is None:
                    _tl = _stl.trendline(_hcd)
                if _tl:
                    _htf.append((_lbl, _tl, _hcd, _col))
        except Exception as _e:                      # noqa: BLE001 - خط اختیاری است
            print(f"خط روند تایم بالا: {type(_e).__name__}")
        buf = _c(s["sym"], cd, s["entry"], s["sl"], s.get("tp1"), s.get("tp2"),
                 s["dir"], ob=_obox,
                 pat={"key": bp.get("key"),
                      "label": bp["name"].upper().replace("_", " ")} if bp else None,
                 htf=_htf)
        with open(path, "wb") as f:
            f.write(buf.read())
        return path
    except Exception:                                # noqa: BLE001 - چارت اختیاری است
        return None


# ── the cycle ──────────────────────────────────────────────────────────────

def _for_telegram(x):
    """Hamid's setup in the shape telegram.py already knows.

    The footer is set explicitly rather than left to default. The default states
    22.7% and +0.069R, which is the original engine's measured record — quoting
    it on a signal from this method would read as evidence for something it has
    never been measured on. What this method has actually measured is 43 trades
    at 46.5% and +0.184R with the interval spanning zero, and the message says
    exactly that, including that it is not yet an edge.
    """
    return {
        "sym": x["symbol"], "tf": "15m", "dir": x["dir"],
        "entry": float(x["entry"]), "sl": float(x["sl"]),
        "tp1": float(x["tp1"]), "tp2": float(x.get("tp2") or 0) or None,
        "rr": x["rr"],
        "memory": x.get("memory"),
        "liq_note": x.get("liq_note"),
        "liqmap_note": x.get("liqmap_note"),
        "strategy": "hamid", "strategyName": "روش خود حمید (۴ساعته → ۱ساعته → ۱۵دقیقه)",
        "ob": {"low": x["block"]["low"], "high": x["block"]["high"]},
        "level": {"type": "R" if x["dir"] == "SHORT" else "S",
                  "touches": x["on_level"]["touches"]},
        "footer": (f"<i>فاصلهٔ استاپ {x.get('stop_pct')}٪. "
                   f"{x.get('why','')}</i>\n"
                   + (f"<i>🏦 قابل معامله در: {x['venues']}</i>\n"
                      if x.get("venues") else "")
                   + f"<i>{_method_record()}</i>"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="auto", choices=["auto", "active", "quiet"])
    ap.add_argument("--symbols", type=int, default=60)
    ap.add_argument("--dry", action="store_true", help="بدون نوشتن خروجی")
    a = ap.parse_args()

    t0 = time.time()
    st = _state()
    st["cycles"] += 1
    pace = pacing()
    print(f"چرخهٔ {st['cycles']} امروز — {pace['done']} سیگنال تا الان، "
          f"انتظار {pace['expected']}، آستانه {pace['relax']} شل‌تر")

    for r in ROOMS:
        brain.room_log(r, "بیدارباش چرخه", "wake")

    # اطلاعات جهانی، قبل از هر تصمیمی. تا حالا چرخه فقط کندل می‌خواند؛ حمید
    # درست پرسید که چرا. حالا هر چرخه ترس و طمع، دامیننس، فاندینگ، پوزیشن باز،
    # تقویم اقتصادی، اخبار و ترندها را می‌گیرد و هرکدام به اتاق خودش می‌رود.
    world = {}
    try:
        from hamid import intel
        world = intel.gather(quiet=True)
        print(f"اطلاعات جهانی: {world.get('verdict')}")
    except Exception as e:                           # noqa: BLE001 - اطلاعات جانبی، نه تحلیل
        print(f"اطلاعات جهانی نیامد: {type(e).__name__}: {e}")

    # what kind of day
    try:
        btc15 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                 for k in sources.klines("BTCUSDT", "15m", 200)]
    except Exception as e:                           # noqa: BLE001
        print(f"بیت‌کوین در دسترس نبود: {e}")
        btc15 = []
    mode, why = regime(btc15) if a.mode == "auto" else (a.mode, "دستی انتخاب شد")
    ACTIVITY.clear()
    act(f"شروع چرخه در حالت {'فعال' if mode == 'active' else 'سکوت'} — {why}")
    print(f"حالت: {mode} — {why}")
    brain.event("cycle", mode=mode, why=why, pacing=pace)

    report = {"generated": int(time.time() * 1000),
              "generatedText": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              # شناسنامهٔ جفتِ ایجنت↔پنل — حمید چند هوش مصنوعی را با هم مقایسه
              # می‌کند؛ هر خروجی باید بگوید مال کدام جفت است تا هیچ‌وقت قاطی نشود.
              # نام پنل ثابت نوشته شده بود، پس گزارشِ **هر دو** خط تولید
              # می‌گفت «لیام تریدر ۹» — یعنی همان شناسنامه‌ای که قرار بود
              # جلوی قاطی‌شدن را بگیرد، خودش قاطی‌شان می‌کرد.
              "agent": {"name": "کلود — Claude Code",
                        "panel": _tgname(), "code": _tgcode()},
              "mode": mode, "why": why, "pacing": pace,
              "world": {k: world.get(k) for k in
                        ("verdict", "fear_greed", "dominance", "funding",
                         "calendar", "news", "trending") if k in world}}

    # اول تسویه و یادگیری، بعد تصمیم — تا وتو و مشورتِ حافظه با دانشِ همین
    # لحظه باشد، نه یک چرخه کهنه‌تر.
    try:
        settled_open, settled_closed = settle_books(report)
    except Exception as e:                           # noqa: BLE001
        settled_open = settled_closed = 0
        print(f"تسویهٔ دفتر: {type(e).__name__}: {e}")

    # 📨 پل ناتیفیکیشن بیت‌یونیکس — حمید ناتیف صرافی را به ربات فوروارد
    # می‌کند، همین‌جا صندوق خوانده و تحقیق فوری همان ارز جواب داده می‌شود.
    try:
        from hamid import notif_bridge
        from hamid.pump_radar import Kcache
        n_ans = notif_bridge.poll(kc=Kcache())
        if n_ans:
            act(f"📨 {n_ans} ناتیف فورواردشدهٔ بیت‌یونیکس تحقیق و جواب داده شد")
    except Exception as e:                           # noqa: BLE001 - پل چرخه را نمی‌کشد
        print(f"پل ناتیف: {type(e).__name__}: {e}")

    # 📰 انجین دسته‌بندی خبر — تیترهای داغ به دسته و اتاق مقصد مسیردهی می‌شوند
    try:
        from hamid import discovery
        cls = discovery.classify_news(((world.get("news") or {}).get("hot")) or [])
        routed = [c for c in cls if c["room"]]
        report["news_classified"] = cls[:8]
        for c in routed[:4]:
            brain.room_log(c["room"], f"خبر [{c['cat']}]: {(c['title'] or '')[:80]}", "news")
        if routed:
            act(f"📰 {len(routed)} خبر مهم دسته‌بندی و به اتاق آمار/یادگیری مسیردهی شد")
    except Exception as e:                           # noqa: BLE001 - خبر چرخه را نمی‌کشد
        print(f"دسته‌بندی خبر: {type(e).__name__}: {e}")

    # بازسنجی روزانهٔ حافظه (Memory Curator — دستور حمید): درس‌های قدیمی با
    # شواهد انجین‌های جدید سنجیده می‌شوند؛ تأییدشده می‌ماند، ردشده بازنشسته
    try:
        from hamid import revalidate as _rv
        _rc = _rv.run()
        if _rc:
            act(f"🧹 بازسنجی حافظه: {_rc['confirmed']} تأیید · "
                f"{_rc['pending']} در انتظار · {_rc['retired']} بازنشسته")
    except Exception as e:                           # noqa: BLE001
        print(f"بازسنجی حافظه: {type(e).__name__}: {e}")

    # Universe Snapshot روزانه (AuraLiam369 §5 فاز ۱) — فایل یکتای روز،
    # ضد survivorship bias؛ اگر امروز ساخته شده، هیچ کاری نمی‌کند.
    try:
        from hamid import universe as _uni
        _snap, _created, _udiff = _uni.daily()
        if _created:
            act(f"🌐 Universe امروز ثبت شد: {_snap['n']} نماد از {_snap['venue']}"
                + (f" · تازه‌لیست: {', '.join(_udiff['listed'][:4])}"
                   if _udiff and _udiff["listed"] else ""))
    except Exception as e:                           # noqa: BLE001 - چرخه را نمی‌کشد
        print(f"Universe: {type(e).__name__}: {e}")

    reads, setups, inds = [], [], []   # هر دو مسیر ممکن است پرشان کنند
    if mode == "active":
        _vidx = {}                                   # صرافی‌های هدف؛ پر می‌شود پایین‌تر
        try:
            tick = sources.tickers()
            ranked = [s["symbol"] for s in
                      sorted(tick, key=lambda x: -float(x["quoteVolume"] or 0))
                      if s["symbol"].endswith("USDT")]
            # تنوع (شکایت حمید: «استراتژی را روی همهٔ ارزها اجرا کن»):
            # سه‌چهارم سهمیه، پرحجم‌ترین‌ها؛ یک‌چهارم، پنجرهٔ چرخان روی
            # رتبه‌های بعدی — هر چرخه تکهٔ تازه‌ای از بازار دیده می‌شود و
            # طی چند چرخه کل فهرست پوشش می‌گیرد.
            core_n = max(20, a.symbols * 3 // 4)
            rot_n = a.symbols - core_n
            tail = ranked[core_n:core_n + 200] or ranked[core_n:]
            if tail and rot_n > 0:
                off = (st["cycles"] * rot_n) % len(tail)
                rot = (tail + tail)[off:off + rot_n]
                syms = ranked[:core_n] + rot
                act(f"جهان اسکن: {core_n} پرحجم + {len(rot)} چرخان "
                    f"(رتبه‌های {core_n + off} به بعد)")
            else:
                syms = ranked[:a.symbols]

            # اولویت صرافی‌های حمید (دستور ۱۴ اوت): بیت‌یونیکس / XT / KCEX.
            # مجموعه عوض نمی‌شود، فقط ترتیب — و ترتیب حالا واقعاً مهم است،
            # چون ارسال per-symbol فوری شده و سهمیهٔ روزانه دارد: هر که
            # زودتر خوانده شود زودتر سیگنال می‌گیرد. سیگنالی که حمید
            # نمی‌تواند اجرا کند سهمیه را نباید بخورد.
            try:
                from hamid import venues as _vn
                _vidx = _vn.index()
                syms, _vnote = _vn.prioritize(syms, idx=_vidx)
                act(_vnote)
            except Exception as e:                   # noqa: BLE001 - اسکن را نمی‌کشد
                print(f"اولویت صرافی: {type(e).__name__}: {e}")
                _vidx = {}

            # 🆕 انجین کشف لیست‌شدن — دیفِ نمادها با حافظهٔ اجرای قبل
            try:
                from hamid import discovery as _dv
                nl = _dv.new_listings(tick, venue=sources.used().get("tickers"))
                report["new_listings"] = nl["new"]
                if nl["new"]:
                    act(f"🆕 ارز تازه‌لیست‌شده: {', '.join(nl['new'][:5])} — "
                        "به حافظه رفت و زیر نظر رادار است")
                    from hamid import memory as _dmem
                    for s_ in nl["new"][:5]:
                        _dmem.remember("کشف", s_,
                                       f"ارز تازه در صرافی لیست شد: {s_} — نوپا و پرریسک؛ "
                                       "فقط با ساختار تأییدشده سیگنال می‌شود")
            except Exception as e:                   # noqa: BLE001
                print(f"کشف لیست تازه: {type(e).__name__}: {e}")
        except Exception as e:                       # noqa: BLE001
            print(f"لیست ارزها نیامد: {e}")
            syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        act(f"در حال خواندن {len(syms)} ارز برتر از صرافی‌های جهانی")

        # ── ارسال فوریِ per-symbol (دستور صریح حمید، ۱۴ اوت) ───────────────
        # «به محض اینکه سیگنالی پیدا شد و شرایطش اوکی بود منتظر نمان که
        # چرخهٔ پایش بقیهٔ ارزها تمام شود؛ ارسال کن و بقیهٔ پایش را انجام
        # بده. اگر چندتا بود، هرکدام را به محض گرفتن تأییدیه بفرست.»
        #
        # همان دروازه‌ها، فقط زودتر: وتوی تجربه و مشورت حافظه اینجا هم
        # اجرا می‌شوند، و send_signals خودش بازجویی/هم‌زمانی/ضدتکرار را
        # دارد. ارسال پایان چرخه تور ایمنی می‌ماند و ضدتکرارِ telegram
        # جلوی دوباره‌فرستادن را می‌گیرد.
        _live = {"sent": 0, "syms": set()}
        try:
            from hamid import paper as _p_live
            _exp_live = _p_live.experience_index()
        except Exception:                            # noqa: BLE001
            _exp_live = {}

        def _send_now(sym, r):
            if mode != "active" or r.setup.get("waiting"):
                return
            if st["signals"] + _live["sent"] >= DAILY_TARGET:
                return                               # سهمیهٔ روز پر است
            x = {"symbol": sym, **r.setup, "trend_4h": r.trend_4h,
                 "channel": r.channel_note}
            try:
                from hamid import venues as _vn2
                x["venues"] = _vn2.where(sym, idx=_vidx)
            except Exception:                        # noqa: BLE001
                pass
            # دروازهٔ بیت‌یونیکس (دستور حمید، ۱۵ اوت): سیگنالی که حمید
            # نتواند بگیرد، سیگنال نیست. تحلیل روی کل جهان ادامه دارد؛
            # فقط ارسال محدود می‌شود.
            try:
                from hamid import venues as _vg
                okv, whyv = _vg.tradable(sym, _vidx)
                if not okv:
                    act(f"⛔ {sym} ارسال نشد — {whyv}")
                    return
            except Exception as e_:                  # noqa: BLE001
                print(f"دروازهٔ صرافی {sym}: {type(e_).__name__}")
                return                               # ندانستن = نفرستادن
            e = _exp_live.get((sym, x.get("dir")))
            if e and not e["thin"] and e["mean_r"] < 0 and e["win_pct"] < 45:
                return                               # وتوی تجربه — مثل مسیر عادی
            try:
                from hamid import memory as _m_live
                m = _m_live.consult(sym, x["dir"])
                if m.get("note"):
                    x["memory"] = m["note"]
            except Exception:                        # noqa: BLE001
                pass
            import telegram as _tg_live
            one = _for_telegram(x)
            one["analyzed_at"] = int(time.time() * 1000)
            n = _tg_live.send_signals([one], _tg_chart)
            if n:
                _live["sent"] += n
                _live["syms"].add(sym)
                act(f"⚡ {sym} همان لحظه فرستاده شد — بدون انتظار برای بقیهٔ اسکن")

        first, reads, setups, flows, inds = run_active(syms, on_ready=_send_now)
        if _live["sent"]:
            st["signals"] += _live["sent"]
            report["sent_live"] = sorted(_live["syms"])
        report["market"] = first
        report["reads"] = len(reads)
        report["money_flow"] = flows
        act(f"{len(reads)} ارز خوانده شد؛ {len(setups)} ارز ساختار اردر بلاک دارند")
        if flows:
            act(f"جهش حجم در {len(flows)} ارز دیده شد — واکنش گذشتهٔ هرکدام اندازه گرفته شد")
        # استراتژی ایندوسمنت (NEAR-style) — فقط اندازه‌گیری، هنوز سیگنال نمی‌شود
        report["inducement"] = [{"symbol": s_, "dir": x.dir, "entry": x.entry,
                                 "sl": x.sl, "tp1": x.tp1, "tp2": x.tp2,
                                 "room_r": x.room_r, "note": x.note}
                                for s_, x in inds]
        if inds:
            act(f"استراتژی ایندوسمنت: {len(inds)} ستاپ پیدا شد — به دفتر آزمایش رفت (تا تأیید آماری سیگنال نمی‌شود)")
        # تاریخچهٔ همان ارزها فوری در اختیار اتاق سیگنال و ریسک
        for f in flows:
            brain.room_log("scan", f"پول در حال {f['flow']} به {f['symbol']} "
                                   f"(z={f['z']}) — {f['verdict']}", "flow")
        rows = [{"symbol": s, **r.setup, "trend_4h": r.trend_4h,
                 "channel": r.channel_note} for s, r in setups]
        ready = [x for x in rows if not x.get("waiting")]
        waiting = [x for x in rows if x.get("waiting")]

        # The target is fifteen a day, not fifteen a cycle. One cycle produced
        # fifteen on its own; at forty-eight cycles a day that is seven hundred,
        # which is not a signal service, it is a firehose. So the day's budget
        # binds in both directions — pacing() already relaxes the floor when the
        # day is behind, and this is the other half.
        #
        # یادگیری روی رتبه‌بندی. فقط قوانینی که بعد از تصحیح بونفرونی از صفر
        # رد شده‌اند اعمال می‌شوند — رتبه‌بندی، نه گیت، تا یک قانونِ هنوز-جوان
        # نتواند سیگنالی را کاملاً خفه کند. تا وقتی هیچ قانونی تأیید نشده،
        # این بلوک هیچ اثری ندارد و گزارش صادقانه همین را می‌گوید.
        learned = []
        try:
            from hamid import paper as _paper
            # ── کانال دوم: دانشِ **پایدار** از بک‌تست کندل واقعی ────────
            #
            # اندازه‌گیری ۱۶ اوت: ماشین شرط‌های دفتر کاغذی در ۸ روز پیاپی
            # صفر شرط تأیید کرد، پس learn_score عملاً همیشه ۰ بود — یعنی
            # رتبه‌بندی «یادگیرنده» هیچ اثری نداشت. دفتر پایداری
            # (rule_ledger) قانون‌هایی را می‌دهد که در چند اندازه‌گیریِ
            # مستقل با علامت ثابت تکرار شده‌اند.
            #
            # **فقط قانونِ هم‌استراتژی اعمال می‌شود.** قانونی که روی ibs
            # اندازه گرفته شده دربارهٔ روش حمید چیزی ثابت نمی‌کند؛ منتقل
            # کردنش یعنی ادعای بی‌شاهد. تا وقتی بک‌تستِ روش حمید حکم
            # ندهد، این کانال باز است ولی ساکت — و همین درست است.
            _stable = []
            try:
                _sr = json.loads((brain.BRAIN / "learning" /
                                  "stable-rules.json").read_text())
                _stable = [r for r in (_sr.get("rules") or [])
                           if r.get("strategy") == "hamid"]
                _other = len(_sr.get("rules") or []) - len(_stable)
                if _other:
                    print(f"دانش پایدار: {_other} قانون برای استراتژی دیگر "
                          "اندازه‌گیری شده — روی روش حمید اعمال نمی‌شود")
            except Exception:                        # noqa: BLE001 - نبودش حالت معتبر است
                pass
            rj = json.loads((_paper.BOOK / "reasons.json").read_text())
            if rj.get("book") != str(_paper.CLOSED):
                raise FileNotFoundError("reasons از دفتر واقعی نیامده — نادیده گرفته شد")
            conds = {c[0]: c[1] for c in
                     [(x["condition"], x) for x in rj.get("confirmed") or []]}
            # پل تمرین→سیگنال (گزینهٔ ۲، دستور حمید ۱۶ اوت): یافته‌ای که روی
            # دفتر تمرین کشف و روی دفتر سیگنال واقعی **تکرار** شده. اندازهٔ
            # اثرش از دفتر واقعی است، نه از تمرین. اگر همان شرط از راه
            # مستقیم هم تأیید شده باشد، نسخهٔ مستقیم می‌ماند — پل فقط
            # چیزی اضافه می‌کند که وگرنه هرگز به رتبه‌بندی نمی‌رسید.
            try:
                from hamid import bridge as _bridge
                for b in _bridge.promoted():
                    conds.setdefault(b["condition"], b)
            except Exception as e:                   # noqa: BLE001 - پل اختیاری است
                print(f"پل تمرین: {type(e).__name__}: {e}")
            if conds:
                cond_fns = dict((n, f) for n, f in _paper.CONDITIONS)
                def learn_score(x):
                    w = {"trend_4h": x.get("trend_4h"), "dir": x["dir"],
                         "impulse": x["block"]["impulse"], "returns": x["block"]["returns"],
                         "reactions": x["on_level"]["reactions"],
                         "stop_pct": x.get("stop_pct"), "liq": x.get("liq"),
                         "stage": "second" if not x.get("waiting") else "first"}
                    sc = 0.0
                    for name, r in conds.items():
                        fn = cond_fns.get(name)
                        if fn and fn(w):
                            sc += r["diff"]          # مثبت جایزه، منفی جریمه
                    return sc
                for x in ready:
                    x["learn_score"] = round(learn_score(x), 3)
                learned = [{"rule": n, "diff": round(r["diff"], 3),
                            "n": r["n_with"],
                            "via": r.get("via") or "direct"}
                           for n, r in conds.items()]
        except FileNotFoundError:
            pass
        except Exception as e:                       # noqa: BLE001 - یادگیری چرخه را نمی‌کشد
            print(f"یادگیری در رتبه‌بندی: {type(e).__name__}: {e}")
        report["learning_rules"] = learned or "هنوز هیچ قانونی از تصحیح آماری رد نشده"

        # Ranked by impulse alone. The first version multiplied impulse by the
        # number of times price had returned to the block, on the assumption
        # that more returns meant more validation. The backtest points the other
        # way: blocks with three or more returns came back 35.7% and −0.075R
        # against 46.5% and +0.184R overall. That reading is not acted on — its
        # interval spans zero like everything else in that run — but a ranking I
        # invented, with no evidence for it and weak evidence against, does not
        # get to keep deciding which signals reach Hamid.
        #
        # Impulse stays because it is the one threshold here derived from a
        # control rather than from intuition.
        # ناظر تجربه — جواب مستقیم به حرف حمید: «یاد بگیرد و مثل روز اول
        # سیگنال ندهد». قبل از صدور، کارنامهٔ بستهٔ همین ارز و همین جهت از
        # دفتر کاغذی پرسیده می‌شود؛ ۱۲ معامله به بالا با میانگین منفی و برد
        # زیر ۴۵٪ یعنی این سیگنال به حمید نمی‌رسد. وتوشده همچنان کاغذی ثبت
        # می‌شود تا اگر رکوردش برگشت، خودش دوباره راه باز کند — وتو حکم ابد
        # نیست، حافظه است. زیر ۱۲ معامله حق وتو نیست: نمونهٔ کوچک قاضی بدی است.
        vetoed = []
        try:
            from hamid import paper as _p2
            exp_idx = _p2.experience_index()
            kept = []
            for x in ready:
                e = exp_idx.get((x["symbol"], x["dir"]))
                if e and not e["thin"] and e["mean_r"] < 0 and e["win_pct"] < 45:
                    x["vetoed"] = e
                    vetoed.append(x)
                    act(f"ناظر تجربه: سیگنال {x['symbol']} {x['dir']} رد شد — "
                        f"{e['n']} معاملهٔ قبلی همین ارز/جهت، میانگین {e['mean_r']}R، "
                        f"برد {e['win_pct']}٪")
                else:
                    kept.append(x)
            ready = kept
        except Exception as e:                       # noqa: BLE001 - ناظر چرخه را نمی‌کشد
            print(f"ناظر تجربه: {type(e).__name__}: {e}")
        report["vetoes"] = [{"sym": x["symbol"], "dir": x["dir"], **x["vetoed"]}
                            for x in vetoed]

        # مشورت با حافظه — قانون حمید: «بر اساس دانش انباشته + مقایسه با گذشته،
        # سیگنال را نهایی کن و شباهت قوی را صریح ذکر کن.» برای هر ستاپ آماده،
        # حافظهٔ آماری همین ارز/جهت پرسیده می‌شود؛ جمله‌اش با عدد روی سیگنال
        # می‌نشیند و به تلگرام هم می‌رود. اثر رتبه‌ای فقط با ۸+ مورد مشابه.
        # کدام صرافیِ هدف این نماد را دارد — روی کپشن می‌نشیند تا حمید
        # نپرسد «این را کجا بزنم».
        try:
            from hamid import venues as _vn3
            for x in ready:
                x["venues"] = _vn3.where(x["symbol"], idx=_vidx)
        except Exception as e:                       # noqa: BLE001
            print(f"برچسب صرافی: {type(e).__name__}: {e}")

        try:
            from hamid import memory as _mem
            for x in ready:
                m = _mem.consult(x["symbol"], x["dir"])
                if m["note"]:
                    x["memory"] = m["note"]
                    if m["adj"]:
                        x["learn_score"] = round((x.get("learn_score") or 0) + m["adj"], 3)
                    if m["verdict"] in ("good", "bad"):
                        act(f"حافظه دربارهٔ {x['symbol']}: {m['note']}")
        except Exception as e:                       # noqa: BLE001 - حافظه چرخه را نمی‌کشد
            print(f"مشورت حافظه: {type(e).__name__}: {e}")

        ready.sort(key=lambda x: (-(x.get("learn_score") or 0), -x["block"]["impulse"]))
        room = max(0, DAILY_TARGET - st["signals"])
        per_cycle = max(1, round(DAILY_TARGET / 8))    # never a whole day at once
        take = min(room, per_cycle, len(ready))
        held = len(ready) - take
        report["setups"] = ready[:take] + waiting
        report["held_back"] = held
        # سهمیه فقط برای نمایش و تلگرام است. دفتر کاغذی همهٔ آماده‌ها را
        # می‌گیرد: یادگیری به معاملهٔ بسته نیاز دارد و با ۲ سیگنال در چرخه،
        # رسیدن به ۲۰ معامله (کف نتیجه‌گیری) هفته‌ها طول می‌کشید. ثبت کاغذی
        # هزینه‌ای ندارد و هیچ پیامی برای حمید نمی‌سازد.
        report["paper_candidates"] = ready + vetoed + [x for x in waiting]
        st["signals"] += take
        print(f"{len(reads)} ارز خوانده شد، {len(setups)} ستاپ، "
              f"{take} سیگنال فرستاده شد"
              + (f"، {held} تای دیگر نگه داشته شد (سهمیهٔ روز)" if held else ""))
    else:
        act("بازار آرام است — به‌جای اسکن کامل، تقویم اقتصادی و نامزدهای پامپ بررسی می‌شوند")
        report.update(run_quiet())

        # ── یادگیری در روز آرام هم تعطیل نیست (ایراد حمید، ۱۵ اوت) ─────────
        #
        # «قرار بود بی‌وقفه ترید انجام شود و به صورت پیپرتریدینگ … و نتایج
        # بررسی و علت را پیدا کند و به یادگیری اضافه کند.»
        #
        # قبلاً کل خواندن ساختار پشت `mode == "active"` بود، پس در روز آرام
        # هیچ کندلی خوانده نمی‌شد و میز تمرین صفر معامله باز می‌کرد. حالت
        # آرام برای این است که روی تیک مرده **سیگنال نفرستیم** — نه این‌که
        # یاد نگیریم. اتفاقاً روز آرام همان‌جایی است که وقت آزاد داریم.
        #
        # پس ساختار خوانده می‌شود ولی `on_ready=None` است: هیچ سیگنالی
        # نمی‌رود، فقط دفتر تمرین و کاغذی پر می‌شود. جهان کوچک‌تر است تا
        # چرخهٔ نیم‌ساعته از بودجه‌اش رد نشود.
        try:
            q_syms = []
            try:
                q_tick = sources.tickers()
                q_syms = [t["symbol"] for t in
                          sorted(q_tick, key=lambda x: -float(x["quoteVolume"] or 0))
                          if t["symbol"].endswith("USDT")][:QUIET_LEARN_N]
            except Exception:                        # noqa: BLE001
                q_syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
            act(f"یادگیری روز آرام: {len(q_syms)} ارز فقط برای تمرین خوانده می‌شود "
                "— هیچ سیگنالی از این مسیر نمی‌رود")
            _f, reads, setups, flows, inds = run_active(q_syms, on_ready=None)
            print(f"روز آرام: {len(reads)} ارز خوانده شد، {len(setups)} ستاپ "
                  "(فقط خوراک یادگیری)")
        except Exception as e:                       # noqa: BLE001 - یادگیری چرخه را نمی‌کشد
            print(f"یادگیری روز آرام: {type(e).__name__}: {e}")

    # Paper book. Every signal is placed as a limit order and tracked to its
    # stop or target, carrying the conditions that were true when it was opened.
    # Judging it later against a re-derived context would attribute the outcome
    # to conditions that arrived after the decision.
    try:
        from hamid import paper
        ctx = {}
        try:
            ctx["fear"] = research.fear_greed()["value"]
        except Exception:                            # noqa: BLE001 - optional context
            pass
        g = (report.get("market") or {}).get("dominance") or {}
        ctx["usdt_dom"] = g.get("usdt_dominance")
        ctx["btc_dom"] = g.get("btc_dominance")
        ctx["mode"] = mode
        ctx["relax"] = pace.get("relax")   # هزینهٔ هدف ۱۵تایی باید سنجیدنی باشد (داور)
        # همان چیزی که موقع باز کردن معامله در دنیا می‌گذشت — بعداً حلقهٔ
        # یادگیری از روی همین قضاوت می‌کند که چه چیزی واقعاً مهم بوده.
        fnd = (world.get("funding") or {})
        ctx["funding"] = fnd.get("BTC")
        cal = (world.get("calendar") or {}).get("next_48h") or []
        ctx["news_soon"] = len([e for e in cal if 0 <= e.get("in_hours", 99) <= 6])
        ctx["hot_news"] = len((world.get("news") or {}).get("hot") or [])
        cands = report.get("paper_candidates") or \
            [x for x in report.get("setups", []) if not x.get("waiting")]
        for c in cands:
            # وتوشده دفتر جدا می‌گیرد — بازبینی کد: قبلاً با برچسب second در
            # رکورد سرفصل می‌نشست و کارنامهٔ «سیگنال‌شده» را با معامله‌هایی که
            # هرگز فرستاده نشدند آلوده می‌کرد.
            c["stage_tag"] = ("vetoed" if c.get("vetoed")
                              else "second" if not c.get("waiting") else "first")
        opened = paper.open_from(cands, ctx)
        # 🧪 آزمایش v2 (دستور حمید): همان IBS+پولبک‌پلاس ولی با فیلتر سخت‌گیرِ
        # «گذشتهٔ غیرمنفی + هم‌مسیری روند ۴س + حجم غیرمخالف» — دفتر جدا تا
        # با CI سنجیده شود؛ طبق مسیر ارتقا، تا اثبات نشده سیگنال زنده نمی‌شود.
        try:
            from hamid import memory as _vmem
            flows = {f["symbol"]: f for f in (report.get("money_flow") or [])}
            v2 = []
            for c0 in cands:
                if c0.get("waiting") or c0.get("vetoed"):
                    continue
                _, hadj = _vmem.history(c0["symbol"], c0["dir"])
                if hadj < 0:
                    continue
                if c0.get("trend_4h") not in (None,) and \
                   (c0.get("trend_4h") == "up") != (c0["dir"] == "LONG"):
                    continue
                fl = flows.get(c0["symbol"])
                if fl and (fl.get("flow") == "ورود") != (c0["dir"] == "LONG"):
                    continue
                v2.append({**c0, "stage_tag": "v2"})
            if v2:
                opened += paper.open_from(v2, {**ctx, "v2": True})
                act(f"🧪 v2: {len(v2)} ستاپ از فیلتر گذشته/روند/حجم گذشت — دفتر آزمایشی")
        except Exception as e:                       # noqa: BLE001
            print(f"v2: {type(e).__name__}")
        ind_cands = [{"symbol": s_, "dir": x.dir, "entry": x.entry, "sl": x.sl,
                      "tp1": x.tp1, "tp2": x.tp2, "stage_tag": "inducement"}
                     for s_, x in (inds if mode == "active" else [])]
        if ind_cands:
            opened += paper.open_from(ind_cands, ctx)
        # میز تمرین به حالت بازار وابسته نیست — این دفتر «فقط خوراک یادگیری»
        # است و هیچ‌وقت سیگنال نمی‌شود، پس دلیلی ندارد در روز آرام خاموش
        # باشد. تا امروز پشت `mode == "active"` بود و شنبه‌ها صفر می‌ماند.
        try:
            pc = practice_candidates(reads)
            if pc:
                n_pr = paper.open_from(pc, ctx)
                opened += n_pr
                act(f"میز تمرین: {n_pr} معاملهٔ تمرینی باز شد — "
                    "فقط خوراک یادگیری، سیگنال نیست")
        except Exception as e:                       # noqa: BLE001 - تمرین چرخه را نمی‌کشد
            print(f"میز تمرین: {type(e).__name__}: {e}")
        # تسویه اول چرخه انجام شده (settle_books) — اینجا فقط باز کردن و ترازو.
        eq = paper._equity()
        report["paper"] = {"opened": opened, "open": settled_open + opened,
                           "closed_now": settled_closed, **eq}
        act(f"دفتر کاغذی: {opened} سفارش تازه گذاشته شد، {settled_closed} معامله "
            f"اول چرخه بسته شد، {settled_open + opened} سفارش باز است")
        print(f"دفتر کاغذی: {opened} سفارش جدید، {settled_open + opened} باز، "
              f"{settled_closed} بسته — "
              f"${eq['balance']} ({eq['return_pct']:+.2f}٪) از {eq['trades']} معامله")
    except Exception as e:                           # noqa: BLE001 - the book is not the analysis
        print(f"دفتر کاغذی: {type(e).__name__}: {e}")

    # دسته‌بندی از پیپرمود (دستور حمید، ۱۴ اوت): «کدام استراتژی در کدام
    # تایم‌فریم بیشتر جواب می‌دهد، اردر بلاک روی کدام ارز و تایم‌فریم بهتر
    # است.» داخل همین گزارش می‌نشیند نه فایل جدا، تا پنل بدون فچ دوم
    # ببیندش و هیچ‌وقت از دفتر عقب نیفتد.
    try:
        from hamid import classify as _cls
        _cj = _cls.build()
        report["classify"] = {
            "n_trades": _cj["n_trades"], "timeframes": _cj["timeframes"],
            "headline": _cj["headline"], "rule": _cj["rule"],
            "source": _cj["source"],
            "alpha_note": _cj["strategy_by_tf"]["alpha_note"],
            # «چقدر مانده تا حکم» — تا این روی پنل نباشد، سرعت یادگیری
            # فقط یک حس است، نه عددی که بشود دنبالش کرد.
            "closest_to_verdict": _cj.get("closest_to_verdict") or [],
        }
        for ln in _cls.fa_lines(_cj, limit=3):
            act("📊 " + ln)
    except Exception as e:                           # noqa: BLE001 - جدول، چرخه را نمی‌کشد
        print(f"دسته‌بندی: {type(e).__name__}: {e}")

    # Deliver. telegram.py refuses loudly and sends nothing without credentials,
    # so this is safe to call before Hamid has added the token.
    if mode == "active" and report.get("setups"):
        try:
            import telegram
            outs = [_for_telegram(x) for x in report["setups"] if not x.get("waiting")]
            for s_ in outs:
                s_["analyzed_at"] = report["generated"]
            sent = telegram.send_signals(outs, _tg_chart)   # چارت ۵د + واترمارک
            report["telegram"] = sent
            if sent:
                act(f"{sent} سیگنال با چارت به تلگرام فرستاده شد")
        except Exception as e:                     # noqa: BLE001 - delivery is not the analysis
            print(f"تلگرام: {type(e).__name__}: {e}")

    # امتیازدهی اتاق‌ها — راندمان هر اتاق بر اساس شواهد داخل brain/. تا حالا
    # هیچ ورک‌فلویی این را اجرا نمی‌کرد؛ تنها جای اجرایش داخل selftest بود،
    # یعنی «حقوق اتاق‌ها» فقط وقتی تازه می‌شد که کسی دستی تست می‌گرفت. حالا هر
    # چرخه اجرا می‌شود و دیده‌بان هم تازگی‌اش را جدا چک می‌کند.
    try:
        import subprocess as _sp
        r_pay = _sp.run([sys.executable, str(HERE.parent / "payroll.py")],
                        capture_output=True, text=True, timeout=120)
        if r_pay.returncode == 0:
            pj = json.loads((ROOT / "brain" / "rooms" / "payroll.json").read_text())
            base = pj.get("base", 1000)
            rooms = pj.get("rooms") or {}
            # جریمه، نه فقط پاداش: اتاقی که کم بیاورد از حقوق پایه کم می‌شود و
            # پنل همین را نشان می‌دهد — مسئولیت وقتی واقعی است که دیده شود.
            detail = {name: {"score": r.get("score"), "salary": r.get("salary"),
                             "bonus": r.get("bonus", 0),
                             "penalty": max(0, base - (r.get("salary") or base)),
                             "why": r.get("why")}
                      for name, r in rooms.items()}
            fined = [n for n, r in detail.items() if r["penalty"] > 0]
            report["payroll"] = {"rooms": len(rooms), "total": pj.get("total"),
                                 "base": base, "detail": detail}
            act(f"حقوق‌دهی اتاق‌ها: {len(rooms)} اتاق امتیاز گرفت"
                + (f"، {len(fined)} اتاق جریمه شد ({'، '.join(fined[:4])})" if fined else "، بدون جریمه"))
            print(f"راندمان اتاق‌ها: {report['payroll']['rooms']} اتاق امتیاز گرفت")
        else:
            print(f"payroll شکست خورد: {r_pay.stderr[-200:]}")
    except Exception as e:                           # noqa: BLE001 - امتیازدهی چرخه را نمی‌کشد
        print(f"payroll: {type(e).__name__}: {e}")

    # آلارم‌های رسیده — بازبینی و سیگنال، در هر دو حالت فعال و آرام
    try:
        fired = watch_alarms()
        if fired:
            from hamid.analyze_pump import rsi as _rsi
            from hamid.structure import atr as _atr
            # آلارم‌ها هم از همان دروازهٔ بقیه رد می‌شوند — یافتهٔ بازبینی
            # معماری: این تنها مسیری بود که سیگنال بدون ناظر به حمید می‌رسید.
            try:
                from hamid import paper as _pgate
                _exp_idx = _pgate.experience_index()
            except Exception:                        # noqa: BLE001
                _exp_idx = {}
            try:
                from hamid import memory as _amem
            except Exception:                        # noqa: BLE001
                _amem = None
            sigs = []
            for al in fired:
                try:
                    rows = sources.klines(al["sym"], "15m", 120)
                    cs = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                           "c": k[4], "v": k[5]} for k in rows]
                    r15, av = _rsi(cs), _atr(cs) or 0
                    if not av:
                        continue
                    d = al.get("dir", "LONG")
                    # بازبینی: در اشباع دنبال قیمت نمی‌دویم — همان قانونی که
                    # حمید برای نقطهٔ ورودِ کم‌استاپ گذاشته
                    if r15 is not None and ((d == "LONG" and r15 >= 78) or
                                            (d == "SHORT" and r15 <= 22)):
                        act(f"آلارم {al['sym']} رسید ولی RSI پانزده‌دقیقه {r15} — "
                            "اشباع است، سیگنال نشد")
                        continue
                    e_ = _exp_idx.get((al["sym"], d))
                    if e_ and not e_["thin"] and e_["mean_r"] < 0 and e_["win_pct"] < 45:
                        act(f"ناظر تجربه آلارم {al['sym']} را رد کرد — "
                            f"{e_['n']} معاملهٔ قبلی، میانگین {e_['mean_r']}R")
                        continue
                    mem_note = None
                    if _amem:
                        try:
                            mem_note = _amem.consult(al["sym"], d, "alarm")["note"]
                        except Exception:            # noqa: BLE001
                            pass
                    px = al["price"]
                    sgn = 1 if d == "LONG" else -1
                    sig = {"sym": al["sym"], "tf": "15m", "dir": d, "entry": px,
                           "sl": round(px - sgn * 0.8 * av, 10),
                           "tp1": round(px + sgn * 1.6 * av, 10),
                           "tp2": round(px + sgn * 2.4 * av, 10), "rr": 2.0,
                           "memory": mem_note,
                           "analyzed_at": al.get("triggered_at"),
                           # همیشه «alarm» — بازبینی کد: با استراتژی اصلی (ibs/smc)
                           # سهمیهٔ پرشده آلارم را می‌انداخت و قول «رسید=سیگنال» می‌شکست
                           "strategy": "alarm",
                           "strategyName": (al.get("strategyName") or "آلارم رادار")
                           + " — قیمت رسید",
                           "footer": "<i>آلارمِ رسیدن قیمت به ناحیهٔ ازپیش‌ثبت‌شده — "
                                     "رکورد این مسیر جدا اندازه‌گیری می‌شود.</i>"}
                    # شرایط لحظهٔ باز شدن — بدون این، دلیل استاپِ آلارم‌ها
                    # بعداً قابل توضیح نبود (استاپ‌های ۱۱ اوت همه ctx خالی داشتند)
                    sig["_stop_pct"] = round(abs(px - sig["sl"]) / px * 100, 2)
                    try:
                        from hamid import liquidity as _lq2
                        sig["_liq"] = _lq2.read(cs, d)["side"]
                    except Exception:                # noqa: BLE001
                        sig["_liq"] = None
                    sigs.append(sig)
                except Exception as e:               # noqa: BLE001 - یک آلارم بقیه را نمی‌کشد
                    print(f"بازبینی آلارم {al.get('sym')}: {type(e).__name__}")
            report["alarms_fired"] = [{"sym": x["sym"], "entry": x["entry"],
                                       "name": x["strategyName"]} for x in sigs]
            if sigs:
                import telegram
                sent_al = telegram.send_signals(sigs, _tg_chart)
                from hamid import paper as _pp
                _pp.open_from([{"symbol": x["sym"], "dir": x["dir"],
                                "entry": x["entry"], "sl": x["sl"], "tp1": x["tp1"],
                                "tp2": x["tp2"], "stage_tag": "alarm",
                                "stop_pct": x.get("_stop_pct"),
                                "liq": x.get("_liq"),
                                "tg_msg_id": x.get("tg_msg_id")} for x in sigs],
                              {"mode": mode})
                act(f"⏰ {len(sigs)} آلارم فعال‌شده سیگنال شد"
                    + (f"، {sent_al} به تلگرام رفت" if sent_al else "")
                    + " — و برای اندازه‌گیری، کاغذی هم ثبت شد")
    except Exception as e:                           # noqa: BLE001 - آلارم چرخه را نمی‌کشد
        print(f"پایش آلارم: {type(e).__name__}: {e}")

    # مرور دوساعته — ثبت قابل‌مقایسه برای نمره دادن به تغییرِ هر مرور
    try:
        rv = review_cycle()
        if rv:
            report["review"] = rv
        else:
            report["review"] = (brain.room_load("review", {}) or {}).get("history", [None])[0]
    except Exception as e:                           # noqa: BLE001
        print(f"مرور دوساعته: {type(e).__name__}: {e}")

    # دیده‌بان پنل — هر چرخه، نه روزی دو بار. آن باگ ۳۹ ساعته دقیقاً به این
    # دلیل زنده ماند که هیچ‌کس همان جایی را نگاه نمی‌کرد که حمید نگاه می‌کند.
    try:
        from hamid import watchdog
        bad = watchdog.run(alert=True, quiet=True)
        report["watchdog"] = {"ok": not bad,
                              "problems": [{"name": n, "detail": d} for n, d in bad]}
        if bad:
            print(f"دیده‌بان: {len(bad)} خرابی — " +
                  "، ".join(n for n, _ in bad))
        else:
            print("دیده‌بان: پنل سالم است")
    except Exception as e:                           # noqa: BLE001
        print(f"دیده‌بان اجرا نشد: {type(e).__name__}: {e}")

    st["modes"][mode] = st["modes"].get(mode, 0) + 1
    act("چرخه تمام شد — نتیجه روی پنل منتشر می‌شود")
    report["activity"] = ACTIVITY[-25:]
    if not a.dry:
        _save_state(st)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "hamid-latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, default=str))
        print(f"نوشته شد در signals/hamid-latest.json")

    brain.event("cycle_done", mode=mode, seconds=round(time.time() - t0, 1),
                signals_today=st["signals"])
    print(f"چرخه در {time.time() - t0:.1f} ثانیه تمام شد — "
          f"{st['signals']} سیگنال امروز از هدف {DAILY_TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
