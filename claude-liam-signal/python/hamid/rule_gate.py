"""دروازهٔ قانون‌های پایدار — گلوگاه ارسال (تغییر کنترل‌شدهٔ چرخهٔ ۲۰ اوت).

تا امروز قانون‌های تأییدشدهٔ بک‌تست فقط **وزن نرم** بودند (scan.apply_learned_rules
امتیاز را جابه‌جا می‌کرد). این دروازه پلهٔ بعدی است و فقط برای قانون‌هایی
باز می‌شود که سخت‌ترین آزمون را پس داده‌اند: دفتر پایداری
(brain/learning/stable-rules.json) — یعنی در چند اندازه‌گیری مستقلِ روزانه
با همان علامت تکرار شده‌اند، نه یک روز شانسی.

قانون اجرا:
- قانون «منفی» پایدار + آخرین CI کاملاً زیر صفر + شرطش روی همین سیگنال
  برقرار → **وتو**. سیگنال به دفتر vetoed می‌رود تا خود دروازه نمره بگیرد
  (چرخهٔ بعد قضاوت می‌شود — قانون «یک تغییر کنترل‌شده در هر چرخه»).
- قانون «مثبت» پایدار + CI بالای صفر + برقرار → برچسب الیت؛ در سهمیهٔ
  ارسال مقدم است. (ترفیع، نه معافیت — از باقی دروازه‌ها باز باید بگذرد.)
- شرطی که به جهت بیت‌کوین نیاز دارد و بیت‌کوین در دسترس نیست →
  قانون ۱ و ۳: دادهٔ اجباریِ ناقص = NO_SIGNAL، نه عبورِ کور.

تعریف جهت بیت‌کوین مو به مو همان تعریف ماشین استخراج (mine.py) است:
کلوز حالا در برابر ۸ کندل قبل روی همان شبکه، با ناحیهٔ مردهٔ ±۰.۲۵٪ —
تعریفِ متفاوت یعنی قانونِ سنجیده و قانونِ اجراشده دو چیز متفاوت‌اند.
آزمون ساختاری test_rule_gate همین هم‌ارزی را با scan.RULE_TESTS قفل می‌کند.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
STABLE = ROOT / "brain" / "learning" / "stable-rules.json"
LOG = ROOT / "signals" / "rule-gate-log.json"
MIN_DAYS = 5                       # هم‌مقدار با min_days خود دفتر پایداری

# فقط شرط‌هایی که در گلوگاه ارسال قابل ارزیابیِ **دقیق**اند. شرط ناموجود
# در این نگاشت اجرا نمی‌شود — تقریب، قانونِ دیگری با همان نام است.
_TESTS = {
    "داخل اردر بلاک": lambda s, b: s.get("inOB") == 1 or s.get("inside") is True,
    "بیت‌کوین صعودی": lambda s, b: b == "UP",
    "بیت‌کوین نزولی": lambda s, b: b == "DOWN",
    "لانگ همسو با بیت‌کوین": lambda s, b: s.get("dir") == "LONG" and b == "UP",
    "شورت همسو با بیت‌کوین": lambda s, b: s.get("dir") == "SHORT" and b == "DOWN",
    "لانگ خلاف بیت‌کوین": lambda s, b: s.get("dir") == "LONG" and b == "DOWN",
    "شورت خلاف بیت‌کوین": lambda s, b: s.get("dir") == "SHORT" and b == "UP",
}
_NEEDS_BTC = {k for k in _TESTS if "بیت‌کوین" in k}


def btc_dir(cd):
    """همان تعریف mine.py/scan.py — close now vs 8 bars ago, ±0.25%."""
    if not cd or len(cd) <= 8:
        return None
    chg = (cd[-1]["c"] - cd[-9]["c"]) / cd[-9]["c"] * 100
    return "UP" if chg > 0.25 else "DOWN" if chg < -0.25 else "FLAT"


def load_rules(path=None):
    try:
        j = json.loads((path or STABLE).read_text())
    except Exception:                                # noqa: BLE001 - بدون دفتر، بدون دروازه
        return []
    min_days = j.get("min_days") or MIN_DAYS
    out = []
    for r in j.get("rules") or []:
        ci = r.get("last_ci") or [0, 0]
        if (r.get("days_confirmed") or 0) < min_days:
            continue
        if r.get("verdict") == "منفی" and ci[1] < 0:
            out.append({**r, "mode": "veto"})
        elif r.get("verdict") == "مثبت" and ci[0] > 0:
            out.append({**r, "mode": "boost"})
    return out


def assess(signal, btc, rules=None):
    """حکم دروازه برای یک سیگنال.

    خروجی: {"ok": bool, "reason": str|None, "boost": bool, "applied": [...]}
    - ok=False یعنی وتو (با دلیل).
    - boost=True یعنی دست‌کم یک قانون مثبت پایدار برقرار است → الیت.
    """
    rules = load_rules() if rules is None else rules
    applied, boost = [], False
    for r in rules:
        if r.get("strategy") != signal.get("strategy"):
            continue
        cond = r.get("condition")
        test = _TESTS.get(cond)
        if not test:
            continue                                 # قابل ارزیابیِ دقیق نیست
        if cond in _NEEDS_BTC and btc is None:
            # قانون ۱ و ۳: بستر بیت‌کوین برای سیگنال آلت اجباری است؛
            # ناموجود = NO_SIGNAL، نه فرضِ خوش‌بینانه.
            return {"ok": False, "boost": False, "applied": applied,
                    "reason": f"دادهٔ بیت‌کوین ناموجود — شرط «{cond}» "
                              f"قابل ارزیابی نیست (قانون ۱)"}
        try:
            hit = bool(test(signal, btc))
        except Exception:                            # noqa: BLE001 - فیلد عجیب، قانون بعدی
            continue
        if not hit:
            continue
        applied.append({"rule": cond, "mode": r["mode"],
                        "days": r.get("days_confirmed"),
                        "delta": r.get("mean_delta")})
        if r["mode"] == "veto":
            return {"ok": False, "boost": False, "applied": applied,
                    "reason": (f"قانون پایدار ({r.get('days_confirmed')} روز، "
                               f"Δ={r.get('mean_delta')}): «{cond}» — وتو")}
        boost = True
    return {"ok": True, "boost": boost, "applied": applied, "reason": None}


def log_verdict(signal, verdict):
    """ثبت حکم روی لاگ دروازه — تا پاسبان و گزارش روزانه ببینند."""
    row = {"at": int(time.time() * 1000), "sym": signal.get("sym"),
           "dir": signal.get("dir"), "strategy": signal.get("strategy"),
           "ok": verdict["ok"], "boost": verdict["boost"],
           "applied": verdict["applied"], "reason": verdict["reason"]}
    try:
        p = LOG
        j = json.loads(p.read_text()) if p.exists() else {"rows": []}
        j["rows"] = ([row] + (j.get("rows") or []))[:200]
        j["updated"] = row["at"]
        p.write_text(json.dumps(j, ensure_ascii=False, indent=1))
    except Exception:                                # noqa: BLE001 - لاگ، نه مسیر اصلی
        pass
    return row
