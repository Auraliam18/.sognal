"""بک‌تست شبانهٔ فایل متا (aura_ibs_meta) روی کندل واقعی — دفتر آزمایش.

سؤال دقیقی که جواب می‌دهد (فرضیهٔ حمید، ۲۰ اوت): «نزدیک TP2 تارگت را
بردار و استاپ را تنگ تریل کن» بهتر از خروج کلاسیک روی TP2 هست یا نه؟

هر دو حالت روی **همان کندل‌ها** بازپخش می‌شوند و تفاضل میانگین R با
بوت‌استرپ بلوکی-ارزی سنجیده می‌شود (بلوک = ارز، چون دو حالت روی یک ارز
هم‌بسته‌اند). حکم فقط با CI؛ بازهٔ صفرعرض شاهد نیست.

خروجی: brain/backtests/meta-latest.json
اجرا:   python3 -m hamid.backtest_meta --symbols 40 --bars 2000
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

META = HERE.parent.parent / "meta" / "aura_ibs_meta.py"
_spec = importlib.util.spec_from_file_location("aura_ibs_meta", META)
meta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(meta)

ROOT = HERE.parent.parent.parent
OUT = ROOT / "brain" / "backtests" / "meta-latest.json"


def boot(vals, n=3000, alpha=0.05):
    if len(vals) < 25:
        return None
    k = len(vals)
    m = sorted(sum(random.choice(vals) for _ in range(k)) / k for _ in range(n))
    lo, hi = m[int(n * alpha / 2)], m[int(n * (1 - alpha / 2))]
    return None if hi - lo < 1e-9 else (round(lo, 3), round(hi, 3))


def boot_diff_by_symbol(per_sym, n=3000):
    """بوت‌استرپ بلوکی-ارزی روی تفاضل میانگین دو حالت. per_sym:
    {sym: (rs_trail, rs_classic)} — بازنمونه‌گیری از ارزها، نه معامله‌ها."""
    syms = [s for s, (a, b) in per_sym.items() if a and b]
    if len(syms) < 5:
        return None
    out = []
    for _ in range(n):
        pick = [random.choice(syms) for _ in syms]
        ta = [r for s in pick for r in per_sym[s][0]]
        tb = [r for s in pick for r in per_sym[s][1]]
        if ta and tb:
            out.append(statistics.fmean(ta) - statistics.fmean(tb))
    if not out:
        return None
    out.sort()
    lo, hi = out[int(len(out) * .025)], out[int(len(out) * .975)]
    return None if hi - lo < 1e-9 else (round(lo, 3), round(hi, 3))


def agg(rows):
    rs = [t["R"] for t in rows]
    if not rs:
        return {"n": 0}
    return {"n": len(rs),
            "win": round(100 * sum(1 for r in rs if r > 0) / len(rs), 1),
            "ev": round(statistics.fmean(rs), 3),
            "ci": (lambda c: list(c) if c else None)(boot(rs)),
            "exits": {k: sum(1 for t in rows if t["outcome"] == k)
                      for k in sorted({t["outcome"] for t in rows})}}


def run(symbols=40, bars=2000, tf="15m", fetch=None, quiet=False):
    if fetch is None:
        import sources
        from hamid.trainer import top_symbols
        syms = top_symbols(symbols)

        def fetch(sym):
            return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
                     "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                    for k in sources.klines(sym, tf, bars)]
    else:
        syms = [f"S{i}USDT" for i in range(symbols)]

    t0 = time.time()
    per_sym, all_a, all_b = {}, [], []

    def one(sym):
        try:
            cd = fetch(sym)
            if len(cd) < 300:
                return sym, None
            a = meta.walk(cd, "trail_after_tp2")
            b = meta.walk(cd, "tp2")
            return sym, (a, b)
        except Exception:                            # noqa: BLE001 - یک ارز، کل اجرا نه
            return sym, None

    with ThreadPoolExecutor(max_workers=10) as pool:
        for sym, res in pool.map(one, syms):
            if not res:
                continue
            a, b = res
            per_sym[sym] = ([t["R"] for t in a], [t["R"] for t in b])
            all_a += a
            all_b += b

    diff_ci = boot_diff_by_symbol(per_sym)
    ev_a = statistics.fmean([t["R"] for t in all_a]) if all_a else None
    ev_b = statistics.fmean([t["R"] for t in all_b]) if all_b else None
    rep = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "strategy": meta.VERSION, "source": "کندل واقعی",
           "symbols_ok": len(per_sym), "bars": bars, "tf": tf,
           "took_s": round(time.time() - t0, 1),
           "trail_after_tp2": agg(all_a), "classic_tp2": agg(all_b),
           "diff_trail_minus_classic": {
               "mean": round(ev_a - ev_b, 3) if ev_a is not None and ev_b is not None else None,
               "ci_symbol_blocked": list(diff_ci) if diff_ci else None,
               "verdict": ("تریل بهتر است ✅" if diff_ci and diff_ci[0] > 0 else
                           "کلاسیک بهتر است ⛔" if diff_ci and diff_ci[1] < 0 else
                           "از صفر رد نشد — قانون عوض نمی‌شود")}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"متا IBS — {len(per_sym)} ارز، {rep['took_s']}s")
        for k in ("trail_after_tp2", "classic_tp2"):
            d = rep[k]
            if d["n"]:
                print(f"  {k:<18} n={d['n']:>4} برد {d['win']}٪ E={d['ev']:+.3f}R CI={d['ci']}")
        print(f"  تفاضل (تریل−کلاسیک): {rep['diff_trail_minus_classic']}")
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
