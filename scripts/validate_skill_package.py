from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

EXPECTED_IDS = [f"E{i:02d}" for i in range(26)]


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"unclosed frontmatter: {path}")
    return yaml.safe_load(text[4:end]) or {}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = root / "config/engine_registry.yaml"
    if not registry_path.exists():
        return ["missing config/engine_registry.yaml"]
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if registry.get("live_execution") is not False:
        errors.append("live_execution must be false")
    if registry.get("scan_heartbeat_seconds") != 30:
        errors.append("scan_heartbeat_seconds must be 30")

    rows = registry.get("engines") or []
    ids = [r.get("id") for r in rows]
    if ids != EXPECTED_IDS:
        errors.append(f"engine IDs mismatch: {ids}")

    seen_skill_names: set[str] = set()
    seen_agent_names: set[str] = set()
    for row in rows:
        eid = row["id"]
        skill_path = root / ".claude/skills" / row["claude_skill"] / "SKILL.md"
        agent_rel = f"{eid.lower()}-{row['slug']}.md"
        agent_path = root / ".claude/agents" / agent_rel
        runtime_path = root / row["runtime_skill_file"]
        for path in (skill_path, agent_path, runtime_path):
            if not path.exists():
                errors.append(f"missing {path.relative_to(root)}")
        if skill_path.exists():
            fm = frontmatter(skill_path)
            if fm.get("name") != row["claude_skill"]:
                errors.append(f"skill name mismatch: {skill_path}")
            if fm.get("name") in seen_skill_names:
                errors.append(f"duplicate skill name: {fm.get('name')}")
            seen_skill_names.add(fm.get("name"))
        if agent_path.exists():
            fm = frontmatter(agent_path)
            if fm.get("name") != row["claude_agent"]:
                errors.append(f"agent name mismatch: {agent_path}")
            if fm.get("name") in seen_agent_names:
                errors.append(f"duplicate agent name: {fm.get('name')}")
            seen_agent_names.add(fm.get("name"))
            if fm.get("memory") != "project":
                errors.append(f"agent memory must be project: {agent_path}")
        if runtime_path.exists():
            runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
            if runtime.get("engine_id") != eid:
                errors.append(f"runtime skill ID mismatch: {runtime_path}")

    signal = yaml.safe_load((root / "config/signal_policy.yaml").read_text(encoding="utf-8"))
    if signal.get("release_mode") != "immediate_per_symbol_no_batch_barrier":
        errors.append("signal release mode must be immediate per symbol")
    if signal.get("live_execution") is not False:
        errors.append("signal policy live_execution must be false")

    secret_patterns = [re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}")]
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".json", ".py"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in secret_patterns:
                if pat.search(text):
                    errors.append(f"possible hard-coded secret in {path.relative_to(root)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    errors = validate(root)
    if errors:
        print("LIAM package validation FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("LIAM package validation OK: 26 engines, 26 agents, immediate 30s/event-driven policy, live execution disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
