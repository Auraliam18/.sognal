# Agent — the panel's work, on the laptop

The browser panel stops when its tab does. This runs the same engine as a plain
Node process: it scans, streams every symbol on 5m and 15m, paper-trades what it
signals, learns from every close, trains on history across all cores, and sends
to Telegram. No tab, no window, nothing to keep open.

## Run

```bash
cd claude-liam-signal/agent
export TG_TOKEN="123456:ABC-your-bot-token"
export TG_CHAT="your-numeric-chat-id"
node agent.js
```

Node 20 or newer — it uses the built-in `fetch` and `WebSocket`, so there is
nothing to install.

Leave it running. To keep it alive across reboots and crashes:

```bash
# macOS / Linux
nohup node agent.js >> agent.log 2>&1 &

# or, with pm2 if you have it
pm2 start agent.js --name signal && pm2 save
```

## What it does on its own

- **Scans** the top 100 symbols by volume every 30 minutes and rebuilds the
  watch list from that.
- **Watches** every one of them on 5m and 15m through a single websocket, and
  re-runs the strategy for a symbol the moment one of its candles closes.
- **Paper-trades** every signal to its end — stop, first target with the stop
  moved to entry, second target, or an eight-hour timeout — and learns from the
  result.
- **Trains** daily by replaying four days of real candles across the top 80
  symbols, one worker per core. On four cores this settles several hundred
  positions in seconds and feeds all of them to the model and case memory.
- **Repairs itself**: a dropped stream reconnects, a silent stream is cycled,
  and open positions fall back to REST price polling so they are never left
  unresolved.
- **Reports** every five minutes to Telegram, and sends each signal with entry,
  stop, both targets, R:R, confidence, the order block, the channel, and what
  similar past setups did.

## Settings

Environment variables, all optional except the Telegram pair:

| Variable | Default | Meaning |
|---|---|---|
| `TG_TOKEN`, `TG_CHAT` | — | Bot token from @BotFather, chat id from @userinfobot |
| `UNIVERSE` | 100 | How many symbols to watch |
| `SCAN_MIN` | 30 | Minutes between full sweeps |
| `TRAIN_DAYS` | 4 | Days of history per training pass |
| `TRAIN_TOP` | 80 | Symbols included in training |
| `CORES` | all | Workers used for training |
| `REPORT_MIN` | 5 | Minutes between reports |

## Files

`state.json` holds everything that must survive a restart: learned weights,
case memory, open and closed positions, the Telegram queue, USDT dominance
samples. Deleting it starts the agent from nothing.

`engine.js` is generated from `../../index.html` by `extract-engine.js`, so the
agent and the panel can never drift apart. After changing the panel's engine,
run `node extract-engine.js`.

## Checking it

```bash
node mock-test.js    # whole path against a stubbed exchange
node worker-test.js  # the worker pool itself
```
