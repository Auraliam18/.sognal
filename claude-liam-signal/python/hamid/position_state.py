"""Immutable paper lifecycle identity; used by both settlement and Git reconciliation."""
import math


def number(value):
    if isinstance(value, bool):
        raise ValueError("boolean price")
    v = float(value)
    if not math.isfinite(v):
        raise ValueError("nonfinite price")
    return v


def geometry(direction, entry, sl, tp1, tp2=None):
    try:
        e, s, t = map(number, (entry, sl, tp1))
        if min(e, s, t) <= 0 or direction not in {"LONG", "SHORT"}:
            return False
        if not (s < e < t if direction == "LONG" else t < e < s):
            return False
        if tp2 is not None and tp2 != 0:
            t2 = number(tp2)
            return t2 > 0 and (t2 >= t if direction == "LONG" else t2 <= t)
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def key(row):
    try:
        why = row.get("why") or {}
        sym, side, stage, opened = row["sym"], row["dir"], why["stage"], row["opened"]
        if not sym or not stage or side not in {"LONG", "SHORT"} or type(opened) is not int or opened <= 0:
            return None
        return (sym, side, stage, opened, number(row["entry"]), number(row["sl"]),
                number(row["tp1"]), number(row["tp2"]) if row.get("tp2") else None)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return None


def reconcile(positions, closed):
    pending = {key(p) for p in positions} - {None}
    done = set()
    for row in closed:
        if row.get("closed") and row.get("outcome"):
            ident = key(row)
            if ident in pending:
                done.add(ident)
    return [p for p in positions if key(p) not in done]


def _prefer(a, b):
    if a == b:
        return a
    if not a or not b:
        return a or b
    # Only the established mutable fields may converge. Fail visibly on any
    # disagreement about decision context, identifiers or other immutable data.
    changes = {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    if changes - {"filled", "late_fill", "sl_eff"}:
        raise ValueError("conflicting decision metadata for one open lifecycle")
    merged = dict(a)
    for k in changes:
        values = [v for v in (a.get(k), b.get(k)) if v is not None]
        if k == "filled":
            merged[k] = min(values)
        elif k == "late_fill":
            merged[k] = bool(merged.get("filled") and merged["filled"] - merged["opened"] > 21600000)
        else:
            merged[k] = (max if a["dir"] == "LONG" else min)(values)
    if "late_fill" in changes or "late_fill" in merged:
        merged["late_fill"] = bool(merged.get("filled") and merged["filled"] - merged["opened"] > 21600000)
    return merged


def merge_open(base, left, right):
    def index(rows):
        out = {}
        for row in rows:
            k = key(row)
            if k is None:
                raise ValueError("unidentifiable open position: manual reconciliation required")
            out[k] = _prefer(out.get(k), row)
        return out
    base, left, right = map(index, (base, left, right))
    result = []
    for k in dict.fromkeys([*left, *right]):
        if k in base and (k not in left or k not in right):
            continue
        a, b = left.get(k), right.get(k)
        result.append(b if a == base.get(k) else a if b == base.get(k) else _prefer(a, b))
    return result
