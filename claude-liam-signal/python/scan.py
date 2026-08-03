#!/usr/bin/env python3
"""What the engine says about the market right now, on real candles.

The panel normally does this itself in the browser. Where Binance is
unreachable — which is most of Iran, and this project's own container — the
panel has nothing to chart and correctly says so instead of inventing a signal.
This script does the same work somewhere the network reaches, and writes the
result to signals/latest.json for the panel to display.

Nothing here decides anything the engine would not have decided. Same engine,
same gates, same thresholds, lifted out of index.html. The only judgement added
is the ordering, which follows what the real-candle backtest measured:

    5m   n=1860  win 27.6%  E=+0.141R  [+0.062, +0.220]   edge, interval clear
    15m  n=2071  win 18.3%  E=+0.005R  [-0.052, +0.063]   no measurable edge

So a 5m setup outranks a 15m one of the same stage. That is a ranking, not a
gate — 15m spanning zero means no evidence of an edge, not evidence of none, and
switching it off is a bigger claim than one 52-day window supports.

    python3 scan.py --symbols 100 --telegram
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "signals"
sys.path.insert(0, str(HERE))
from backtest import get, top_symbols, MS          # same fetching, same retries
import sources                                      # the venue that actually served
import brain                                        # permanent memory

BARS = 420                                          # engine sees 400 after the open one goes
STAGE_RANK = {"SIGNAL": 3, "ARMED": 2, "PULLBACK_1": 1, "WATCH": 0}
TF_RANK = {"5m": 1, "15m": 0}                       # measured, see the docstring
STRATS = {"smc": "کانال + اردر بلاک", "ibs": "IBS + پولبک"}


def klines_now(sym, tf, bars=BARS):
    rows = get(f"/api/v3/klines?symbol={sym}&interval={tf}&limit={bars}")
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
             "c": float(k[4]), "v": float(k[5])} for k in rows]


def _source_label():
    """Say which venue the numbers came from, not which one was asked first.

    This line is printed on the panel. It read "real Binance candles" whether or
    not Binance had served them, which is the kind of caption that is true until
    the day it silently is not."""
    u = sources.used()
    where = u.get("klines")
    if where is None:
        return "کندل واقعی بایننس، اسکن‌شده روی رانر گیت‌هاب"
    label = next((v["label"] for v in sources.VENUES if v["id"] == where), where)
    return f"کندل واقعی {label}، اسکن‌شده روی رانر گیت‌هاب"


def top_by_48h(n):
    """The most-traded pairs over the last 48 hours, not the last 24.

    Binance's ticker endpoint only reports a rolling 24h window, so using it
    would quietly answer a different question from the one asked. Summing 48
    hourly candles per pair costs one extra request each and answers the actual
    one. The 24h ranking is used only to decide which pairs are worth measuring
    properly — a coin outside the top 250 by day is not going to enter the top
    100 by two days.
    """
    shortlist = top_symbols(250)
    vols = {}

    def vol48(sym):
        rows = get(f"/api/v3/klines?symbol={sym}&interval=1h&limit=48")
        return sym, sum(float(r[7]) for r in rows)      # index 7 is quote volume

    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(vol48, s) for s in shortlist]:
            try:
                sym, v = f.result()
                vols[sym] = v
            except Exception:                            # noqa: BLE001 - drop what will not answer
                continue
    ranked = sorted(vols.items(), key=lambda kv: -kv[1])
    return [s for s, _ in ranked[:n]]


def ctx_dir(setup):
    """The market direction the mined history was keyed on. The live scan has no
    per-setup dominance series, so this stays '?' and the lookup falls back to
    the symbol record — which is the honest degradation, not a guess."""
    return setup.get("dom_dir", "?")


def usdt_dominance():
    """Context only — it never decides, it can only conflict with a direction."""
    try:
        rows = get("/api/v3/ticker/24hr")
        by = {r["symbol"]: r for r in rows}
        btc = by.get("BTCUSDT")
        if not btc:
            return None
        return {"btcChange": float(btc["priceChangePercent"])}
    except Exception:                                # noqa: BLE001 - context is optional
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=100)
    ap.add_argument("--tf", default="5m,15m")
    ap.add_argument("--cores", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--telegram", action="store_true",
                    help="deliver new signals as charts (needs TELEGRAM_BOT_TOKEN/CHAT_ID)")
    args = ap.parse_args()
    tfs = [t.strip() for t in args.tf.split(",") if t.strip()]

    t0 = time.time()
    syms = top_by_48h(args.symbols)
    pairs = [(s, tf) for tf in tfs for s in syms]
    print(f"scanning the {len(syms)} most-traded pairs of the last 48h "
          f"× {len(tfs)} timeframes", flush=True)

    jobs, failed = [], 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(klines_now, s, tf): (s, tf) for s, tf in pairs}
        for f, (s, tf) in futs.items():
            try:
                cd = f.result()
                if len(cd) >= 360:
                    jobs.append({"sym": s, "tf": tf, "candles": cd})
            except Exception:                        # noqa: BLE001 - one bad series is not fatal
                failed += 1
    print(f"  {len(jobs)} series fetched, {failed} failed", flush=True)
    if not jobs:
        sys.exit("no candles — every venue refused, not just Binance")

    tmp = HERE / ".scan-tmp"
    tmp.mkdir(exist_ok=True)
    procs = []
    for i in range(args.cores):
        shard = jobs[i::args.cores]
        if not shard:
            continue
        p = tmp / f"scan-{i}.json"
        p.write_text(json.dumps(shard))
        procs.append(subprocess.Popen(["node", str(HERE / "scan_worker.js"), str(p)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    setups = []
    for p in procs:
        so, se = p.communicate()
        if p.returncode != 0:
            sys.exit(f"scan worker failed: {se.decode()[:600]}")
        setups += json.loads(so.decode() or "[]")

    setups.sort(key=lambda s: (STAGE_RANK.get(s["stage"], 0), TF_RANK.get(s["tf"], 0),
                               s["conf"] or 0, s["ev"] or 0), reverse=True)

    # ── the learning room is asked before anything is called a signal ─────────
    # Storing experience is not learning; using it is. Every setup is looked up
    # against what this coin, this strategy and this direction have actually done
    # before, and against setups of the same coarse shape. Where the record is
    # clearly bad on a real sample the setup is held back rather than sent — and
    # where the record is thin it says so and changes nothing, because a verdict
    # built on four trades is not evidence.
    idx = brain.build_index()
    consulted = held = 0
    for s in setups:
        shape = brain.shape_key({
            "strategy": s.get("strategy"), "dir": s.get("dir"), "tf": s.get("tf"),
            "rr": s.get("rr"), "adx": s.get("adx"),
            "dom_dir": (ctx_dir(s)),
        })
        rec = brain.recall(sym=s["sym"], strategy=s.get("strategy"),
                           direction=s.get("dir"), shape=shape, idx=idx)
        best = rec.get("symbol") or rec.get("shape")
        s["learning"] = {
            "verdict": rec["verdict"],
            "n": best["n"] if best else 0,
            "hit": best["hit"] if best else None,
            "ev": best["ev"] if best else None,
        }
        consulted += 1
        if s["stage"] == "SIGNAL" and rec["verdict"] == "bad":
            s["stage"] = "ARMED"
            s["skip"] = (f"اتاق یادگیری مخالف است — {best['n']} مورد مشابه، "
                         f"برد {best['hit']}٪، انتظار {best['ev']:+.2f}R")
            held += 1
    print(f"learning room consulted on {consulted} setups, held back {held}", flush=True)

    counts = {k: sum(1 for s in setups if s["stage"] == k) for k in STAGE_RANK}
    signals = [s for s in setups if s["stage"] == "SIGNAL"]

    # Each strategy is counted on its own. Blurring them together would hide the
    # thing worth knowing, which is whether one of them is carrying the other.
    per_strategy = {
        k: {"name": v,
            "signals": sum(1 for s in signals if s.get("strategy") == k),
            "armed": sum(1 for s in setups if s.get("strategy") == k and s["stage"] == "ARMED"),
            "watching": sum(1 for s in setups if s.get("strategy") == k and s["stage"] == "WATCH")}
        for k, v in STRATS.items()}

    # A setup that has not fired yet is worth an alarm at the price that would
    # make it fire, so it gets looked at the moment price arrives rather than
    # whenever the next scan happens to run.
    alarms = [{"sym": s["sym"], "tf": s["tf"], "dir": s["dir"],
               "strategy": s.get("strategy"), "strategyName": s.get("strategyName"),
               "price": s["entry"], "now": s.get("price"),
               "distancePct": (abs((s.get("price") or s["entry"]) - s["entry"]) / s["entry"] * 100)
               if s["entry"] else None,
               "why": s.get("waitReason") or s.get("skip") or "منتظر تأییدیه",
               "stage": s["stage"]}
              for s in setups if s["stage"] in ("ARMED", "PULLBACK_1")]
    alarms.sort(key=lambda a: a["distancePct"] if a["distancePct"] is not None else 999)

    # The events room: what was true at this moment, written down now so the
    # learning room can ask later which conditions went with which outcome.
    ctx = usdt_dominance()
    brain.event("scan", symbols=len(syms), series=len(jobs),
                counts=counts, per_strategy=per_strategy, context=ctx,
                signals=[{"sym": s["sym"], "tf": s["tf"], "dir": s["dir"],
                          "strategy": s.get("strategy"), "entry": s["entry"],
                          "sl": s["sl"], "tp1": s["tp1"], "rr": s["rr"]}
                         for s in signals])
    brain.room_save("scan", {"lastScan": int(time.time() * 1000),
                             "counts": counts, "per_strategy": per_strategy})
    brain.room_save("radar", {"alarms": alarms[:80]})
    for s in signals:
        brain.room_log("watch", f"{s['sym']} {s['tf']} {s['dir']} — {s.get('strategyName','')}", "sig")

    report = {
        "generated": int(time.time() * 1000),
        "generatedText": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source": _source_label(),
        "symbols": len(syms), "series": len(jobs), "timeframes": tfs,
        "counts": counts,
        "per_strategy": per_strategy,
        "alarms": alarms[:40],
        "learning": {
            "experiences": len(brain.read(brain.LEARNING / "experiences.jsonl")),
            "heldBack": held,
            "note": "قبل از هر سیگنال، سابقهٔ همان ارز با همان استراتژی و همان جهت "
                    "پرسیده می‌شود. اگر سابقه بد و نمونه کافی باشد، سیگنال نگه داشته "
                    "می‌شود. اگر سابقه کم باشد چیزی تغییر نمی‌کند.",
        },
        "context": ctx,
        "note": "۵ دقیقه بالاتر از ۱۵ دقیقه رتبه می‌گیرد، چون بک‌تست روی کندل واقعی "
                "روی ۵ دقیقه لبه اندازه گرفت (+۰.۱۴۱R با بازهٔ کاملاً بالای صفر) و روی "
                "۱۵ دقیقه نه (+۰.۰۰۵R، بازه صفر را در بر می‌گیرد). این فقط رتبه‌بندی است — "
                "هیچ ارزی به‌خاطر تایم‌فریمش حذف نمی‌شود.",
        "signals": signals,
        "watch": [s for s in setups if s["stage"] != "SIGNAL"][:60],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    # Telegram gets the candles so it can draw the setup; the published file does
    # not, or 236 setups × 120 bars would make it megabytes for no reader.
    if args.telegram:
        from telegram import send_signals

        def draw(s, path):
            if not s.get("candles"):
                return None
            from chart import render
            return render(s["candles"], s, path)

        send_signals(signals, draw)

    def strip(s):
        return {k: v for k, v in s.items() if k != "candles"}

    report["signals"] = [strip(s) for s in report["signals"]]
    report["watch"] = [strip(s) for s in report["watch"]]
    (OUT / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

    print(f"\n{counts['SIGNAL']} signals · {counts['ARMED']} armed · "
          f"{counts['PULLBACK_1']} first pullback · {counts['WATCH']} watching")
    for k, v in per_strategy.items():
        print(f"  {v['name']:<22} {v['signals']:>3} signal · {v['armed']:>3} armed · {v['watching']:>4} watching")
    if alarms:
        print(f"\nalarms set on {len(alarms)} setups waiting for confirmation — nearest:")
        for a in alarms[:6]:
            d = f"{a['distancePct']:.2f}%" if a["distancePct"] is not None else "—"
            print(f"  {a['sym']:<12} {a['tf']:<4} {a['dir']:<5} at {a['price']:<12.6g} ({d} away) — {a['why']}")
    for s in signals[:20]:
        room = f"{s['room']['r']}×" if s.get("room") else "—"
        print(f"  🚨 {s['sym']:<12} {s['tf']:<4} {s['dir']:<5} "
              f"entry {s['entry']:<12.6g} sl {s['sl']:<12.6g} tp1 {s['tp1']:<12.6g} "
              f"rr {s['rr']}  conf {s['conf']}%  ev {s['ev']:.2f}R  room {room}")
    if not signals:
        print("  no setup passed every gate this pass — that is a normal result, not a fault")
    print(f"\nwritten to signals/latest.json in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
