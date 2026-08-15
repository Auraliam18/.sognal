"""دسته‌بندی از پیپرمود — دستور حمید، ۱۴ اوت.

«دسته‌بندی کن خودت که کدوم استراتژی توی چه تایم‌فریمی بیشتر جواب می‌ده،
 یا اوردر بلاکا توی چه ارزهایی با چه تایم‌فریم‌هایی بهتره.»

سه جدول از همان دفتر پیپر — بدون هیچ فچ تازه‌ای، فقط شمارش روی چیزی که
واقعاً اتفاق افتاده:

  ۱. استراتژی × تایم‌فریم
  ۲. کلاس اردر بلاک × تایم‌فریم   (تازه/کهنه، هانت‌خورده/نخورده، واکنش‌ها)
  ۳. اردر بلاک × ارز × تایم‌فریم   (کدام ارز با OB بهتر جواب می‌دهد)

## قانونی که این فایل را از یک جدول ساده جدا می‌کند

CLAUDE.md: «یک یافته فقط وقتی عمل می‌شود که فاصلهٔ اطمینانش از صفر رد کرده
باشد.» پس هر خانه سه چیز دارد: عدد، فاصلهٔ اطمینان بوت‌استرپ، و حکم. حکمِ
«بهتر است» فقط وقتی صادر می‌شود که CI پایین از صفر بالاتر باشد؛ وگرنه
«هنوز تصمیم‌گرفتنی نیست» — که خودش یک جواب صادقانه است، نه شکست.

و چون چندین خانه هم‌زمان آزمون می‌شوند، آلفا بونفرونی‌وار بین خانه‌های
واجدشرایط تقسیم می‌شود. بدون آن، با ۲۰ خانه تقریباً همیشه یکی «معنادار»
درمی‌آید — همان تلهٔ p-hacking که کل این مخزن از آن پرهیز می‌کند.

عدد این جدول‌ها از **بازار شبیه‌سازی‌نشده** می‌آید (کندل واقعی، بازپخش
تاریخی)، ولی معاملهٔ کاغذی است نه اجرای واقعی: بدون لغزش واقعی و بدون
عمق دفتر سفارش. پس «کدام بهتر است» می‌دهد، نه «چقدر درمی‌آورد».
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "classify.json"

MIN_N = 25              # کمتر از این، خانه فقط گزارش می‌شود بدون حکم
BOOT = 2000
ALPHA = 0.05

FA_SETUP = {"ob_pullback": "پولبک به اردر بلاک",
            "bos_continuation": "ادامهٔ BOS"}
FA_STAGE = {"practice": "میز تمرین", "first": "پولبک اول",
            "second": "پولبک دوم", "inducement": "ایندوسمنت/ویک",
            "alarm": "آلارم", "v2": "نسخهٔ ۲", "vetoed": "وتوشده",
            "sig-ibs": "سیگنال IBS", "sig-alarm": "سیگنال آلارم"}


def load(path=None):
    """ردیف‌های بسته‌شدهٔ دارای R — تنها چیزی که قابل شمارش است."""
    p = Path(path or CLOSED)
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
        except Exception:                             # noqa: BLE001 - ردیف خراب رد
            continue
        if t.get("R") is None or t.get("outcome") == "expired":
            continue
        rows.append(t)
    return rows


def _tf(t):
    """تایم‌فریم ردیف. ردیف‌های قدیمیِ بی‌برچسب UNKNOWN می‌شوند نه ۱۵د.

    قانون ۱ پروژه: دادهٔ UNKNOWN در فیلد اجباری حدس زده نمی‌شود. برچسب‌زدن
    ۲۲۰۰ معاملهٔ قدیمی به «۱۵د» جدول را شلوغ‌تر و **غلط** می‌کرد."""
    return t.get("tf") or (t.get("why") or {}).get("tf") or "UNKNOWN"


def _strategy(t):
    w = t.get("why") or {}
    return w.get("setup") or w.get("stage") or "UNKNOWN"


def ob_class(t):
    """کلاس اردر بلاک این معامله، یا None اگر اصلاً OB نداشته.

    سه محورِ خود حمید: تازگی، هانت‌خوردگی، و تعداد واکنش معتبر."""
    w = t.get("why") or {}
    if w.get("ob_align") is None and w.get("ob_fresh") is None:
        return None
    fresh = "تازه" if w.get("ob_fresh") else "کهنه"
    hunts = w.get("ob_hunts") or 0
    hunted = "هانت‌خورده" if hunts else "دست‌نخورده"
    rc = w.get("reactions") or 0
    react = "۳+ واکنش" if rc >= 3 else ("۲ واکنش" if rc == 2 else "۰-۱ واکنش")
    return f"{fresh} · {hunted} · {react}"


def _boot_ci(vals, alpha, rng):
    """فاصلهٔ اطمینان بوت‌استرپِ میانگین. نمونهٔ کوچک → فاصلهٔ پهن، که درست است."""
    n = len(vals)
    if n < 2:
        return None, None
    means = []
    for _ in range(BOOT):
        means.append(sum(rng.choice(vals) for _ in range(n)) / n)
    means.sort()
    lo = means[int((alpha / 2) * BOOT)]
    hi = means[min(BOOT - 1, int((1 - alpha / 2) * BOOT))]
    return round(lo, 3), round(hi, 3)


def needed_n(rs):
    """چند معامله لازم است تا CI این خانه از صفر رد کند؟

    تقریب نرمال: n ≈ (۱.۹۶ × انحراف‌معیار ÷ میانگین)². دقیق نیست — CI واقعی
    بوت‌استرپ است — ولی برای «چقدر مانده» کافی است و همان چیزی است که
    مشخص می‌کند وقت را کجا بگذاریم.

    میانگین ≤ ۰ یعنی هیچ مقدار نمونه‌ای این خانه را مثبت نمی‌کند؛ None
    برمی‌گردد و صادقانه «با نمونهٔ بیشتر مثبت نمی‌شود» گفته می‌شود."""
    n = len(rs)
    if n < 5:
        return None
    m = sum(rs) / n
    if m <= 0:
        return None
    var = sum((x - m) ** 2 for x in rs) / n
    sd = var ** 0.5
    if sd == 0:
        return n
    return int((1.96 * sd / m) ** 2) + 1


def cell(rows, alpha=ALPHA, rng=None):
    """آمار یک خانه + حکم. حکم فقط وقتی که CI صفر را رد کرده باشد."""
    rng = rng or random.Random(20260814)
    rs = [t["R"] for t in rows if t.get("R") is not None]
    n = len(rs)
    wins = sum(1 for r in rs if r > 0)
    mean = round(sum(rs) / n, 3) if n else None
    out = {"n": n, "wins": wins, "stops": n - wins,
           "win_pct": round(wins / n * 100, 1) if n else None,
           "mean_r": mean, "sum_r": round(sum(rs), 2) if n else 0}
    # «چقدر مانده تا حکم» — دستور حمید: «دیتاهای پیپر سریع به نتیجه برسند.»
    # بدون این عدد، سرعت‌بخشیدن حدس است؛ با آن معلوم است کدام دفتر ۱۰ معامله
    # کم دارد و کدام ۴۰۰۰ (یعنی عملاً هرگز).
    need = needed_n(rs)
    out["need_n"] = need
    out["short_by"] = (max(0, need - n) if need else None)
    if need is None and n >= 5 and mean is not None and mean <= 0:
        out["eta"] = "با نمونهٔ بیشتر مثبت نمی‌شود — میانگینش زیر صفر است"
    elif need:
        out["eta"] = (f"~{need} معامله لازم است؛ {max(0, need - n)} کم دارد"
                      if need > n else "نمونه کافی است")
    if n < MIN_N:
        out["verdict"] = "نمونه کم"
        out["note"] = f"فقط {n} معامله — کمتر از کف {MIN_N}؛ حکمی صادر نمی‌شود"
        return out
    lo, hi = _boot_ci(rs, alpha, rng)
    out["ci"] = [lo, hi]
    if lo is not None and lo > 0:
        out["verdict"] = "مثبت"
        out["note"] = f"میانگین {mean}R و کف فاصلهٔ اطمینان {lo}R — از صفر رد کرد"
    elif hi is not None and hi < 0:
        out["verdict"] = "منفی"
        out["note"] = f"میانگین {mean}R و سقف فاصلهٔ اطمینان {hi}R — زیر صفر است"
    else:
        out["verdict"] = "نامعلوم"
        out["note"] = (f"میانگین {mean}R ولی فاصلهٔ اطمینان [{lo}, {hi}] "
                       "صفر را در بر می‌گیرد — هنوز تصمیم‌گرفتنی نیست")
    return out


def _table(rows, keyfn, min_n=MIN_N, seed=20260814):
    """گروه‌بندی + آلفای بونفرونی بین خانه‌های واجدشرایط.

    آلفا **بعد از** شمارش خانه‌های به‌قدر کافی بزرگ تقسیم می‌شود؛ تقسیم بر
    کل خانه‌ها (که اغلبشان ۳ معامله دارند) بی‌دلیل همه را خفه می‌کرد."""
    groups = {}
    for t in rows:
        k = keyfn(t)
        if k is None:
            continue
        groups.setdefault(k, []).append(t)
    tested = [k for k, v in groups.items() if len(v) >= min_n]
    alpha = ALPHA / max(1, len(tested))
    rng = random.Random(seed)
    out = {}
    for k, v in groups.items():
        out[k] = cell(v, alpha=alpha, rng=rng)
    return {"cells": out, "tested": len(tested),
            "alpha": round(alpha, 5),
            "alpha_note": (f"آلفا {ALPHA} بین {len(tested)} خانهٔ واجدشرایط "
                           f"تقسیم شد (بونفرونی) → {round(alpha, 5)}"
                           if tested else "خانهٔ واجدشرایطی نبود")}


def strategy_by_tf(rows):
    """جدول ۱ — کدام استراتژی در کدام تایم‌فریم."""
    return _table(rows, lambda t: f"{_strategy(t)} @ {_tf(t)}")


def ob_by_tf(rows):
    """جدول ۲ — کدام کلاس اردر بلاک در کدام تایم‌فریم."""
    def k(t):
        c = ob_class(t)
        return f"{c} @ {_tf(t)}" if c else None
    return _table(rows, k)


def ob_by_symbol(rows, min_n=MIN_N):
    """جدول ۳ — اردر بلاک روی کدام ارز و تایم‌فریم بهتر است."""
    def k(t):
        c = ob_class(t)
        return f"{t.get('sym')} @ {_tf(t)}" if c else None
    return _table(rows, k, min_n=min_n)


def best(table, kind="مثبت", top=5):
    """خانه‌های حکم‌دار، مرتب بر میانگین — همان چیزی که به پنل می‌رود."""
    got = [{"key": k, **v} for k, v in table["cells"].items()
           if v.get("verdict") == kind]
    got.sort(key=lambda x: -(x["mean_r"] or 0), reverse=(kind == "منفی"))
    return got[:top]


def closest(table, top=6):
    """خانه‌های بی‌حکم، مرتب بر «چقدر کم دارد» — نقشهٔ راهِ رسیدن به نتیجه."""
    got = [{"key": k, **v} for k, v in table["cells"].items()
           if v.get("verdict") not in ("مثبت", "منفی")
           and v.get("short_by") is not None and v["short_by"] > 0]
    got.sort(key=lambda x: x["short_by"])
    return [{"key": g["key"], "n": g["n"], "mean_r": g["mean_r"],
             "need_n": g["need_n"], "short_by": g["short_by"]}
            for g in got[:top]]


def build(rows=None):
    rows = load() if rows is None else rows
    s_tf = strategy_by_tf(rows)
    o_tf = ob_by_tf(rows)
    o_sym = ob_by_symbol(rows)
    tfs = sorted({_tf(t) for t in rows})
    return {
        "n_trades": len(rows),
        "timeframes": tfs,
        "strategy_by_tf": s_tf,
        "ob_by_tf": o_tf,
        "ob_by_symbol": o_sym,
        "headline": {
            "strategy_wins": best(s_tf, "مثبت"),
            "strategy_loses": best(s_tf, "منفی"),
            "ob_wins": best(o_tf, "مثبت"),
            "ob_loses": best(o_tf, "منفی"),
            "ob_symbol_wins": best(o_sym, "مثبت"),
        },
        # نزدیک‌ترین خانه‌ها به حکم — این فهرست می‌گوید وقتِ بازپخش کجا
        # بیشترین بازده را دارد. خانه‌ای که ۱۰ معامله کم دارد ارزش یک اجرا
        # را دارد؛ خانه‌ای که ۴۰۰۰ تا کم دارد، نه.
        "closest_to_verdict": closest(s_tf),
        "source": "دفتر پیپر (کندل واقعی، بازپخش تاریخی) — نه اجرای واقعی؛ "
                  "بدون لغزش و عمق دفتر سفارش. «کدام بهتر است» می‌دهد، "
                  "نه «چقدر درمی‌آورد».",
        "rule": (f"حکم فقط با کف نمونهٔ {MIN_N} و فاصلهٔ اطمینان بوت‌استرپی "
                 "که صفر را رد کرده باشد، با آلفای بونفرونی."),
    }


def fa_lines(j, limit=6):
    """چند خط فارسیِ خواندنی برای گزارش دوساعته و تلگرام."""
    L = []
    h = j.get("headline") or {}
    for lbl, key in (("✅ بهترین", "strategy_wins"), ("⛔️ بدترین", "strategy_loses")):
        for c in (h.get(key) or [])[:2]:
            L.append(f"{lbl} استراتژی×تایم: {c['key']} — {c['n']} معامله، "
                     f"برد {c['win_pct']}٪، {c['mean_r']}R "
                     f"(فاصلهٔ اطمینان {c['ci'][0]}..{c['ci'][1]})")
    for c in (h.get("ob_wins") or [])[:2]:
        L.append(f"✅ اردر بلاک: {c['key']} — {c['n']} معامله، {c['mean_r']}R")
    for c in (h.get("ob_symbol_wins") or [])[:2]:
        L.append(f"✅ OB روی ارز: {c['key']} — {c['n']} معامله، {c['mean_r']}R")
    for c in (j.get("closest_to_verdict") or [])[:2]:
        L.append(f"⏳ نزدیک‌ترین به حکم: {c['key']} — {c['n']} دارد، "
                 f"~{c['need_n']} لازم است ({c['short_by']} کم دارد)")
    if not L:
        L.append("هیچ خانه‌ای هنوز فاصلهٔ اطمینانش از صفر رد نکرده — "
                 "دسته‌بندی ساخته شد ولی حکمی ندارد. این جواب است، نه شکست.")
    return L[:limit]


def main():
    j = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"دسته‌بندی از {j['n_trades']} معاملهٔ بسته‌شده · "
          f"تایم‌فریم‌ها: {'، '.join(j['timeframes'])}")
    print(f"  استراتژی×تایم: {j['strategy_by_tf']['alpha_note']}")
    print(f"  OB×تایم: {j['ob_by_tf']['alpha_note']}")
    for ln in fa_lines(j, limit=10):
        print("  " + ln)
    print(f"→ {OUT}")
    return j


if __name__ == "__main__":
    main()
