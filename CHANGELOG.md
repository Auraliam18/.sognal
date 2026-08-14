# Changelog

## 2.1.0 — 2026-08-13

- Added 26 Claude Skills, 26 read-only specialist subagents, and 26 runtime skill contracts.
- Added Hamid personalization and PDF version-2 indicator/trading rules.
- Replaced five-minute batch semantics with continuous event-driven feed + 30-second coverage heartbeat.
- Added immediate per-symbol signal release, chart/Telegram reply contract, and signal IDs.
- Added opposing-OB rotation/pullback calibration skill.
- Expanded lead-lag pump chain to full historical event study up to 24 hours.
- Added post-trade multi-horizon reviews and controlled memory promotion.
- Added source hierarchy, update routines, hooks, guards, schemas, validator, and tests.
- Kept LIVE_EXECUTION disabled.
