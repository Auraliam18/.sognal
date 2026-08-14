"""آزمون‌های عیب‌یاب و تعمیرکار + علت‌یابی گزارش خالی (دستور حمید ۱۴ اوت).

بدون شبکه؛ همهٔ نوشتن‌ها به مسیر موقت — مغز واقعی دست نمی‌خورد.

  ۱. عیب‌یاب کوچک شدن حافظهٔ انباشته را عیب جدی می‌گیرد (ترس حمید)
  ۲. حافظهٔ بزرگ‌شده سالم گزارش می‌شود
  ۳. مرور دوساعتهٔ خالی، علت‌یابی خودکار دارد — نه فقط یک جمله
  ۴. سه بازهٔ خالی پیاپی → درس دائمی در حافظه
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
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


print("── عیب‌یاب و تعمیرکار ──")

import medic                                                    # noqa: E402

tmp = Path(tempfile.mkdtemp())
medic.OUT = tmp / "medic.json"
medic.OUT.write_text(json.dumps({"sick": False, "findings": [],
                                 "total_closed": 2031}))


def fetch_shrunk(url, timeout=25):
    if "hamid-latest" in url:
        return 200, json.dumps({"generated": time.time() * 1000,
                                "mode": "quiet", "why": "تست",
                                "paper": {"total_closed": 1500}}).encode()
    raise RuntimeError("این مسیر در تست مهم نیست")


medic.fetch = fetch_shrunk
sick, finds, wake, total = medic.examine()
check("کوچک شدن حافظه (۲۰۳۱→۱۵۰۰) عیب جدی است",
      sick and any("کوچک شد" in f for f in finds))
check("total برگردانده می‌شود", total == 1500)


def fetch_grown(url, timeout=25):
    if "hamid-latest" in url:
        return 200, json.dumps({"generated": time.time() * 1000,
                                "mode": "quiet", "why": "تست",
                                "paper": {"total_closed": 2100}}).encode()
    raise RuntimeError("x")


medic.fetch = fetch_grown
sick2, finds2, _, total2 = medic.examine()
check("حافظهٔ بزرگ‌شده سالم است", any("حافظهٔ انباشته سالم" in f for f in finds2))

print("── علت‌یابی مرور دوساعتهٔ خالی ──")

import brain                                                    # noqa: E402
from hamid import cycle, paper, memory                          # noqa: E402

tmp2 = Path(tempfile.mkdtemp())
paper.CLOSED = tmp2 / "closed.jsonl"
paper.OPEN = tmp2 / "open.jsonl"
paper.CLOSED.write_text("")
paper.OPEN.write_text('{"sym":"BTCUSDT"}\n{"sym":"ETHUSDT"}\n')
saved = {}
brain.room_load = lambda room, default=None: {"at": 0,
                                              "history": [{"closed": 0}, {"closed": 0}]}
brain.room_save = lambda room, j: saved.update(j)
cycle.act = lambda t: None
cycle.ROOT = tmp2
(tmp2 / "signals").mkdir()
(tmp2 / "signals" / "hamid-latest.json").write_text(json.dumps(
    {"mode": "quiet", "why": "بازار آرام", "reads": 31, "setups": []}))
import telegram as tg                                           # noqa: E402
tg.creds = lambda: (None, None)
memory.STORE = tmp2 / "lessons.json"

cycle.review_cycle()
v = saved["history"][0]["verdict"]
check("گزارش خالی علت‌یابی خودکار دارد", "علت‌یابی خودکار" in v)
check("معامله‌های باز را می‌بیند", "معاملهٔ کاغذی باز" in v)
check("رژیم سکوت را می‌گوید", "سکوت" in v)
check("شمارش خوانده‌شده‌ها را می‌گوید", "31 ارز" in v or "۳۱ ارز" in v)
lessons = memory.lessons(kind="عیب", limit=3)
check("سه بازهٔ خالی پیاپی → درس دائمی",
      any("سه مرور دوساعتهٔ پیاپی خالی" in (l.get("text") or "") for l in lessons))

real_medic = Path(__file__).resolve().parents[3] / "brain" / "medic.json"
check("مغز واقعی دست نخورد (medic.json تست جدا بود)",
      medic.OUT != real_medic)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون عیب‌یاب گذشت")
