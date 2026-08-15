"""یادگیری نباید به حالت بازار وابسته باشد — ایراد حمید، ۱۵ اوت.

«قرار بود بی‌وقفه ترید انجام شود و به صورت پیپرتریدینگ … و نتایج بررسی و
علت را پیدا کند و به یادگیری اضافه کند.»

چه بود: کل خواندن ساختار و میز تمرین پشت `mode == "active"` بودند. امروز
شنبه است و نوسان بیت‌کوین زیر آستانهٔ آخر هفته، پس چرخه در حالت آرام رفت و
میز تمرین **صفر** معامله باز کرد — همان صفری که حمید روی پنل دید.

حالت آرام برای این است که روی تیک مرده **سیگنال نفرستیم**، نه این‌که یاد
نگیریم. این آزمون همان مرز را قفل می‌کند:

  · میز تمرین در هر دو حالت کار می‌کند
  · روز آرام ساختار را می‌خواند ولی `on_ready=None` — هیچ سیگنالی نمی‌رود
  · `reads` قبل از انشعاب تعریف شده، پس افتادنِ خواندنِ روز آرام چرخه را
    با NameError نمی‌کشد
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

SRC = (HERE / "cycle.py").read_text(encoding="utf-8")

ok = 0
fail = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


print("── یادگیری بی‌وقفه (مستقل از حالت بازار) ──")

# ── ۱. میز تمرین دیگر پشت active نیست ─────────────────────────────────────
i = SRC.find("pc = practice_candidates(reads)")
check("میز تمرین در کد هست", i > 0)
block = SRC[max(0, i - 500):i]
last_try = block.split("try:")[-1]
check("میز تمرین پشت شرط active نیست",
      'if mode == "active":' not in last_try)

# ── ۲. روز آرام ساختار می‌خواند، ولی بی‌سیگنال ────────────────────────────
check("روز آرام ساختار را می‌خواند", "run_active(q_syms" in SRC)
check("روز آرام هیچ سیگنالی نمی‌فرستد (on_ready=None)",
      "run_active(q_syms, on_ready=None)" in SRC)
quiet_tail = SRC.split("report.update(run_quiet())")[1][:1500]
check("مسیر روز آرام به ارسال فوری وصل نیست", "_send_now" not in quiet_tail)
check("مسیر روز آرام به send_signals وصل نیست", "send_signals" not in quiet_tail)
check("جهان روز آرام محدود است (بودجهٔ چرخه)", "QUIET_LEARN_N" in SRC)

# ── ۳. reads هرگز تعریف‌نشده نمی‌ماند ─────────────────────────────────────
check("reads قبل از انشعاب حالت تعریف شده",
      SRC.count("reads, setups, inds = [], [], []") >= 2)
_main = SRC[SRC.find("def main("):]
check("تعریف reads قبل از اولین استفاده در main است",
      _main.find("reads, setups, inds = [], [], []")
      < _main.find("practice_candidates(reads)"))

# ── ۴. ارسال فوری هنوز per-symbol است (خواستهٔ دیگر حمید) ────────────────
check("ارسال فوری داخل حلقهٔ هر نماد صدا زده می‌شود",
      "on_ready(sym, r)" in SRC)
# بدنهٔ واقعی run_active، نه یک پنجرهٔ حدسی — نسخهٔ اول ۴۰۰۰ کاراکتر برید و
# اصلاً به return نرسید، پس آزمون روی -1 قضاوت می‌کرد.
_s = SRC.find("def run_active(")
_e = SRC.find("\ndef ", _s + 1)
_ra = SRC[_s:_e if _e > 0 else len(SRC)]
check("ارسال فوری داخل بدنهٔ run_active است", "on_ready(sym, r)" in _ra)
check("ارسال فوری قبل از return تابع است، یعنی وسط اسکن",
      0 < _ra.find("on_ready(sym, r)") < _ra.find("return first, reads"))
_tail = _ra[_ra.find("on_ready(sym, r)"):]
check("بعد از ارسال، اسکن ادامه دارد (نمادهای بعدی خوانده می‌شوند)",
      "inducement.find" in _tail or "inds.append" in _tail)
check("خطای ارسال، اسکن را نمی‌کشد",
      "ارسال فوری نباید اسکن را بکشد" in SRC or
      re.search(r"on_ready\(sym, r\)\s*\n\s*except", SRC) is not None)
check("ارسال فوری فقط برای ستاپ آمادهٔ حالت فعال است",
      'if mode != "active" or r.setup.get("waiting"):' in SRC)

# ── ۵. نحو سالم ───────────────────────────────────────────────────────────
import ast                                            # noqa: E402

try:
    ast.parse(SRC)
    check("cycle.py نحو درستی دارد", True)
except SyntaxError as e:                              # noqa: BLE001
    check(f"cycle.py نحو درستی دارد ({e})", False)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون یادگیری بی‌وقفه گذشت")
