---
name: liam-e15-watch-alert
description: Implement, audit, test, or research E15 Watch & Alert Engine / Watch Agent for the LIAM crypto system. Use when work touches watch alert or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E15.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E15
  owner: AuraLiam369
  version: 2.1.0
---

# E15 — Watch & Alert Engine / Watch Agent

## Mission

Mark important nearby levels and trigger immediate symbol re-analysis when price approaches or crosses a relevant line, zone, OB, FVG, or liquidity level.

## Trigger events

- `STRUCTURE_PACKET`
- `SMC_PACKET`
- `PRICE_UPDATE`
- `CATALYST_WINDOW_OPEN`

## Required inputs

- all active levels/zones
- ATR/volatility
- strategy proximity
- data health

## Deterministic Python responsibilities

- distance/ETA
- dynamic thresholds
- alert state machine
- cooldown/dedupe
- per-symbol requeue

## Agent responsibilities

- resolve ambiguous alert priority
- explain why a symbol remains on watch

## Hard rules

- Alert does not equal signal.
- A triggered alert re-enters the full analysis path immediately.
- Do not wait for the next full universe batch.
- Persist alerts across restarts.

## Learning routine

Weekly alert precision/recall audit; tune only after replay/paper validation.

## Memory and evidence

- Private namespace: `agent/e15/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `WatchCase` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://docs.python.org/3/library/asyncio.html
- https://docs.nats.io/nats-concepts/jetstream
- Gregor Hohpe & Bobby Woolf — Enterprise Integration Patterns
- Tyler Akidau et al. — Streaming Systems

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
