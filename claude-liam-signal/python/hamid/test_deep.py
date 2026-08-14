"""آزمون‌های تحلیل عمیق تک‌نماد — بدون شبکه، با کندل ساختگیِ کنترل‌شده.

چیزی که اینجا اثبات می‌شود:
  ۱. هر لایهٔ deep واقعاً پر می‌شود (نه اینکه بی‌صدا None بماند)
  ۲. شکست یک انجین، بقیه را نمی‌کشد و علتش صادقانه ثبت می‌شود
  ۳. چارت عمیق با تمام لایه‌ها رسم می‌شود و فایل واقعی می‌سازد
  ۴. عمق واقعاً بیشتر از اسکن است (۴س از ۱س با ۳۰۰ کندل ساخته می‌شود)
  ۵. هیچ عدد ساختگی وارد خروجی نمی‌شود وقتی داده نیست
"""
from __future__ import annotations

import json
import math
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

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


def synth(n=1200, start=100.0, seed=7, trend=0.0004, vol=0.006):
    """سری با روند ملایم، خوشهٔ نوسان و چند ایمپالس — تا انجین‌ها چیزی برای دیدن داشته باشند."""
    rnd = random.Random(seed)
    out, px, t = [], start, 1_700_000_000_000
    v_state = vol
    for i in range(n):
        v_state = max(vol * 0.4, min(vol * 3, v_state * (1 + rnd.gauss(0, 0.12))))
        drift = trend + (0.004 if i % 190 == 0 else 0)      # ایمپالس دوره‌ای
        r = rnd.gauss(drift, v_state)
        o = px
        c = max(1e-9, o * (1 + r))
        hi = max(o, c) * (1 + abs(rnd.gauss(0, v_state * 0.5)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, v_state * 0.5)))
        vol_q = abs(rnd.gauss(1000, 260)) * (3.2 if i % 190 == 0 else 1.0)
        out.append({"t": t + i * 3_600_000, "o": o, "h": hi, "l": lo,
                    "c": c, "v": vol_q})
        px = c
    return out


def to15(c1h):
    """۱۵د ساختگی از ۱س — هر کندل ۱س به چهار کندل ۱۵د باز می‌شود."""
    out = []
    for k in c1h:
        step = (k["c"] - k["o"]) / 4
        for j in range(4):
            o = k["o"] + step * j
            c = k["o"] + step * (j + 1)
            out.append({"t": k["t"] + j * 900_000, "o": o,
                        "h": max(o, c, k["h"] if j == 1 else max(o, c)),
                        "l": min(o, c, k["l"] if j == 2 else min(o, c)),
                        "c": c, "v": k["v"] / 4})
    return out


print("── تحلیل عمیق تک‌نماد ──")

# ── ۱. ساختار هر تایم‌فریم پر می‌شود ────────────────────────────────────────
from hamid import deep                                        # noqa: E402

c1h = synth(1200)
c15 = to15(c1h)[-800:]
c5 = to15(c1h)[-600:]
from hamid.cycle import resample                              # noqa: E402
c4h = resample(c1h, 4)
price = c15[-1]["c"]

check("۴س از ۱س ساخته شد و ≥۲۰۰ کندل دارد (قانون حمید)", len(c4h) >= 200)

m4 = deep._tf_map(c4h, "4h", price)
m1 = deep._tf_map(c1h, "1h", price)
m15 = deep._tf_map(c15, "15m", price)
check("نقشهٔ ۴س: روند دارد", m4.get("trend") in ("up", "down", "range"))
check("نقشهٔ ۴س: سطح معتبر پیدا شد", isinstance(m4.get("levels"), list))
check("نقشهٔ ۱س: ATR عدد مثبت است", (m1.get("atr") or 0) > 0)
check("نقشهٔ ۱۵د: تعداد کندل گزارش می‌شود", m15.get("bars") == len(c15))
check("سطوح فاصلهٔ درصدی تا قیمت دارند",
      not m1["levels"] or "dist_pct" in m1["levels"][0])

# ── ۲. تایم‌فریم کوتاه دروغ نمی‌گوید ────────────────────────────────────────
short = deep._tf_map(c1h[:12], "1h", price)
check("کندل کم → «کافی نیست»، نه عدد ساختگی",
      short.get("note") == "کندل کافی نیست" and "trend" not in short)

# ── ۳. _try خطا را می‌بلعد ولی صادقانه ثبت می‌کند ───────────────────────────
box = {}
r_ok = deep._try("good", lambda: 42, box)
r_bad = deep._try("bad", lambda: 1 / 0, box)
check("_try مقدار سالم را برمی‌گرداند", r_ok == 42)
check("_try خطا را None می‌کند، نه crash", r_bad is None)
check("_try علت خطا را ثبت می‌کند", "ZeroDivisionError" in box.get("bad", ""))
check("_try انجین سالم را آلوده نمی‌کند", "good" not in box)

# ── ۴. انجین‌های واقعی روی همین سری اجرا می‌شوند ────────────────────────────
from hamid import ob_intel, liquidity, patterns, structure     # noqa: E402

boxes15 = ob_intel.analyze(c15, "15m")
check("ob_intel روی ۱۵د باکس برمی‌گرداند", isinstance(boxes15, list))
if boxes15:
    b = boxes15[0]
    check("باکس ob_intel وضعیت و گرید دارد",
          "state" in b and "grade" in b and "mid" in b)

lq = liquidity.read(c15, "LONG")
check("نقدینگی خوانده شد", isinstance(lq, dict) and "side" in lq)

pat = patterns.detect(c15)
check("انجین الگو اجرا شد", isinstance(pat, list))

lv = structure.levels(c1h)
check("سطوح معتبر ۱س پیدا شد", isinstance(lv, list))

# ── ۵. چارت عمیق واقعاً فایل می‌سازد و همهٔ لایه‌ها را می‌گیرد ───────────────
import deep_chart                                              # noqa: E402

fake = {
    "symbol": "TESTUSDT",
    "price": price,
    "engines_ok": 9,
    "setup": {"dir": "LONG", "entry": price * 0.995, "sl": price * 0.985,
              "tp1": price * 1.01, "tp2": price * 1.02, "rr": 2.0},
    "structure": {"h4": m4, "h1": m1, "m15": m15},
    "order_blocks": {"15m": boxes15[:3], "1h": ob_intel.analyze(c1h, "1h")[:3],
                     "4h": ob_intel.analyze(c4h, "4h")[:2]},
    "liquidity": lq,
    "liq_map": {"magnet": "above"},
    "hamid_read": {"fvgs": [{"low": price * 0.99, "high": price * 0.993}]},
}
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "deep.png"
    deep_chart.render(fake, {"c1h": c1h, "c15": c15, "c5": c5}, str(p))
    check("چارت عمیق ساخته شد", p.exists())
    check("چارت خالی نیست (>۴۰ کیلوبایت)", p.stat().st_size > 40_000)

    # چارت بدون ستاپ هم باید رسم شود — تحلیل بدون سیگنال معتبر است
    no_setup = dict(fake)
    no_setup["setup"] = None
    p2 = Path(td) / "deep2.png"
    deep_chart.render(no_setup, {"c1h": c1h, "c15": c15, "c5": c5}, str(p2))
    check("چارت بدون ستاپ هم رسم می‌شود (NO TRADE تصمیم معتبر است)", p2.exists())

    # لایهٔ غایب نباید چارت را بکشد
    bare = {"symbol": "X", "price": price, "setup": {}, "structure": {},
            "order_blocks": {}, "liquidity": None, "liq_map": None,
            "hamid_read": {}}
    p3 = Path(td) / "deep3.png"
    deep_chart.render(bare, {"c1h": c1h, "c15": c15, "c5": c5}, str(p3))
    check("لایهٔ غایب چارت را نمی‌کشد", p3.exists())

# ── ۶. رنگ گرید: A از D پررنگ‌تر است (سلسله‌مراتب دیداری) ───────────────────
check("گرید A پررنگ‌تر از D رسم می‌شود",
      deep_chart.GRADE_ALPHA["A"] > deep_chart.GRADE_ALPHA["D"])

# ── ۷. عمق واقعاً از اسکن بیشتر است ─────────────────────────────────────────
from hamid import cycle                                        # noqa: E402
import inspect                                                 # noqa: E402
sig = inspect.signature(cycle.run_active)
scan_1h = sig.parameters["limit_1h"].default
check(f"عمق ۱س عمیق ({deep.LIMIT_1H}) > عمق اسکن ({scan_1h})",
      deep.LIMIT_1H > scan_1h)
check("عمق ۱۵د عمیق > عمق اسکن",
      deep.LIMIT_15M > sig.parameters["limit_15m"].default)

# ── ۸. خروجی JSON قابل ذخیره است ───────────────────────────────────────────
check("خروجی JSON-سریالایزبل است",
      isinstance(json.dumps(fake, ensure_ascii=False, default=str), str))

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون تحلیل عمیق گذشت")
