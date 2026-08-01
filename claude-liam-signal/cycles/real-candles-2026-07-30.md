# The first backtest on candles that really traded

**30 July 2026 · real Binance klines · 60 pairs · 120 series · 3,931 trades**
Run: [Historical backtest #1](https://github.com/Auraliam18/.sognal/actions/runs/30587472612) ·
reproduce with `python3 claude-liam-signal/python/backtest.py`

Every number reported until now came from the simulator. It is a hard model —
volatility clustering, fat tails, regime switching — and it answers one question
well: does the engine have an edge against a market that is not trying to be
kind. It does not answer what the engine did on the actual tape. This is the
first measurement that does, and it does not agree with the simulator.

* 60 most-traded USDT pairs, 5,000 candles each on 15m (≈52 days) and 5m (≈17 days).
* The engine lifted straight out of `index.html` — not a re-implementation.
* Never more than 400 bars of history visible, exactly as in the panel, and only
  bars up to the current one, so nothing can see its own future.
* Managed the way the paper desk manages: target one moves the stop to entry,
  then target two or the return to entry closes it, eight hours is a timeout,
  and a bar that could have hit either side is assumed to have hit the losing one.

## The strategy as it ships

| slice | n | win | expectancy | 95% interval | |
|---|---|---|---|---|---|
| **overall** | 3,931 | **22.7%** | **+0.069R** | [+0.023, +0.118] | ✓ above zero |
| 15m only | 2,071 | 18.3% | +0.005R | [-0.052, +0.063] | — spans zero |
| 5m only | 1,860 | 27.6% | +0.141R | [+0.062, +0.220] | ✓ above zero |
| long | 2,070 | 25.0% | +0.138R | [+0.072, +0.207] | ✓ above zero |
| short | 1,861 | 20.2% | -0.007R | [-0.075, +0.060] | — spans zero |

How the trades ended: **2,069 stopped, 1,212 timed out, 380 reached target two,
270 came back to entry after target one.**

## The correction

The cycle report from the same evening said 45% win and +0.283R. Real candles say
**22.7% win and +0.069R** — half the win rate and a quarter of the expectancy.

The edge is real: the interval clears zero on 3,931 trades. But it is roughly
four times smaller than the simulator has been claiming, and everything decided
by comparing simulator numbers to each other should be read with that in mind.
The simulator is still the right tool for asking *does this rule help* — it is
cheap, it has thousands of markets, and both arms of a comparison are wrong in
the same direction. It is the wrong tool for asking *how well does this do*.

This is the fifth correction in this project and the largest.

### Is it the data, or is it a different harness?

Worth asking before accepting the number, because the two harnesses are not
identical. `tests/harness.js` closes fully at target one; the backtest moves the
stop to entry there and then waits for target two, exactly as the paper desk
does. It also caps the visible history at 400 bars, requires R ≥ 1 rather than
R ≥ 0.5, and uses a six-bar cooldown rather than eight.

Most of those differences make the backtest *more* generous, not less — target
two pays more than target one, and a trade that reaches target one and then times
out is still credited. The win criterion is the same in both: a trade wins if and
only if it touched target one.

The one difference that could plausibly cut the other way is the 400-bar window,
so it was measured on its own — same engine, same simulated markets, only the
window changed:

| history the engine can see | n | win | expectancy |
|---|---|---|---|
| 400 bars, as the panel gets | 474 | 47.5% | 0.472R |
| unlimited | 466 | 47.2% | 0.460R |

No difference. The gap between 45% and 22.7% is the data, not the harness.

## Three things the real tape says that the simulator never did

**The 15m timeframe carries no measurable edge on its own.** 2,071 trades,
+0.005R, interval [-0.052, +0.063]. The whole of the result comes from 5m.
That is the opposite of the assumption the panel has been built on, and it is a
single 52-day window, so it is a finding to test again before acting on — but it
is the first hard evidence about which timeframe is worth the attention.

**Shorts carry no measurable edge.** 1,861 trades at -0.007R, interval
[-0.075, +0.060], against longs at +0.138R with the interval clear. On a tape
that spent the window rising this is what a direction-agnostic engine would look
like, so it is not yet proof that the short logic is broken. It is a reason to
split the next backtest by market regime rather than to switch shorts off.

**Over half of all trades are stopped and a third time out.** Only 650 of 3,931
ever reach target one. The strategy is not a high-win-rate strategy; it is a
low-win-rate, high-payoff one, and its positive expectancy comes entirely from
the size of the winners.

That last point matters more than the other two, because the stated goal is a win
rate above 90%. **This engine cannot reach 90% with targets placed where they
are, and no amount of filtering will get it there** — filters change which trades
are taken, not what a trade pays. A 90% win rate requires targets close enough to
be hit nine times in ten, which means a reward far smaller than the risk, which
means the expectancy has to be rebuilt from scratch on the other side of the
trade. That is a different strategy, not a tuned version of this one. It can be
built and measured the same way; it should not be pretended into existence by
reporting the current one differently.

## The channel rules, on real candles

The four rules from the channel summary failed on simulated markets
([the measurement](channel-rules-2026-07-30.md)). Two of them could not be tested
there at all, because the simulator never produces thin tape. Real candles do, so
here is the answer the simulator could not give:

| | n | win | expectancy | 95% interval |
|---|---|---|---|---|
| as shipped | 3,931 | 22.7% | +0.069R | [+0.023, +0.118] |
| with all three rules required | 1,693 | 21.7% | +0.067R | [-0.004, +0.143] |

**Δ = -0.002R, interval [-0.088, +0.088].** Requiring room to run, an inducement
sweep and non-thin structure discarded 57% of the trades and moved expectancy by
two thousandths of an R, in the wrong direction. On real candles, as on simulated
ones, the rules do not earn a gate. They stay on the card as information.

Worth naming plainly: this is now the second independent measurement, on a
completely different kind of data, reaching the same conclusion. The rules
describe the setup accurately — they are just not predictive of the outcome once
the rest of the chain has already filtered.

## What should happen next

1. **Re-run over a window that contains a downtrend**, to find out whether the
   short result is the strategy or the market.
2. **Split 15m and 5m properly** rather than treating them as one pool, and if
   5m keeps carrying the result, weight the scanner toward it.
3. **Decide about the 90% goal explicitly.** Either the goal moves to expectancy,
   or a second strategy gets built for a high win rate at low reward. Both are
   legitimate; leaving it unstated is not.
4. Longer history than 52 days, once the fetch is caching properly across runs.
