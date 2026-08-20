"""آزمون خود-درمانی دفتر معامله — حلقهٔ احیا (کشف ۲۰ اوت).

صحنهٔ واقعی که این را لازم کرد: یک معاملهٔ ASTERUSDT (sig-smc، باز ۰۸:۱۷)
دوازده بار در دفتر بسته ثبت شده بود — همان معامله، دوازده زمانِ بستهٔ
متفاوت. کل دفتر ۶٬۸۰۸ ردیف اضافه از ۱۶٬۳۷۶ داشت (۴۲٪) و میانگین دفتر
ارسالی را از +0.14R به +0.34R باد کرده بود.

    python3 -m hamid.test_paper_dedup
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import memory, paper                                 # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


# ایزوله‌سازی کامل از تولید
tmp = Path(tempfile.mkdtemp(prefix="pdedup-"))
paper.OPEN = tmp / "open.jsonl"
paper.CLOSED = tmp / "closed.jsonl"
memory.digest_closed = lambda rows: None
paper.brain.room_log = lambda *a, **k: None
paper._candles_since = lambda sym, opened: []         # بدون شبکه


def tr(sym, opened, closed=None, stage="sig-smc", r=0.1):
    row = {"sym": sym, "dir": "LONG", "entry": 1.0, "sl": 0.99, "tp1": 1.02,
           "opened": opened, "filled": opened, "why": {"stage": stage}}
    if closed is not None:
        row.update({"closed": closed, "R": r, "outcome": "trail"})
    return row


def w(p, rows):
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


print("\n۱. جمع‌کردن تکراری‌های دفتر بسته — قدیمی‌ترین بسته‌شدن می‌ماند")
w(paper.CLOSED,
  [tr("ASTERUSDT", 100, closed=c) for c in (500, 300, 400, 300, 700)]
  + [tr("BUSDT", 200, closed=250, stage="practice")])
removed, ids = paper.dedup_closed()
rows = paper._read(paper.CLOSED)
check("۵ بسته‌شدنِ یک معامله → ۱ ردیف (۴ حذف)", removed == 4, f"{removed}")
aster = [t for t in rows if t["sym"] == "ASTERUSDT"]
check("قدیمی‌ترین زمان بسته ماند (۳۰۰)", aster[0]["closed"] == 300)
check("معاملهٔ سالم دست نخورد",
      any(t["sym"] == "BUSDT" for t in rows) and len(rows) == 2)
check("هویت‌ها برای فیلتر زامبی برگشتند", len(ids) == 2)

print("\n۲. دفتر تمیز → هیچ بازنویسی")
removed2, _ = paper.dedup_closed()
check("اجرای دوم چیزی حذف نمی‌کند (idempotent)", removed2 == 0)

print("\n۳. زامبیِ احیاشده در دفتر باز، دوباره بسته نمی‌شود")
# همان صحنهٔ ASTER: معامله قبلاً بسته شده ولی merge آن را به open برگردانده
import time as _t
_now = int(_t.time() * 1000)
w(paper.OPEN, [tr("ASTERUSDT", 100),                  # زامبی — در closed هست
               tr("CUSDT", _now - 60_000, stage="practice")])  # تازه‌باز
paper.mark()
op = paper._read(paper.OPEN)
cl = paper._read(paper.CLOSED)
check("زامبی از دفتر باز حذف شد",
      all(t["sym"] != "ASTERUSDT" for t in op))
check("و بستهٔ تازه‌ای برایش ثبت نشد (نه بار سیزدهم)",
      sum(1 for t in cl if t["sym"] == "ASTERUSDT") == 1)
check("سفارش واقعاً باز سر جایش ماند",
      any(t["sym"] == "CUSDT" for t in op))

print("\n۴. هویت، دفترها را قاطی نمی‌کند")
# همان نماد و لحظه در دو دفتر (practice و sig-smc) دو معاملهٔ جداست
w(paper.CLOSED, [tr("DUSDT", 100, closed=200, stage="practice"),
                 tr("DUSDT", 100, closed=210, stage="sig-smc")])
removed3, _ = paper.dedup_closed()
check("دو دفترِ متفاوت = دو معاملهٔ جدا، هیچ حذفی", removed3 == 0)

print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
