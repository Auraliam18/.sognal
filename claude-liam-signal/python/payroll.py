#!/usr/bin/env python3
"""Scores the rooms, pays them, and pays a bonus when a room earns one.

A room is a job, and a job that is never appraised drifts. This is the appraisal:
every room is scored on what it actually did, and the score sets a salary and,
occasionally, a bonus. It is play money and it changes no trade — the point is
that a room which has stopped contributing becomes visible instead of quietly
carrying on.

Nothing here is a matter of taste. Each room is scored on evidence that already
exists in brain/, and a room with nothing to show scores zero rather than a
polite average:

  scan      did it look at the market, and how much of it
  watch     did the setups it passed forward turn out positive
  radar     did the alarms it set get reached
  paper     did the practice desk settle trades and keep expectancy above zero
  learn     is the memory growing, and does it hold findings rather than noise
  intel     was the market context recorded when it mattered
  sup       did the supervisor's vetoes correlate with worse outcomes
  calib     did a change it made get graded on the cycle after

Salary follows the score. A bonus needs more than a good week: the room has to
beat its own trailing average, which is what stops a lucky day paying twice.

    python3 payroll.py            # score, pay, write brain/rooms/<room>/pay.json
"""
import json, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import brain

BASE = 1000                       # play money, monthly
BONUS_CAP = 0.35                  # a bonus can be at most this share of base


def _pct(part, whole):
    return 0.0 if not whole else max(0.0, min(1.0, part / whole))


def score_rooms():
    """Every score is 0..1 and every one is read off something already recorded."""
    exps = brain.read(brain.LEARNING / "experiences.jsonl")
    idx_p = brain.LEARNING / "index.json"
    idx = json.loads(idx_p.read_text()) if idx_p.exists() else {}
    events = []
    for f in sorted(brain.EVENTS.glob("*.jsonl"))[-7:]:
        events += brain.read(f)
    scans = [e for e in events if e.get("kind") == "scan"]
    out = {}

    # scan — breadth of coverage on the most recent pass
    last = scans[-1] if scans else None
    out["scan"] = {
        "score": _pct(last.get("series", 0), 200) if last else 0.0,
        "why": f"{last.get('series',0)} سری در آخرین اسکن" if last else "اسکنی ثبت نشده",
    }

    # watch — did what it forwarded actually pay
    fired = [e for e in exps if e.get("r") is not None]
    ev = statistics.fmean([e["r"] for e in fired]) if len(fired) >= 30 else None
    out["watch"] = {
        "score": 0.0 if ev is None else max(0.0, min(1.0, 0.5 + ev)),
        "why": (f"{len(fired)} ستاپ، انتظار {ev:+.3f}R" if ev is not None
                else f"فقط {len(fired)} ستاپ — هنوز برای قضاوت کم است"),
    }

    # radar — were the alarms it set actually reached
    radar = brain.room_load("radar", {})
    alarms = radar.get("alarms", [])
    near = [a for a in alarms if (a.get("distancePct") or 99) < 1.0]
    out["radar"] = {
        "score": _pct(len(near), 12),
        "why": f"{len(alarms)} آلارم، {len(near)} تای آن کمتر از ۱٪ فاصله",
    }

    # paper — settled trades and expectancy above zero
    paper = brain.room_load("paper", {})
    closed = paper.get("closed", 0)
    net = paper.get("net", 0)
    out["paper"] = {
        "score": min(1.0, _pct(closed, 60) * (1.0 if net > 0 else 0.4)),
        "why": f"{closed} تمرین بسته‌شده، خالص {net:+.1f}R",
    }

    # learn — is the memory growing, and does it hold findings
    pats = len(list(brain.PATTERNS.glob("*.json")))
    out["learn"] = {
        "score": min(1.0, 0.6 * _pct(len(exps), 2000) + 0.4 * _pct(pats, 8)),
        "why": f"{len(exps)} تجربه، {pats} الگوی تأییدشده",
    }

    # intel — was context recorded alongside the setups
    with_ctx = sum(1 for e in exps if e.get("btc_dir") or e.get("btcdom_dir"))
    out["intel"] = {
        "score": _pct(with_ctx, max(1, len(exps))),
        "why": f"{with_ctx} از {len(exps)} تجربه دامیننس همان لحظه را دارد",
    }

    # sup — did the supervisor's refusals track worse outcomes
    vetoed = [e for e in exps if e.get("skip")]
    took = [e for e in exps if not e.get("skip")]
    gap = None
    if len(vetoed) >= 25 and len(took) >= 25:
        gap = statistics.fmean([e["r"] for e in took]) - statistics.fmean([e["r"] for e in vetoed])
    out["sup"] = {
        "score": 0.0 if gap is None else max(0.0, min(1.0, 0.5 + gap)),
        "why": (f"آنچه رد کرد {gap:+.3f}R بدتر بود" if gap is not None
                else "هنوز رد و قبول کافی برای مقایسه نیست"),
    }

    # calib — a change is only worth paying for once it has been graded
    calib = brain.room_load("calib", {})
    graded = calib.get("graded", 0)
    out["calib"] = {
        "score": _pct(graded, 6),
        "why": f"{graded} تغییر نمره‌خورده",
    }

    for r in ("trade", "market", "deep", "chart"):
        st = brain.room_load(r, {})
        out[r] = {"score": 0.35 if st else 0.0,
                  "why": "فعال" if st else "چیزی ثبت نکرده"}
    return out


def pay(scores):
    """Salary from the score; a bonus only for beating the room's own history."""
    result = {}
    for room, s in scores.items():
        hist = brain.room_load(room, {}).get("pay_history", [])
        avg = statistics.fmean(hist[-6:]) if len(hist) >= 3 else None
        salary = round(BASE * (0.4 + 0.6 * s["score"]))
        bonus = 0
        reason = "بدون پاداش"
        if avg is not None and s["score"] > avg + 0.08:
            bonus = round(BASE * BONUS_CAP * min(1.0, (s["score"] - avg) / 0.3))
            reason = f"بهتر از میانگین خودش ({avg:.2f} → {s['score']:.2f})"
        elif avg is None:
            reason = "هنوز سابقهٔ کافی برای مقایسه ندارد"
        elif s["score"] < avg - 0.15:
            reason = f"افت نسبت به میانگین خودش ({avg:.2f} → {s['score']:.2f})"

        st = brain.room_load(room, {})
        st["pay_history"] = (hist + [s["score"]])[-24:]
        st["last_pay"] = {"score": round(s["score"], 3), "salary": salary,
                          "bonus": bonus, "why": s["why"], "bonusWhy": reason,
                          "at": int(time.time() * 1000)}
        brain.room_save(room, st)
        result[room] = st["last_pay"]
    return result


def main():
    scores = score_rooms()
    paid = pay(scores)
    total = sum(p["salary"] + p["bonus"] for p in paid.values())

    ranked = sorted(paid.items(), key=lambda kv: -kv[1]["score"])
    print(f"\n{'اتاق':<10} {'امتیاز':>7} {'حقوق':>8} {'پاداش':>8}   دلیل")
    print("-" * 88)
    for room, p in ranked:
        print(f"{room:<10} {p['score']:>7.2f} {p['salary']:>8} {p['bonus']:>8}   {p['why']}")
    print("-" * 88)
    print(f"{'جمع':<10} {'':>7} {total:>17}")

    idle = [r for r, p in paid.items() if p["score"] < 0.1]
    if idle:
        print(f"\nاتاق‌هایی که چیزی برای نشان دادن ندارند: {', '.join(idle)}")

    report = {"at": int(time.time() * 1000),
              "atText": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
              "base": BASE, "total": total, "rooms": paid}
    (brain.ROOMS / "payroll.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    brain.event("payroll", total=total,
                rooms={r: p["score"] for r, p in paid.items()})
    print(f"\nwritten to brain/rooms/payroll.json")


if __name__ == "__main__":
    main()
