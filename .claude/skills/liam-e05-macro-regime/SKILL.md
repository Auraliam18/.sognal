---
name: liam-e05-macro-regime
description: Implement, audit, test, or research E05 Macro Regime Engine / Macro Agent for the LIAM crypto system. Use when work touches macro regime or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E05.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E05
  owner: AuraLiam369
  version: 2.1.0
---

# E05 — Macro Regime Engine / Macro Agent

## Mission

Classify risk-on/risk-off context from crypto totals, dominance, DXY/VIX/economic events, and source-verified macro catalysts.

## Trigger events

- `MACRO_DATA_RELEASE`
- `DAILY_MACRO_REFRESH`
- `RISK_REGIME_SHIFT`
- `SIGNAL_CANDIDATE`

## Required inputs

- TOTAL/TOTAL2/TOTAL3/OTHERS/ETH.D
- DXY
- VIX
- Fear & Greed
- official economic calendar

## Deterministic Python responsibilities

- calendar normalization
- event-window flags
- regime features
- freshness and source checks

## Agent responsibilities

- interpret source-verified macro events
- assess risk-on/risk-off
- write concise impact window

## Hard rules

- AInvest and social posts are discovery sources, not final truth.
- Verify material claims with official releases or primary sources.
- Record event time in Hamid’s configured timezone.

## Learning routine

Daily 72-hour catalyst calendar; immediate review after high-impact releases; weekly source-quality audit.

## Memory and evidence

- Private namespace: `agent/e05/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `MacroRegimePacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://fred.stlouisfed.org/docs/api/fred/
- https://www.cboe.com/tradable_products/vix/
- https://www.cmegroup.com/education.html
- https://alternative.me/crypto/fear-and-greed-index/
- https://docs.coingecko.com/reference/crypto-global

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
