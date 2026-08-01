#!/usr/bin/env python3
"""Checks every link in the chain and says plainly which ones hold.

"Does it work?" deserves a reproducible answer rather than an assurance. Each
check below either passes on evidence or fails with the reason. Nothing is
skipped quietly: a check that cannot run because something upstream is missing
says so and counts as a failure, because a green run that skipped half its
checks is worse than a red one.

    python3 selftest.py
"""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import brain

RESULTS = []


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:                       # noqa: BLE001 - a throwing check is a failing check
        ok, detail = False, f"{type(e).__name__}: {e}"
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<46} {detail}", flush=True)
    return ok


def node(script, *args):
    p = subprocess.run(["node", str(HERE / script), *[str(a) for a in args]],
                       capture_output=True, text=True, timeout=300)
    return p


# ── the engine ────────────────────────────────────────────────────────────────
def engine_exports():
    p = subprocess.run(["node", "-e", """
      const H=require(process.argv[1]);
      const E=H.loadEngine();
      const want=['smcSetup','ibsPullback','confLearn','confP','confEV'];
      const missing=want.filter(k=>typeof E[k]!=='function');
      console.log(JSON.stringify({missing}));
    """, str(ROOT / "tests" / "harness.js")], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return False, p.stderr.strip()[:160]
    missing = json.loads(p.stdout)["missing"]
    return (not missing), ("both engines callable" if not missing else f"missing {missing}")


def both_strategies_fire():
    """Simulated candles only — this asks whether the wiring runs, not whether
    the strategies are any good. That is what mine.py is for."""
    jobs = HERE / ".selftest-jobs.json"
    p = subprocess.run(["node", "-e", f"""
      const {{simulate}}=require({json.dumps(str(ROOT / 'tests' / 'sim.js'))});
      const mk=(s,n)=>simulate(s,n).map((c,i)=>({{...c,t:1750000000000+i*900000}}));
      const jobs=[];
      for(let s=0;s<6;s++) jobs.push({{sym:'SIM'+s+'USDT',tf:'15m',candles:mk(s*571+13,1400),
        context:{{btc:mk(7,1400),btcdom:mk(9,1400)}},perSide:15}});
      require('fs').writeFileSync({json.dumps(str(jobs))},JSON.stringify(jobs));
    """], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return False, p.stderr.strip()[:160]
    r = node("mine_worker.js", jobs)
    jobs.unlink(missing_ok=True)
    if r.returncode != 0:
        return False, r.stderr.strip()[:200]
    exps = json.loads(r.stdout or "[]")
    by = {}
    for e in exps:
        by[e["strategy"]] = by.get(e["strategy"], 0) + 1
    ok = by.get("ibs", 0) > 0 and by.get("smc", 0) > 0
    return ok, f"ibs={by.get('ibs',0)} smc={by.get('smc',0)}"


def fill_is_required():
    """The correction that mattered most: a trade at an unreached price must not
    be counted. Verified against the source rather than assumed."""
    src = (HERE / "mine_worker.js").read_text()
    has_fn = "function fill(" in src
    used = "if (!f) continue;" in src
    return (has_fn and used), ("fill() defined and enforced" if has_fn and used
                               else "fill gate missing — results would be inflated")


def rr_is_consistent():
    p = subprocess.run(["node", "-e", f"""
      const H=require({json.dumps(str(ROOT / 'tests' / 'harness.js'))});
      const {{simulate}}=require({json.dumps(str(ROOT / 'tests' / 'sim.js'))});
      const E=H.loadEngine(); const out=[];
      for(let s=0;s<25;s++){{
        const cd=simulate(s*97+11,700).map((c,i)=>({{...c,t:i}}));
        const x=E.ibsPullback(cd); if(!x||!x.tp1) continue;
        out.push(Math.abs(x.tp1-x.entry)/Math.abs(x.entry-x.sl));
      }}
      console.log(JSON.stringify({{n:out.length,max:Math.max(...out),min:Math.min(...out)}}));
    """], capture_output=True, text=True, timeout=180)
    if p.returncode != 0:
        return False, p.stderr.strip()[:160]
    d = json.loads(p.stdout)
    ok = d["n"] > 0 and abs(d["max"] - 1.5) < 0.01 and abs(d["min"] - 1.5) < 0.01
    return ok, f"{d['n']} setups, R:R {d['min']:.2f}–{d['max']:.2f} (must be 1.50)"


# ── the brain ─────────────────────────────────────────────────────────────────
def brain_writes_and_reads():
    probe = {"sym": "SELFTEST", "tf": "15m", "dir": "LONG", "strategy": "smc",
             "r": 1.5, "rr": 1.5, "adx": 30, "dom_dir": "UP",
             "reason": "selftest", "outcome": "target2", "win": 1}
    before = len(brain.read(brain.LEARNING / "experiences.jsonl"))
    brain.learn(probe)
    after = len(brain.read(brain.LEARNING / "experiences.jsonl"))
    # remove the probe so a self-test never pollutes the record
    p = brain.LEARNING / "experiences.jsonl"
    lines = [l for l in p.read_text().splitlines() if '"SELFTEST"' not in l]
    p.write_text("\n".join(lines) + ("\n" if lines else ""))
    for f in ("positive.jsonl", "negative.jsonl"):
        q = brain.LEARNING / f
        if q.exists():
            ls = [l for l in q.read_text().splitlines() if '"SELFTEST"' not in l]
            q.write_text("\n".join(ls) + ("\n" if ls else ""))
    return (after == before + 1), f"{before} → {after}, probe removed"


def brain_has_history():
    n = len(brain.read(brain.LEARNING / "experiences.jsonl"))
    return n >= 500, f"{n} experiences stored"


def index_is_current():
    p = brain.LEARNING / "index.json"
    if not p.exists():
        return False, "index.json missing — recall would answer from nothing"
    idx = json.loads(p.read_text())
    n_sym = len(idx.get("by_symbol", {}))
    n_shape = len(idx.get("by_shape", {}))
    return (n_sym > 0 and n_shape > 0), f"{n_sym} symbol keys, {n_shape} shape keys"


def recall_answers_and_refuses():
    """It must answer where there is history and say 'thin' where there is not.
    A recall that always answers is worse than none."""
    idx = json.loads((brain.LEARNING / "index.json").read_text())
    known = None
    for k in idx.get("by_symbol", {}):
        if idx["by_symbol"][k]["n"] >= 12:
            known = k
            break
    if not known:
        return False, "no symbol has enough history to answer from"
    sym, strat, direction = known.split("|")
    good = brain.recall(sym=sym, strategy=strat, direction=direction, idx=idx)
    unknown = brain.recall(sym="NOSUCHCOIN", strategy="smc", direction="LONG", idx=idx)
    ok = good["verdict"] != "thin" and unknown["verdict"] == "thin"
    return ok, f"{sym} {direction} → {good['verdict']}, unknown → {unknown['verdict']}"


def learning_is_consulted():
    """The one that matters. Storing experience is not learning; using it is."""
    src = (HERE / "scan.py").read_text()
    calls = "brain.recall(" in src
    attaches = "learning" in src and "recall" in src
    return (calls and attaches), ("the live scan asks the record before signalling"
                                  if calls else
                                  "NOT CONSULTED — signals ignore everything learned")


def events_room_records():
    files = sorted(brain.EVENTS.glob("*.jsonl"))
    if not files:
        return False, "no event files"
    recs = brain.read(files[-1])
    kinds = sorted({r.get("kind") for r in recs})
    return len(recs) > 0, f"{len(recs)} events today, kinds: {', '.join(kinds)}"


def rooms_have_memory():
    have = [d.name for d in sorted(brain.ROOMS.glob("*")) if (d / "state.json").exists()]
    return len(have) >= 2, f"{len(have)} rooms with saved state: {', '.join(have) or 'none'}"


# ── delivery ──────────────────────────────────────────────────────────────────
def chart_renders():
    from chart import render
    cd = [{"t": i, "o": 100 + i * 0.1, "h": 100.5 + i * 0.1,
           "l": 99.5 + i * 0.1, "c": 100.2 + i * 0.1, "v": 10} for i in range(120)]
    s = {"sym": "TESTUSDT", "tf": "5m", "dir": "LONG", "strategy": "smc",
         "entry": 105, "sl": 104, "tp1": 107, "tp2": 108, "rr": 2.0,
         "ob": {"low": 104.2, "high": 105.4}, "conf": 41, "ev": 0.2}
    out = HERE / ".selftest-chart.png"
    render(cd, s, str(out))
    size = out.stat().st_size
    out.unlink(missing_ok=True)
    return size > 8000, f"{size} bytes"


def telegram_refuses_without_creds():
    import telegram
    saved = (os.environ.pop("TELEGRAM_BOT_TOKEN", None),
             os.environ.pop("TELEGRAM_CHAT_ID", None))
    try:
        n = telegram.send_signals([{"sym": "X", "tf": "5m", "dir": "LONG",
                                    "entry": 1, "sl": 0.9, "tp1": 1.2, "rr": 2,
                                    "strategy": "smc"}], lambda s, p: None)
    finally:
        if saved[0]:
            os.environ["TELEGRAM_BOT_TOKEN"] = saved[0]
        if saved[1]:
            os.environ["TELEGRAM_CHAT_ID"] = saved[1]
    return n == 0, "sends nothing and says so"


def signal_is_sent_once():
    import telegram, pathlib
    tmp = HERE / ".selftest-sent.json"
    real, telegram.SENT = telegram.SENT, pathlib.Path(tmp)
    os.environ["TELEGRAM_BOT_TOKEN"] = "selftest"
    os.environ["TELEGRAM_CHAT_ID"] = "0"
    calls = []
    post = telegram._post
    telegram._post = lambda *a, **k: (calls.append(1), {"ok": True})[1]
    try:
        sig = [{"sym": "ONCEUSDT", "tf": "5m", "dir": "LONG", "entry": 1.0,
                "sl": 0.9, "tp1": 1.2, "rr": 2, "strategy": "smc"}]
        telegram.send_signals(sig, lambda s, p: None)
        first = len(calls)
        telegram.send_signals(sig, lambda s, p: None)
        second = len(calls)
    finally:
        telegram._post = post
        telegram.SENT = real
        tmp.unlink(missing_ok=True)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)
    return (first == 1 and second == 1), f"first pass {first} call, second pass {second}"


def published_scan_is_fresh():
    p = ROOT / "signals" / "latest.json"
    if not p.exists():
        return False, "signals/latest.json missing"
    j = json.loads(p.read_text())
    age_min = (time.time() * 1000 - j["generated"]) / 60000
    per = j.get("per_strategy") or {}
    both = len(per) == 2
    stale = age_min >= 240
    why = ""
    if stale:
        why = (" — the cron cannot fire from a non-default branch, so this only "
               "updates on a push until PR #1 merges")
    return (not stale and both), (
        f"{age_min:.0f} min old, {j['counts']['SIGNAL']} signals, "
        f"{'both strategies counted' if both else 'PER-STRATEGY COUNTS MISSING'}{why}")


def alarms_are_set():
    p = ROOT / "signals" / "latest.json"
    j = json.loads(p.read_text())
    a = j.get("alarms") or []
    return len(a) > 0, f"{len(a)} alarms with entry price and distance"


def payroll_runs():
    p = subprocess.run([sys.executable, str(HERE / "payroll.py")],
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return False, p.stderr.strip()[:160]
    j = json.loads((brain.ROOMS / "payroll.json").read_text())
    return len(j["rooms"]) >= 8, f"{len(j['rooms'])} rooms scored, total {j['total']}"


def main():
    print("\nENGINE")
    check("both strategies exported from the panel", engine_exports)
    check("both strategies produce setups", both_strategies_fire)
    check("a fill is required before a trade counts", fill_is_required)
    check("strategy 1 risk and reward share a price", rr_is_consistent)

    print("\nMEMORY")
    check("brain stores and reads back", brain_writes_and_reads)
    check("history is large enough to learn from", brain_has_history)
    check("the recall index exists and is populated", index_is_current)
    check("recall answers, and refuses when thin", recall_answers_and_refuses)
    check("the events room is recording", events_room_records)
    check("rooms keep their own memory", rooms_have_memory)
    check("LEARNING IS ACTUALLY CONSULTED", learning_is_consulted)

    print("\nDELIVERY")
    check("charts render", chart_renders)
    check("telegram refuses without credentials", telegram_refuses_without_creds)
    check("a signal is delivered once, not repeatedly", signal_is_sent_once)
    check("the published scan is fresh and per-strategy", published_scan_is_fresh)
    check("alarms are set on waiting setups", alarms_are_set)
    check("the payroll scores every room", payroll_runs)

    failed = [(n, d) for ok, n, d in RESULTS if not ok]
    print(f"\n{'=' * 74}")
    print(f"{len(RESULTS) - len(failed)} of {len(RESULTS)} checks pass")
    if failed:
        print("\nfailing:")
        for n, d in failed:
            print(f"  · {n} — {d}")
    print("=" * 74)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
