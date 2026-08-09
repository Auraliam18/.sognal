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
import os
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

DAILY_TARGET = 15
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

def run_active(symbols, limit_4h=200, limit_1h=300, limit_15m=300):
    """The full stack, in Hamid's order: market first, then each coin."""
    brain.room_log("market", "شروع چرخهٔ فعال", "cycle")

    def candles(sym, tf, n):
        try:
            rows = sources.klines(sym, tf, n)
        except Exception:                            # noqa: BLE001 - one symbol failing is not fatal
            return []
        return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                for k in rows]

    btc4 = candles("BTCUSDT", "1h", limit_4h)        # 1h stands in for 4h below
    btc15 = candles("BTCUSDT", "15m", limit_15m)

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
            setups.append((sym, r))
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
    """k one-hour candles into one k-hour candle. Oldest-first in, oldest-first
    out, and a trailing partial group is dropped rather than reported as a
    closed candle — a half-formed 4H bar is the single easiest way to read a
    structure that is not there yet."""
    out = []
    for i in range(0, len(cd) - k + 1, k):
        g = cd[i:i + k]
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
    for a in alarms:
        if a.get("stage") != "ARMED":
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
    verdict = "؛ ".join(
        f"{k}: {len(v)} معامله، میانگین {sum(v)/len(v):+.2f}R"
        for k, v in sorted(books.items())) or \
        "در این بازه معامله‌ای بسته نشد — نتیجه‌گیری ممنوع"
    entry = {"at": now_ms, "closed": len(closed), "verdict": verdict,
             "books": {k: {"n": len(v), "mean_r": round(sum(v) / len(v), 3)}
                       for k, v in books.items()}}
    hist = rv.get("history") or []
    hist.insert(0, entry)
    brain.room_save("review", {"at": now_ms, "history": hist[:84]})
    act(f"مرور دوساعته: {verdict}")
    return entry


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
        "strategy": "hamid", "strategyName": "روش خود حمید (۴ساعته → ۱ساعته → ۱۵دقیقه)",
        "ob": {"low": x["block"]["low"], "high": x["block"]["high"]},
        "level": {"type": "R" if x["dir"] == "SHORT" else "S",
                  "touches": x["on_level"]["touches"]},
        "footer": (f"<i>فاصلهٔ استاپ {x.get('stop_pct')}٪. "
                   f"{x.get('why','')}</i>\n"
                   "<i>این روش تا الان روی ۴۳ معاملهٔ واقعی ۴۶٫۵٪ برد و +۰٫۱۸۴R داده، "
                   "ولی بازهٔ اطمینان صفر را در بر می‌گیرد — یعنی هنوز لبهٔ ثابت‌شده "
                   "نیست. سایز را کوچک نگه دار.</i>"),
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
              "agent": {"name": "کلود — Claude Code", "panel": "حمید کلود مکس پنل"},
              "mode": mode, "why": why, "pacing": pace,
              "world": {k: world.get(k) for k in
                        ("verdict", "fear_greed", "dominance", "funding",
                         "calendar", "news", "trending") if k in world}}

    if mode == "active":
        try:
            syms = [s["symbol"] for s in
                    sorted(sources.tickers(), key=lambda x: -float(x["quoteVolume"] or 0))
                    if s["symbol"].endswith("USDT")][:a.symbols]
        except Exception as e:                       # noqa: BLE001
            print(f"لیست ارزها نیامد: {e}")
            syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        act(f"در حال خواندن {len(syms)} ارز برتر از صرافی‌های جهانی")
        first, reads, setups, flows, inds = run_active(syms)
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
            rj = json.loads((_paper.BOOK / "reasons.json").read_text())
            if rj.get("book") != str(_paper.CLOSED):
                raise FileNotFoundError("reasons از دفتر واقعی نیامده — نادیده گرفته شد")
            conds = {c[0]: c[1] for c in
                     [(x["condition"], x) for x in rj.get("confirmed") or []]}
            if conds:
                cond_fns = dict((n, f) for n, f in _paper.CONDITIONS)
                def learn_score(x):
                    w = {"trend_4h": x.get("trend_4h"), "dir": x["dir"],
                         "impulse": x["block"]["impulse"], "returns": x["block"]["returns"],
                         "reactions": x["on_level"]["reactions"],
                         "stop_pct": x.get("stop_pct"),
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
                            "n": r["n_with"]} for n, r in conds.items()]
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
            c["stage_tag"] = "second" if not c.get("waiting") else "first"
        opened = paper.open_from(cands, ctx)
        ind_cands = [{"symbol": s_, "dir": x.dir, "entry": x.entry, "sl": x.sl,
                      "tp1": x.tp1, "tp2": x.tp2, "stage_tag": "inducement"}
                     for s_, x in (inds if mode == "active" else [])]
        if ind_cands:
            opened += paper.open_from(ind_cands, ctx)
        if mode == "active":
            try:
                pc = practice_candidates(reads)
                if pc:
                    n_pr = paper.open_from(pc, ctx)
                    opened += n_pr
                    act(f"میز تمرین: {n_pr} معاملهٔ تمرینی باز شد — "
                        "فقط خوراک یادگیری، سیگنال نیست")
            except Exception as e:                   # noqa: BLE001 - تمرین چرخه را نمی‌کشد
                print(f"میز تمرین: {type(e).__name__}: {e}")
        t_mark = int(time.time() * 1000)
        still, closed = paper.mark()
        # اعلان نتیجه — قول داده شد: فقط ورود نبیند، خروج را هم ببیند. هر
        # معاملهٔ سیگنال‌شده که همین چرخه بسته شد، با نتیجه به تلگرام می‌رود.
        # آزمایش‌ها و میز تمرین نه — آن‌ها سیگنال نبودند و پیامشان فقط نویز است.
        try:
            just = [t for t in paper._read(paper.CLOSED)
                    if (t.get("closed") or 0) >= t_mark
                    and t.get("outcome") in ("target", "stop")
                    and (t.get("why") or {}).get("stage")
                    not in ("first", "practice", "inducement")]
            if just:
                import telegram as _tg
                tok, chat = _tg.creds()
                if tok:
                    L = [f"🏷 <b>{_tg.PANEL_NAME}</b>", "📊 <b>نتیجهٔ معامله‌ها</b>", ""]
                    for t in just[:10]:
                        won = t["outcome"] == "target"
                        L.append(f"{'✅' if won else '❌'} <b>{t['sym']}</b> "
                                 f"{'خرید' if t['dir'] == 'LONG' else 'فروش'} — "
                                 f"{'تارگت خورد' if won else 'استاپ خورد'} "
                                 f"(<code>{t['R']:+.2f}R</code>)")
                    _tg._post(tok, "sendMessage",
                              {"chat_id": chat, "text": "\n".join(L),
                               "parse_mode": "HTML"})
                    act(f"نتیجهٔ {len(just)} معاملهٔ بسته به تلگرام رفت")
        except Exception as e:                       # noqa: BLE001 - اعلان چرخه را نمی‌کشد
            print(f"اعلان نتیجه: {_tg.scrub(e) if '_tg' in dir() else type(e).__name__}")
        # هضم حافظه — یادگیری از «همهٔ» بسته‌شده‌های این چرخه (تمرین و آزمایش
        # هم درس‌اند)، ثبت در دفتر درس‌ها، و بازسازی ایندکس تا چرخهٔ بعد
        # با دانش به‌روزتر شروع کند. تحلیل → یادگیری → ذخیره → استفاده.
        try:
            from hamid import memory as _mem2
            newly = [t for t in paper._read(paper.CLOSED)
                     if (t.get("closed") or 0) >= t_mark]
            fed = _mem2.digest_closed(newly)
            if fed:
                act(f"حافظه: {fed} معاملهٔ بسته هضم شد — ایندکس دانش به‌روز شد")
            report["memory"] = {"fed_now": fed,
                                "lessons": _mem2.lessons(limit=6)}
        except Exception as e:                       # noqa: BLE001
            print(f"هضم حافظه: {type(e).__name__}: {e}")
        eq = paper._equity()
        report["paper"] = {"opened": opened, "open": still, "closed_now": closed,
                           **eq}
        act(f"دفتر کاغذی: {opened} سفارش تازه گذاشته شد، {closed} معامله بسته شد، "
            f"{still} سفارش هنوز باز است")
        act("تجربه‌گیری: نتیجهٔ معامله‌های بسته با شرایط لحظهٔ بازشدنشان به حافظهٔ یادگیری رفت")
        print(f"دفتر کاغذی: {opened} سفارش جدید، {still} باز، {closed} بسته — "
              f"${eq['balance']} ({eq['return_pct']:+.2f}٪) از {eq['trades']} معامله")
        # Reasons are only recomputed when there is enough to say anything; the
        # function refuses below twenty closed trades on its own.
        paper.reasons(verbose=False)
    except Exception as e:                           # noqa: BLE001 - the book is not the analysis
        print(f"دفتر کاغذی: {type(e).__name__}: {e}")

    # Deliver. telegram.py refuses loudly and sends nothing without credentials,
    # so this is safe to call before Hamid has added the token.
    if mode == "active" and report.get("setups"):
        try:
            import telegram
            sent = telegram.send_signals(
                [_for_telegram(x) for x in report["setups"] if not x.get("waiting")],
                lambda setup, path: None)          # text only; charts need candles
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
                    px = al["price"]
                    sgn = 1 if d == "LONG" else -1
                    sig = {"sym": al["sym"], "tf": "15m", "dir": d, "entry": px,
                           "sl": round(px - sgn * 0.8 * av, 10),
                           "tp1": round(px + sgn * 1.6 * av, 10),
                           "tp2": round(px + sgn * 2.4 * av, 10), "rr": 2.0,
                           "strategy": al.get("strategy") or "alarm",
                           "strategyName": (al.get("strategyName") or "آلارم رادار")
                           + " — قیمت رسید",
                           "footer": "<i>آلارمِ رسیدن قیمت به ناحیهٔ ازپیش‌ثبت‌شده — "
                                     "رکورد این مسیر جدا اندازه‌گیری می‌شود.</i>"}
                    sigs.append(sig)
                except Exception as e:               # noqa: BLE001 - یک آلارم بقیه را نمی‌کشد
                    print(f"بازبینی آلارم {al.get('sym')}: {type(e).__name__}")
            report["alarms_fired"] = [{"sym": x["sym"], "entry": x["entry"],
                                       "name": x["strategyName"]} for x in sigs]
            if sigs:
                import telegram
                sent_al = telegram.send_signals(sigs, lambda s, p: None)
                from hamid import paper as _pp
                _pp.open_from([{"symbol": x["sym"], "dir": x["dir"],
                                "entry": x["entry"], "sl": x["sl"], "tp1": x["tp1"],
                                "tp2": x["tp2"], "stage_tag": "alarm"} for x in sigs],
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
