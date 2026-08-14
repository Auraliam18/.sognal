---
name: liam-research-governance
description: Run controlled, source-ranked research and convert only validated findings into versioned experiments and memory. Use for books, papers, new ideas, API changes, or repeated trading errors.
when_to_use: Automatically when the task matches this domain; invoke manually for an explicit audit.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  owner: AuraLiam369
  version: 2.1.0
---

# Controlled Research

Use `config/source_policy.yaml` and `config/research_schedule.yaml`.

Workflow: QUESTION → primary sources → evidence table → hypothesis → test plan → backtest/walk-forward → paper/shadow → Memory Curator.

Never browse randomly, read all GitHub, or promote an unverified idea. Record provenance, date, claim, confidence, sample size, regime, and validation status.
