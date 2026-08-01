#!/usr/bin/env python3
"""The memory. Everything the system learns lands here and stays.

The panel used to forget. Close the tab, and the practice trades, the case
memory and the confidence model were gone — every session started from nothing.
This is the fix: one directory on disk, committed to the repository, that
outlives any browser, any container and any machine.

    brain/
      learning/     experiences.jsonl   every setup ever mined, with its outcome
                    positive.jsonl      what repeated and worked
                    negative.jsonl      what repeated and lost
      patterns/     <name>.json         a pattern, written down once it earns it
      events/       YYYY-MM-DD.jsonl    the events room — every moment, in order
      rooms/<room>/ state.json          each room's own memory
      backtests/                        raw results, kept

Everything is JSON Lines, one record per line, append-only. That choice matters:
a crashed write costs one line rather than the file, two processes appending do
not corrupt each other, and a 200MB history can be scanned without loading it.

The one thing this must be fast at is the question asked before every signal:
"has this coin, in this direction, in a situation like this, worked before?"
`recall` answers it off an index rather than by reading the history.
"""
import json, os, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BRAIN = ROOT / "brain"
LEARNING = BRAIN / "learning"
PATTERNS = BRAIN / "patterns"
EVENTS = BRAIN / "events"
ROOMS = BRAIN / "rooms"


def _ensure():
    for d in (LEARNING, PATTERNS, EVENTS, ROOMS, BRAIN / "backtests"):
        d.mkdir(parents=True, exist_ok=True)


def append(path, record):
    """One JSON object per line. Append-only, so a torn write costs one line."""
    _ensure()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read(path, limit=None):
    if not Path(path).exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue                      # a torn last line is not a reason to fail
    return out[-limit:] if limit else out


# ── the events room ───────────────────────────────────────────────────────────
def event(kind, **fields):
    """Every moment worth remembering, in the order it happened.

    The learning room reads this afterwards to ask which strategy worked in
    which stretch of market, so the record has to carry the context that was
    true at the time — not just what happened, but what the market looked like
    while it happened.
    """
    rec = {"t": int(time.time() * 1000),
           "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "kind": kind, **fields}
    append(EVENTS / f"{time.strftime('%Y-%m-%d', time.gmtime())}.jsonl", rec)
    return rec


def events_between(start_ms, end_ms):
    out = []
    for f in sorted(EVENTS.glob("*.jsonl")):
        for r in read(f):
            if start_ms <= r.get("t", 0) <= end_ms:
                out.append(r)
    return out


# ── experience ────────────────────────────────────────────────────────────────
def learn(exp):
    """One mined setup and what became of it.

    Required: sym, tf, dir, strategy, r, outcome. Everything else is context
    and the more of it the better — the reason a trade worked is only findable
    later if what was true at the time was written down at the time.
    """
    append(LEARNING / "experiences.jsonl", exp)
    if exp.get("r", 0) > 0:
        append(LEARNING / "positive.jsonl", exp)
    elif exp.get("r", 0) < 0:
        append(LEARNING / "negative.jsonl", exp)


def build_index():
    """Collapse the history into the lookup a live scan can afford.

    Keyed on (symbol, strategy, direction) and on the coarse shape of the setup,
    because the useful question is never "this exact bar again" — it is "this
    kind of situation, on this coin, before".
    """
    _ensure()
    by_sym = defaultdict(lambda: {"n": 0, "wins": 0, "net": 0.0})
    by_shape = defaultdict(lambda: {"n": 0, "wins": 0, "net": 0.0})
    by_reason = defaultdict(lambda: {"n": 0, "wins": 0, "net": 0.0})
    for e in read(LEARNING / "experiences.jsonl"):
        r = e.get("r", 0)
        for key, table in ((f"{e.get('sym')}|{e.get('strategy')}|{e.get('dir')}", by_sym),
                           (shape_key(e), by_shape),
                           (f"{e.get('strategy')}|{e.get('reason','?')}", by_reason)):
            t = table[key]
            t["n"] += 1
            t["wins"] += 1 if r > 0 else 0
            t["net"] += r
    def finish(table):
        return {k: {"n": v["n"], "hit": round(100 * v["wins"] / v["n"], 1),
                    "ev": round(v["net"] / v["n"], 3)}
                for k, v in table.items() if v["n"] >= 3}
    idx = {"built": int(time.time() * 1000),
           "by_symbol": finish(by_sym), "by_shape": finish(by_shape),
           "by_reason": finish(by_reason)}
    (LEARNING / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    return idx


def shape_key(e):
    """A setup's coarse shape: strategy, direction, and the bands that mattered.

    Buckets rather than raw numbers, because two setups are 'alike' when they
    sit in the same band, not when they share a decimal.
    """
    def band(v, edges):
        if v is None:
            return "?"
        for i, edge in enumerate(edges):
            if v < edge:
                return str(i)
        return str(len(edges))
    return "|".join([
        str(e.get("strategy")), str(e.get("dir")), str(e.get("tf")),
        "rr" + band(e.get("rr"), [1.5, 2.5, 4]),
        "adx" + band(e.get("adx"), [20, 25, 35]),
        "dom" + str(e.get("dom_dir", "?")),
    ])


def recall(sym=None, strategy=None, direction=None, shape=None, idx=None):
    """What the history says about a situation. Never guesses.

    Below a handful of cases it says the history is thin rather than pretending
    to know — a number built on four trades is not evidence, and reporting it as
    though it were is how a system starts lying to the person using it.
    """
    if idx is None:
        p = LEARNING / "index.json"
        idx = json.loads(p.read_text()) if p.exists() else {"by_symbol": {}, "by_shape": {}}
    out = {}
    if sym and strategy and direction:
        out["symbol"] = idx["by_symbol"].get(f"{sym}|{strategy}|{direction}")
    if shape:
        out["shape"] = idx["by_shape"].get(shape)
    best = out.get("symbol") or out.get("shape")
    out["verdict"] = ("thin" if not best or best["n"] < 12
                      else "good" if best["ev"] > 0.05
                      else "bad" if best["ev"] < -0.05 else "flat")
    return out


# ── per-room memory ───────────────────────────────────────────────────────────
def room_path(room):
    return ROOMS / room / "state.json"


def room_load(room, default=None):
    p = room_path(room)
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text())
    except Exception:                          # noqa: BLE001 - a torn file is an empty room
        return default if default is not None else {}


def room_save(room, state):
    p = room_path(room)
    p.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["_saved"] = int(time.time() * 1000)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def room_log(room, line, level="info"):
    append(ROOMS / room / "log.jsonl",
           {"t": int(time.time() * 1000), "level": level, "line": line})


# ── patterns ──────────────────────────────────────────────────────────────────
def save_pattern(name, pattern):
    """A pattern is only written down once the measurement earns it."""
    PATTERNS.mkdir(parents=True, exist_ok=True)
    (PATTERNS / f"{name}.json").write_text(json.dumps(pattern, ensure_ascii=False, indent=1))


def load_patterns():
    return {p.stem: json.loads(p.read_text()) for p in PATTERNS.glob("*.json")}


def stats():
    exp = read(LEARNING / "experiences.jsonl")
    ev = sum(len(read(f)) for f in EVENTS.glob("*.jsonl"))
    return {"experiences": len(exp),
            "positive": len(read(LEARNING / "positive.jsonl")),
            "negative": len(read(LEARNING / "negative.jsonl")),
            "events": ev, "patterns": len(list(PATTERNS.glob("*.json"))),
            "rooms": len([d for d in ROOMS.glob("*") if d.is_dir()])}


if __name__ == "__main__":
    _ensure()
    print(json.dumps(stats(), indent=1))
