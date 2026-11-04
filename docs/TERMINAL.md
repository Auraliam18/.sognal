# LIAM Terminal

Entry point: `/terminal/` on the existing GitHub Pages site. The classic panel remains available at `/aura/`.

The terminal reads a versioned repository snapshot built by `scripts/build_terminal.py`. It makes no LLM calls, never executes orders, and does not change strategy, risk, delivery, learning weights, or trading gates. Public chart candles come from Binance's market-data-only endpoint; this is labeled separately from the configured Bitunix execution venue.

## Data and identity

- All valid closed-paper records are exported, including duplicates, into content-addressed pages. The manifest records exact counts. Malformed lines are counted rather than silently hidden.
- Each book has separate statistics. Practice, first pullback, inducement, vetoed, v2, alarms, and sent scan records do not inflate the main second-pullback book. Missing stage identity goes to `other`. The `sig-*` book is not attributed to a specific named agent without evidence.
- Expired/unfilled/unavailable results do not count toward settled win rate. Returns use R, not hypothetical compounded cash balances. CSV exports preserve every matching record and protect spreadsheet formula cells.
- Timestamps come from each producer, never the site-build time. Missing timestamps remain unknown. The classification producer now emits its actual calculation time.
- Agent cards are evidence bindings to existing deterministic modules. They are not claims of 26 independently running LLMs, profitability, or verified uptime. Source freshness and required fields are evaluated separately.
- The `PanelHealth` schema and tab-to-engine map are published inside the snapshot. Inspect the complete snapshot from the Health view.

## Delivery and cost

The Pages workflow checks out main and the existing gh-pages site separately, validates contracts, builds the full archive on the GitHub runner, and adds `/terminal/` to the deployment artifact. It does not write archive exports back to git or replace the legacy site's runtime files. Existing cron and dispatch triggers remain; frontend pushes also trigger deployment.

The browser shares one snapshot across all eight routes, checks for a new published snapshot every two minutes while visible, and fetches archive pages on demand. Refresh does not trigger a market scan. Requests are bounded by timeouts; route changes abort obsolete chart/archive requests. Old data remains visibly marked when transport fails. No credentials are shipped to the browser.

## Validation

`python -m unittest discover -s scripts -p test_terminal.py -v`

`node --test terminal/lib.test.mjs`

`python scripts/build_terminal.py`

`npm ci && npx playwright install chromium && node terminal/browser.test.mjs`

Browser fixtures exist only in test routes; they are never deployed. CI covers every route, chart rendering, 26 bindings, archive filtering/export, mobile overflow, and initial/cached transport errors. The runtime never substitutes fixtures for missing data.
