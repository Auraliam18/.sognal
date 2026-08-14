---
name: liam-e12-lead-lag-pump-chain
description: Implement, audit, test, or research E12 Lead-Lag Engine / Relationship Agent for the LIAM crypto system. Use when work touches lead lag pump chain or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E12.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E12
  owner: AuraLiam369
  version: 2.1.0
---

# E12 — Lead-Lag Engine / Relationship Agent

## Mission

Detect historical and live pump chains: when a leader moves, identify repeat follower assets and their lag distribution up to 24 hours.

## Trigger events

- `PUMP_EVENT_15M`
- `VOLUME_SPIKE`
- `LEADER_EVENT_UPDATED`
- `FOLLOWER_VOLUME_ENTERED`

## Required inputs

- all historical 15M events
- volume/RSI/USDT.D/BTC/news/sector features
- current market state

## Deterministic Python responsibilities

- event study
- conditional/baseline probability
- lift
- lag median/IQR
- MFE/MAE
- multiple-testing control
- incremental follower clocks

## Agent responsibilities

- research common narrative/network causes
- interpret regime differences
- explain candidate follower

## Hard rules

- Analyze all available leader pumps, not only the latest two.
- Two repeated followers create RESEARCH_WATCH, not an automatic signal.
- A follower signal still requires live volume plus Hamid strategy gates.
- Never answer that the cycle was missed; maintain the clock continuously.

## Learning routine

Run immediately on every qualifying pump event; nightly incremental recomputation; weekly false-discovery and regime stability audit.

## Memory and evidence

- Private namespace: `agent/e12/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `LeadLagPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- Ruey S. Tsay — Analysis of Financial Time Series
- https://www.statsmodels.org/stable/index.html
- https://docs.scipy.org/doc/scipy/
- https://www.jstor.org/stable/2529269
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
