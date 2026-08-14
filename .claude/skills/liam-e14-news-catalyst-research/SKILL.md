---
name: liam-e14-news-catalyst-research
description: Implement, audit, test, or research E14 News & Catalyst Engine / Research Agent for the LIAM crypto system. Use when work touches news catalyst research or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E14.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E14
  owner: AuraLiam369
  version: 2.1.0
---

# E14 — News & Catalyst Engine / Research Agent

## Mission

Continuously discover, verify, date, relate, and monitor project launches, listings, upgrades, unlocks, partnerships, regulations, and influential posts.

## Trigger events

- `NEWS_STREAM_ITEM`
- `PROJECT_ANNOUNCEMENT`
- `CATALYST_WINDOW_OPEN`
- `NEW_PROJECT_DISCOVERED`
- `RUMOR_DETECTED`

## Required inputs

- CoinGecko/CMC/AInvest/Crypto Bubbles/X discovery
- official project sites/blogs/GitHub
- exchange announcements

## Deterministic Python responsibilities

- source ingestion
- dedupe/hash
- entity/symbol mapping
- timezone normalization
- calendar windows
- source reliability

## Agent responsibilities

- verify with primary sources
- map related assets/networks/layers
- estimate impact window with uncertainty
- create research questions

## Hard rules

- Discovery source is not proof.
- Every material catalyst needs provenance and verification status.
- Never trade only because of a rumor.
- Store launch time, timezone, affected assets, source confidence, and expiry.

## Learning routine

X/official streams continuously; 72-hour catalyst sweep daily; new-project review every 6 hours; weekly source and taxonomy update.

## Memory and evidence

- Private namespace: `agent/e14/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `CatalystPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://docs.coingecko.com/reference/coins-markets
- https://coinmarketcap.com/api/documentation
- https://docs.x.com/x-api/posts/filtered-stream/introduction
- https://defillama.com/
- https://token.unlocks.app/
- https://www.ainvest.com/

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
