from __future__ import annotations

import json
import re
import sys

BLOCK_PATTERNS = [
    (r"\bgit\s+push\b.*--force", "force-push is blocked"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset is blocked"),
    (r"\brm\s+-rf\b", "recursive forced deletion is blocked"),
    (r"Remove-Item\b.*-Recurse.*-Force", "recursive forced deletion is blocked"),
    (r"LIVE_EXECUTION\s*[=:]\s*(true|1|yes|on)", "LIVE_EXECUTION activation is blocked"),
    (r"live_execution\s*:\s*true", "live_execution activation is blocked"),
    (r"(?:API|SECRET|TOKEN|PRIVATE)[_-]?KEY\s*=\s*['\"][^$<{]", "hard-coded credential appears in command"),
]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = event.get("tool_input") or {}
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")
    for pattern, reason in BLOCK_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason + "; use a reversible branch/backup and keep live execution disabled."
                }
            }))
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
