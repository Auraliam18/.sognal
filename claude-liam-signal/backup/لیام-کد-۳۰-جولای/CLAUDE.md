# Working agreement

## Standing instruction — do not wait to be asked

On every task, use the available connectors and plugins according to what each
is actually good at. This is not something Hamid should have to repeat.

| | what it carries |
|---|---|
| **GitHub Actions** | All heavy compute. Paper-trading cycles, parameter searches, deploys. Never the laptop. |
| **Notion** | The comparable record. One row per cycle with expectancy, interval, verdict, and the change made. |
| **Google Drive** | Durable archive of reports, so numbers outlive any machine. |
| **Gmail** | Digests as drafts. Never send from Hamid's account without being asked. |
| **Google Calendar** | The cadence, made visible. |
| **Telegram** | Live delivery from the panel: signals, outcomes, room reports. |
| **n8n** | Orchestration between the above, so the pipeline runs without a session open. |
| **Canva** | Only when something genuinely needs to be a graphic. Inventing work for a tool is not using it. |

If a connector's token has expired, say so plainly and carry on with the rest.

## What must not change

The strategy, the rooms, the supervisor, the two-hourly review with **one
controlled change per cycle** graded on the cycle after, and the rule that a
finding is only acted on once its confidence interval clears zero. Connectors
carry the work; they do not decide anything.

## How results are reported

Every number comes from a measurement that can be re-run. `tests/` holds the
simulator, harness, cycle runner, parameter search, gate funnel and age split.
A number without a way to reproduce it does not get reported.

State plainly whether a figure comes from simulated markets or live candles.
The simulator has volatility clustering, fat tails and regime switching, and it
tests whether the engine has an edge against a hard model — not whether it
makes money on the real tape.

## Corrections

When a previous conclusion turns out to be wrong, say so directly and show the
measurement that overturned it. Two have already been corrected this way: a
freshness window widened on the strength of a friendly tape, and a claim that
the second pullback carried no advantage.

## Repository layout

- `index.html` — the panel. One file, no build step.
- `sw.js` — service worker. Bump `CACHE` on every deploy.
- `tests/` — simulator, harness, and every measurement script.
- `claude-liam-signal/` — reference material, work plan, cycle reports.
- `claude-liam-signal/agent/` — the standalone Node agent. `engine.js` is
  generated from `index.html`; rerun `extract-engine.js` after engine changes.
- `claude-liam-signal/n8n/` — importable orchestration workflows.

Deploys go to both `claude/hamid-signal-agent-smc-dkot7v` and `gh-pages`.
