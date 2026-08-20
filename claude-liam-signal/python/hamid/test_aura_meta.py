"""آزمون فایل متا (aura_ibs_meta) — قانون ۳: کد تازه بدون تست تحویل نمی‌شود.

    python3 -m hamid.test_aura_meta
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

META = Path(__file__).resolve().parents[2] / "meta" / "aura_ibs_meta.py"
spec = importlib.util.spec_from_file_location("aura_ibs_meta", META)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


print("\n۱. ایزوله بودن — قرارداد داشبورد")
src = META.read_text(encoding="utf-8")
imports = [ln.strip() for ln in src.splitlines()
           if ln.strip().startswith(("import ", "from "))]
bad = [ln for ln in imports
       if not any(x in ln for x in ("__future__", "import json", "import sys"))]
check("فقط کتابخانهٔ استاندارد (json/sys)", not bad, str(bad))
check("هیچ شبکه/فایل‌سیستم خانگی در کد نیست",
      "urllib" not in src and "requests" not in src and "open(ROOT" not in src)
check("سفارش واقعی نمی‌فرستد (بدون هیچ API صرافی)",
      "bitunix" not in src.lower() and "api_key" not in src.lower())

print("\n۲. بازار ساختگی با ستاپ لانگ واقعی")


def bar(t, o, h, l, c):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": 1.0}


def market():
    """زیگزاگ صعودی با پاهای بلند: ۷ کندل بالا، ۵ کندل پایین — سوینگ‌های
    فرکتال ۴کندله واقعاً شکل می‌گیرند و BOS/پولبک ساخته می‌شود."""
    cd, px, t = [], 100.0, 1_700_000_000_000
    for i in range(240):
        leg = i % 12
        up = leg < 7
        drift = 0.50 if up else -0.40                 # نوسان، با برایند صعودی
        o = px
        px = px + drift
        # ویکِ نامتقارن: کندل صعودی سایهٔ بالایی بلند دارد و کندل نزولی
        # سایهٔ پایینی — وگرنه سقفِ قله با سقفِ کندلِ بعدش «مساوی» می‌شود
        # و فرکتالِ اکید (>) هیچ سوینگی پیدا نمی‌کند.
        hi = max(o, px) + (0.20 if up else 0.05)
        lo = min(o, px) - (0.05 if up else 0.20)
        cd.append(bar(t + i * 900_000, o, hi, lo, px))
    return cd


cd = market()
sw = m.swings(cd)
check("سوینگ پیدا می‌شود", len(sw) >= 4, str(len(sw)))
s = m.signal(cd, qmin=40)
check("با آستانهٔ پایین سیگنال درمی‌آید", s is not None)
if s:
    risk = abs(s["entry"] - s["sl"])
    sgn = 1 if s["dir"] == "LONG" else -1
    check("تارگت و استاپ اجباری‌اند", all(s.get(k) for k in ("sl", "tp1", "tp2")))
    check("TP1 دقیقاً 1.5R", abs(abs(s["tp1"] - s["entry"]) / risk - 1.5) < 1e-9)
    check("TP2 دقیقاً 2.5R", abs(abs(s["tp2"] - s["entry"]) / risk - 2.5) < 1e-9)
    check("استاپ آن‌سوی ورود است", (s["entry"] - s["sl"]) * sgn > 0)

print("\n۳. بدون نگاه به آینده")
cut = len(cd) - 30
s_then = m.signal(cd[:cut], qmin=40)
s_again = m.signal(cd[:cut], qmin=40)
check("قطعی است (دو بار همان جواب)", s_then == s_again)
check("خروجی فقط تابع پنجره است، نه کل تاریخ",
      s_then is None or s_then["t"] == cd[cut - 1]["t"])

print("\n۴. ماشین وضعیت — پر شدن، نردبان، و قانون جدید نزدیک-TP2")
setup = {"strategy": m.VERSION, "dir": "LONG", "entry": 100.0, "sl": 98.0,
         "tp1": 103.0, "tp2": 105.0, "t": 0}
st = m.open_position(setup)
check("سفارش pending است", st["phase"] == "pending")
st, ev = m.step(st, bar(1, 99.5, 100.5, 99.0, 100.2))
check("لمس ورود → FILLED", st["phase"] == "open"
      and any(e["event"] == "FILLED" for e in ev))
# ⅓ مسیر تا TP1 (=101) → استاپ به سود کارمزددار
st, ev = m.step(st, bar(2, 100.2, 101.1, 100.0, 101.0))
check("⅓ مسیر → استاپ در سودِ کارمزددار",
      st["position"]["sl"] >= 100.0 * (1 + m.FEE_PCT) - 1e-9
      and any(e.get("rule") == "ladder_1_3" for e in ev))
# ⅔ مسیر (=102) → استاپ به سطح ⅓ (=101)
st, ev = m.step(st, bar(3, 101.0, 102.1, 100.9, 102.0))
check("⅔ مسیر → استاپ در سطح ⅓",
      abs(st["position"]["sl"] - 101.0) < 1e-9)
# نزدیک TP2: پیشروی ≥ 0.85×2.5R = 2.125R → اکسترمم ≥ 104.25
st, ev = m.step(st, bar(4, 102.0, 104.4, 101.9, 104.3))
check("نزدیک TP2 → TP برداشته شد",
      st["position"]["tp_removed"]
      and any(e["event"] == "TP_REMOVED" for e in ev))
tight = 104.4 * (1 - m.TIGHT_GAP_PCT)
check("و تریل تنگ پشت اکسترمم نشست",
      abs(st["position"]["sl"] - tight) < 1e-6, str(st["position"]["sl"]))
# TP2 (105) رد می‌شود ولی خروجی نیست — تریل ادامه دارد
st, ev = m.step(st, bar(5, 104.3, 106.0, 104.2, 105.8))
check("عبور از TP2 دیگر خروج نیست — تریل ادامه می‌دهد",
      st["phase"] == "open"
      and st["position"]["sl"] > tight)
# برگشت به تریل → خروج در سود بالای 2.5R
sl_now = st["position"]["sl"]
st, ev = m.step(st, bar(6, 105.8, 105.9, sl_now - 0.2, sl_now - 0.1))
done = next(e for e in ev if e["event"] == "CLOSED")
check("برخورد تریل → بسته با R بیشتر از 2.5 (فرضیهٔ حمید در این صحنه)",
      done["outcome"] == "trail" and done["R"] > 2.5, str(done))

print("\n۵. بدخیم‌ترین فرض و استاپ")
st2 = m.open_position(setup)
st2, _ = m.step(st2, bar(1, 99.5, 100.5, 99.0, 100.2))       # پر شد
st2, ev = m.step(st2, bar(2, 100.0, 105.5, 97.5, 104.0))      # هم SL هم TP2
done = next(e for e in ev if e["event"] == "CLOSED")
check("کندل دوسویه = استاپ (R=-1)، نه تارگت",
      done["outcome"] == "stop" and abs(done["R"] + 1.0) < 1e-9)
st3 = m.open_position(setup)
seen = []
for i in range(m.FILL_BARS + 2):
    st3, ev = m.step(st3, bar(i, 101.0, 101.5, 100.6, 101.2))  # هرگز به ورود نمی‌رسد
    seen += ev
check("سفارشِ پرنشده بعد از مهلت EXPIRED می‌شود",
      any(e["event"] == "EXPIRED" for e in seen) and st3["phase"] == "flat")

print("\n۶. مقایسهٔ دو حالت خروج — هر دو مسیر واقعاً اجرا می‌شوند")
# بازارِ روندیِ خالص سفارش لیمیت را پر نمی‌کند (قیمت به میانهٔ باکس
# برنمی‌گردد) — walk درست کار می‌کرد و ۰ معامله جوابِ صادقانه بود.
# برای سنجش چرخهٔ کامل، هر سومین موج یک پولبک عمیق تا خود باکس دارد.
def market_deep():
    cd2, px, t = [], 100.0, 1_700_000_000_000
    for i in range(300):
        cyc, leg = (i // 12) % 3, i % 12
        up = leg < 7
        drift = 0.50 if up else (-0.80 if cyc == 2 else -0.40)
        o = px
        px = px + drift
        hi = max(o, px) + (0.20 if up else 0.05)
        lo = min(o, px) - (0.05 if up else 0.20)
        cd2.append(bar(t + i * 900_000, o, hi, lo, px))
    return cd2


rep = m.compare(market_deep(), qmin=40)
check("هر دو حالت معامله ساختند",
      rep["trail_after_tp2"]["n"] > 0 and rep["classic_tp2"]["n"] > 0,
      json.dumps(rep, ensure_ascii=False)[:120])
check("خروجی حکم قطعی نمی‌دهد (تک‌سری = نمونه ناکافی)", "CI" in rep["note"])

print("\n۷. CLI — همان قراردادی که داشبورد صدا می‌زند")
tmp = Path(tempfile.mkdtemp(prefix="meta-"))
kl = tmp / "k.json"
kl.write_text(json.dumps(cd))
r = subprocess.run([sys.executable, str(META), "signal", "--klines", str(kl)],
                   capture_output=True, text=True)
out = json.loads(r.stdout)
check("signal از CLI جواب JSON می‌دهد", r.returncode == 0 and "signal" in out)
r2 = subprocess.run([sys.executable, str(META), "backtest", "--klines", str(kl)],
                    capture_output=True, text=True)
check("backtest از CLI اجرا می‌شود",
      r2.returncode == 0 and "classic_tp2" in r2.stdout)

print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
