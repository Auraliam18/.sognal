---
name: liam-e09-indicators
description: Implement, audit, test, or research E09 Indicator Engine / Indicator Agent for the LIAM crypto system. Use when work touches indicators or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E09.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E09
  owner: AuraLiam369
  version: 2.1.0
---

# E09 — Indicator Engine / Indicator Agent

## Mission

Compute Hamid’s indicator set causally and use it as context/confirmation, not as a standalone signal generator.

## Trigger events

- `CANDLE_CLOSE`
- `INDICATOR_CROSS`
- `DIVERGENCE_CANDIDATE`
- `REGIME_CHANGED`

## Required inputs

- OHLCV
- timeframe
- market regime

## Deterministic Python responsibilities

- RSI/MACD/MFI/IBS/ADX/ATR/Stochastic/EMA/SMA/BB/Alligator/Ichimoku/CPR/VWAP
- divergence detection
- unit tests

## Agent responsibilities

- interpret multi-indicator conflicts
- compare historical effectiveness by regime
- audit formula/version

## Hard rules

- No repainting or future candles.
- Volume remains primary context for Hamid.
- Stochastic has priority over RSI in a confirmed range.
- ADX measures trend strength, not direction.
- The 30M MACD cross + 15M RSI midline rule is a versioned trigger, not a universal truth.

## Learning routine

Monthly formula/library audit; event-triggered calibration when indicator contribution degrades by regime.

## Memory and evidence

- Private namespace: `agent/e09/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `IndicatorPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- J. Welles Wilder Jr. — New Concepts in Technical Trading Systems
- John Bollinger — Bollinger on Bollinger Bands
- John J. Murphy — Technical Analysis of the Financial Markets
- https://ta-lib.org/
- https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1992.tb04681.x

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
