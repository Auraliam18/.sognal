---
name: liam-e20-post-trade-review
description: Implement, audit, test, or research E20 Post-Trade Engine / Reviewer Agent for the LIAM crypto system. Use when work touches post trade review or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E20.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E20
  owner: AuraLiam369
  version: 2.1.0
---

# E20 — Post-Trade Engine / Reviewer Agent

## Mission

Immediately and retrospectively explain target/stop/no-fill outcomes, identify which pre-trade factors held or failed, and create evidence-backed lessons.

## Trigger events

- `SIGNAL_RESULT`
- `TRADE_CLOSED`
- `REVIEW_1H`
- `REVIEW_6H`
- `REVIEW_24H`

## Required inputs

- immutable pre-trade snapshot
- full event trail
- actual path
- engine packets
- prior lessons

## Deterministic Python responsibilities

- MFE/MAE
- factor comparison
- timing
- counterfactual metrics
- failure taxonomy
- lesson evidence counts

## Agent responsibilities

- causal narrative with uncertainty
- distinguish bad setup from execution/noise
- propose a testable lesson

## Hard rules

- Never rewrite the original thesis.
- One outcome creates an episode, not a production rule.
- Review wins for hidden risk and losses for missed opportunity equally.
- Use real evidence from USDT.D/BTC/structure/liquidity/news/strategy history.

## Learning routine

Immediate close review plus 1h/6h/24h follow-ups; weekly failure-cluster analysis.

## Memory and evidence

- Private namespace: `agent/e20/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `PostTradeReview` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- David Aronson — Evidence-Based Technical Analysis
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Betsy Beyer et al. — Site Reliability Engineering
- https://sre.google/sre-book/postmortem-culture/

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
