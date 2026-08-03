#!/usr/bin/env python3
"""آیا این روش روی دادهٔ بی‌ساختار هم سیگنال می‌دهد؟

The control every rule in this repository should have to pass, and the one that
caught the level engine. A random walk has no support, no resistance and no
order blocks — none of them exist in the generating process. So whatever rate
the method fires at here is the rate it fires at on nothing.

That number is not required to be zero. Real markets and random walks share a
lot of surface behaviour, and a method that never fired on noise would probably
never fire at all. What matters is the gap: if the method signals on 42% of
random walks and 60% of real coins, then most of what it is finding is not
structure, and the daily signal count is measuring the generator rather than the
market.

    python3 -m hamid.control            # current rule
    python3 -m hamid.control --sweep    # impulse threshold against the control
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import stack
from hamid.cycle import resample
from hamid.selfcheck import series


def walks(n, bars=1200, sigma=0.005):
    for seed in range(n):
        random.seed(seed)
        p = [100.0]
        for _ in range(bars):
            p.append(max(1.0, p[-1] * (1 + random.gauss(0, sigma))))
        c1h = series(p, spread=0.12)
        yield resample(c1h, 4), c1h, c1h


def rate(n=40):
    sig = wait = 0
    for c4h, c1h, c15 in walks(n):
        r = stack.read("RNDUSDT", c4h, c1h, c15)
        if r.setup:
            if r.setup.get("waiting"):
                wait += 1
            else:
                sig += 1
    return sig, wait, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()

    if not a.sweep:
        s, w, n = rate(a.n)
        print(f"\nآستانهٔ فعلی MIN_IMPULSE={stack.MIN_IMPULSE}")
        print(f"  سیگنال روی قدم‌زدن تصادفی: {s}/{n} = {s/n*100:.0f}%")
        print(f"  در حال انتظار:              {w}/{n} = {w/n*100:.0f}%")
        return 0

    print("\nاثر آستانهٔ ضربه روی دادهٔ بی‌ساختار\n" + "─" * 46)
    original = stack.MIN_IMPULSE
    for thr in (0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0):
        stack.MIN_IMPULSE = thr
        s, w, n = rate(a.n)
        print(f"  MIN_IMPULSE={thr:>4}  سیگنال {s:>2}/{n} = {s/n*100:>3.0f}%   انتظار {w:>2}")
    stack.MIN_IMPULSE = original
    return 0


if __name__ == "__main__":
    sys.exit(main())
