"""آزمون آفلاین فاز ۲ دامیننس — ساختار مستقل USDT.D/BTC.D و دروازهٔ صداقت.

سری‌ها مصنوعی و بذردار (seed) هستند: روند نزولی/صعودی با پولبک، تا موتور
سوینگ چیزی برای شمردن داشته باشد. هیچ شبکه‌ای صدا زده نمی‌شود.

    python3 -m hamid.test_dominance
"""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import dominance, premortem                        # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


T0 = (1_754_000_000_000 // 3_600_000) * 3_600_000     # هم‌تراز با سرِ ساعت


def mk_points(hours, slope, base=8.0, amp=0.08, per=5.0, b_slope=0.0, b_base=56.0):
    """نقطهٔ ۵دقیقه‌ای: روند خطی + موج سینوسی (پولبک‌ساز) — بدون تصادف."""
    pts = []
    for i in range(int(hours * 12)):
        h = i / 12.0
        u = base + slope * h + amp * math.sin(h / per)
        b = b_base + b_slope * h + amp * math.sin(h / per + 1.0)
        pts.append({"t": T0 + i * 300_000, "u": round(u, 4), "b": round(b, 4)})
    return pts


# ── کندل‌سازی از نقاط ───────────────────────────────────────────────────────
pts = mk_points(10, slope=-0.01)
bars = dominance._bars(pts, "u")
check("سطل آخرِ باز حذف می‌شود", len(bars) == 9)
check("o/h/l/c از خودِ نقاط سطل", bars[0]["o"] == pts[0]["u"]
      and bars[0]["c"] == pts[11]["u"]
      and bars[0]["h"] == max(p["u"] for p in pts[:12])
      and bars[0]["l"] == min(p["u"] for p in pts[:12]))
b4 = dominance._bars(pts, "u", 4 * 3_600_000)
check("کندل ۴س هم از همان نقاط ساخته می‌شود", 1 <= len(b4) <= 3)

# ── دروازهٔ صداقت: دادهٔ کم = INSUFFICIENT، نه حدس ─────────────────────────
st = dominance.structural(mk_points(30, slope=-0.01))
check("زیر ۶۰ کندل ۱س حکم ساختاری صادر نمی‌شود",
      st["regime"] == "INSUFFICIENT" and st["bars_1h"] < 60, str(st))
check("شمارش صریح در جواب هست", "کندل ۱س" in (st.get("note") or ""))

# ── رژیم‌ها ─────────────────────────────────────────────────────────────────
st_bull = dominance.structural(mk_points(300, slope=-0.01))
check("USDT.D ساختاراً نزولی → BULLISH",
      st_bull["regime"] == "BULLISH", str(st_bull.get("usdt")))
check("چرایی با روند ۱س", "۱س down" in (st_bull.get("why") or ""), st_bull.get("why"))

st_bear = dominance.structural(mk_points(300, slope=+0.01))
check("USDT.D ساختاراً صعودی → BEARISH",
      st_bear["regime"] == "BEARISH", str(st_bear.get("usdt")))

st_rng = dominance.structural(mk_points(300, slope=0.0, amp=0.05))
check("بدون جهت → RANGE (اعتراف، نه حدس)",
      st_rng["regime"] == "RANGE", str(st_rng.get("usdt")))

st_uns = dominance.structural(mk_points(300, slope=-0.01),
                              macro=[{"title": "CPI", "in_hours": 1.5}])
check("رویداد کلان تا ۲ ساعت → UNSAFE با دلیل",
      st_uns["regime"] == "UNSAFE" and "CPI" in st_uns.get("unsafe_reason", ""))
st_far = dominance.structural(mk_points(300, slope=-0.01),
                              macro=[{"title": "CPI", "in_hours": 8}])
check("رویداد دور، رژیم را معلق نمی‌کند", st_far["regime"] == "BULLISH")

check("bars_4h گزارش می‌شود", st_bull.get("bars_4h", 0) >= 60
      or "INSUFFICIENT" in str(st_bull.get("usdt", {}).get("trend_4h")))

# ── دروازهٔ ۷ پیش‌مورتم: رژیم ساختاری با وزن ۲، دلتا فقط وقتی داده کم است ──
tmp = Path(tempfile.mkdtemp())
premortem.DOM = tmp / "dominance.json"


def quiet_c15(n=60, px=100.0):
    """کندل ۱۵د آرام و خنثی — تا فقط بند دامیننس فرق دو حالت را بسازد."""
    out = []
    for i in range(n):
        p = px + 0.03 * math.sin(i / 7.0)
        out.append({"t": T0 + i * 900_000, "o": p, "h": p + 0.05,
                    "l": p - 0.05, "c": p, "v": 10.0})
    return out


SIG = {"sym": "AUSDT", "dir": "LONG", "entry": 100.0, "sl": 99.0, "tp1": 102.0}

premortem.DOM.write_text(json.dumps(
    {"structure": {"regime": "BULLISH", "why": "USDT.D ساختار ۱س down"},
     "chg_1h": {"usdt": +0.5}}))          # دلتا عمداً مخالف است — نباید خوانده شود
rv = premortem.review(dict(SIG), quiet_c15())
check("رژیم ساختاری BULLISH → دلیل تارگتِ لانگ",
      any("رژیم ساختاری" in x for x in rv["pro"]), str(rv["pro"]))
check("با رژیم ساختاری، دلتای عددی دیگر شمرده نمی‌شود",
      not any("USDT.D در حال" in x for x in rv["con"]), str(rv["con"]))

premortem.DOM.write_text(json.dumps(
    {"structure": {"regime": "BEARISH", "why": "USDT.D ساختار ۱س up"}}))
rv2 = premortem.review(dict(SIG), quiet_c15())
check("رژیم BEARISH → دلیل استاپِ لانگ با وزن ۲",
      any("رژیم ساختاری" in x for x in rv2["con"])
      and rv2["con_w"] >= rv["con_w"] + 2, f"{rv2['con']} / con_w={rv2['con_w']}")

premortem.DOM.write_text(json.dumps(
    {"structure": {"regime": "INSUFFICIENT", "bars_1h": 12},
     "chg_1h": {"usdt": +0.5}}))
rv3 = premortem.review(dict(SIG), quiet_c15())
check("INSUFFICIENT → برگشت به دلتای عددی (وزن ۱)",
      any("USDT.D در حال رشد" in x for x in rv3["con"]), str(rv3["con"]))

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های دامیننس گذشت")
