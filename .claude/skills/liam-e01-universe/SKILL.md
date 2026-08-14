---
name: liam-e01-universe
description: Implement, audit, test, or research E01 Universe Engine / Universe Agent for the LIAM crypto system. Use when work touches universe or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E01.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E01
  owner: AuraLiam369
  version: 2.1.0
---

# E01 — Universe Engine / Universe Agent

## Mission

Maintain a survivorship-safe Top-200 global crypto universe and a separate Bitunix-tradable subset for actionable signals.

## Trigger events

- `DAILY_UNIVERSE_REFRESH`
- `LISTING`
- `DELISTING`
- `SYMBOL_MAPPING_CHANGED`
- `LIQUIDITY_CHANGED`

## Required inputs

- CoinGecko/CMC rankings
- Bitunix trading pairs
- volume/liquidity filters
- stablecoin/wrapped exclusions

## Deterministic Python responsibilities

- stable ID mapping
- ranking
- liquidity filters
- snapshot versioning
- symbol/contract resolution

## Agent responsibilities

- research ambiguous renames/migrations
- classify sector/network/layer/use case
- verify new projects

## Hard rules

- Top-200 global is for research and lead-lag; only supported target-exchange symbols may become live signals.
- Keep historical universe snapshots.
- Never map assets only by ticker symbol.

## Learning routine

Daily refresh plus event-triggered listing/migration review; weekly metadata reconciliation.

## Memory and evidence

- Private namespace: `agent/e01/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `UniverseSnapshot` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://docs.coingecko.com/reference/coins-markets
- https://coinmarketcap.com/api/documentation
- https://www.bitunix.com/api-docs/futures/market/get_trading_pairs.html
- https://coinmarketcap.com/api/documentation/pro-api-reference/cryptocurrency

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
