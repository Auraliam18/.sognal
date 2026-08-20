"""آزمون دروازهٔ قانون‌های پایدار — گلوگاه ارسال.

    python3 -m hamid.test_rule_gate
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import rule_gate as rg                               # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


def rule(strategy, condition, verdict, days=8, ci=(-0.4, -0.1), delta=-0.25):
    return {"strategy": strategy, "condition": condition, "verdict": verdict,
            "days_confirmed": days, "days_in_window": 10,
            "mean_delta": delta, "last_n": 200, "last_ci": list(ci)}


def stable(rules, min_days=5):
    tmp = Path(tempfile.mkdtemp(prefix="rg-")) / "stable.json"
    tmp.write_text(json.dumps({"rules": rules, "min_days": min_days},
                              ensure_ascii=False))
    return tmp


print("\n۱. کدام قانون اجازهٔ اجرا دارد")
rules = rg.load_rules(stable([
    rule("ibs", "لانگ خلاف بیت‌کوین", "منفی", days=6, ci=(-0.53, -0.15)),
    rule("smc", "شورت همسو با بیت‌کوین", "منفی", days=8, ci=(-0.37, -0.02)),
    rule("ibs", "داخل اردر بلاک", "مثبت", days=7, ci=(0.08, 0.34), delta=0.18),
    rule("ibs", "بیت‌کوین نزولی", "منفی", days=3, ci=(-0.4, -0.1)),   # روز کم
    rule("smc", "لانگ خلاف بیت‌کوین", "مثبت", days=6, ci=(-0.1, 0.8)),  # CI صفر را دربر دارد
]))
check("سه قانون واجد شرایط شدند", len(rules) == 3, str(len(rules)))
check("قانونِ با روزِ ناکافی اجرا نمی‌شود",
      all(not (r["condition"] == "بیت‌کوین نزولی") for r in rules))
check("قانونِ مثبتِ بدون CI بالای صفر اجرا نمی‌شود",
      all(not (r["strategy"] == "smc" and r["mode"] == "boost") for r in rules))

print("\n۲. وتو و الیت")
sig_bad = {"sym": "XUSDT", "dir": "LONG", "strategy": "ibs"}
v = rg.assess(sig_bad, "DOWN", rules)
check("لانگ ibs خلاف بیت‌کوین → وتو", not v["ok"] and "وتو" in v["reason"])
v = rg.assess(sig_bad, "UP", rules)
check("همان سیگنال با بیت‌کوین صعودی → عبور", v["ok"])
v = rg.assess({"sym": "XUSDT", "dir": "SHORT", "strategy": "smc"}, "DOWN", rules)
check("شورت smc همسو با بیت‌کوین → وتو (قانون پایدارش منفی است)", not v["ok"])
v = rg.assess({"sym": "XUSDT", "dir": "LONG", "strategy": "ibs", "inOB": 1},
              "UP", rules)
check("داخل اردر بلاک ibs → الیت", v["ok"] and v["boost"])
v = rg.assess({"sym": "XUSDT", "dir": "LONG", "strategy": "smc", "inOB": 1},
              "UP", rules)
check("قانونِ ibs روی سیگنال smc اعمال نمی‌شود (قانون ۷)",
      v["ok"] and not v["boost"])

print("\n۳. دادهٔ ناقص = NO_SIGNAL (قانون ۱ و ۳)")
v = rg.assess(sig_bad, None, rules)
check("بیت‌کوین ناموجود و قانونِ بیت‌کوینی فعال → وتو با دلیل صریح",
      not v["ok"] and "قانون ۱" in v["reason"])
v = rg.assess({"sym": "XUSDT", "dir": "LONG", "strategy": "ibs", "inOB": 1},
              None, [r for r in rules if r["condition"] == "داخل اردر بلاک"])
check("قانونِ بی‌نیاز از بیت‌کوین با بیت‌کوینِ ناموجود کار می‌کند",
      v["ok"] and v["boost"])

print("\n۴. تعریف جهت بیت‌کوین — مو به مو همان تعریف ماشین استخراج")
mk = lambda closes: [{"t": i, "c": c} for i, c in enumerate(closes)]
check("رشد >۰.۲۵٪ → UP", rg.btc_dir(mk([100] * 9 + [100.6])) == "UP")
check("افت >۰.۲۵٪ → DOWN", rg.btc_dir(mk([100] * 9 + [99.4])) == "DOWN")
check("ناحیهٔ مرده → FLAT", rg.btc_dir(mk([100] * 9 + [100.1])) == "FLAT")
check("دادهٔ کم → None، نه حدس", rg.btc_dir(mk([100] * 5)) is None)

print("\n۵. هم‌ارزی با scan.RULE_TESTS — تا دو تعریف از هم نلغزند")
import scan                                                     # noqa: E402
shared = set(rg._TESTS) & set(scan.RULE_TESTS)
check("هر شرط دروازه در ماشین استخراج هم هست", set(rg._TESTS) <= set(scan.RULE_TESTS))
cases = [({"dir": "LONG", "inOB": 1}, "UP"), ({"dir": "LONG"}, "DOWN"),
         ({"dir": "SHORT"}, "DOWN"), ({"dir": "SHORT", "inside": True}, "UP"),
         ({"dir": "LONG"}, "FLAT")]
drift = [c for c in shared for s, b in cases
         if bool(rg._TESTS[c](s, b)) != bool(scan.RULE_TESTS[c](s, b))]
check("و روی همهٔ حالت‌ها همان جواب را می‌دهد", not drift, str(drift[:3]))

print("\n۶. دفتر واقعی پایداری — دروازه با وضعیت امروز چه می‌کند")
live = rg.load_rules()
print(f"      ↳ قانون‌های فعال الان: "
      + (", ".join(f"{r['strategy']}«{r['condition']}»({r['mode']})" for r in live)
         or "هیچ"))
check("خواندن دفتر واقعی خطا نمی‌دهد", isinstance(live, list))

print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
