# Work plan — what each room owes, and how it is judged

Written for the rooms, not about them. Each has one job, a standard it is held
to, and a named failure the supervisor watches for. The supervisor checks every
second and files a report every five minutes.

## Scan room
Sweep the top 100 symbols by volume every 30 minutes across 5m, 15m and 1h.
Its output is not signals — it is the universe the other rooms work on, and the
market regime that colours every decision.
- **Standard**: a completed sweep no older than 1.6x the interval.
- **Fails as**: falling behind schedule. Repair is to run one immediately.

## Watch room
Hold one websocket carrying a kline stream per symbol per timeframe, and on
every closed candle re-run the strategy for that symbol alone. This is where
setups are actually found; the scan room is too slow to catch them.
- **Standard**: stream connected, a message inside two minutes.
- **Fails as**: a silent socket. Repair is to drop it and reconnect.

## Radar room
Carry the second-by-second price for every marked entry zone and every open
paper position. When price enters a zone, wake the full analysis.
- **Standard**: prices flowing, whether by websocket or the REST fallback.
- **Fails as**: no ticks for 45 seconds. Repair engages REST polling and keeps
  going — the fallback exists because a dead socket must never stop the work.

## Paper trading room
Every signal becomes a position and is followed to its end: stop, first target
with the stop moved to entry, second target, or timeout. No position is ever
left unresolved.
- **Standard**: open positions evaluated within a minute.
- **Fails as**: positions drifting unchecked. Repair polls prices directly.

## Learning room
This is the room that decides whether tomorrow is better than today. Three
duties:

1. **Learn from every close.** One gradient step per settled trade, on the same
   feature vector the decision used. A result that arrives without teaching
   anything is a defect, and the supervisor treats an unlearned closed trade as
   a fault to repair.
2. **Answer from experience before each signal.** Retrieve the nearest past
   situations by that same feature vector and report their hit rate and net R.
   A setup that looked like this before and lost is worth knowing about, and it
   rides along with the signal to Telegram.
3. **Train on history, not just on what happens to arrive.** Once a day, replay
   four days of real candles across the top 80 symbols on 5m and 15m, take
   every setup the live engine would have taken, settle it against what
   actually followed, and feed all of it to duties 1 and 2. One pass yields
   several hundred outcomes, which is the difference between a model with an
   opinion and a model with a memory.

- **Standard**: no settled trade left unlearned; the case memory grows.
- **Fails as**: results piling up untaught. Repair replays them.

Weights start at zero deliberately. Hand-picked values were measured against
held-out data and scored AUC 0.44 — worse than no model. Anything the model
believes, it has to have earned from a real outcome.

## Intelligence room
Read what publishes numbers rather than opinions: open interest, account
long/short, taker flow, Fear & Greed, and USDT dominance. Money moving into
Tether is money leaving alts, so a rising USDT.D vetoes alt longs and a sharply
falling one vetoes alt shorts.
- **Standard**: a reading no older than 15 minutes.
- **Fails as**: stale data. Repair forces a refresh.

## Supervisor
Check all of the above every second. Repair on the spot, log what broke and
what fixed it, and file a five-minute report to the feed and to Telegram.

## How the plan changes with the market
- **Trending**: the watch room carries the load; setups complete fast and the
  first pullback is usually the whole opportunity.
- **Ranging**: expect the learning room to veto more often; a range makes prior
  swings close, targets cheap, and R:R poor — which is exactly what the R floor
  is there to catch.
- **Shock**: intelligence leads. Lopsided positioning with rising open interest
  marks where the stops are, and the panel should be reading that before it
  reads structure.

## Standing rule
Every number reported to Hamid comes from a measurement that can be re-run.
`tests/evaluate.js` and `tests/diagnose.js` exist so a claim about the engine
can be checked rather than argued about. A number without a way to reproduce it
does not get reported.
