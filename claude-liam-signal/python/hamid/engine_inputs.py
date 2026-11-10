"""Paper-only risk decisions and independent public derivatives evidence."""
import math
import time
from . import sizing

PRIMARY = {"second", "signal", "hamid"}


def positive(x):
    return type(x) in (int,float) and math.isfinite(x) and x > 0


def portfolio(rows, equity, cycle_at, *, available=True):
    positions = [r for r in rows if (r.get("why") or {}).get("stage") in PRIMARY]
    unknown = [r.get("sym") for r in positions if not positive(r.get("notional_usd"))]
    cap = equity*sizing._cfg()["max_total_exposure_pct"]/100 if positive(equity) else None
    exposure = None if unknown or not available else round(sum(r["notional_usd"] for r in positions),2)
    return {"cycle_at":cycle_at, "observed_at":int(time.time()*1000), "book":"hamid",
            "approved":cap is not None and exposure is not None and cap-exposure >= sizing._cfg()["min_notional_usd"],
            "open_exposure_usd":exposure,"limit_usd":cap,"equity_usd":equity,
            "unsized_symbols":unknown,"open_positions":len(positions),
            "reason":"ledger_unavailable" if not available else "legacy_position_size_unknown" if unknown else
                     "invalid_equity" if cap is None else "no_capacity" if cap-exposure < sizing._cfg()["min_notional_usd"] else "capacity_available"}


def liquidations(get, now=None):
    end = int(time.time() if now is None else now)
    # Use a bounded time range, not an unqualified/cached latest page.
    url = f"https://api.gateio.ws/api/v4/futures/usdt/liq_orders?from={end-3600}&to={end}&limit=100"
    records = get(url)
    if not isinstance(records,list):
        raise ValueError("invalid liquidation response")
    events = []
    for row in records:
        try:
            t,px,qty = int(row["time"]),float(row["fill_price"]),float(row["order_size"])
            sym = row["contract"]
            if (not isinstance(sym,str) or not sym.endswith("_USDT") or not sym[:-5]
                or not end-3600 <= t <= end or not positive(px) or not positive(abs(qty))):
                continue
            events.append({"symbol":sym,"at":t*1000,"fill_price":px,"order_contracts":qty})
        except (KeyError,TypeError,ValueError,OverflowError):
            continue
    return {"source":"Gate futures/usdt/liq_orders","events":events,"observed_at":end*1000,
            "at":max((e["at"] for e in events),default=None)}
