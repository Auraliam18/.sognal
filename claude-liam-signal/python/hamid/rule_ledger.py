"""دفتر پایداری قانون‌ها — دانش انباشته می‌شود، نه هر روز از نو ساخته.

دستور حمید (۱۶ اوت): «هر سه را باز کن.»

## مشکلی که این حل می‌کند

اندازه‌گیری ۱۶ اوت روی تاریخچهٔ گیت، هشت روز پیاپی:

    روز      معاملهٔ بک‌تست   قانونِ حکم‌دار
    ۰۹ اوت        ۳۷۰۹              ۷
    ۱۰ اوت        ۳۷۴۰              ۵
    ۱۱ اوت        ۳۷۵۷              ۲
    ۱۲ اوت        ۳۷۴۵              ۱
    ۱۳ اوت        ۳۷۲۰              ۳
    ۱۴ اوت        ۳۷۲۷              ۱
    ۱۵ اوت        ۳۷۵۱              ۳
    ۱۶ اوت        ۳۷۳۷              ۴

نه رشد، نوسان. علتش هم روشن بود: پنجرهٔ بک‌تست **چرخان و ثابت** است —
هر روز همان ۷۰ ارز و ۳۰ روز از نو سنجیده می‌شود. پس دانش انباشته نمی‌شد؛
هر صبح از صفر ساخته می‌شد و شب فراموش می‌شد.

## ایدهٔ این فایل

هر بار که بک‌تست اجرا می‌شود، حکمِ آن روز **ثبت** می‌شود. بعد سؤال عوض
می‌شود از:

    «آیا امروز فاصلهٔ اطمینانش از صفر رد کرد؟»        ← شکننده

به:

    «در چند روزِ مستقل، با همان علامت، از صفر رد کرد؟»  ← انباشته

قانونی که هفت روز از هشت روز مثبت بوده، هفت اندازه‌گیریِ تقریباً مستقل را
گذرانده. قانونی که یک روز ظاهر شد و رفت، همان چیزی است که تصحیح بونفرونی
قرار بود جلویش را بگیرد — و این‌جا خودش را لو می‌دهد.

نتیجهٔ همان اندازه‌گیری: از ۲۳ قانون، فقط **دو** تا در ۷ روز از ۸ روز
پایدار ماندند (`داخل اردر بلاک` مثبت، `شورت همسو با بیت‌کوین` برای smc
منفی). بقیه یکی‌دو روز آمدند و رفتند.

## آستانه

`MIN_DAYS` و `WINDOW` پارامترند، نه قانون نازل‌شده. پیش‌فرض: در ۱۰ روز
اخیر، دست‌کم ۵ روز با همان علامت و **هیچ روزی با علامت مخالف**. اگر حمید
عدد دیگری بخواهد، همین‌جا عوض می‌شود.

اجرا:  python3 -m hamid.rule_ledger
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
BACKTEST = ROOT / "brain" / "backtests" / "latest.json"
HISTORY = ROOT / "brain" / "learning" / "rule-history.jsonl"
STABLE = ROOT / "brain" / "learning" / "stable-rules.json"

WINDOW = 10          # چند روز اخیر نگاه شود
MIN_DAYS = 5         # دست‌کم چند روز با همان علامت
DECIDED = ("مثبت", "منفی")


def _read_history():
    out = []
    try:
        for line in HISTORY.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:                        # noqa: BLE001 - خط خراب رد
                continue
    except FileNotFoundError:
        pass
    return out


def record(bt=None, day=None):
    """حکم‌های امروز را به دفتر اضافه کن. تکراری ثبت نمی‌شود.

    کلید یکتا (روز، استراتژی، شرط) است، پس اجرای چندبارهٔ ورک‌فلو در یک
    روز دفتر را متورم نمی‌کند — و متورم‌شدن این‌جا یعنی «پایداری» دروغی
    بزرگ می‌شود، که دقیقاً همان چیزی است که می‌خواهیم جلویش را بگیریم.
    """
    if bt is None:
        try:
            bt = json.loads(BACKTEST.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            return []
    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    have = {(r["day"], r["strategy"], r["condition"]) for r in _read_history()}
    new = []
    for strat, rs in (bt.get("reasons") or {}).items():
        for r in rs:
            v = r.get("verdict")
            if v not in DECIDED:
                continue                             # فقط حکم‌دارها ثبت می‌شوند
            key = (day, strat, r.get("condition"))
            if key in have:
                continue
            new.append({"day": day, "strategy": strat,
                        "condition": r.get("condition"), "verdict": v,
                        "n": r.get("n"), "ev": r.get("ev"),
                        "delta": r.get("delta"), "ci": r.get("ci")})
    if new:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as f:
            for row in new:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return new


def stable(window=WINDOW, min_days=MIN_DAYS, hist=None):
    """قانون‌هایی که در چند روزِ مستقل، با علامت ثابت، حکم گرفته‌اند."""
    hist = _read_history() if hist is None else hist
    if not hist:
        return {"rules": [], "days_seen": 0, "window": window,
                "min_days": min_days}
    days = sorted({r["day"] for r in hist})[-window:]
    keep = [r for r in hist if r["day"] in days]
    by = {}
    for r in keep:
        by.setdefault((r["strategy"], r["condition"]), []).append(r)
    out = []
    for (strat, cond), rs in by.items():
        pos = {r["day"] for r in rs if r["verdict"] == "مثبت"}
        neg = {r["day"] for r in rs if r["verdict"] == "منفی"}
        # علامت متناقض در همین پنجره = ناپایدار، هر چقدر هم تکرار شده باشد.
        if pos and neg:
            continue
        sign = "مثبت" if pos else "منفی"
        n_days = len(pos or neg)
        if n_days < min_days:
            continue
        deltas = [r["delta"] for r in rs if r.get("delta") is not None]
        out.append({
            "strategy": strat, "condition": cond, "verdict": sign,
            "days_confirmed": n_days, "days_in_window": len(days),
            "mean_delta": (round(sum(deltas) / len(deltas), 3)
                           if deltas else None),
            "last_n": rs[-1].get("n"), "last_ci": rs[-1].get("ci"),
        })
    out.sort(key=lambda x: (-x["days_confirmed"], x["condition"]))
    return {"rules": out, "days_seen": len(days), "window": window,
            "min_days": min_days,
            "rule": ("پایدار یعنی در چند اندازه‌گیریِ مستقل با همان علامت "
                     "تکرار شده — نه اینکه یک روز شانسی از صفر رد کرده باشد.")}


def backfill_from_git(days_back=14):
    """دفتر را از تاریخچهٔ گیت پر کن — دانشی که قبلاً اندازه گرفته شد ولی
    هیچ‌جا نماند. بدون این، پایداری از امروز صفر شروع می‌شود در حالی که
    هشت روز اندازه‌گیری واقعی روی main موجود است."""
    import subprocess
    revs = subprocess.run(
        ["git", "log", "--format=%H %cI", f"--since={days_back} days ago",
         "origin/main"], capture_output=True, text=True, cwd=ROOT).stdout.split("\n")
    seen_day = {}
    for line in revs:
        if not line.strip():
            continue
        h, iso = line.split()
        seen_day.setdefault(iso[:10], h)
    added = 0
    for day in sorted(seen_day):
        r = subprocess.run(["git", "show",
                            f"{seen_day[day]}:brain/backtests/latest.json"],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            continue
        try:
            bt = json.loads(r.stdout)
        except Exception:                            # noqa: BLE001
            continue
        added += len(record(bt=bt, day=day))
    return added


def main():
    added = backfill_from_git()
    if added:
        print(f"از تاریخچهٔ گیت پر شد: {added} حکم تاریخی ثبت شد")
    new = record()
    print(f"حکم تازهٔ امروز: {len(new)}")
    j = stable()
    STABLE.parent.mkdir(parents=True, exist_ok=True)
    STABLE.write_text(json.dumps(j, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"\nپنجره: {j['days_seen']} روز · شرط پایداری: ≥{j['min_days']} روز "
          "با علامت ثابت")
    if not j["rules"]:
        print("  هیچ قانونی هنوز پایدار نشده — دانشی برای عمل نیست، و همین جواب است.")
    for r in j["rules"]:
        mark = "✅" if r["verdict"] == "مثبت" else "⛔"
        print(f"  {mark} [{r['strategy']}] {r['condition']} — "
              f"{r['days_confirmed']}/{r['days_in_window']} روز · "
              f"دلتای میانگین {r['mean_delta']:+}")
    print(f"→ {STABLE}")
    return j


if __name__ == "__main__":
    main()
