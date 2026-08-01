# The four channel rules, measured

**30 July 2026 · simulated markets · 4,152 trades · reproduce with
`node tests/channel-rules.js` then `node tests/channel-rules-agg.js`**

The eight-point summary of the setup names four things that are not in the
engine's decision anywhere: room to run before the opposing zone, the inducement
sweep that precedes the real move, false structure built from inside candles, and
thin participation. Each was implemented, each was measured on its own, and none
of them was allowed to gate anything until the measurement came back.

Baseline across all 4,152 trades: **0.384R, 44.9% win rate**.

## 1. Room to run — *not adopted*

Distance from entry to the nearest opposing order block, FVG or twice-touched
level, expressed in units of the trade's own risk.

| slice | n | win | expectancy | 95% interval |
|---|---|---|---|---|
| room < 1R | 2,111 | 43.1% | 0.339R | [0.280, 0.399] |
| room 1–1.5R | 187 | 48.1% | 0.466R | [0.252, 0.677] |
| room 1.5–3R | 181 | 47.0% | 0.411R | [0.204, 0.614] |
| room ≥ 3R | 206 | 43.2% | 0.391R | [0.166, 0.616] |
| no blocker at all | 1,467 | 47.2% | 0.434R | [0.368, 0.503] |

Filtering at 1.5R gains **0.078R, interval [-0.007, 0.163]** — it straddles zero.

A single borderline result invites a second look, so nine thresholds were swept:

| threshold | keeps | drops | Δ | interval | |
|---|---|---|---|---|---|
| 0.25R | 3,171 | 982 | +0.064R | [-0.031, 0.161] | — |
| 0.50R | 2,550 | 1,603 | +0.092R | [+0.008, 0.178] | ✓ |
| 0.75R | 2,222 | 1,931 | +0.076R | [-0.007, 0.163] | — |
| 1.00R | 2,039 | 2,114 | +0.090R | [+0.009, 0.175] | ✓ |
| 1.25R | 1,931 | 2,222 | +0.073R | [-0.006, 0.161] | — |
| 1.50R | 1,852 | 2,301 | +0.076R | [-0.012, 0.160] | — |
| 2.00R | 1,768 | 2,385 | +0.068R | [-0.019, 0.153] | — |
| 2.50R | 1,714 | 2,439 | +0.062R | [-0.024, 0.145] | — |
| 3.00R | 1,671 | 2,482 | +0.073R | [-0.014, 0.153] | — |

Two of nine clear zero, and they are not adjacent: 0.5 passes, 0.75 fails, 1.0
passes, 1.25 fails. A rule that were real would show a gradient — more room,
better outcome — and this does not. At nine comparisons on a 95% interval, half a
false positive is the expectation, and two is inside what chance produces. **The
rule is not adopted as a gate.**

It is not thrown away either. Room to run is computed on every setup and shown on
the card, because when the panel says *2.3× risk before the opposing block* that
is worth a trader's eye even when it is not worth an automatic veto.

## 2. Inducement sweep — *not adopted*

Whether resting liquidity (two or more touches at the same level) was wicked
through and rejected before the order block formed.

| slice | n | win | expectancy | 95% interval |
|---|---|---|---|---|
| swept | 2,149 | 44.4% | 0.363R | [0.306, 0.421] |
| not swept | 2,003 | 45.5% | 0.407R | [0.345, 0.468] |

Difference **-0.043R, interval [-0.125, 0.040]**. Not only does it fail to clear
zero, the sign points the wrong way: on this data the swept setups did slightly
*worse*. Requiring an inducement would have removed roughly half the trades to buy
nothing. **Not adopted.** Shown on the card as context.

## 3 and 4. False structure and thin volume — *not testable here*

These two could not be measured, and it is worth being exact about why rather
than reporting a null result as though it meant something.

* Inside-candle ratio across all 4,152 trades: minimum 0.000, median 0.210,
  90th percentile 0.280, **maximum 0.450**.
* Volume ratio: **minimum 0.400**, 10th percentile 0.870, median 1.000.

The thresholds are 0.45 and 0.45. The simulator's most compressed tape only just
touches the first and never reaches the second — one trade out of 4,152 tripped
the flag. That is not evidence the rule is worthless; it is evidence the
simulator cannot produce the thing the rule is about. It generates every bar with
a full range and ordinary volume, and the rule exists for illiquid alt pairs where
neither is true.

**Both wait on real candles.** That is what
`claude-liam-signal/python/backtest.py` and the `Historical backtest` workflow
are for: they run the same engine over klines that actually traded, on 15m and
5m, where thin tape genuinely exists.

## What changed in the engine

Nothing gates on the strength of this. `roomToRun`, `liquidityPools`,
`inducementSwept` and `structureIsThin` stay in the engine and their output
appears on the setup card, so the reasoning is visible. The decision chain is
unchanged: risk-to-reward, confidence, expectancy, ADX floor, dominance conflict.

This is the fourth time a plausible-sounding rule has failed to survive its own
measurement, and it is the reason the rule about intervals exists.
