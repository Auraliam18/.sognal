#!/usr/bin/env python3
"""اردر بلاک، دقیقاً با تعریف خود حمید.

His words, and the whole rule:

    «در روند نزولی می‌آیم دره را پیدا می‌کنم و کندل‌های قرمز را نگاه می‌کنم و
     برمی‌گردم عقب تا برسم به اولین کندل سبز که بدنهٔ آن از مجموع شدوهایش
     بزرگ‌تر است — و برعکس برای اردر بلاک صعودی»

Two things in that sentence are doing real work and are easy to lose:

  · **از مجموع شدوهایش** — the body must beat *both* wicks added together, not
    either one. A candle with a long tail on each side is indecision, and the
    point of the rule is to find the last candle where one side was clearly in
    control before the move went the other way.
  · **برمی‌گردم عقب** — the walk starts at the swing and goes backwards. The
    order block is the last opposite-coloured candle *before* the impulse, not
    the first one after it.

Validity is his too: «اگر قیمت به آن برگشته، یعنی تقریباً معتبر است — که منتظر
پولبک دومش توی تایم ۱۵ دقیقه می‌مانم». So a box price has never revisited is
not yet an order block worth trading, and the entry waits for the second visit.
"""
from dataclasses import dataclass, field

from hamid.structure import atr, swings


@dataclass
class OrderBlock:
    i: int                       # the candle the box is drawn around
    t: int
    low: float
    high: float
    dir: str                     # "bearish" (sell zone) | "bullish" (buy zone)
    impulse: float               # how far price travelled away from it, in ATR
    returns: int = 0             # «اگر قیمت به آن برگشته»
    return_bars: list = field(default_factory=list)
    consumed: bool = False       # price closed through it — no longer a block

    @property
    def mid(self):
        return (self.low + self.high) / 2

    @property
    def valid(self):
        """«تقریباً معتبر»: price came back to it at least once, and it has not
        been closed through."""
        return self.returns >= 1 and not self.consumed

    @property
    def second_pullback(self):
        """The one Hamid actually waits for, on 15m."""
        return self.returns >= 2 and not self.consumed


def body_beats_shadows(c):
    """«بدنه‌اش از مجموع شدوهایش بزرگ‌تر است»"""
    body = abs(c["c"] - c["o"])
    upper = c["h"] - max(c["o"], c["c"])
    lower = min(c["o"], c["c"]) - c["l"]
    return body > (upper + lower)


def is_green(c):
    return c["c"] > c["o"]


def find(cd, direction, lookback=120, max_walk=12):
    """Walk back from each swing to the last opposite candle with a real body.

    `direction="bearish"` looks at peaks and walks back to a red candle — the
    zone price should be sold into. `direction="bullish"` looks at troughs and
    walks back to a green candle.

    Note this reads the *swing*, not the trend. Hamid picks the دره in a
    downtrend and the قله in an uptrend, but the mechanic is the same either
    way, and which ones matter is decided later by the 4H direction rather than
    here. Filtering by trend inside this function would hide the blocks that a
    counter-trend reaction is built on.
    """
    if len(cd) < 30:
        return []
    a = atr(cd) or (cd[-1]["c"] * 0.004)
    want_green = direction == "bullish"
    swing_kind = "low" if want_green else "high"
    out = []

    for s in swings(cd):
        if s.kind != swing_kind or s.i < len(cd) - lookback:
            continue
        # «برمی‌گردم عقب» — backwards from the swing
        for j in range(s.i, max(0, s.i - max_walk) - 1, -1):
            c = cd[j]
            if is_green(c) != want_green:
                continue
            if not body_beats_shadows(c):
                continue
            # how decisive was the move away from it? a block nobody left in a
            # hurry is just a candle.
            end = min(len(cd), s.i + 10)
            away = (max(x["h"] for x in cd[j:end]) - c["h"]) if want_green \
                else (c["l"] - min(x["l"] for x in cd[j:end]))
            ob = OrderBlock(i=j, t=c["t"], low=c["l"], high=c["h"],
                            dir=direction, impulse=away / a if a else 0)
            _measure(cd, ob, a)
            out.append(ob)
            break

    # the same candle found from two swings is one block
    seen, uniq = set(), []
    for ob in sorted(out, key=lambda o: -o.i):
        if ob.i in seen:
            continue
        seen.add(ob.i)
        uniq.append(ob)
    return uniq


def _measure(cd, ob, a):
    """Count returns to the box, and notice when it stops being one."""
    last = -99
    for i in range(ob.i + 2, len(cd)):
        c = cd[i]
        if c["l"] <= ob.high and c["h"] >= ob.low:
            if i - last >= 3:            # one visit, not five bars of the same visit
                ob.returns += 1
                ob.return_bars.append(i)
                last = i
        # closed clean through it: the orders that were there are gone
        if ob.dir == "bearish" and c["c"] > ob.high + 0.2 * a:
            ob.consumed = True
        if ob.dir == "bullish" and c["c"] < ob.low - 0.2 * a:
            ob.consumed = True


def fvg(cd, lookback=120):
    """FVGهای مصرف‌نشده — a gap between candle i-1's and i+1's range.

    Hamid marks these on 1H alongside the order blocks and only cares about the
    ones price has not yet filled, so a gap that has been traded through is
    dropped rather than reported as unconsumed.
    """
    out = []
    start = max(1, len(cd) - lookback)
    for i in range(start, len(cd) - 1):
        up_gap = cd[i + 1]["l"] > cd[i - 1]["h"]
        dn_gap = cd[i + 1]["h"] < cd[i - 1]["l"]
        if not (up_gap or dn_gap):
            continue
        lo = cd[i - 1]["h"] if up_gap else cd[i + 1]["h"]
        hi = cd[i + 1]["l"] if up_gap else cd[i - 1]["l"]
        filled = any(c["l"] <= lo and c["h"] >= hi for c in cd[i + 2:])
        if filled:
            continue
        out.append({"i": i, "t": cd[i]["t"], "low": lo, "high": hi,
                    "dir": "bullish" if up_gap else "bearish"})
    return out
