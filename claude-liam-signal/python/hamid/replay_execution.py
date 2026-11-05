"""Deterministic 15m limit-order replay; no network, state writes or orders.

Uses the existing paper book's 24h fill/hold windows and 1/3, 2/3 trailing
ladder. The current bar cannot raise its own stop. Funding is not modelled.
"""
from math import isfinite
from hamid import fees

BAR_MS = 900_000


def replay(candles, setup, placed_at, fill_hours=24, hold_hours=24, symbol=None):
    entry, sl, tp = (float(setup[k]) for k in ("entry", "sl", "tp1"))
    direction = setup["dir"]
    if direction not in ("LONG", "SHORT") or not all(isfinite(x) and x > 0 for x in (entry, sl, tp)):
        raise ValueError("invalid order geometry")
    sign = 1 if direction == "LONG" else -1
    if sign * (entry - sl) <= 0 or sign * (tp - entry) <= 0:
        raise ValueError("stop/target are on the wrong side")
    risk, dist = abs(entry - sl), abs(tp - entry)
    end_fill = placed_at + fill_hours * 3_600_000
    filled = None
    best, stop = entry, sl
    last = None
    for c in candles:
        if c["t"] < placed_at:
            continue
        if filled is None:
            if c["t"] >= end_fill:
                return {"outcome": "expired", "R": None, "R_net": None, "end": end_fill}
            if not c["l"] <= entry <= c["h"]:
                continue
            filled = c["t"]
        if c["t"] >= filled + hold_hours * 3_600_000:
            break
        progress = sign * (best - entry) / dist
        level = entry + sign * dist / 3 if progress >= 2/3 else entry + sign * entry * .0015 if progress >= 1/3 else None
        if level is not None:
            stop = max(stop, level) if sign == 1 else min(stop, level)
        hit_stop = c["l"] <= stop if sign == 1 else c["h"] >= stop
        hit_target = c["h"] >= tp if sign == 1 else c["l"] <= tp
        last = c
        if hit_stop or hit_target:
            price = stop if hit_stop else tp
            gross = sign * (price - entry) / risk
            # Configured taker/taker + slippage, conservative for a limit order.
            cost = fees.cost_in_r(entry, sl, symbol)
            return dict(outcome=("trail" if stop != sl else "stop") if hit_stop else "target",
                        R=gross, R_net=gross-cost, fee_r=cost, filled=filled,
                        end=c["t"]+BAR_MS, sl_eff=stop)
        best = max(best, c["h"]) if sign == 1 else min(best, c["l"])
    if filled is not None and last and last["t"] + BAR_MS >= filled + hold_hours * 3_600_000:
        gross = sign * (last["c"] - entry) / risk
        cost = fees.cost_in_r(entry, sl, symbol)
        return dict(outcome="timeout", R=gross, R_net=gross-cost, fee_r=cost,
                    filled=filled, end=last["t"]+BAR_MS, sl_eff=stop)
    # End of observed data is right-censoring, not a fictional market close.
    return dict(outcome="censored", R=None, R_net=None, filled=filled,
                end=(last["t"]+BAR_MS if last else placed_at))
