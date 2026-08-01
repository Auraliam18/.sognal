# لیام کد — ۳۰ جولای ۲۰۲۶

Everything as it stood on this date: the panel, the engine, every measurement
script, the standalone agent, the orchestration workflows, and the full commit
history from the first day.

## What is here

| | |
|---|---|
| `index.html` | The panel, `cycle v14.0`. One file, no build step. |
| `sw.js` | Service worker, cache `hsa-shell-v14.0`. |
| `tests/` | Simulator, harness, cycle runner, parameter search, gate funnel, age split, browser suites. |
| `agent/` | The standalone Node agent. `engine.js` is generated from `index.html`. |
| `n8n/` | Importable orchestration workflows. |
| `workflows/` | The GitHub Actions that carry the compute. |
| `cycles/` | Every paper-trading cycle report and parameter search finding. |
| `reference/` | The last Codex build, kept unmodified. |
| `CLAUDE.md` | The standing instruction: which service carries what. |
| `WORKPLAN.md` | What each room owes and how it is judged. |
| `تاریخچه-کامل.txt` | Every commit from the first day, oldest first. |

## Where the engine stood

Freshness window 10 bars, target floor 1.8R, decisive break 0.35 ATR,
displacement 1.5 ATR — all four measured rather than chosen, the last two earned
by an overnight search that fitted 144 configurations on 200 simulated markets
and judged them on 200 more it never saw.

Last full cycle: 5,964 trades, 44% win, 1.89 average R, +0.255R expectancy with
a 95% interval of [0.219, 0.293].

## What was wrong and got fixed

Recorded because the corrections matter more than the code:

- Entry was taken at the box edge while the signal only existed after price
  closed beyond it — look-ahead. The fill is now that close.
- Targets were the nearest prior swing, paying 0.74R on average. They now have
  to pay at least 1.8R or the setup is skipped.
- The 0–100 quality score did not predict anything; it gates nothing now.
- Expectancy falls monotonically with how long ago the structure broke. The
  window was 70 bars, admitting four buckets of reliably losing trades.
- Paper trading was being run on the simulator. It belongs on the live tape,
  with loose gates, so the learning room has a sample to learn from.

## Restoring from this

Copy `index.html` and `sw.js` over the repository root, bump the cache string in
`sw.js`, and push to both `claude/hamid-signal-agent-smc-dkot7v` and `gh-pages`.
The agent's `engine.js` is regenerated with `node agent/extract-engine.js`.
