"""آزمون آفلاین حافظهٔ ایجنت — چرخهٔ تحلیل → یادگیری → ذخیره → استفاده.

    python3 -m hamid.test_memory
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import memory                                      # noqa: E402
import brain                                                  # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


tmp = Path(tempfile.mkdtemp())
memory.LESSONS = tmp / "lessons.json"

LEARNED, INDEXED = [], []
_orig = (brain.learn, brain.build_index, brain.recall)
brain.learn = lambda e: LEARNED.append(e)
brain.build_index = lambda: INDEXED.append(1)

# ── ذخیره و بازیابی درس ────────────────────────────────────────────────────
memory.remember("تحلیل", "AUSDT", "درس اول دربارهٔ A")
memory.remember("ضعف", "-", "دیر رسیدیم به خوشه")
memory.remember("نتیجه", "AUSDT", "برد A با روند موافق")
check("درس‌ها ذخیره و جدیدترین اول", memory.lessons()[0]["text"].startswith("برد A"))
check("فیلتر بر اساس ارز", [l["kind"] for l in memory.lessons(sym="AUSDT")] == ["نتیجه", "تحلیل"])
check("فیلتر بر اساس نوع", memory.lessons(kind="ضعف")[0]["sym"] == "-")

# ── هضم معامله‌های بسته ────────────────────────────────────────────────────
trades = [
    {"sym": "BUSDT", "dir": "LONG", "R": 1.5, "outcome": "target",
     "why": {"stage": "second", "trend_4h": "up", "fear": 40}},
    {"sym": "CUSDT", "dir": "SHORT", "R": -1.0, "outcome": "stop",
     "why": {"stage": "practice", "trend_4h": "down"}},
    {"sym": "DUSDT", "dir": "LONG", "R": None, "outcome": "expired", "why": {}},
]
fed = memory.digest_closed(trades)
check("دو معامله هضم شد، منقضی نه", fed == 2 and len(LEARNED) == 2)
check("تجربه با شرایط لحظهٔ باز شدن رفت",
      LEARNED[0]["strategy"] == "second" and LEARNED[0]["trend_4h"] == "up")
check("ایندکس دانش بازسازی شد", len(INDEXED) == 1)
lb = memory.lessons(sym="BUSDT")[0]
check("درسِ برد دلیلش را دارد", "✅ برد" in lb["text"] and "trend_4h=up" in lb["text"])
lc = memory.lessons(sym="CUSDT")[0]
check("درسِ باخت علتش را دارد", "❌ باخت" in lc["text"])

# ── مشورت قبل از صدور ──────────────────────────────────────────────────────
brain.recall = lambda **k: {"symbol": {"n": 14, "hit": 64.3, "ev": 0.21}, "verdict": "good"}
m = memory.consult("BUSDT", "LONG")
check("جملهٔ صریح با عدد", m["note"] and "14 مورد" in m["note"] and "64.3٪" in m["note"])
check("نمونهٔ کافیِ خوب → رتبهٔ مثبت", m["adj"] > 0)

brain.recall = lambda **k: {"symbol": {"n": 9, "hit": 22.0, "ev": -0.3}, "verdict": "bad"}
check("نمونهٔ کافیِ بد → رتبهٔ منفی", memory.consult("X", "LONG")["adj"] < 0)

brain.recall = lambda **k: {"symbol": {"n": 4, "hit": 100.0, "ev": 0.9}, "verdict": "thin"}
m4 = memory.consult("X", "LONG")
check("زیر ۸ مورد: ذکر می‌شود ولی رتبه دست نمی‌خورد", m4["note"] and m4["adj"] == 0)

brain.recall = lambda **k: {"verdict": "thin"}
mA = memory.consult("AUSDT", "LONG")
check("بدون آمار، آخرین درس ذکر می‌شود", mA["note"] and "آخرین تجربه" in mA["note"])

brain.learn, brain.build_index, brain.recall = _orig

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های حافظه گذشتند")
