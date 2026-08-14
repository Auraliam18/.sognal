"""Reference-only deterministic signal chart renderer.

The implementation team should connect this contract to the project data model and
Golden Fixtures. It contains no network calls and cannot place trades.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_chart_payload(payload: dict[str, Any]) -> None:
    required = {"signal_id", "symbol", "timeframe", "candles", "entry", "stop", "targets"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"missing chart fields: {missing}")
    if not payload["candles"]:
        raise ValueError("candles cannot be empty")


def render_reference(payload_path: str, output_path: str) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    validate_chart_payload(payload)
    candles = payload["candles"]

    fig, ax = plt.subplots(figsize=(14, 8))
    for i, c in enumerate(candles):
        o, h, l, cl = map(float, (c["open"], c["high"], c["low"], c["close"]))
        ax.vlines(i, l, h, linewidth=1)
        bottom, height = min(o, cl), max(abs(cl - o), 1e-12)
        ax.add_patch(Rectangle((i - 0.3, bottom), 0.6, height, fill=False, linewidth=1))

    for line in payload.get("trendlines", []):
        ax.plot(line["x"], line["y"], linewidth=1)
    for zone in payload.get("zones", []):
        ax.axhspan(zone["low"], zone["high"], alpha=0.12)

    ax.axhline(float(payload["entry"]), linestyle="--", label="Entry")
    ax.axhline(float(payload["stop"]), linestyle=":", label="SL")
    for idx, target in enumerate(payload["targets"], start=1):
        ax.axhline(float(target), linestyle="-.", label=f"TP{idx}")

    ax.text(0.5, 0.5, "Trade_osuli", transform=ax.transAxes, ha="center", va="center", fontsize=44, alpha=0.08)
    ax.set_title(f"{payload['symbol']} {payload['timeframe']} | {payload['signal_id']}")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("payload")
    parser.add_argument("output")
    args = parser.parse_args()
    render_reference(args.payload, args.output)
