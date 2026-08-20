"""کارنامهٔ رادار پامپ — انجینی که ۱۰ روز بی‌نمره دوید (دستور حمید، ۲۰ اوت).

## چرا این فایل لازم شد

رادار پامپ بزرگ‌ترین انجین مخزن است (۱۵۸۲ خط) و پرمصرف‌ترین چرخه —
هر ~۳ دقیقه، شبانه‌روز. ولی کارنامه‌اش این بود:

  • `brain/pump-picks.jsonl` از ۱۰ اوت **صفر بایت** ماند
  • دفتر معاملهٔ `sig-pump-radar`: **۳ ردیف در کل تاریخ**، هر سه ۹ روز پیش

علتِ اولی پیدا شد: فایل نه در backup ورک‌فلو بود نه در `reapply`، پس
`git reset --hard origin/main` که پیش از هر تلاشِ پوش می‌دود، هر بار
پاکش می‌کرد — ثانیه‌ها بعد از نوشتنش. (همان کلاس خطای ۱۷ اوت، عضو سوم.)

پس هیچ‌کس نمی‌داند رادار خوب کار می‌کند یا بد. این فایل همان را می‌سنجد.

## دو کار

**`recover()`** — دفتر را از تاریخچهٔ گیت بازمی‌سازد. پیشنهادها گم نشده‌اند:
هر اجرای رادار `signals/pump-radar.json` را کامیت کرده و آرایهٔ
`recommendation` داخلش بوده. ۲۴۹ پیشنهاد یکتا از ۹ اوت تا امروز
بازیابی‌پذیر است — یعنی لازم نیست ۱۰ روز دیگر منتظر بمانیم.

**`score()`** — هر پیشنهاد را روی **کندل واقعی** می‌سنجد:

    ۱. پر شد؟ آیا قیمت تا انقضا به `entry` رسید؟ (نرسید = NO_FILL،
       معامله نیست — همان قرارداد دفترهای دیگر)
    ۲. بعد از پر شدن: اول به هدف پامپ (+۵٪، همان ادعای خودِ رادار)
       رسید یا اول به استاپ خورد؟ کندلی که هر دو را زده = **استاپ**
       (بدخیم‌ترین فرض، مثل backtest.simulate)
    ۳. R نسبت به ریسکِ لحظهٔ ورود

خروجی: `brain/backtests/pump-score.json` با precision، میانگین R و
بازهٔ ۹۵٪. حکم فقط از CI — بازهٔ صفرعرض شاهد نیست و رد می‌شود.

## معیار حکم (پیشنهاد به حمید، نه اجرای خودسر — قانون ۱۲)

- CI بالای صفر  → رادار ارزش چرخهٔ ۳دقیقه‌ای را دارد
- CI زیر صفر    → از مسیر سیگنال کنار می‌رود
- CI دربرگیرندهٔ صفر با n<۱۰۰ → نمونه کم، ادامه با همین کادنس
- CI دربرگیرندهٔ صفر با n≥۱۰۰ → اثری ندارد؛ کادنس پایین بیاید

هیچ‌کدام خودکار اجرا نمی‌شود. این فایل فقط عدد می‌دهد.

اجرا:
    python3 -m hamid.pump_score --recover     # بازسازی دفتر از تاریخ گیت
    python3 -m hamid.pump_score               # نمره‌دهی روی کندل واقعی
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
PICKS = ROOT / "brain" / "pump-picks.jsonl"
OUT = ROOT / "brain" / "backtests" / "pump-score.json"
REPORT = "signals/pump-radar.json"

PUMP_TARGET_PCT = 5.0        # ادعای خودِ رادار: «≥۵٪ رشد تا ۲۴س بعد»
WINDOW_MS = 24 * 3600 * 1000  # پنجرهٔ پیش‌فرض وقتی pick انقضا ندارد
MIN_N = 25                    # زیر این تعداد، بوت‌استرپ حرفی برای گفتن ندارد


# ── دفتر ───────────────────────────────────────────────────────────────────

def read_picks(path=None):
    p = Path(path) if path else PICKS
    out = []
    if not p.exists():
        return out
    for ln in p.read_text().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except Exception:                        # noqa: BLE001
                continue
    return out


def write_picks(rows, path=None):
    p = Path(path) if path else PICKS
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r.get("t") or 0)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return len(rows)


def _key(r):
    return (r.get("sym"), round(float(r.get("entry") or 0), 12))


def recover(repo=None, ref="origin/main", quiet=False, _shas=None, _show=None):
    """بازسازی دفتر پیشنهادها از تاریخچهٔ گزارش‌های رادار.

    یکتاسازی بر (نماد، قیمت ورود) — همان پیشنهاد در ده‌ها گزارشِ پشت‌سرهم
    تکرار می‌شود و شمردنِ چندبارهٔ یک پیشنهاد، نمونه را تقلبی بزرگ می‌کند.
    قدیمی‌ترین رخداد نگه داشته می‌شود چون همان لحظهٔ صدور واقعی است.
    """
    repo = Path(repo) if repo else ROOT

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True).stdout

    shas = _shas if _shas is not None else git(
        "log", "--format=%H", ref, "--", REPORT).split()
    show = _show or (lambda sha: git("show", f"{sha}:{REPORT}"))

    found = {}
    for sha in shas:
        try:
            j = json.loads(show(sha))
        except Exception:                            # noqa: BLE001
            continue
        gen = j.get("generated")
        for p in (j.get("recommendation") or []):
            if not p.get("symbol") or not p.get("entry"):
                continue
            row = {"t": gen, "sym": p["symbol"], "entry": p["entry"],
                   "price": p.get("price"), "score": p.get("score"),
                   "sl": p.get("sl"), "dist_pct": p.get("dist_pct"),
                   "expires_at": p.get("expires_at"), "src": "recovered"}
            # لحظهٔ صدور = **قدیمی‌ترین** گزارشی که این پیشنهاد در آن دیده شد.
            # صریح کمینه می‌گیریم، نه با تکیه بر ترتیب `git log`: اگر روزی
            # ترتیب یا مسیر فراخوانی عوض شود، پنجرهٔ سنجش بی‌صدا جابه‌جا
            # می‌شود و آن‌وقت نمرهٔ رادار از پنجرهٔ اشتباه درمی‌آید.
            old = found.get(_key(row))
            if old is None or (row["t"] or 0) < (old["t"] or 0):
                found[_key(row)] = row

    have = {_key(r): r for r in read_picks()}
    added = {k: v for k, v in found.items() if k not in have}
    have.update(added)
    n = write_picks(list(have.values()))
    if not quiet:
        print(f"بازیابی از {len(shas)} گزارش: {len(added)} پیشنهاد تازه · "
              f"دفتر اکنون {n} ردیف")
    return len(added), n


# ── نمره‌دهی ───────────────────────────────────────────────────────────────

def judge(pick, candles):
    """سرنوشت یک پیشنهاد روی کندل واقعی. None یعنی داده کافی نیست.

    قانون ۱: دادهٔ ناقص = هیچ، نه حدس. کندلی که هم هدف هم استاپ را زده،
    استاپ حساب می‌شود — ترتیبِ داخل کندل معلوم نیست و خوش‌بینی ممنوع.
    """
    entry = float(pick["entry"])
    if entry <= 0:
        return None
    t0 = pick.get("t") or 0
    t_end = pick.get("expires_at") or (t0 + WINDOW_MS)
    win = [c for c in candles if t0 <= c["t"] <= t_end]
    if len(win) < 2:
        return None

    sl = pick.get("sl")
    sl = float(sl) if sl else entry * (1 - 0.011)     # پیش‌فرض رادار ~۱.۱٪
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    target = entry * (1 + PUMP_TARGET_PCT / 100)

    fill = None
    for i, c in enumerate(win):
        if c["l"] <= entry <= c["h"]:
            fill = i
            break
    if fill is None:
        return {"outcome": "no_fill", "R": None, "filled": False}

    for c in win[fill:]:
        hit_sl = c["l"] <= sl
        hit_tp = c["h"] >= target
        if hit_sl:                                   # هم‌زمان هم = استاپ
            return {"outcome": "stop", "R": -1.0, "filled": True}
        if hit_tp:
            return {"outcome": "pumped", "R": round((target - entry) / risk, 3),
                    "filled": True}
    out = win[-1]["c"]
    return {"outcome": "timeout", "R": round((out - entry) / risk, 3),
            "filled": True}


def boot(vals, n=4000, alpha=0.05):
    if len(vals) < MIN_N:
        return None
    k = len(vals)
    m = sorted(sum(random.choice(vals) for _ in range(k)) / k for _ in range(n))
    lo, hi = m[int(n * alpha / 2)], m[int(n * (1 - alpha / 2))]
    if hi - lo < 1e-9:
        return None                                  # بازهٔ صفرعرض شاهد نیست
    return round(lo, 3), round(hi, 3)


def verdict(n, ci):
    if ci is None:
        return "نمونه کم — نتیجه‌گیری ممنوع"
    if ci[0] > 0:
        return "بالای صفر — ارزش چرخهٔ فعلی را دارد"
    if ci[1] < 0:
        return "زیر صفر — از مسیر سیگنال کنار برود"
    return ("از صفر رد نشد و نمونه بزرگ است — کادنس پایین بیاید"
            if n >= 100 else "از صفر رد نشد — نمونه هنوز کم است، ادامه")


def run(fetch=None, quiet=False, picks=None):
    rows = picks if picks is not None else read_picks()
    if not rows:
        rep = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
               "n_picks": 0, "note": "دفتر پیشنهادها خالی است — اول --recover"}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        if not quiet:
            print("دفتر پیشنهادها خالی است.")
        return rep

    if fetch is None:
        import sources

        def fetch(sym):
            return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
                     "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                    for k in sources.klines(sym, "15m", 1500)]

    by_sym = {}
    for r in rows:
        by_sym.setdefault(r["sym"], []).append(r)

    judged, errs = [], 0

    def one(sym):
        try:
            return sym, fetch(sym)
        except Exception:                            # noqa: BLE001 - یک ارز، کل اجرا نه
            return sym, None

    with ThreadPoolExecutor(max_workers=10) as pool:
        for sym, cd in pool.map(one, list(by_sym)):
            if not cd:
                errs += 1
                continue
            for p in by_sym[sym]:
                v = judge(p, cd)
                if v:
                    judged.append({**p, **v})

    filled = [j for j in judged if j["filled"]]
    rs = [j["R"] for j in filled if j["R"] is not None]
    pumped = [j for j in filled if j["outcome"] == "pumped"]
    ci = boot(rs)
    rep = {
        "generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source": "کندل واقعی — نه شبیه‌ساز",
        "n_picks": len(rows), "n_judged": len(judged), "symbols_missing": errs,
        "fill_rate_pct": round(100 * len(filled) / len(judged), 1) if judged else None,
        "n_filled": len(filled),
        "precision_pct": round(100 * len(pumped) / len(filled), 1) if filled else None,
        "pump_target_pct": PUMP_TARGET_PCT,
        "ev_r": round(statistics.fmean(rs), 3) if rs else None,
        "ci": list(ci) if ci else None,
        "verdict": verdict(len(rs), ci),
        "outcomes": {k: sum(1 for j in judged if j["outcome"] == k)
                     for k in sorted({j["outcome"] for j in judged})},
        "by_score": {},
    }
    for s in sorted({j.get("score") for j in filled if j.get("score") is not None}):
        g = [j["R"] for j in filled if j.get("score") == s and j["R"] is not None]
        if len(g) >= MIN_N:
            c = boot(g)
            rep["by_score"][str(s)] = {"n": len(g),
                                       "ev": round(statistics.fmean(g), 3),
                                       "ci": list(c) if c else None}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"\nکارنامهٔ رادار پامپ — کندل واقعی، {rep['n_picks']} پیشنهاد")
        print("─" * 70)
        print(f"  نمره‌خورده {rep['n_judged']} · پر شد {rep['n_filled']} "
              f"({rep['fill_rate_pct']}٪)")
        print(f"  دقت (رسیدن به +{PUMP_TARGET_PCT}٪): {rep['precision_pct']}٪")
        print(f"  میانگین {rep['ev_r']}R · بازهٔ ۹۵٪ "
              f"{rep['ci'] or '— (نمونه کم)'}")
        print(f"  {rep['outcomes']}")
        print("─" * 70)
        print(f"  حکم: {rep['verdict']}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recover", action="store_true",
                    help="بازسازی دفتر از تاریخچهٔ گیت، بدون نمره‌دهی")
    a = ap.parse_args()
    if a.recover:
        recover()
        return 0
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
