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

    A rejection has three parts, and the first version of this checked only the
    third. That was not a small miss: measured on a pure random walk — no
    structure of any kind — the old rule kept fourteen levels carrying about
    twenty "reactions" each. It was counting price leaving the area, which price
    always does, including when it blows straight through the line.

    So all three now have to hold:

      1. **Price came from somewhere.** It has to approach the level from one
         side, not already be sitting on it.
      2. **It did not close through.** If price ends up on the far side, the
         level did not hold — that is a break, and calling a break a reaction is
         how a chart fills up with lines that mean nothing.
      3. **It pushed back.** The move away, on the side it came from, is at
         least `mult` tolerances.

    Together that is what «واکنش نشان داد» means when you are looking at a
    chart, and unlike the old rule a random walk mostly fails it.
    """
    end = min(len(cd), i + bars + 1)
    if end <= i + 1 or i < 1:
        return False
    prev = cd[i - 1]["c"]
    if abs(prev - price) < tol:
        return False                     # no approach: already on the line
    side = 1 if prev > price else -1
    after = cd[i + 1:end]
    if side > 0 and min(c["c"] for c in after) < price - tol:
        return False                     # closed through, downwards
    if side < 0 and max(c["c"] for c in after) > price + tol:
        return False                     # closed through, upwards
    away = (max(c["c"] for c in after) - price) if side > 0 \
        else (price - min(c["c"] for c in after))
    return away >= mult * tol


def _tally(cd, price, tol, born_i):
    """Touches and reactions for any horizontal line, from `born_i` onward.

    Used for real swing levels and for the random control lines alike, so the
    two are counted by exactly the same rule and can be compared.
    """
    touches = reactions = 0
    last = -99
    flipped = False
    for i in range(born_i + 3, len(cd)):
        c = cd[i]
        if not (c["l"] - tol <= price <= c["h"] + tol):
            continue
        if i - last < 3:
            continue                     # one visit, not three touches
        touches += 1
        last = i
        if _reacted(cd, i, price, tol):
            reactions += 1
            if cd[i - 1]["c"] > price:
                flipped = True
    return touches, reactions, flipped


def _noise_floor(cd, tol, samples=28):
    """How many reactions does a line in this series get *by chance*?

    This is the part that turns Hamid's eye into a measurement, and it exists
    because of a number. On a pure random walk — a series with no support or
    resistance anywhere in it, by construction — the level rule was keeping
    around forty lines carrying two or more reactions each, and even demanding
    five reactions still kept eleven. Not because the rule was sloppy, but
    because random walks mean-revert locally: over six hundred bars a horizontal
    line drawn *anywhere* in the traversed range gets touched and pushed away
    from many times. Any absolute threshold measures the length of the series
    more than the quality of the level.

    So the threshold is not absolute. Control lines are drawn at prices spread
    through the same range, given the same birth indices, and counted by the
    same rule. A real level has to beat what an arbitrary line in this very
    series already achieves. Rates are per hundred remaining bars, because a
    line drawn early has more chances to be hit than one drawn late.
    """
    lo = min(c["l"] for c in cd)
    hi = max(c["h"] for c in cd)
    if hi <= lo:
        return 0.0
    rates = []
    n = len(cd)
    for k in range(samples):
        price = lo + (hi - lo) * ((k + 0.5) / samples)
        born = int(n * 0.1) + (k * (n // 2)) // max(samples, 1)
        born = min(born, n - 12)
        if born < 0:
            continue
        _, r, _ = _tally(cd, price, tol, born)
        rates.append(r / max(1, n - born) * 100)
    if not rates:
        return 0.0
    rates.sort()
    return rates[int(len(rates) * 0.80)]          # the 80th percentile of noise


def levels(cd, tol=None, min_reactions=2, keep=8):
    """Draw every swing as a horizontal line, extend it forward, and count.

    This is the part Hamid does by eye and by memory: he draws the old highs and
    lows too, extends them, and two weeks later keeps the ones price kept
    respecting. Extending forward is the whole point — a level is only
    interesting because of what happened *after* it was drawn.

    A level survives only if it clears both bars: at least `min_reactions`
    rejections, and a reaction rate above what a random line in the same series
    manages. See `_noise_floor` for why the second one is not optional.
    """
    if len(cd) < 20:
        return []
    tol = tol if tol is not None else max(atr(cd) * 0.25, cd[-1]["c"] * 0.0005)
    floor = _noise_floor(cd, tol)
    n = len(cd)
    out = []
    for s in swings(cd):
        t, r, flip = _tally(cd, s.price, tol, s.i)
        rate = r / max(1, n - s.i) * 100
        if r < min_reactions or rate <= floor:
            continue                     # «کمترین برخورد را داشتند — پاک می‌کنم»
        lv = Level(price=s.price, kind=s.kind, born_i=s.i, born_t=s.t,
                   touches=t, reactions=r)
        # «سقفی که کشیدم در ادامه به کف آن ارز تبدیل شد»
        lv.flipped = flip if s.kind == "high" else not flip
        out.append(lv)

    out.sort(key=lambda l: (-l.reactions, -l.touches))
    # near-duplicates are the same line drawn twice; keep the better-tested one
    merged = []
    for l in out:
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


# ── ۵. خط روند به روش کتاب ─────────────────────────────────────────────────
# دستور حمید (۱۵ اوت): «خط روند ۱ساعته و ۴ساعته که بر اساس ترندلاین‌کشیدن
# یاد گرفتی، در تصویر بماند.»
#
# فرق این با `channel()` مهم است و عمدی: کانال یک برازش کمترین‌مربعات روی
# **همهٔ** سوینگ‌هاست — خطی که از وسط داده رد می‌شود. خط روندِ کتاب این
# نیست. خط روند صعودی از **زیرِ** کف‌ها می‌گذرد و هیچ‌کدام را نمی‌بُرد؛
# خط روند نزولی از **بالای** سقف‌ها. کتاب سه شرط می‌گذارد:
#
#   ۱. دست‌کم سه برخورد معتبر — ترجیح صریح حمید در سند شخصی‌سازی.
#      دو نقطه هر خطی را می‌سازد؛ نقطهٔ سوم است که ادعا را آزمون می‌کند.
#   ۲. خط نباید توسط **بدنهٔ** کندل شکسته شده باشد. ویک اجازه دارد رد شود
#      (همان هانت نقدینگی)، بدنه نه — حمید همین تفکیک را در سندش خواسته.
#   ۳. شیب باید با جهت روند بخواند: صعودی روی کف‌های بالارونده، نزولی روی
#      سقف‌های پایین‌رونده. خط افقی خط روند نیست، آن سطح است.

@dataclass
class Trendline:
    slope: float
    intercept: float
    kind: str                 # "support" (زیر کف‌ها) یا "resistance"
    touches: int
    first_i: int
    last_i: int
    broken: bool = False      # بدنه از آن رد شد؟ خط می‌ماند، وضعیتش عوض می‌شود

    def at(self, i):
        return self.slope * i + self.intercept

    def at_t(self, t, cd):
        """قیمت خط در یک timestamp — برای کشیدن خط تایم بالا روی چارت
        تایم پایین. بدون این، خط ۴ساعته روی محور ۵دقیقه بی‌معنا جابه‌جا
        می‌شود."""
        if len(cd) < 2:
            return None
        step = cd[1]["t"] - cd[0]["t"]
        if step <= 0:
            return None
        return self.at((t - cd[0]["t"]) / step)


def trendline(cd, lookback=120, min_touches=3, tol_mult=0.6):
    """بهترین خط روندِ معتبر در این پنجره، یا None.

    None یعنی «خط روند معتبری نیست» و همان باید رسم شود: هیچ. خط تزئینی
    روی چارت، همان چیزی است که حمید «خط الکی» می‌نامد.
    """
    start = max(0, len(cd) - lookback)
    win = cd[start:]
    if len(win) < 20:
        return None
    tol = atr(win) * tol_mult
    if not tol or tol <= 0:
        return None
    sw = [s for s in swings(win) if s.i < len(win)]
    best = None
    for kind, want in (("support", "low"), ("resistance", "high")):
        pts = [(s.i, s.price) for s in sw if s.kind == want]
        if len(pts) < 2:
            continue
        # هر جفت نقطه یک خط کاندید می‌سازد؛ برخوردها و شکست‌ها شمرده می‌شوند.
        for a in range(len(pts)):
            for b in range(a + 1, len(pts)):
                (x1, y1), (x2, y2) = pts[a], pts[b]
                if x2 == x1:
                    continue
                m = (y2 - y1) / (x2 - x1)
                c = y1 - m * x1
                # شیب باید جهت داشته باشد؛ خط تقریباً افقی سطح است نه روند.
                if abs(m) * len(win) < tol:
                    continue
                # و جهتش باید با نوعش بخواند — تعریف کتاب، نه سلیقه:
                # خط حمایتِ روند از کف‌های **بالارونده** ساخته می‌شود، پس
                # بالا می‌رود؛ خط مقاومتِ روند از سقف‌های **پایین‌رونده**.
                # بدون این شرط، روی سری نزولی یک «حمایت» صعودی پیدا می‌شد
                # که هیچ معنای ساختاری ندارد.
                if (kind == "support") != (m > 0):
                    continue
                # دو لنگرِ خط باید از هم دور باشند و خط باید در طول پنجره
                # مسیر معناداری برود. بدون این دو شرط، روی گام تصادفی هم
                # خط پیدا می‌شد — یعنی همان «خط تزئینی» که روش حمید رد
                # می‌کند. سنجیده شد: با این شرط‌ها نرخ کشف روی گام تصادفی
                # به صفر رسید و روی سری رونددار دست‌نخورده ماند.
                if abs(x2 - x1) < len(win) * 0.35:
                    continue
                if abs(m) * len(win) < tol * 3:
                    continue
                touches, bad, last_touch = 0, 0, -99
                for i, k in enumerate(win):
                    line = m * i + c
                    if kind == "support":
                        # بدنه زیر خط = شکست. ویک تا نزدیکیِ خط = برخورد.
                        if min(k["o"], k["c"]) < line - tol:
                            bad += 1
                            continue
                        near = abs(k["l"] - line) <= tol
                    else:
                        if max(k["o"], k["c"]) > line + tol:
                            bad += 1
                            continue
                        near = abs(k["h"] - line) <= tol
                    # برخورد یعنی قیمت واقعاً به خط **رسید**، نه اینکه صرفاً
                    # بالای آن بود. نسخهٔ اول هر کندلِ بالای خط را برخورد
                    # می‌شمرد و ۳۷ برخورد می‌داد — عددی که شرط «≥۳ برخورد»
                    # را بی‌معنا می‌کرد چون همیشه برقرار بود.
                    #
                    # و هر نزدیک‌شدن یک برخورد است، نه هر کندلِ آن نزدیکی:
                    # پنج کندلِ چسبیده یک لمس‌اند، نه پنج تا.
                    if near and i - last_touch > 3:
                        touches += 1
                        last_touch = i
                if touches < min_touches:
                    continue
                # چند شکستِ بدنه یعنی خط دیگر معتبر نیست. کمی بردباری لازم
                # است چون یک کندل پرت نباید خطِ درست را دور بریزد.
                broken = bad > max(2, len(win) // 40)
                cand = Trendline(m, c, kind, touches, min(x1, x2), max(x1, x2),
                                 broken)
                score = (0 if broken else 1, touches, max(x1, x2))
                if best is None or score > best[0]:
                    best = (score, cand)
    return best[1] if best else None
