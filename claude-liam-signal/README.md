# claude-liam-signal

My working folder. Reference material, measurement results, and notes that
outlive a single session.

## reference/

`codex-final-v4.html` — the last Codex panel, copied byte-for-byte from
`Auraliam18/Liam-Vercel` (commit "Refactor snapshot version and state
management", 2026-07-02). Its version string is `cycle v4 · اسکلپ+رادار`.
`codex-final-v4.engine.js` is the same file's main script, extracted for
reading. Nothing in it was modified.

Where the other copies live, all identical to one of these two hashes:
`Liam-Vercel/README.md` = `.github/workflows/deno.yml` (146,138 B, the newest),
`Liam-Vercel/Api/State.js` = `Liam-Vercel/1` (133,679 B),
`.sognal/Cluade signal.index.html.txt` (107,439 B, `cycle v3`).
`Auraliam18/.codex` is an empty repository.

## What the Codex version had that this panel did not

It has no supervisor and no rooms — 105 functions, none of them a watchdog or
heartbeat. What it does have, and what was worth taking:

- **USDT dominance**, done properly: rate-limited sampling, samples persisted
  across sessions, a regression slope in percent-per-hour rather than a naive
  last-minus-first, five direction states, and graceful degradation that keeps
  using samples up to 30 minutes old when the feed is unreachable. Ported into
  the engine and wired to the decision layer: a rising USDT.D fights alt longs,
  a sharply falling one fights alt shorts, and BTC and the commodity-style
  tickers are exempt.
- `btcConflicts` and `fresh5mChochAgainst` — veto rules reading BTC's own
  15m setup and a fresh 5m structure break against the trade.

## Measurements

Kept in `../tests/`. `evaluate.js` runs the strategy over simulated markets;
`worker.js` shards it across cores. Numbers reported to date, and what they
mean, are in the commit messages rather than duplicated here, so they cannot
drift out of sync with the code that produced them.
