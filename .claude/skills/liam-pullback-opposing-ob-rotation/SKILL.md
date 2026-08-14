---
name: liam-pullback-opposing-ob-rotation
description: Detect false pullbacks and rotation between opposing order blocks, estimate time-to-break empirically, and require sweep/displacement/acceptance before the main-move signal.
when_to_use: Automatically when the task matches this domain; invoke manually for an explicit audit.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  owner: AuraLiam369
  version: 2.1.0
---

# Opposing OB Rotation

Use `docs/PULLBACK_BETWEEN_OPPOSING_OB_FA.md`.

Classify: ROTATION, LIQUIDITY_BUILD, FAKE_PULLBACK, ACCEPTANCE, DISPLACEMENT_READY, BREAKOUT_CONFIRMED, INVALIDATED.
Do not use a fixed pullback duration. Learn distributions by symbol/timeframe/regime. Until the four user chart images are uploaded and labeled, keep image-specific thresholds UNCALIBRATED and create Golden Fixtures only after review.
