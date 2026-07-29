# Parameter search — 2026-07-29 11:22 UTC

144 configurations, fitted on 200 markets and judged on 200 the engine never saw. 6894.3s.

**Shipped configuration** — out-of-sample +0.226R [0.1628, 0.2823] on 1925 trades.

| rank | fresh | R min | decisive | displacement | in-sample | out-of-sample | interval | trades |
|---|---|---|---|---|---|---|---|---|
| 1 | 10 | 1.8 | 0.35 | 1.5 | +0.2228R | **+0.2831R** | [0.2172, 0.3413] | 2014 |
| 2 | 10 | 2.2 | 0.35 | 1.2 | +0.1802R | **+0.2728R** | [0.2087, 0.3364] | 2310 |
| 3 | 10 | 1.8 | 0.35 | 1.2 | +0.198R | **+0.2693R** | [0.2152, 0.3215] | 2408 |
| 4 | 10 | 1.8 | 0.35 | 1.9 | +0.2369R | **+0.2677R** | [0.1916, 0.3387] | 1533 |
| 5 | 10 | 2.2 | 0.35 | 1.5 | +0.2086R | **+0.2627R** | [0.1969, 0.334] | 1932 |
| 6 | 15 | 1.8 | 0.35 | 1.5 | +0.1943R | **+0.2599R** | [0.1999, 0.3146] | 2280 |
| 7 | 10 | 1.8 | 0.5 | 1.2 | +0.1793R | **+0.253R** | [0.1804, 0.3131] | 1995 |
| 8 | 10 | 1.8 | 0.5 | 1.5 | +0.2052R | **+0.252R** | [0.1797, 0.3192] | 1704 |
| 9 | 10 | 1.5 | 0.35 | 1.5 | +0.2139R | **+0.251R** | [0.1971, 0.3094] | 2063 |
| 10 | 10 | 1.5 | 0.35 | 1.9 | +0.2055R | **+0.2474R** | [0.1807, 0.3075] | 1571 |
| 11 | 10 | 1.5 | 0.35 | 1.2 | +0.1917R | **+0.2387R** | [0.1905, 0.2997] | 2495 |
| 12 | 10 | 2.6 | 0.35 | 1.2 | +0.1969R | **+0.2378R** | [0.1686, 0.3171] | 2215 |

## Verdict

Best out-of-sample: fresh 10, R min 1.8, decisive 0.35 ATR, displacement 1.5 ATR.
That is +0.057R per trade over the shipped configuration, on markets neither saw during fitting.
In-sample minus out-of-sample is -0.06R — the smaller that gap, the less of the gain is fitting noise.

Adopting it means editing index.html: freshness window, RMIN, and the two ATR thresholds in smcOrderBlocks.