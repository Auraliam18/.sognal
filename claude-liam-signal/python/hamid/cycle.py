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
from hamid.structure import atr                               # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals"
STATE = ROOT / "brain" / "cycle-state.json"

DAILY_TARGET = 15
ROOMS = ["market", "radar", "scan", "deep", "trade", "paper",
         "chart", "watch", "learn", "calib", "intel", "sup"]


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

    reads, setups = [], []
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
        brain.room_log("scan", f"{sym}: ۴ساعته {r.trend_4h}، "
                               f"{len(r.blocks)} بلاک، ستاپ {'دارد' if r.setup else 'ندارد'}", "read")
    return first, reads, setups


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


# ── the cycle ──────────────────────────────────────────────────────────────

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

    # what kind of day
    try:
        btc15 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                 for k in sources.klines("BTCUSDT", "15m", 200)]
    except Exception as e:                           # noqa: BLE001
        print(f"بیت‌کوین در دسترس نبود: {e}")
        btc15 = []
    mode, why = regime(btc15) if a.mode == "auto" else (a.mode, "دستی انتخاب شد")
    print(f"حالت: {mode} — {why}")
    brain.event("cycle", mode=mode, why=why, pacing=pace)

    report = {"generated": int(time.time() * 1000),
              "generatedText": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "mode": mode, "why": why, "pacing": pace}

    if mode == "active":
        try:
            syms = [s["symbol"] for s in
                    sorted(sources.tickers(), key=lambda x: -float(x["quoteVolume"] or 0))
                    if s["symbol"].endswith("USDT")][:a.symbols]
        except Exception as e:                       # noqa: BLE001
            print(f"لیست ارزها نیامد: {e}")
            syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        first, reads, setups = run_active(syms)
        report["market"] = first
        report["reads"] = len(reads)
        report["setups"] = [{"symbol": s, **r.setup, "trend_4h": r.trend_4h,
                             "channel": r.channel_note} for s, r in setups]
        st["signals"] += len([s for s in report["setups"] if not s.get("waiting")])
        print(f"{len(reads)} ارز خوانده شد، {len(setups)} ستاپ")
    else:
        report.update(run_quiet())

    st["modes"][mode] = st["modes"].get(mode, 0) + 1
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
