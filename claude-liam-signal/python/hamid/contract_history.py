"""Closed trade candles from the exact Bitunix contract; never interpolate gaps."""
import math
import threading
import time
from urllib.parse import urlencode

STEP = {"1m":60000, "5m":300000, "15m":900000, "1h":3600000, "4h":14400000}
CHILD = {"4h":"1h", "1h":"15m", "15m":"5m", "5m":"1m"}
_lock = threading.Lock()
_slot = 0.0


def _read(sym, tf, end, n):
    global _slot
    import sources
    with _lock:
        slot = max(_slot, time.monotonic())
        _slot = slot + .11
    time.sleep(max(0, slot - time.monotonic()))
    q = urlencode(dict(symbol=sym, interval=tf, endTime=end-1, limit=n, type="LAST_PRICE"))
    j = sources._json("https://fapi.bitunix.com/api/v1/futures/market/kline?" + q)
    if str(j.get("code")) != "0" or not isinstance(j.get("data"), list):
        raise ValueError("Bitunix contract unavailable: " + str(j.get("code")))
    return [[int(r["time"]), *(float(r[k]) for k in ("open","high","low","close","baseVol")), int(r["time"])] for r in j["data"]]


def valid(r):
    _, o,h,l,c,v,_ = r
    return all(math.isfinite(x) for x in (o,h,l,c,v)) and v >= 0 and 0 < l <= min(o,c) <= max(o,c) <= h


def closed(sym, tf, n, now=None, read=_read):
    step = STEP[tf]
    end = int(time.time()*1000 if now is None else now)//step*step
    start = end - n*step
    calls = 0
    def window(frame, lo, hi, allow_child):
        nonlocal calls
        dt = STEP[frame]
        rows = {}
        cursor = hi
        while cursor > lo:
            calls += 1
            if calls > 16:
                raise ValueError("contract recovery request budget")
            size = min(200,(cursor-lo)//dt)
            page = read(sym, frame, cursor, size)
            for r in page:
                t = r[0]
                if lo <= t < cursor and t % dt == 0:
                    if t in rows and rows[t] != r:
                        raise ValueError("conflicting contract candles")
                    rows[t] = r
            if any(t not in rows for t in range(cursor-size*dt,cursor,dt)):
                raise ValueError("short or non-contiguous Bitunix history for " + frame)
            cursor -= size*dt
        for t in sorted(rows):
            if valid(rows[t]):
                continue
            if not allow_child or frame not in CHILD:
                raise ValueError("invalid Bitunix trade OHLC")
            bars = window(CHILD[frame], t, t+dt, allow_child-1)
            rows[t] = [t,bars[0][1],max(b[2] for b in bars),min(b[3] for b in bars),
                       bars[-1][4],sum(b[5] for b in bars),t]
        return [rows[t] for t in range(lo,hi,dt)]
    return window(tf,start,end,2)


def analysis_rows(sym, tf, n, provenance=None):
    import sources
    try:
        return sources.klines(sym,tf,n)
    except RuntimeError as spot_error:
        try:
            rows = closed(sym,tf,n)
        except (KeyError,ValueError,TypeError,OSError,OverflowError) as error:
            raise RuntimeError(f"{sym} {tf}: {error}; {spot_error}") from error
        if provenance is not None:
            provenance[f"{sym}:{tf}"] = "Bitunix futures LAST_PRICE"
        return rows
