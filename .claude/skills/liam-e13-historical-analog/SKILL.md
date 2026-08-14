---
name: liam-e13-historical-analog
description: Implement, audit, test, or research E13 Historical Analog Engine / Analog Agent for the LIAM crypto system. Use when work touches historical analog or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E13.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E13
  owner: AuraLiam369
  version: 2.1.0
---

# E13 — Historical Analog Engine / Analog Agent

## Mission

Find past states that resemble the current symbol across structure, location, indicators, volume, liquidity, BTC/USDT.D, news, and session—not visual shape alone.

## Trigger events

- `SIGNAL_CANDIDATE`
- `PUMP_EVENT`
- `UNUSUAL_BEHAVIOR`
- `POST_TRADE_REVIEW`

## Required inputs

- feature store
- episodic memory
- regime labels
- strategy outcomes

## Deterministic Python responsibilities

- feature vector normalization
- nearest-neighbor/DTW/matrix-profile candidates
- outcome stats
- no-lookahead queries

## Agent responsibilities

- compare critical similarities/differences
- reject superficial analogs
- summarize historical behavior

## Hard rules

- Current and historical features must use the same version.
- No future leakage.
- Always report sample size and regime.
- Analog similarity proposes evidence; it cannot bypass hard strategy gates.

## Learning routine

Nightly index refresh; event-triggered feature review after poor analog performance.

## Memory and evidence

- Private namespace: `agent/e13/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `AnalogPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://www.nber.org/papers/w7613
- Ruey S. Tsay — Analysis of Financial Time Series
- https://scikit-learn.org/stable/
- https://www.cs.ucr.edu/~eamonn/MatrixProfile.html
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
