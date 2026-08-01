# Python tooling

## `screener.py` — where to look right now

The engine's full evaluation runs on every closed candle for every symbol, and
most of those symbols have nothing happening. This narrows the field first,
cheaply, so the expensive work lands where a setup is plausible.

```bash
python3 screener.py                      # top 100 by volume, ranked
python3 screener.py --top 200 --show 40  # wider net
python3 screener.py --json --out today.json
```

Nothing to install — standard library only.

## What it scores

Proxies for "a setup could be forming here", weighted by what measurement
showed actually matters:

| | why |
|---|---|
| **bars since the structure break** | The strongest factor found. Expectancy fell monotonically with age: 0–10 bars +0.149R, 40–70 −0.255R, past 120 −0.352R. A break inside 10 candles scores 40; past 20 it scores 8. |
| **ATR relative to price** | A setup needs room between entry and target to be worth the risk. |
| **volume picking up** | Last 6 candles against the previous 54. |
| **range over 60 candles** | Somewhere for a target to sit. |
| **quote volume** | Log-scaled. Enough that a stop is fillable, not so much that it dominates. |

It deliberately is **not** the engine. It decides where to look; the engine
decides what to trade. Keeping them separate means a bug here costs attention,
not money.

## Output

The last line is the one to read: how many symbols broke structure within the
last 10 candles — the band where expectancy was measured positive. On a quiet
day that number is low and there is nothing to hunt.

## If it prints "no host answered"

Binance geo-blocks some regions outright, and every mirror will fail the same
way. A VPN is what fixes it. The script walks all four hosts before giving up,
so this message means the block, not a flaky connection.
