---
name: liam-signal-release-gate
description: Audit a candidate before SIGNAL_READY and enforce freshness, complete hard gates, risk approval, unique ID, chart snapshot, dedupe, and immediate Telegram delivery.
when_to_use: Automatically when the task matches this domain; invoke manually for an explicit audit.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  owner: AuraLiam369
  version: 2.1.0
---

# Signal Release Gate

Reject unless all mandatory packets are fresh and `missing_requirements=[]`.
Require USDT.D, BTC context, 4H/1H/15M/5M, structure/SMC/liquidity, strategy version, risk approval, snapshot hash, signal ID, and a new dedupe key.
Release the symbol immediately; never wait for the 30-second sweep or other symbols.
