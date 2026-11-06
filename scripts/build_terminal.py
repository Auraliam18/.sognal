"""Publish a read-only LIAM terminal from one repository snapshot.

No market computation, model calls, strategy changes, or message delivery.
Historical books remain separate; all records have an exported page. Missing
timestamps stay unknown rather than inheriting the publication time.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "claude-liam-signal/python"))
from hamid.settled_evidence import Outcomes
import jsonl_store
import role_evidence
import yaml

VERSION = "1.0.0"
FEEDS = {
    "scan": ("latest.json", 1200), "hamid": ("hamid-latest.json", 2700),
    "dominance": ("dominance.json", 3600), "radar": ("pump-radar.json", 1800),
    "blocks": ("ob-radar.json", 3600), "news": ("news.json", 7200),
    "delivery": ("telegram-log.json", 3600), "classification": ("classify.json", 86400),
    "learning": ("improve.json", 86400), "conformance": ("conformance.json", 14400),
    "bubbles": ("bubbles.json", 1800), "btc": ("btc-patterns.json", 3600),
}
BOOKS = {
    "hamid": "روش حمید · پولبک دوم", "scan": "اسکن ارسالی · sig-*",
    "practice": "تمرین و بازپخش", "first": "آزمایش پولبک اول",
    "inducement": "آزمایش ایندوسمنت", "alarm": "آلارم‌ها",
    "vetoed": "گروه کنترلِ وتوشده", "v2": "آزمایش نسخهٔ دوم", "other": "دفتر نامشخص",
}
ENGINE_BINDINGS = [
    ("hamid", "ارکستراتور", "cycle", ["reads", "mode"], []),
    ("scan", "جهان بازار", "venues", ["symbols"], ["E02"]),
    ("scan", "کیفیت داده", "watchdog", ["generated", "source"], []),
    ("dominance", "دامیننس تتر", "dominance", ["usdt_dominance", "structure.usdt"], ["E02"]),
    ("dominance", "دامیننس بیت‌کوین", "dominance", ["btc_dominance", "structure.btc_d"], ["E02"]),
    ("hamid", "رژیم و کلان", "intel", ["world", "mode"], ["E03", "E04"]),
    ("btc", "تحلیل بیت‌کوین", "patterns", ["btc.4h", "btc.1h"], ["E02"]),
    ("blocks", "ساختار و سطوح", "structure", ["states"], ["E02"]),
    ("blocks", "اردر بلاک و FVG", "ob_intel", ["states", "events"], ["E07"]),
    ("scan", "اندیکاتورها", "strategy_api", ["signals"], ["E02"]),
    ("hamid", "نقدینگی و مشتقات", "liquidity", ["world.funding"], ["E02"]),
    ("scan", "مسیریاب استراتژی", "cycle", ["per_strategy"], ["E03", "E07", "E08"]),
    ("radar", "پیش‌رو و دنباله‌رو", "pump_study", ["universe_n", "coins", "recommendation"], ["E02"]),
    ("learning", "همتای تاریخی", "coin_history", ["symbols_profiled"], ["E18"]),
    ("news", "خبر و رویداد", "intel", ["classified", "calendar"], ["E02"]),
    ("scan", "پایش و آلارم", "watchdog", ["alarms"], ["E07", "E08"]),
    ("hamid", "ریسک", "sizing", ["paper.risk_per_trade_pct"], ["E02", "E03"]),
    ("hamid", "کمیتهٔ سیگنال", "trend_gate", ["setups", "vetoes"], ["E03", "E06", "E16"]),
    ("ledger", "پیپر و بازپخش", "paper", [], []),
    ("ledger", "مدیریت معامله", "paper", [], ["E16"]),
    ("hamid", "بازبینی پس از معامله", "loss_autopsy", ["review"], ["E18"]),
    ("learning", "حافظه و یادگیری", "memory", ["n_trades"], ["E20"]),
    ("learning", "پژوهش بهبود", "improve", ["proposals", "rule"], ["E18", "E21"]),
    ("conformance", "ناظر سامانه", "conformance", ["checks", "ok"], ["E02"]),
    ("terminal", "کیفیت پنل", None, [], []),
    ("delivery", "تحویل تلگرام", "notif_bridge", ["sent"], ["E17"]),
]


def number(value):
    return value if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) else None


def stamp(value):
    n = number(value)
    if n is None or n <= 0:
        return None
    return int(n if n > 10**11 else n * 1000)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def at(data, path):
    for key in path.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def freshness(ts, now, ttl):
    if ts is None:
        return "unknown"
    age = (now - ts) / 1000
    if age < -300:
        return "clock_error"
    return "fresh" if age <= ttl else "stale"


def book_of(row):
    stage = str((row.get("why") or {}).get("stage") or "")
    if stage.startswith("sig-"):
        return "scan"
    if stage in {"practice", "first", "inducement", "alarm", "vetoed", "v2"}:
        return stage
    return "hamid" if stage in {"second", "signal", "hamid"} else "other"


def public_trade(row, index):
    # Explicit allowlist: the public export never serializes arbitrary metadata.
    fields = ("sym", "dir", "tf", "entry", "sl", "tp1", "tp2", "R", "outcome", "opened", "closed", "filled", "exit", "strategy", "signal_id", "tg_msg_id")
    out = {k: row.get(k) for k in fields}
    out["tf"] = row.get("tf") or (row.get("why") or {}).get("tf")
    out["book"] = book_of(row)
    out["record"] = index
    out["id"] = str(row.get("id") or row.get("signal_id") or f"record-{index}")
    out["stage"] = (row.get("why") or {}).get("stage")
    out["mode"] = "paper"
    return out


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def ledger(root, output, now, page_size=1000):
    path = root / "brain/paper/closed.jsonl"
    exists = path.exists() or jsonl_store.parts(path).exists()
    stats = {b: {"book": b, "name": label, "records": 0, "settled": 0, "wins": 0, "sum_r": 0, "outcomes": Counter(), "days": defaultdict(float)} for b, label in BOOKS.items()}
    rows, bad, last = [], 0, None
    evidence, grades = Outcomes(), Counter()
    for i, line in enumerate(jsonl_store.lines(path)):
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("non-object")
        except (ValueError, UnicodeDecodeError):
            bad += 1
            continue
        ident = evidence.observe(row, i)
        row = public_trade(row, i)
        row["_ident"] = ident
        rows.append(row)
        stat = stats[row["book"]]
        stat["records"] += 1
        stat["outcomes"][str(row.get("outcome") or "unknown")] += 1
        closed = stamp(row.get("closed"))
        if closed:
            last = max(last or 0, closed)
    for row in rows:
        grade = evidence.status(row.pop("_ident"),row["record"])
        row["evidence"] = grade
        grades[grade] += 1
        if grade != "unique":
            continue
        stat = stats[row["book"]]
        closed = stamp(row.get("closed"))
        r = number(row.get("R"))
        # Expiry and unavailable prices are not filled, settled trades.
        if r is not None and row.get("outcome") not in {"expired", "no_data", "no_fill", None}:
            stat["settled"] += 1
            stat["wins"] += r > 0
            stat["sum_r"] += r
            if closed:
                stat["days"][time.strftime("%Y-%m-%d", time.gmtime(closed / 1000))] += r
    rows.sort(key=lambda r: stamp(r.get("closed")) or 0, reverse=True)
    pages = []
    # Partition by book before pagination: a 9k-row primary book must not
    # download a 170k-row mixed research archive just to filter its own rows.
    for book in BOOKS:
        book_rows = [row for row in rows if row["book"] == book]
        for offset in range(0, len(book_rows), page_size):
            part = book_rows[offset:offset + page_size]
            digest = hashlib.sha256(json.dumps(part, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
            name = f"history/{digest}.json"
            write_json(output / name, part)
            pages.append({"url": name, "count": len(part), "books": [book], "symbols": sorted({str(r["sym"]) for r in part if r["sym"]}), "first": part[0].get("closed"), "last": part[-1].get("closed")})
    for stat in stats.values():
        n = stat["settled"]
        stat["mean_r"] = round(stat["sum_r"] / n, 5) if n else None
        stat["win_pct"] = round(100 * stat["wins"] / n, 2) if n else None
        stat["sum_r"] = round(stat["sum_r"], 5)
        stat["days"] = [{"date": d, "r": round(r, 5)} for d, r in sorted(stat["days"].items())]
    open_path = root / "brain/paper/open.jsonl"
    open_rows = [r for r in jsonl_store.read(open_path) if isinstance(r, dict)]
    opened = [public_trade(r, i) for i, r in enumerate(open_rows)]
    # Keep different research books separate from the main paper portfolio.
    primary = [r for r in open_rows if book_of(r) == "hamid"]
    notionals = [r["notional_usd"] for r in primary if number(r.get("notional_usd")) is not None and r["notional_usd"] > 0]
    portfolio = {"available": open_path.is_file() or jsonl_store.parts(open_path).is_dir(),
                 "book": "hamid", "open_positions": len(primary), "sized_positions": len(notionals),
                 "exposure_usd": sum(notionals) if len(notionals) == len(primary) else None}
    return {"portfolio": portfolio, "available": exists, "computed_at": now, "last_result_at": last, "mode": "paper", "records": len(rows), "malformed_records": bad, "evidence_counts": dict(grades), "books": list(stats.values()), "open": opened, "recent": rows[:100], "pages": pages, "source": "brain/paper/closed.jsonl + .parts", "limitations": "پیپر و بازپخش روی کندل واقعی؛ فیل صرافی، لغزش و سرمایهٔ واقعی نیست. فقط یک نتیجهٔ سازگار با قیمت‌های معتبر برای هر موقعیت در آمار می‌آید؛ همهٔ ردیف‌های خام برای بررسی محفوظ‌اند."}


def engine_packets(root, feeds, history, now):
    registry = yaml.safe_load((root / "config/engine_registry.yaml").read_text(encoding="utf-8"))
    registry_file = root / "strategies/registry.yaml"
    routes = yaml.safe_load(registry_file.read_text(encoding="utf-8")) if registry_file.exists() else {}
    lessons = role_evidence.mapping(read_json(root / "brain/memory/lessons.json"))
    reconciliation = role_evidence.mapping(read_json(root / "brain/paper/reconciliation.json"))
    intel = role_evidence.mapping(read_json(root / "brain/intel/latest.json"))
    risk = role_evidence.mapping(read_json(root / "config/risk.json"))
    result = []
    for i, (feed, name, module, required, deps) in enumerate(ENGINE_BINDINGS):
        definition = registry["engines"][i]
        missing = []
        if feed in feeds:
            evidence = feeds[feed]
            status = evidence["state"]
            missing = [field for field in required if at(evidence["data"], field) is None]
            if feed == "radar" and not (number(at(evidence["data"], "universe_n")) or 0) > 0:
                missing.append("observed market universe")
            if status == "fresh" and feed == "conformance" and at(evidence["data"], "ok") is False:
                status = "attention"
            ts = evidence["generated"]
            path = evidence["path"]
        else:
            status = "fresh" if feed == "terminal" or (feed == "ledger" and history["available"]) else "missing"
            ts, path = now, "terminal/data/snapshot.json" if feed == "terminal" else history["source"]
        stats, gaps, clock = role_evidence.inspect(definition["id"], feeds.get(feed, {}).get("data"),
                lessons=lessons, reconciliation=reconciliation, risk=risk, portfolio=history.get("portfolio", {}),
                intel=intel, routes=role_evidence.mapping(routes), cycle=role_evidence.mapping(feeds.get("hamid", {}).get("data")))
        missing.extend(gaps)
        if definition["id"] == "E19":
            path = "brain/paper/reconciliation.json"
        if definition["id"] == "E10" and "brain/intel/latest.json" in stats.get("sources", {}).values():
            path += " + brain/intel/latest.json"
        if definition["id"] == "E11":
            path += " + strategies/registry.yaml + signals/hamid-latest.json"
        if definition["id"] == "E21":
            path += " + brain/memory/lessons.json"
        if clock is not None:
            ts = stamp(clock[0])
            clock_state = freshness(ts, now, clock[1])
            if clock_state != "fresh" and status == "fresh":
                status = clock_state
        if status == "fresh" and missing:
            status = "partial"
        result.append({"evidence": stats, "evidence_ttl": clock[1] if clock else None, "id": definition["id"], "name": name, "output": definition["output"], "state": status, "observed_at": ts, "source": path, "feed": feed, "required": required, "missing": missing, "dependencies": deps, "version": registry["version"], "module": f"hamid/{module}.py" if module else "scripts/build_terminal.py", "claim": "وضعیت شواهدِ منتشرشده؛ تضمین عملکرد یا اثبات اجرای مدل نیست"})
    by_id = {e["id"]:e for e in result}
    def blocked(e, trail=()):
        if e["id"] in trail:
            return True
        return e["own_state"] != "fresh" or any(blocked(by_id[d],trail+(e["id"],)) for d in e["dependencies"])
    for e in result:
        e["own_state"] = e["state"]
    for e in result:
        e["blocked_dependencies"] = [d for d in e["dependencies"] if blocked(by_id[d])]
        if e["own_state"] == "fresh" and e["blocked_dependencies"]:
            e["state"] = "partial"
    return result


def build(root=ROOT, output=None, now=None, page_size=1000):
    root, output = Path(root), Path(output or root / "terminal/data")
    now = int(now if now is not None else time.time() * 1000)
    feeds = {}
    for key, (filename, ttl) in FEEDS.items():
        path = root / "signals" / filename
        data = read_json(path)
        generated = stamp(data.get("generated")) if isinstance(data, dict) else None
        feeds[key] = {"path": f"signals/{filename}", "generated": generated, "ttl": ttl, "state": freshness(generated, now, ttl) if data is not None else "missing", "data": data, "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
    history = ledger(root, output, now, page_size)
    try:
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        commit = git.stdout.strip() if git.returncode == 0 else "local"
    except FileNotFoundError:
        commit = "local"
    personalization = yaml.safe_load((root / "config/personalization.yaml").read_text(encoding="utf-8"))
    snapshot = {"schema_version": 1, "version": VERSION, "generated": now, "commit": commit, "live_execution": False, "feeds": feeds, "ledger": history, "engines": engine_packets(root, feeds, history, now), "policy": personalization, "risk": read_json(root / "config/risk.json", {}), "source_url": "https://github.com/Auraliam18/.sognal"}
    assert len(snapshot["engines"]) == 26
    assert sum(p["count"] for p in history["pages"]) == history["records"]
    checks = [
        {"name": "all_26_bindings", "ok": len(snapshot["engines"]) == 26},
        {"name": "all_records_exported", "ok": sum(p["count"] for p in history["pages"]) == history["records"]},
        {"name": "no_malformed_records", "ok": history["malformed_records"] == 0},
        {"name": "ledger_available", "ok": history["available"]},
        {"name": "live_execution_disabled", "ok": personalization.get("live_execution") is False},
    ]
    snapshot["panel_health"] = {"contract": "PanelHealth", "engine_id": "E24", "version": VERSION, "generated": now, "live_execution": False, "ok": all(c["ok"] for c in checks), "checks": checks, "tab_bindings": {
        "overview": ["E03", "E04", "E05", "E06"], "market": ["E01", "E07", "E08", "E09", "E10", "E12", "E14"],
        "signals": ["E11", "E15", "E17", "E25"], "history": ["E18", "E19"], "agents": [f"E{i:02d}" for i in range(26)],
        "learning": ["E13", "E20", "E21", "E22"], "strategy": ["E00", "E11", "E16"], "health": ["E02", "E23", "E24"]}}
    if personalization.get("live_execution") is not False:
        raise ValueError("This terminal requires the repository's paper-only execution policy")
    write_json(output / "snapshot.json", snapshot)
    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = build(args.root, args.output)
    print(f"terminal: {len(value['engines'])} evidence bindings, {value['ledger']['records']} historical records, {len(value['ledger']['pages'])} pages; live execution disabled")
