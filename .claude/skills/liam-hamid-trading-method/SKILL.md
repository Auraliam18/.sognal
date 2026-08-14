---
name: liam-hamid-trading-method
description: Apply Hamid’s exact multi-timeframe crypto trading method, PDF v2 indicator preferences, strategy hierarchy, and output format. Use for any trading logic, signal, chart, or strategy change.
when_to_use: Automatically when the task matches this domain; invoke manually for an explicit audit.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  owner: AuraLiam369
  version: 2.1.0
---

# Hamid Trading Method

Read `.claude/rules/00-hamid-personalization.md` and enforce it as the domain source of truth.

Before accepting a signal path, verify:
1. USDT.D → BTC.D/Macro → BTC.
2. Coin 4H → 1H → 15M → 5M.
3. Trendlines/channels/S/R and role flips.
4. OB/FVG/liquidity and volume.
5. Strategy ID/version and Historical Analog.
6. Risk, snapshot, Signal ID, immediate per-symbol delivery.

Return `missing_requirements` rather than guessing. Never treat an internal CHoCH as a standalone reversal.
