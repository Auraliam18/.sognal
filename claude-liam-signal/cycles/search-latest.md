# Parameter search — 2026-07-29 09:24 UTC

8 configurations, fitted on 40 markets and judged on 40 the engine never saw. 58.4s.

**Shipped configuration** — out-of-sample +0.2408R [0.0845, 0.3966] on 363 trades.

| rank | fresh | R min | decisive | displacement | in-sample | out-of-sample | interval | trades |
|---|---|---|---|---|---|---|---|---|
| 1 | 15 | 1.8 | 0.35 | 1.9 | +0.2861R | **+0.2731R** | [0.1122, 0.4267] | 334 |
| 2 | 15 | 1.8 | 0.35 | 1.2 | +0.2388R | **+0.2459R** | [0.1201, 0.3714] | 534 |
| 3 | 15 | 1.8 | 0.5 | 1.5 | +0.2793R | **+0.2408R** | [0.0845, 0.3966] | 363 |
| 4 | 15 | 1.8 | 0.35 | 1.5 | +0.282R | **+0.2293R** | [0.1059, 0.365] | 442 |
| 5 | 15 | 1.8 | 0.5 | 1.2 | +0.226R | **+0.2114R** | [0.0638, 0.3537] | 436 |

## Verdict

Best out-of-sample: fresh 15, R min 1.8, decisive 0.35 ATR, displacement 1.9 ATR.
That is +0.032R per trade over the shipped configuration, on markets neither saw during fitting.
In-sample minus out-of-sample is 0.013R — the smaller that gap, the less of the gain is fitting noise.

Adopting it means editing index.html: freshness window, RMIN, and the two ATR thresholds in smcOrderBlocks.