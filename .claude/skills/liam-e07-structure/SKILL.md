---
name: liam-e07-structure
description: Implement, audit, test, or research E07 Structure Engine / Structure Agent for the LIAM crypto system. Use when work touches structure or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E07.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E07
  owner: AuraLiam369
  version: 2.1.0
---

# E07 — Structure Engine / Structure Agent

## Mission

Detect and preserve valid pivots, trendlines, channels, S/R, BOS/CHoCH, role flips, and multi-timeframe structure exactly in Hamid’s hierarchy.

## Trigger events

- `CANDLE_CLOSE`
- `PIVOT_CONFIRMED`
- `LINE_APPROACHING`
- `STRUCTURE_BREAK`

## Required inputs

- OHLCV 4H/1H/15M/5M
- ATR
- volume
- existing line lifecycle

## Deterministic Python responsibilities

- causal pivots
- line fitting/scoring
- channel pairing
- S/R clustering
- BOS/CHoCH
- line lifecycle

## Agent responsibilities

- review ambiguous competing lines
- compare Golden Fixtures
- explain why a line/channel is valid

## Hard rules

- Use at least 200 candles for 4H and 1H map building.
- Prefer lines with at least three valid reactions unless a strategy explicitly permits two.
- Do not force a line through unrelated pivots.
- Never delete valid historical lines; track BROKEN/FLIPPED/HISTORICAL.
- A wick touch and body acceptance must be recorded separately.

## Learning routine

Weekly chart-pattern and line-validation review; event-triggered research when false-break rate drifts.

## Memory and evidence

- Private namespace: `agent/e07/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `StructurePacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- John J. Murphy — Technical Analysis of the Financial Markets
- Charles D. Kirkpatrick II & Julie R. Dahlquist — Technical Analysis: The Complete Resource for Financial Market Technicians
- Robert D. Edwards, John Magee & W.H.C. Bassetti — Technical Analysis of Stock Trends
- Al Brooks — Trading Price Action series
- https://www.nber.org/papers/w7613
- https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1992.tb04681.x

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
