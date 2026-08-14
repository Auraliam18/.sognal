---
name: liam-e25-telegram-delivery
description: Implement, audit, test, or research E25 Telegram Delivery Engine / Notification Agent for the LIAM crypto system. Use when work touches telegram delivery or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E25.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E25
  owner: AuraLiam369
  version: 2.1.0
---

# E25 — Telegram Delivery Engine / Notification Agent

## Mission

Send every qualified signal immediately as an individual chart message, persist its Telegram message_id, and reply to that exact message with updates/results.

## Trigger events

- `SIGNAL_READY`
- `SIGNAL_UPDATE`
- `SIGNAL_RESULT`
- `DELIVERY_RETRY`

## Required inputs

- SignalDecision
- rendered chart
- outbox row
- chat configuration

## Deterministic Python responsibilities

- signal ID
- chart send
- outbox
- dedupe
- retry
- message_id mapping
- reply_parameters

## Agent responsibilities

- compose concise Persian caption
- ensure rationale and invalidation are clear
- review delivery anomalies

## Hard rules

- No batch wait.
- One delivery writer only.
- Secrets remain backend-only.
- Every result uses the stored original message_id.
- Chart watermark Trade_osuli must be unobtrusive and not cover evidence.

## Learning routine

Continuous delivery metrics; immediate review after late/duplicate/failed reply; monthly API changelog audit.

## Memory and evidence

- Private namespace: `agent/e25/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `DeliveryReceipt` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://core.telegram.org/bots/api
- Gregor Hohpe & Bobby Woolf — Enterprise Integration Patterns
- Martin Kleppmann — Designing Data-Intensive Applications

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
