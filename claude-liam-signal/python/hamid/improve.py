"""از نتیجه‌ها تصمیم بگیر — دستور حمید، ۱۵ اوت.

«باید از بررسی نتیجه‌ها و پیپرتریدینگ تصمیم بگیریم که چیکار کنیم … ایجنت‌ها
با بررسی نتایج و تاریخچهٔ ارزها و نحوهٔ واکنش‌های آن‌ها در گذشته تصمیم
می‌گیرند که چه شرایطی برای بهبود عملکرد انجین داشته باشند.»

## جای خالی‌ای که این پر می‌کند

از قبل دو چیز داشتیم و هر دو در سطح **کل بازار** بودند:

  · `paper.reasons()` — ۲۷ شرط را با بوت‌استرپ و بونفرونی می‌سنجد و
    می‌گوید کدام شرط برندگان را از بازندگان جدا می‌کند.
  · `paper.experience_index()` — کارنامهٔ (ارز، جهت) که فقط حق **وتو** دارد.

هیچ‌کدام نمی‌گفت «این ارز **چطور واکنش نشان می‌دهد**». حمید دقیقاً همین را
خواست: تاریخچهٔ هر ارز و نحوهٔ واکنشش، و از آن، پیشنهادِ شرط.

## چهار واکنشی که اندازه گرفته می‌شود

از MFE/MAE و شمارهٔ کندلِ آن‌ها — چیزهایی که میز تمرین روی هر معامله ثبت
می‌کند — چهار رفتار قابل تشخیص است، و هر کدام یک تصمیم متفاوت می‌سازد:

  ۱. **استاپ تنگ** — معامله اول به سود رفت، بعد استاپ خورد. یعنی جهت درست
     بود و فاصله غلط. تصمیم: استاپ بازتر یا ورود عمیق‌تر.
  ۲. **خروج زودهنگام** — به ۱R+ رسید و آخرش زیر آن بسته شد. جهت و فاصله
     درست، نگه‌داشتن غلط. تصمیم: تریل دیرتر.
  ۳. **چرخش** — نه رفت نه خورد، ۸+ کندل معطل ماند. همان
     NO_TRADE_ROTATION که حمید در سندش توصیف کرده: قیمت بین دو OB مخالف
     می‌چرخد و پولبک فریبنده می‌سازد. تصمیم: این ارز را در این حالت نگیر.
  ۴. **سالم** — سریع رفت و رسید.

## چرا این فایل تصمیم را اجرا نمی‌کند

قانون ۱۲ سند غیرقابل‌مذاکره: «هیچ تغییر Strategy مستقیم وارد Production
نمی‌شود.» و دستور صریح حمید (۱۵ اوت): «تو اجازه نداری سر خود قانون
بنویسی؛ اینجا من دستور می‌دهم.»

پس خروجی این ماژول **پیشنهاد** است، نه تغییر: هر پیشنهاد با نمونه، فاصلهٔ
اطمینان، و وضعیت اعتبارسنجی می‌آید و منتظر دستور می‌ماند. هیچ آستانه‌ای
را خودش عوض نمی‌کند.

## و چرا بیشترشان «هنوز نه» می‌گیرند

هر ارز × هر رفتار یعنی ده‌ها آزمون هم‌زمان. بدون تصحیح، چند تای‌شان صرفاً
از بخت مثبت می‌شوند. آلفا با بونفرونی بین پیشنهادهای واجدشرایط تقسیم
می‌شود — همان کاری که ماشین شبانه با شرط‌ها می‌کند.

اجرا:
    python3 -m hamid.improve
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "brain" / "improve" / "proposals.json"
PANEL = ROOT / "signals" / "improve.json"

MIN_N = 20                  # زیر این، هیچ ادعایی دربارهٔ یک ارز نمی‌شود
ALPHA = 0.05
NOT_TRADES = ("expired",)


def _rows():
    out = []
    try:
        for line in CLOSED.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except Exception:                        # noqa: BLE001 - خط خراب رد
                continue
            if t.get("R") is None or t.get("outcome") in NOT_TRADES:
                continue
            out.append(t)
    except FileNotFoundError:
        pass
    return out


def _boot_ci(vals, alpha, rng, n=2000):
    """همان بوت‌استرپ درصدیِ classify — تا دو جای پروژه دو عدد ندهند."""
    if len(vals) < 8:
        return None
    means = []
    k = len(vals)
    for _ in range(n):
        means.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    means.sort()
    lo = means[int(alpha / 2 * n)]
    hi = means[min(n - 1, int((1 - alpha / 2) * n))]
    # فاصلهٔ صفرعرض یعنی همهٔ مقادیر یکی‌اند — بوت‌استرپ روی مقدار ثابت
    # همان مقدار را برمی‌گرداند و عددی می‌سازد که **شبیه شواهد است ولی
    # نیست**. اولین اجرای واقعی همین را داد: CI=[0.15, 0.15] چون ۱۱۲ از
    # ۱۱۹ معامله دقیقاً روی +۰.۱۵R بسته شده بودند — یعنی نردبان تریل
    # داشت کارِ خودش را می‌کرد، نه اینکه چیزی خراب باشد.
    if hi - lo < 1e-9:
        return None
    return round(lo, 3), round(hi, 3)


def behaviour(t):
    """این معامله کدام رفتار را نشان داد؟ None یعنی داده‌اش را نداریم."""
    w = t.get("why") or {}
    mfe, bar = w.get("mfe"), w.get("mfe_bar")
    if mfe is None:
        return None
    r = t.get("R") or 0
    if t.get("outcome") == "stop" and mfe >= 0.5:
        return "stop_tight"          # جهت درست بود، فاصله غلط
    if mfe >= 1.0 and r < 0.5:
        return "exit_early"          # رسید و پس داد
    if mfe < 0.5 and (bar or 0) >= 8:
        return "rotation"            # معطل ماند — چرخش بین دو OB
    return "clean"


def profile(rows, min_n=MIN_N):
    """کارنامهٔ رفتاری هر ارز — «این ارز چطور واکنش نشان می‌دهد»."""
    by = {}
    for t in rows:
        b = behaviour(t)
        if b is None:
            continue
        by.setdefault(t["sym"], []).append((b, t))
    out = {}
    for sym, items in by.items():
        if len(items) < min_n:
            continue
        n = len(items)
        cnt = {k: 0 for k in ("stop_tight", "exit_early", "rotation", "clean")}
        for b, _ in items:
            cnt[b] += 1
        rs = [t.get("R") or 0 for _, t in items]
        bars = [(t.get("why") or {}).get("mfe_bar") for _, t in items
                if (t.get("why") or {}).get("mfe_bar") is not None
                and (t.get("R") or 0) > 0]
        out[sym] = {
            "n": n,
            "mean_r": round(sum(rs) / n, 3),
            "win_pct": round(100 * sum(1 for r in rs if r > 0) / n, 1),
            "stop_tight_pct": round(100 * cnt["stop_tight"] / n, 1),
            "exit_early_pct": round(100 * cnt["exit_early"] / n, 1),
            "rotation_pct": round(100 * cnt["rotation"] / n, 1),
            "clean_pct": round(100 * cnt["clean"] / n, 1),
            "median_bars_to_move": (round(statistics.median(bars), 1)
                                    if bars else None),
        }
    return out


# هر رفتار، چه تصمیمی پیشنهاد می‌کند و از چه سهمی به بالا نگران‌کننده است.
# این آستانه‌ها **حکم** نیستند؛ فقط تعیین می‌کنند چه چیزی ارزش آزمودن دارد.
# حکم را فاصلهٔ اطمینان می‌دهد، پایین‌تر.
# `metric` مهم است: برای رفتارهایی که نتیجه‌شان را خودِ قانون تریل تعیین
# می‌کند، سنجیدن R بی‌معناست چون R ثابت است. آن‌جا «پس‌دادن» سنجیده می‌شود.
RULES = [
    ("stop_tight", 30.0, "r", "test",
     "استاپ برای این ارز تنگ است — معامله اول به سود رفت بعد استاپ خورد",
     "استاپ بازتر یا ورود عمیق‌تر روی همین ارز"),
    ("rotation", 35.0, "r", "test",
     "معطل می‌ماند — نشانهٔ چرخش بین دو اردر بلاک مخالف",
     "NO_TRADE_ROTATION برای این ارز در این حالت"),
    # این یکی عمداً «آزمون فرضیه» نیست، «مشاهده» است.
    #
    # پس‌دادن در این دسته همیشه مثبت است (تعریفش همین است)، پس «فاصلهٔ
    # اطمینانش از صفر رد کرد» هیچ چیزی ثابت نمی‌کند. اینکه تریلِ دیرتر
    # بهتر بود یا نه، فقط با **بازپخش دوبارهٔ همان کندل‌ها با نردبان
    # دیگر** معلوم می‌شود — یعنی یک بک‌تست، نه استنتاج از این اعداد.
    ("exit_early", 25.0, "giveback", "observe",
     "به ۱R+ رسید و آخرش نزدیک سربه‌سر بسته شد — اندازهٔ پس‌دادن قابل توجه است",
     "آزمایش: همین کندل‌ها را با نردبان تریلِ دیرتر بازپخش کن و مقایسه کن"),
]


def propose(rows=None, min_n=MIN_N, alpha=ALPHA, seed=20260815):
    rows = _rows() if rows is None else rows
    prof = profile(rows, min_n)
    rng = random.Random(seed)

    # کدام (ارز، رفتار) اصلاً واجد شرط آزمون است؟ آلفا فقط بین همین‌ها
    # تقسیم می‌شود — تقسیم بین همهٔ ترکیب‌های ممکن، آلفا را بی‌جهت خرد
    # می‌کند و هیچ‌وقت هیچ حکمی نمی‌آید.
    cands = []
    for sym, p in prof.items():
        for key, thresh, metric, kind, claim, action in RULES:
            if p[f"{key}_pct"] >= thresh:
                cands.append((sym, key, metric, kind, claim, action))
    k = max(1, len(cands))
    adj = alpha / k

    def _val(t, metric):
        if metric == "giveback":
            w = t.get("why") or {}
            return (w.get("mfe") or 0) - (t.get("R") or 0)
        return t.get("R") or 0

    props = []
    for sym, key, metric, kind, claim, action in cands:
        with_b, without_b = [], []
        for t in rows:
            if t["sym"] != sym:
                continue
            b = behaviour(t)
            if b is None:
                continue
            (with_b if b == key else without_b).append(_val(t, metric))
        if len(with_b) < 8:
            continue
        ci = _boot_ci(with_b, adj, rng)
        mean_w = round(sum(with_b) / len(with_b), 3)
        mean_o = (round(sum(without_b) / len(without_b), 3)
                  if without_b else None)
        # حکم فقط وقتی که فاصلهٔ اطمینانِ **تصحیح‌شده** کلاً زیر صفر باشد:
        # یعنی این رفتار روی این ارز واقعاً پول می‌سوزاند، نه اینکه فقط
        # میانگینش بد افتاده.
        # حکم فقط برای رفتارهای آزمون‌پذیر، و فقط وقتی فاصلهٔ اطمینانِ
        # تصحیح‌شده کلاً زیر صفر باشد. رفتارِ «مشاهده‌ای» هرگز حکم نمی‌گیرد
        # — پیشنهادش یک آزمایش است، نه یک تغییر.
        decided = bool(kind == "test" and ci and ci[1] < 0)
        props.append({
            "symbol": sym,
            "behaviour": key,
            "claim": claim,
            "proposed_action": action,
            "n_with": len(with_b),
            "share_pct": prof[sym][f"{key}_pct"],
            "mean_r_with": mean_w,
            "mean_r_without": mean_o,
            "ci": list(ci) if ci else None,
            "alpha_adjusted": round(adj, 5),
            "metric": metric,
            "kind": kind,
            "validation_status": ("BACKTESTED" if decided
                                  else "OBSERVED" if kind == "observe"
                                  else "UNVERIFIED"),
            "decided": decided,
            "note": ("فاصلهٔ اطمینان زیر صفر — شواهد کافی است، منتظر دستور حمید"
                     if decided else
                     "مشاهده است نه حکم؛ جواب فقط با بازپخش مقایسه‌ای می‌آید"
                     if kind == "observe" else
                     "فاصلهٔ اطمینان بی‌معنا یا صفر را در بر می‌گیرد — هنوز حکم نیست"),
        })
    props.sort(key=lambda x: (not x["decided"], x["mean_r_with"]))
    return {
        "generated": int(__import__("time").time() * 1000),
        "n_trades": len(rows),
        "symbols_profiled": len(prof),
        "alpha": alpha,
        "alpha_adjusted": round(adj, 5),
        "candidates": len(cands),
        "profiles": prof,
        "proposals": props,
        "decided": [p for p in props if p["decided"]],
        "rule": ("پیشنهاد است نه تغییر. قانون ۱۲: هیچ تغییر استراتژی مستقیم "
                 "وارد تولید نمی‌شود. اجرا فقط با دستور صریح حمید."),
    }


def main():
    j = propose()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    PANEL.parent.mkdir(parents=True, exist_ok=True)
    PANEL.write_text(json.dumps({k: j[k] for k in
                                 ("generated", "n_trades", "symbols_profiled",
                                  "alpha_adjusted", "proposals", "decided",
                                  "rule")},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"پروفایل رفتاری {j['symbols_profiled']} ارز از {j['n_trades']} معامله")
    print(f"  کاندید بررسی: {j['candidates']} · آلفای بونفرونی {j['alpha_adjusted']}")
    if not j["proposals"]:
        print("  هیچ ارزی رفتار نگران‌کنندهٔ تکرارشونده نشان نداد — پیشنهادی نیست")
    for p in j["proposals"][:8]:
        mark = "✅" if p["decided"] else "⏳"
        print(f"  {mark} {p['symbol']:12s} {p['behaviour']:11s} "
              f"{p['share_pct']:5}% · n={p['n_with']:3d} · "
              f"{p['mean_r_with']:+.3f}R · CI={p['ci']}")
        print(f"      → {p['proposed_action']}")
    if j["decided"]:
        print(f"\n{len(j['decided'])} پیشنهاد شواهدش کامل است — منتظر دستور حمید.")
    print(f"→ {OUT}")
    return j


if __name__ == "__main__":
    main()
