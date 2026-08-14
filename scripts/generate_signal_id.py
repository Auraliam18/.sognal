from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

_SAFE = re.compile(r"[^A-Z0-9]+")


def _safe(value: str, max_len: int = 18) -> str:
    value = _SAFE.sub("", value.upper())[:max_len]
    if not value:
        raise ValueError("empty sanitized identifier")
    return value


def generate_signal_id(symbol: str, strategy_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    utc_now = now.astimezone(timezone.utc)
    stamp = utc_now.strftime("%Y%m%dT%H%M%S") + f"{utc_now.microsecond // 1000:03d}Z"
    suffix = secrets.token_hex(4).upper()
    return f"LIAM-{stamp}-{_safe(symbol)}-{_safe(strategy_id)}-{suffix}"


if __name__ == "__main__":
    print(generate_signal_id("BTCUSDT", "IBS_PULLBACK_PLUS"))
