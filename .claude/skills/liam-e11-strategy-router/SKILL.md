---
name: liam-e11-strategy-router
description: Implement, audit, test, or research E11 Strategy Router / Strategy Agents for the LIAM crypto system. Use when work touches strategy router or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E11.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E11
  owner: AuraLiam369
  version: 2.1.0
---

# E11 — Strategy Router / Strategy Agents

## Mission

Execute versioned S1, S2, Liam S, IBS + Pullback Plus, and ONE-IDM Wick 15 rules without silently mixing them.

## Trigger events

- `STRATEGY_PROXIMITY`
- `ALERT_TRIGGERED`
- `PACKET_SET_COMPLETE`
- `CANDLE_CLOSE`

## Required inputs

- all required evidence packets
- strategy registry
- Golden Fixtures

## Deterministic Python responsibilities

- hard gates
- soft scoring
- entry/SL/TP/RR
- version selection
- missing requirements
- replay tests

## Agent responsibilities

- explain matched strategy
- resolve only documented ambiguity
- propose experiments without production promotion

## Hard rules

- Do not merge strategy rules ad hoc.
- Return missing_requirements explicitly.
- Every signal names strategy_id/version.
- CHoCH alone never authorizes reversal.
- Keep counter-trend disabled except a tested, versioned strategy.

## Learning routine

After every closed trade update evidence; weekly strategy drift report; all changes pass research→backtest→walk-forward→paper→shadow→review.

## Memory and evidence

- Private namespace: `agent/e11/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `StrategyMatch[]` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- references/version2_pdf_extracted_rules_FA.md
- docs/PULLBACK_BETWEEN_OPPOSING_OB_FA.md
- David Aronson — Evidence-Based Technical Analysis
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1992.tb04681.x

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
