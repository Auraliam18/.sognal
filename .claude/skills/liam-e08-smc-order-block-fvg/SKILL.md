---
name: liam-e08-smc-order-block-fvg
description: Implement, audit, test, or research E08 SMC Engine / SMC Agent for the LIAM crypto system. Use when work touches smc order block fvg or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E08.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E08
  owner: AuraLiam369
  version: 2.1.0
---

# E08 — SMC Engine / SMC Agent

## Mission

Detect, validate, score, track, invalidate, and learn high-quality OB/FVG/liquidity structures rather than labeling every opposite candle.

## Trigger events

- `DISPLACEMENT`
- `BOS_MSS`
- `OB_APPROACHING`
- `OB_TOUCHED`
- `FVG_STATE_CHANGED`
- `LIQUIDITY_SWEEP`

## Required inputs

- structure packet
- OHLCV/ATR/volume
- liquidity packet
- HTF location

## Deterministic Python responsibilities

- candidate detection
- state machine
- mitigation depth
- freshness
- nested OB/FVG overlap
- score features

## Agent responsibilities

- validate structural meaning
- research unusual OB behavior
- explain liquidity and invalidation

## Hard rules

- Last opposite candle alone is never sufficient.
- Require displacement plus meaningful BOS/MSS and contextual evidence.
- Track CANDIDATE/FRESH/TOUCHED/PARTIAL/MITIGATED/WEAKENED/CONSUMED/BREAKER/INVALIDATED.
- Repeated tests weaken a zone.
- HTF location outweighs isolated 5M appearance.

## Learning routine

Targeted research only after repeated model error or new concept; every conceptual SMC claim remains experimental until tested on LIAM data.

## Memory and evidence

- Private namespace: `agent/e08/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `SMCPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- Larry Harris — Trading and Exchanges
- Maureen O'Hara — Market Microstructure Theory
- Joel Hasbrouck — Empirical Market Microstructure
- https://arxiv.org/abs/1011.6402
- https://www.youtube.com/@InnerCircleTrader

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
