#!/usr/bin/env python3
"""آزمون آفلاین اتاق دامیننس — هیچ شبکه‌ای صدا زده نمی‌شود.

    python3 freebuff/test_dominance.py
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freebuff import dominance                            # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'OK' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


# ── append_point: گام ۵دقیقه‌ای و ضدتکرار ─────────────────────────────────
def mk_series(n, step_ms=300_000):
    """سری مصنوعی که آخرش «الان» است — append_point با زمان واقعی کار می‌کند."""
    now = int(__import__("time").time() * 1000)
    t0 = now - (n - 1) * step_ms
    return [{"t": t0 + i * step_ms, "u": 5.0 + i * 0.01, "b": 55.0} for i in range(n)]


s = mk_series(3)
s2, added = dominance.append_point(s, 5.05, 55.2)
check("نقطهٔ خیلی زود رد می‌شود (ضدتکرار)", not added and len(s2) == 3)

s_old = [{"t": p["t"] - 600_000 for p in s}]      # آخرین نقطه ۱۰ دقیقه قبل
s3, added = dominance.append_point(s_old, 5.05, 55.2)
check("نقطهٔ بافاصله اضافه می‌شود", added and len(s3) == 2)
check("نقطهٔ جدید در سر سری", s3[-1]["u"] == 5.05)

# cap: سری نمی‌تواند بی‌نهایت رشد کند (آخرین نقطه عقب می‌رود تا افزودن رخ دهد)
big = [{"t": p["t"] - 600_000, "u": p["u"], "b": p["b"]}
       for p in mk_series(dominance.CAP + 10)]
s4, added = dominance.append_point(big, 9.9, 55.0)
check("سری به سقف می‌رسد و بریده می‌شود", added and len(s4) <= dominance.CAP)

# ── _delta ────────────────────────────────────────────────────────────────
s = mk_series(30)                                  # ۳۰ نقطه × ۵دقیقه = ~۲.۵ ساعت
u1, b1 = dominance._delta(s, 60)
check("دلتای ۶۰دقیقه محاسبه می‌شود", u1 is not None)
check("دلتای ۶۰د = ۱۲ گام × ۰.۰۱", abs(u1 - 0.12) < 0.005, str(u1))
u_long, _ = dominance._delta(s, 24 * 60)
check("دلتای خارج از طول سری = None (صداقت)", u_long is None)

# ── combined: ترکیب جهت و محرک‌ها ─────────────────────────────────────────
v = dominance.combined(None, None, None, None, [])
check("سری کوتاه → حکم صادق", "کوتاه" in v)

v = dominance.combined(0.06, 0.15, None, None, [])
check("USDT.D صعودی دیده می‌شود", "صعودی" in v)
v = dominance.combined(-0.06, -0.15, None, None, [])
check("USDT.D نزولی دیده می‌شود", "نزولی" in v)
v = dominance.combined(0.01, 0.02, None, None, [])
check("خنثی", "خنثی" in v)

ttr = {"minted_usd": 50e6, "burned_usd": 10e6, "net_usd": 40e6}
v = dominance.combined(0.01, None, ttr, None, [])
check("چاپ بزرگ تتر اعلام می‌شود", "40M$ چاپ خالص" in v, v)

ttr = {"minted_usd": 5e6, "burned_usd": 45e6, "net_usd": -40e6}
v = dominance.combined(0.01, None, ttr, None, [])
check("سوزاندن بزرگ تتر اعلام می‌شود", "سوزاندن خالص" in v, v)

ttr = {"minted_usd": 12e6, "burned_usd": 12e6, "net_usd": 0}
v = dominance.combined(0.01, None, ttr, None, [])
check("چاپ معمول بی‌سروصدا", "حد معمول" in v, v)

v = dominance.combined(0.01, None, None, {"value": 18, "label": "Extreme Fear"}, [])
check("ترس شدید اعلام می‌شود", "ترس شدید" in v, v)
v = dominance.combined(0.01, None, None, {"value": 82, "label": "Extreme Greed"}, [])
check("طمع شدید اعلام می‌شود", "طمع شدید" in v, v)

macro = [{"title": "CPI", "country": "US", "in_hours": 3.5}]
v = dominance.combined(0.01, None, None, None, macro)
check("رویداد کلان اعلام می‌شود", "CPI" in v and "3.5h" in v, v)
check("بدون محرک، حکم فقط جهتی", dominance.combined(0.01, None, None, None, []) == "USDT.D خنثی")

# ── فایل‌های JSON قابل‌نوشتن ──────────────────────────────────────────────
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "x.json"
    p.write_text(json.dumps({"panel": "پنل فری‌باف ۱"}, ensure_ascii=False))
    check("فارسی در JSON سالم", json.loads(p.read_text())["panel"] == "پنل فری‌باف ۱")

# ── رگرسیون: جست‌وجوی کور روی کل سری دلتای ساختگی می‌ساخت ──
# آزمون‌های قبلی نقاطی با t≈0 (سال ۱۹۷۰) می‌ساختند و آن‌ها به main
# نشسته بودند؛ _delta با min روی کل سری به همان‌ها می‌رسید و به‌جای
# None یک دلتای ۵۶ساله می‌داد. حالا باید None بدهد.
import time as _time                                    # noqa: E402
_now = int(_time.time() * 1000)
_poisoned = [{"t": 0, "u": 6.0, "b": 58.0} for _ in range(50)]
_poisoned += [{"t": _now - i * 300_000, "u": 6.3 + i * 0.001, "b": 58.2}
              for i in range(30)]
u_poison, _b = dominance._delta(_poisoned, 60)
check("نقاط کهنهٔ دور (t=0) به دلتای ساختگی راه نمی‌یابند",
      u_poison is None, f"دلتای ساختگی: {u_poison}")

# سری صعودی: u در طول زمان بالا می‌رود (i صفر = قدیمی‌ترین، i بزرگ‌تر = تازه‌تر)
_real = [{"t": _now - (40 - i) * 300_000, "u": 6.30 + i * 0.002, "b": 58.2 + i * 0.001}
         for i in range(40)]
u_real, b_real = dominance._delta(_real, 60)
check("سری واقعی دلتای معنادار می‌دهد", u_real is not None and b_real is not None)
check("سری صعودی → دلتای مثبت", u_real is not None and u_real > 0, str(u_real))
check("اندازهٔ دلتای منطقی است (کمتر از ۱ واحد درصد)",
      u_real is not None and abs(u_real) < 1, str(u_real))
check("سری نزولی → دلتای منفی",
      dominance._delta([{"t": p["t"], "u": 7.0 - p["u"], "b": 60 - p["b"]}
                        for p in _real], 60)[0] < 0)

# ── رگرسیون: پنجرهٔ سری رشد بی‌حد متوقف می‌شود ──
_junk = [{"t": _now - (10 ** 7) * 1000, "u": 1.0, "b": 1.0} for _ in range(9000)]
_trimmed, _added = dominance.append_point(list(_junk), 6.4, 58.3)
check("سری هرزگیر قدیمی حذف می‌شود", len(_trimmed) <= 130, str(len(_trimmed)))
check("همهٔ نقاط باقی‌مانده تازه‌اند",
      all(_now - p["t"] <= 6 * 3600_000 for p in _trimmed))

print(f"\n{'همهٔ آزمون‌ها سبز' if FAIL == 0 else f'{FAIL} آزمون قرمز'}")
sys.exit(1 if FAIL else 0)
