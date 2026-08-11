#!/usr/bin/env python3
"""Draws the setup the way it would be read off a chart.

A signal that arrives as numbers alone asks the reader to trust it. A signal
that arrives with the candles, the order block, the entry, the stop and the
targets drawn on lets them check it. That is the difference this file makes.

What gets drawn, and nothing else:
  * the candles, dark for down and light for up
  * the order block as a filled band — the box price has to close out of
  * the entry at the box edge, the stop beyond it, and both targets
  * the channel, when the engine found one

No indicator soup. Everything on the picture is something the strategy uses.

    render(candles, setup, "out.png")
"""
import matplotlib
matplotlib.use("Agg")                      # no display anywhere this runs
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BG = "#0b1017"
GRID = "#1b2532"
TEXT = "#c8d4e3"
DIM = "#7f8ea3"
UP = "#2ecc71"
DOWN = "#e74c3c"
BOX = "#3d8bfd"
TP = "#2ecc71"
SL = "#e74c3c"
ENTRY = "#f0a92e"


def _fmt(v):
    """Crypto prices span nine orders of magnitude; a fixed precision lies."""
    a = abs(v)
    if a >= 1000:
        return f"{v:,.1f}"
    if a >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if a >= 0.001:
        return f"{v:.6f}".rstrip("0").rstrip(".")
    return f"{v:.8f}".rstrip("0").rstrip(".")


def _watermark(ax):
    """امضای کانال حمید — Trade_Osuli — پشت کندل‌ها، کم‌رنگ، بدون شلوغی."""
    ax.text(0.5, 0.5, "@Trade_Osuli", transform=ax.transAxes,
            fontsize=34, color=DIM, alpha=0.12, ha="center", va="center",
            rotation=15, fontweight="bold", zorder=0)


def render(candles, s, path, bars=110):
    """candles: [{t,o,h,l,c,v}] oldest first. s: one setup from scan.py."""
    cd = candles[-bars:]
    if len(cd) < 10:
        raise ValueError("not enough candles to draw")

    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=110)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    _watermark(ax)

    width = 0.62
    for i, c in enumerate(cd):
        up = c["c"] >= c["o"]
        col = UP if up else DOWN
        ax.plot([i, i], [c["l"], c["h"]], color=col, linewidth=0.8, solid_capstyle="round", zorder=2)
        lo, hi = (c["o"], c["c"]) if up else (c["c"], c["o"])
        ax.add_patch(Rectangle((i - width / 2, lo), width, max(hi - lo, 1e-12),
                               facecolor=col, edgecolor=col, linewidth=0.6, zorder=3))

    n = len(cd)
    ob = s.get("ob") or {}
    if ob.get("low") is not None and ob.get("high") is not None:
        ax.add_patch(Rectangle((-0.5, ob["low"]), n, ob["high"] - ob["low"],
                               facecolor=BOX, alpha=0.13, edgecolor=BOX,
                               linewidth=1.0, linestyle="--", zorder=1))
        # Latin label on purpose: matplotlib has no Arabic shaping, so Persian
        # here comes out as disconnected letters in reverse order. The caption
        # under the photo carries the Persian; the picture stays legible.
        ax.text(0.5, ob["high"], "ORDER BLOCK", color=BOX, fontsize=7.5,
                va="bottom", ha="left", zorder=6, family="monospace", alpha=0.9)

    def level(y, color, label, style="-", lw=1.3):
        """Stops the line at the last candle so the label sits on clear ground."""
        if y is None:
            return
        ax.plot([-0.5, n - 0.5], [y, y], color=color, linewidth=lw,
                linestyle=style, alpha=0.95, zorder=4)
        ax.text(n + 1.0, y, f"{label} {_fmt(y)}", color=color, fontsize=8.5,
                va="center", ha="left", zorder=6, family="monospace")

    level(s.get("entry"), ENTRY, "ENTRY")
    level(s.get("sl"), SL, "SL")
    level(s.get("tp1"), TP, "TP1", style="--")
    level(s.get("tp2"), TP, "TP2", style=":", lw=1.0)

    lo = min(c["l"] for c in cd)
    hi = max(c["h"] for c in cd)
    for y in (s.get("entry"), s.get("sl"), s.get("tp1"), s.get("tp2")):
        if y is not None:
            lo, hi = min(lo, y), max(hi, y)
    pad = (hi - lo) * 0.07 or hi * 0.01
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-1, n * 1.30)                  # room on the right for the level labels

    long = s.get("dir") == "LONG"
    # The strategy belongs on the picture, not only in the caption: a screenshot
    # forwarded on its own should still say which engine produced it.
    strat = {"ibs": "IBS+PULLBACK", "smc": "CHANNEL+OB"}.get(s.get("strategy"), "")
    title = f"{s.get('sym','')}   {s.get('tf','')}   {'LONG' if long else 'SHORT'}"
    if strat:
        title += f"   ·   {strat}"
    ax.text(0, 1.085, title, transform=ax.transAxes, color=UP if long else DOWN,
            fontsize=13.5, fontweight="bold", va="bottom", ha="left", family="monospace")

    bits = [f"R:R {s.get('rr','—')}"]
    if s.get("conf") is not None:
        bits.append(f"conf {s['conf']}%")
    if s.get("ev") is not None:
        bits.append(f"EV {s['ev']:.2f}R")
    if s.get("quality") is not None:
        bits.append(f"quality {s['quality']}")
    if s.get("adx") is not None:
        bits.append(f"ADX {s['adx']}")
    sub = "   ·   ".join(bits)
    if s.get("room") and s["room"].get("r") is not None:
        r = s["room"]["r"]
        sub += "   ·   room " + ("clear" if r >= 99 else f"{r}x")
    ax.text(0, 1.018, sub, transform=ax.transAxes, color=DIM, fontsize=8.6,
            va="bottom", ha="left", family="monospace")

    ax.grid(color=GRID, linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=DIM, labelsize=8)
    ax.set_xticks([])
    for lbl in ax.get_yticklabels():
        lbl.set_family("monospace")

    ax.text(1.0, -0.06, "Hamid Signal Agent", transform=ax.transAxes,
            color=DIM, fontsize=7.5, ha="right", va="top", family="monospace")

    fig.tight_layout()
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path
