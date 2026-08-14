---
name: liam-e06-btc-analysis
description: Implement, audit, test, or research E06 BTC Analysis Engine / BTC Agent for the LIAM crypto system. Use when work touches btc analysis or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E06.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E06
  owner: AuraLiam369
  version: 2.1.0
---

# E06 — BTC Analysis Engine / BTC Agent

## Mission

Produce the full BTC context using 4H/1H/15M/5M structure, S/R, trendlines/channels, OB/FVG, indicators, Fibonacci, liquidity, and Pullback Plus.

## Trigger events

- `BTC_CANDLE_CLOSE`
- `BTC_STRUCTURE_CHANGED`
- `ALT_SIGNAL_CANDIDATE`
- `BTC_LIQUIDITY_EVENT`

## Required inputs

- BTC OHLCV
- USDT.D/BTC.D/macro packets
- CoinGlass derivatives/liquidity
- indicators

## Deterministic Python responsibilities

- all deterministic TA/SMC features
- liquidity distances
- Fibonacci levels
- scenario state machine

## Agent responsibilities

- interpret conflicting scenarios
- select likely liquidity path with evidence
- compare historical BTC analogs

## Hard rules

- BTC context is mandatory for every alt signal.
- RSI/MACD/MFI are secondary evidence, not sole triggers.
- Internal 15M CHoCH during a pullback is not automatically a reversal.
- Do not signal against validated 4H/1H trend without a versioned counter-trend strategy.

## Learning routine

Daily BTC regime review; immediate post-event analysis after liquidation cascade or unusual divergence.

## Memory and evidence

- Private namespace: `agent/e06/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `BTCContextPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- https://www.bitunix.com/api-docs/futures/websocket/prepare/WebSocket.html
- https://docs.coinglass.com/
- https://docs.coinglass.com/reference/liquidation-aggregate-heatmap
- John J. Murphy — Technical Analysis of the Financial Markets
- Al Brooks — Trading Price Action series
- J. Welles Wilder Jr. — New Concepts in Technical Trading Systems

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
