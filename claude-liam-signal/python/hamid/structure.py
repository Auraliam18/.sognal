#!/usr/bin/env python3
"""روش خود حمید، در قالب کد — سقف و کف معتبر، کانال، روند.

This is not a new strategy. It is Hamid's own method, written down in
`STRATEGY.md`, turned into something that can be measured. Every rule here
traces to a sentence he wrote, and the sentence is quoted above the code that
implements it, so a later change can be checked against what he actually said
rather than against what someone remembered.

The one thing this adds is counting. Hamid keeps a line when he sees price has
"برخورد زیادی داشته و واکنش نشان داده" — hit it repeatedly and reacted. By eye
that is a judgement; here it is a number, and a number can be wrong out loud.
That is the entire reason for writing it down.

    python3 -m hamid.structure          # runs the self-check on synthetic data
"""
from dataclasses import dataclass, field
from statistics import fmean


# ── candles ────────────────────────────────────────────────────────────────
# A candle is a dict: {"t": ms, "o": float, "h": float, "l": float, "c": float,
# "v": float} — the same shape everything else in this repo uses.

def atr(cd, n=14):
    """Average true range. Used as the tolerance for "price touched this line",
    because a fixed percentage is too tight on a quiet coin and too loose on a
    violent one."""
    if len(cd) < 2:
        return 0.0
    trs = []
    for i in range(1, len(cd)):
        h, l, pc = cd[i]["h"], cd[i]["l"], cd[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    tail = trs[-n:] if len(trs) >= n else trs
    return fmean(tail) if tail else 0.0


# ── ۱. سقف‌ها و کف‌ها ───────────────────────────────────────────────────────
# «تمام سقف‌ها و کف‌ها را می‌کشم و ادامه می‌دهم»

@dataclass
class Swing:
    i: int
    t: int
    price: float
    kind: str            # "high" | "low"


def swings(cd, left=2, right=2):
    """Fractal highs and lows: a bar higher (lower) than `left` before it and
    `right` after it.

    `right` bars must exist for a swing to be confirmed, so the last few bars
    never produce one. That is correct and deliberate — a high is not a high
    until price has failed to beat it, and pretending otherwise is how a
    backtest sees levels the trader could not have drawn yet.
    """
    out = []
    for i in range(left, len(cd) - right):
        h, l = cd[i]["h"], cd[i]["l"]
        if all(cd[j]["h"] <= h for j in range(i - left, i)) and \
           all(cd[j]["h"] < h for j in range(i + 1, i + right + 1)):
            out.append(Swing(i, cd[i]["t"], h, "high"))
        if all(cd[j]["l"] >= l for j in range(i - left, i)) and \
           all(cd[j]["l"] > l for j in range(i + 1, i + right + 1)):
            out.append(Swing(i, cd[i]["t"], l, "low"))
    return out


# ── ۲. کدام خط معتبر است ────────────────────────────────────────────────────
# «خطی که برخورد زیادی داشته و واکنش نشان داده معتبر است و نگهش می‌دارم —
#  سقف و کف‌هایی که کمترین برخورد را داشتند پاک می‌کنم»

@dataclass
class Level:
    price: float
    kind: str            # the swing it was born from
    born_i: int
    born_t: int
    touches: int = 0
    reactions: int = 0
    flipped: bool = False        # «سقفی که کشیدم در ادامه به کف تبدیل شد»
    last_touch_i: int = -1
    touch_bars: list = field(default_factory=list)

    @property
    def valid(self):
        return self.reactions >= 2


def _reacted(cd, i, price, tol, bars=6, mult=3.0):
    """Did price actually turn here, or just pass through?

    A line price walks straight through is not support. The test is that within
    the next few bars price is at least `mult` tolerances away from the level,
    and away on one side rather than oscillating across it — which is what
    "واکنش نشان داد" means when you are looking at a chart.
    """
    end = min(len(cd), i + bars + 1)
    if end <= i + 1:
        return False
    after = cd[i + 1:end]
    above = max(c["c"] for c in after) - price
    below = price - min(c["c"] for c in after)
    if above >= mult * tol and below < mult * tol:
        return True                      # bounced up off it
    if below >= mult * tol and above < mult * tol:
        return True                      # rejected down off it
    return False


def levels(cd, tol=None, min_reactions=2, keep=14):
    """Draw every swing as a horizontal line, extend it forward, and count.

    This is the part Hamid does by eye and by memory: he draws the old highs and
    lows too, extends them, and two weeks later keeps the ones price kept
    respecting. Extending forward is the whole point — a level is only
    interesting because of what happened *after* it was drawn.
    """
    if len(cd) < 20:
        return []
    tol = tol if tol is not None else max(atr(cd) * 0.25, cd[-1]["c"] * 0.0005)
    out = []
    for s in swings(cd):
        lv = Level(price=s.price, kind=s.kind, born_i=s.i, born_t=s.t)
        # only bars after it was drawable count — see the note in swings()
        for i in range(s.i + 3, len(cd)):
            c = cd[i]
            if c["l"] - tol <= lv.price <= c["h"] + tol:
                if lv.last_touch_i >= 0 and i - lv.last_touch_i < 3:
                    continue             # one visit, not three touches
                lv.touches += 1
                lv.last_touch_i = i
                lv.touch_bars.append(i)
                if _reacted(cd, i, lv.price, tol):
                    lv.reactions += 1
                    # «سقفی که کشیدم در ادامه به کف آن ارز تبدیل شد»
                    approached_from_above = cd[i - 1]["c"] > lv.price
                    if (lv.kind == "high" and approached_from_above) or \
                       (lv.kind == "low" and not approached_from_above):
                        lv.flipped = True
        out.append(lv)

    # «سقف و کف‌هایی که کمترین برخورد را داشتند پاک می‌کنم»
    kept = [l for l in out if l.reactions >= min_reactions]
    kept.sort(key=lambda l: (-l.reactions, -l.touches))
    # near-duplicates are the same line drawn twice; keep the better-tested one
    merged = []
    for l in kept:
        if not any(abs(l.price / m.price - 1) < 0.0015 for m in merged):
            merged.append(l)
    return merged[:keep]


# ── ۳. روند ─────────────────────────────────────────────────────────────────
# «نگاه می‌کنم در ۴ ساعته ارز چه روندی دارد — نزولی یا صعودی»

def trend(cd, lookback=60):
    """Higher highs and higher lows, or lower highs and lower lows.

    Deliberately says "range" rather than guessing. A method built on knowing
    the 4H direction is worse off with a confident wrong answer than with an
    admission that there is no direction to have.

    One case needs care. A market that only goes up makes no fractal lows at
    all — every prior bar is lower than the current one, so nothing qualifies —
    and requiring both sides then reports the cleanest uptrend on the chart as
    "range". That was measured, not imagined: a straight staircase came back
    range. So when one side is missing, the other side plus the move in close
    price decides it. A trend that never pulls back is still a trend.
    """
    sw = [s for s in swings(cd) if s.i >= len(cd) - lookback]
    hi = [s.price for s in sw if s.kind == "high"][-3:]
    lo = [s.price for s in sw if s.kind == "low"][-3:]
    span = cd[-lookback:] if len(cd) > lookback else cd
    if len(span) < 5:
        return "range"
    drift = span[-1]["c"] / span[0]["c"] - 1
    a = atr(span)
    strong = abs(span[-1]["c"] - span[0]["c"]) > 3 * a if a else abs(drift) > 0.03

    if len(hi) >= 2 and len(lo) >= 2:
        up = hi[-1] > hi[0] and lo[-1] > lo[0]
        down = hi[-1] < hi[0] and lo[-1] < lo[0]
        return "up" if up else "down" if down else "range"

    # only one side produced swings — see the note above
    if len(hi) >= 2 and strong:
        return "up" if hi[-1] > hi[0] and drift > 0 else \
               "down" if hi[-1] < hi[0] and drift < 0 else "range"
    if len(lo) >= 2 and strong:
        return "up" if lo[-1] > lo[0] and drift > 0 else \
               "down" if lo[-1] < lo[0] and drift < 0 else "range"
    return "range"


# ── ۴. کانال ────────────────────────────────────────────────────────────────
# «کانال را می‌کشم … اگر قیمت از کانال بزند بیرون و برگردد و تثبیت بدهد،
#  بی‌قید و شرط سقف یا کف سمت مقابلش را لمس می‌کند»

def _fit(points):
    """Least squares through (index, price). Hamid draws the line by hand
    across the swings; this is the same line, decided by all of them rather
    than by the two that happen to be easiest to click."""
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx, my = fmean(xs), fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    m = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return m, my - m * mx


@dataclass
class Channel:
    upper: tuple
    lower: tuple
    position: float           # 0 at the floor, 1 at the ceiling
    width: float
    slope: str

    def at(self, i):
        return self.upper[0] * i + self.upper[1], self.lower[0] * i + self.lower[1]

    def mid(self, i):
        u, l = self.at(i)
        return (u + l) / 2


def channel(cd, lookback=90):
    """Upper line through the swing highs, lower through the swing lows."""
    start = max(0, len(cd) - lookback)
    sw = [s for s in swings(cd) if s.i >= start]
    hi = [(s.i, s.price) for s in sw if s.kind == "high"]
    lo = [(s.i, s.price) for s in sw if s.kind == "low"]
    if len(hi) < 2 or len(lo) < 2:
        return None
    up, dn = _fit(hi), _fit(lo)
    if not up or not dn:
        return None
    i = len(cd) - 1
    u, l = up[0] * i + up[1], dn[0] * i + dn[1]
    if u <= l:
        return None
    price = cd[-1]["c"]
    avg = (up[0] + dn[0]) / 2
    ref = cd[-1]["c"] / max(len(cd), 1)
    slope = "up" if avg > ref * 0.02 else "down" if avg < -ref * 0.02 else "flat"
    return Channel(up, dn, (price - l) / (u - l), u - l, slope)


def reentry(cd, ch, settle=3):
    """«از کانال بزند بیرون و برگردد به کانال و توی کانال تثبیت بدهد»

    Closed outside, then closed back inside and *stayed* inside for `settle`
    bars. Hamid calls that unconditional: first target the midline, then the
    far side. The word he used was بی‌قید و شرط, and it is the strongest claim
    in his method — which is exactly why it is worth measuring rather than
    assuming.
    """
    if ch is None or len(cd) < settle + 4:
        return None
    n = len(cd)
    inside = []
    for i in range(n - settle - 6, n):
        if i < 0:
            continue
        u, l = ch.at(i)
        inside.append((i, l <= cd[i]["c"] <= u, cd[i]["c"] > u, cd[i]["c"] < l))
    if len(inside) < settle + 2:
        return None
    tail = inside[-settle:]
    if not all(x[1] for x in tail):
        return None                      # not settled inside right now
    before = inside[:-settle]
    broke_up = any(x[2] for x in before)
    broke_dn = any(x[3] for x in before)
    if not (broke_up or broke_dn):
        return None
    i = n - 1
    u, l = ch.at(i)
    return {
        "side": "from_above" if broke_up else "from_below",
        "target1": ch.mid(i),
        "target2": l if broke_up else u,
        "note": "بعد از تثبیت در کانال: اول میدلاین، بعد سمت مقابل",
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from hamid.selfcheck import main
    main()
