"""آزمون کارنامهٔ رادار پامپ — بدون شبکه، بدون دست‌زدن به دفتر تولید.

    python3 -m hamid.test_pump_score
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import pump_score as ps                              # noqa: E402

_REPO = str(Path(__file__).resolve().parents[3])


def _brain_status():
    return subprocess.run(["git", "-C", _REPO, "status", "--short", "brain"],
                          capture_output=True, text=True).stdout


_BRAIN_BEFORE = _brain_status()

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


tmp = Path(tempfile.mkdtemp(prefix="pumpscore-"))
_real_picks, _real_out = ps.PICKS, ps.OUT
ps.PICKS = tmp / "picks.jsonl"
ps.OUT = tmp / "score.json"

T0 = 1_700_000_000_000
BAR = 900_000


def bars(spec):
    """spec: فهرست (low, high, close) — t خودکار."""
    return [{"t": T0 + i * BAR, "o": c, "h": h, "l": l, "c": c, "v": 1.0}
            for i, (l, h, c) in enumerate(spec)]


print("\n۱. سرنوشت یک پیشنهاد روی کندل واقعی")
pick = {"t": T0, "sym": "AUSDT", "entry": 100.0, "sl": 99.0,
        "expires_at": T0 + 20 * BAR}

# نرسید به ورود = معامله نیست
v = ps.judge(pick, bars([(101, 103, 102)] * 5))
check("قیمت به ورود نرسید → no_fill (معامله نیست)",
      v["outcome"] == "no_fill" and v["R"] is None and not v["filled"])

# پر شد و به +۵٪ رسید
v = ps.judge(pick, bars([(99.5, 100.5, 100.0), (100, 106, 105.5)]))
check("پر شد و به هدف پامپ رسید → pumped",
      v["outcome"] == "pumped" and v["filled"])
check("R نسبت به ریسک لحظهٔ ورود است (۵ واحد سود / ۱ واحد ریسک)",
      abs(v["R"] - 5.0) < 1e-6, f"R={v['R']}")

# پر شد و استاپ خورد
v = ps.judge(pick, bars([(99.5, 100.5, 100.0), (98.0, 100.2, 98.5)]))
check("استاپ خورد → R=-1", v["outcome"] == "stop" and v["R"] == -1.0)

# کندلی که هر دو را زده = بدخیم‌ترین فرض
v = ps.judge(pick, bars([(99.5, 100.5, 100.0), (98.0, 106.0, 104.0)]))
check("کندلِ دوسویه استاپ حساب می‌شود، نه هدف (بدون خوش‌بینی)",
      v["outcome"] == "stop")

# بیرون از پنجره حساب نمی‌شود: پر شدن در کندل ۰، پامپ در کندل ۲،
# ولی پنجره تا کندل ۱ باز است — همان پامپ نباید امتیاز بگیرد.
_late_cd = bars([(99.5, 100.5, 100.0), (99.6, 100.4, 100.0), (100, 106, 105.5)])
check("داخل پنجره، پامپ کندل ۲ دیده می‌شود",
      ps.judge(dict(pick, expires_at=T0 + 2 * BAR), _late_cd)["outcome"] == "pumped")
check("همان پامپ بیرون از پنجره دیگر هدف حساب نمی‌شود",
      ps.judge(dict(pick, expires_at=T0 + 1 * BAR), _late_cd)["outcome"] != "pumped")

check("دادهٔ کم → None، نه حدس (قانون ۱)",
      ps.judge(pick, bars([(99, 101, 100)])) is None)

print("\n۲. یکتاسازی بازیابی — یک پیشنهاد در ده گزارش، یک ردیف")
reports = {}
for i in range(10):                                    # همان پیشنهاد، ۱۰ گزارش
    reports[f"sha{i}"] = json.dumps({
        "generated": T0 + i * 180_000,
        "recommendation": [{"symbol": "AUSDT", "entry": 100.0, "price": 101.0,
                            "score": 6, "expires_at": T0 + 20 * BAR}]})
reports["shaX"] = json.dumps({                          # پیشنهاد متفاوت
    "generated": T0 + 99_000, "recommendation": [
        {"symbol": "BUSDT", "entry": 7.0, "price": 7.1, "score": 9}]})
shas = list(reports)                                    # جدید→قدیم مثل git log
added, total = ps.recover(_shas=shas, _show=reports.get, quiet=True)
rows = ps.read_picks()
check("۱۱ گزارش → ۲ پیشنهاد یکتا (نه ۱۱)", total == 2, f"{total}")
check("تکرار یک پیشنهاد نمونه را تقلبی بزرگ نمی‌کند",
      sum(1 for r in rows if r["sym"] == "AUSDT") == 1)
a = [r for r in rows if r["sym"] == "AUSDT"][0]
check("قدیمی‌ترین لحظهٔ صدور نگه داشته شد (نه آخرین تکرار)",
      a["t"] == T0, f"t={a['t']}")

added2, total2 = ps.recover(_shas=shas, _show=reports.get, quiet=True)
check("بازیابی دوباره ردیف تکراری نمی‌سازد", added2 == 0 and total2 == 2)

print("\n۳. حکم فقط از بازهٔ اطمینان")
check("نمونهٔ کم → حکم ممنوع", ps.boot([0.5] * 10) is None)
check("بازهٔ صفرعرض شاهد نیست (R ثابت)", ps.boot([1.0] * 200) is None)
check("زیر صفر → کنار برود", ps.verdict(200, (-0.5, -0.1)).startswith("زیر صفر"))
check("بالای صفر → ارزش دارد", ps.verdict(200, (0.1, 0.5)).startswith("بالای صفر"))
check("دربرگیرندهٔ صفر با نمونهٔ بزرگ → کادنس پایین",
      "کادنس" in ps.verdict(200, (-0.2, 0.3)))
check("دربرگیرندهٔ صفر با نمونهٔ کم → ادامه",
      "ادامه" in ps.verdict(40, (-0.2, 0.3)))
check("بدون بازه → نتیجه‌گیری ممنوع", "ممنوع" in ps.verdict(10, None))

print("\n۴. اجرای کامل بدون شبکه")
CD = {"AUSDT": bars([(99.5, 100.5, 100.0), (100, 106, 105.5)] + [(105, 106, 105)] * 20),
      "BUSDT": bars([(6.9, 7.05, 7.0), (6.5, 7.0, 6.6)] + [(6.5, 6.7, 6.6)] * 20)}
rep = ps.run(fetch=lambda s: CD[s], quiet=True)
check("هر دو پیشنهاد نمره خوردند", rep["n_judged"] == 2, str(rep["n_judged"]))
check("نرخ پر شدن محاسبه شد", rep["fill_rate_pct"] == 100.0)
check("خروجی روی دیسک نشست", ps.OUT.exists() and "verdict" in json.loads(ps.OUT.read_text()))
check("با ۲ نمونه حکم نمی‌دهد", rep["ci"] is None and "ممنوع" in rep["verdict"])

# ارزی که کندل نمی‌دهد نباید کل اجرا را بخواباند
rep2 = ps.run(fetch=lambda s: (_ for _ in ()).throw(RuntimeError("no venue")),
              quiet=True)
check("صرافیِ بی‌جواب کل اجرا را نمی‌خواباند", rep2["symbols_missing"] >= 1)

print("\n۵. ایزوله‌سازی از تولید")
# تفاضلی، نه پاکیِ مطلق — درس ۱۶ اوت (test_fill_books).
_new_dirty = sorted(set(_brain_status().splitlines()) - set(_BRAIN_BEFORE.splitlines()))
if _new_dirty:
    print("      ↳ " + " | ".join(_new_dirty)[:200])
check("آزمون به دفتر تولید دست نزد", not _new_dirty)
check("مسیرها واقعاً منحرف شده بودند",
      ps.PICKS != _real_picks and ps.OUT != _real_out)

ps.PICKS, ps.OUT = _real_picks, _real_out
print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
