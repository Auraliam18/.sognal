# Parameter search — 2026-09-04 06:31 UTC

320 of 320 configurations measured, fitted on 200 markets and judged on 200 the engine never saw. 0s this run.

**Shipped configuration** — out-of-sample +0.3172R [0.2553, 0.3806] on 1629 trades.

| rank | fresh | R min | decisive | displacement | in-sample | out-of-sample | interval | trades |
|---|---|---|---|---|---|---|---|---|
| 1 | 8 | 1.8 | 0.35 | 1.5 | +0.2586R | **+0.3437R** | [0.269, 0.4122] | 1534 |
| 2 | 8 | 1.8 | 0.25 | 1.5 | +0.2707R | **+0.3373R** | [0.2741, 0.4058] | 1666 |
| 3 | 12 | 1.8 | 0.35 | 1.5 | +0.2443R | **+0.3257R** | [0.2518, 0.3999] | 1694 |
| 4 | 8 | 2.2 | 0.35 | 1.5 | +0.2375R | **+0.3221R** | [0.2289, 0.4058] | 1478 |
| 5 | 8 | 2.2 | 0.25 | 1.5 | +0.2548R | **+0.3206R** | [0.2396, 0.411] | 1603 |
| 6 | 12 | 2.2 | 0.35 | 1.5 | +0.2294R | **+0.3192R** | [0.2448, 0.4087] | 1620 |
| 7 | 10 | 1.8 | 0.35 | 1.5 | +0.2484R | **+0.3172R** | [0.2553, 0.3806] | 1629 |
| 8 | 8 | 1.8 | 0.35 | 1.2 | +0.2304R | **+0.3172R** | [0.2528, 0.3798] | 1768 |
| 9 | 8 | 1.8 | 0.25 | 1.2 | +0.2382R | **+0.3163R** | [0.2462, 0.3889] | 1935 |
| 10 | 10 | 2.2 | 0.25 | 1.2 | +0.2237R | **+0.316R** | [0.2378, 0.388] | 1972 |
| 11 | 8 | 2.2 | 0.25 | 1.2 | +0.2216R | **+0.3152R** | [0.2481, 0.3955] | 1855 |
| 12 | 10 | 1.8 | 0.25 | 1.5 | +0.2665R | **+0.31R** | [0.2414, 0.3796] | 1780 |

## Verdict

Best out-of-sample: fresh 8, R min 1.8, decisive 0.35 ATR, displacement 1.5 ATR.
That is +0.027R per trade over the shipped configuration, on markets neither saw during fitting.
In-sample minus out-of-sample is -0.085R — the smaller that gap, the less of the gain is fitting noise.

Adopting it means editing index.html: freshness window, RMIN, and the two ATR thresholds in smcOrderBlocks.