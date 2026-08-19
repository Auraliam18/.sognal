"""بک‌تست شبانهٔ UT Bot روی کندل واقعی — دفتر آزمایش، نه تولید (قانون ۱۲).

هر شب روی برترین ارزها می‌دود، معامله‌ها را **انباشته** می‌کند (اجتماع
یکتا بر (sym, opened) — همان الگوی دفترهای دیگر) و گزارش CI می‌نویسد:

    brain/backtests/utbot-trades.jsonl   دفتر انباشته
    brain/backtests/utbot-latest.json    گزارش امروز + CI + مقایسهٔ فیلتر

سه سؤالی که جواب می‌دهد:
  ۱. کل استراتژی: میانگین R و بازهٔ ۹۵٪ — از صفر رد می‌شود؟
  ۲. فیلتر EMA200+RSI واقعاً کمک می‌کند؟ (با/بی‌فیلتر روی همان کندل‌ها)
  ۳. لانگ و شورت جدا — همان تفکیکی که در ibs درس‌ساز شد.

اجرا:  python3 -m hamid.backtest_utbot --symbols 40 --bars 2000
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import strat_utbot as ut                   # noqa: E402

ROOT = HERE.parent.parent.parent
OUT_DIR = ROOT / "brain" / "backtests"
BOOK = OUT_DIR / "utbot-trades.jsonl"
LATEST = OUT_DIR / "utbot-latest.json"


def boot(vals, n=3000, alpha=0.05):
    if len(vals) < 25:
        return None
    k = len(vals)
    m = sorted(sum(random.choice(vals) for _ in range(k)) / k for _ in range(n))
    lo, hi = m[int(n * alpha / 2)], m[int(n * (1 - alpha / 2))]
    if hi - lo < 1e-9:
        return None                                   # بازهٔ صفرعرض شاهد نیست
    return round(lo, 3), round(hi, 3)


def _load_book():
    if not BOOK.exists():
        return []
    out = []
    for ln in BOOK.read_text().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except Exception:                        # noqa: BLE001
                continue
    return out


def accumulate(new_trades):
    """اجتماع یکتا — هیچ ردیف قدیمی پاک نمی‌شود (قانون «پاک نشود»)."""
    old = _load_book()
    have = {(t.get("sym"), t.get("opened"), t.get("filters")) for t in old}
    added = [t for t in new_trades
             if (t.get("sym"), t.get("opened"), t.get("filters")) not in have]
    if added:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with BOOK.open("a") as f:
            for t in added:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return old + added, len(added)


def describe(trades, label):
    rs = [t["R"] for t in trades]
    if not rs:
        return {"label": label, "n": 0}
    ci = boot(rs)
    return {"label": label, "n": len(rs),
            "win": round(100 * sum(1 for r in rs if r > 0) / len(rs), 1),
            "ev": round(statistics.fmean(rs), 3),
            "ci": list(ci) if ci else None,
            "exits": {k: sum(1 for t in trades if t["outcome"] == k)
                      for k in sorted({t["outcome"] for t in trades})}}


def line(d):
    if not d["n"]:
        return f"  {d['label']:<28} هیچ معامله‌ای"
    ci = f"[{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}]" if d.get("ci") else "— (نمونه کم)"
    mark = ""
    if d.get("ci"):
        mark = ("  ✅ بالای صفر" if d["ci"][0] > 0 else
                "  ⛔ زیر صفر" if d["ci"][1] < 0 else "  — از صفر رد نشد")
    return (f"  {d['label']:<28} n={d['n']:>5} برد {d['win']:>5.1f}٪ "
            f"E={d['ev']:+.3f}R  {ci}{mark}")


def run(symbols=40, bars=2000, tf="15m", fetch=None, quiet=False):
    import sources
    from hamid.trainer import top_symbols

    if fetch is None:
        def fetch(sym):
            return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
                     "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                    for k in sources.klines(sym, tf, bars)]

    syms = top_symbols(symbols)
    t0 = time.time()

    def one(sym):
        try:
            cd = fetch(sym)
            if len(cd) < 400:
                return []
            rows = []
            for flt in (True, False):                # همان کندل، با و بی فیلتر
                for t in ut.walk(cd, use_filters=flt):
                    t["sym"] = sym
                    t["filters"] = int(flt)
                    rows.append(t)
            return rows
        except Exception as e:                       # noqa: BLE001 - یک ارز، کل اجرا نیست
            if not quiet:
                print(f"  {sym}: {type(e).__name__}")
            return []

    fresh = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for rows in pool.map(one, syms):
            fresh += rows
    all_trades, added = accumulate(fresh)
    took = round(time.time() - t0, 1)

    flt = [t for t in all_trades if t.get("filters")]
    raw = [t for t in all_trades if not t.get("filters")]
    rep = {
        "generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "strategy": "utbot", "source": "TradingView ideas — UT Bot Alerts",
        "params": {"key": ut.KEY, "atr": ut.ATR_PERIOD, "tf": tf,
                   "filters": "EMA200 + RSI14"},
        "symbols_run": len(syms), "bars": bars, "added_now": added,
        "with_filters": describe(flt, "با فیلتر EMA200+RSI"),
        "no_filters": describe(raw, "بی‌فیلتر (خام)"),
        "long": describe([t for t in flt if t["dir"] == "LONG"], "لانگ (فیلتردار)"),
        "short": describe([t for t in flt if t["dir"] == "SHORT"], "شورت (فیلتردار)"),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"\nUT Bot — کندل واقعی، {len(syms)} ارز، {took}s، "
              f"{added} معاملهٔ تازه (انباشته {len(all_trades)})")
        print("─" * 78)
        for k in ("with_filters", "no_filters", "long", "short"):
            print(line(rep[k]))
        print("─" * 78)
        print("حکم فقط با CI — تا از صفر رد نشده، این استراتژی فقط دفتر آزمایش است.")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=40)
    ap.add_argument("--bars", type=int, default=2000)
    a = ap.parse_args()
    run(symbols=a.symbols, bars=a.bars)
    return 0


if __name__ == "__main__":
    sys.exit(main())
