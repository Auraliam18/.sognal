"""آزمون آفلاین سه اتاق جدید ایجنت: میز تمرین، پایش آلارم، مرور دوساعته.

    python3 -m hamid.test_agent_loop
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import cycle                                       # noqa: E402
from hamid import paper                                       # noqa: E402
import brain                                                  # noqa: E402
import sources                                                # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


# ── میز تمرین ──────────────────────────────────────────────────────────────
reads = [
    SimpleNamespace(symbol="AUSDT", setup=None, trend_4h="up",
                    blocks=[{"low": 1.0, "high": 1.1, "dir": "bullish"}]),
    SimpleNamespace(symbol="BUSDT", setup={"dir": "LONG"}, trend_4h="up",
                    blocks=[{"low": 1.0, "high": 1.1, "dir": "bullish"}]),
    SimpleNamespace(symbol="CUSDT", setup=None, trend_4h="down",
                    blocks=[{"low": 2.0, "high": 2.2, "dir": "bearish"}]),
    SimpleNamespace(symbol="DUSDT", setup=None, trend_4h="up", blocks=[]),
]
pc = cycle.practice_candidates(reads)
syms = [x["symbol"] for x in pc]
check("ستاپ‌دار و بی‌بلاک حذف، بقیه تمرین", syms == ["AUSDT", "CUSDT"])
check("همه برچسب practice دارند", all(x["stage_tag"] == "practice" for x in pc))
lng = pc[0]
check("لانگ: ورود سقف باکس، استاپ زیر", lng["dir"] == "LONG" and lng["entry"] == 1.1 and lng["sl"] < 1.0)
sht = pc[1]
check("شورت آینه است", sht["dir"] == "SHORT" and sht["entry"] == 2.0 and sht["sl"] > 2.2)
check("هدف‌ها ۱.۵ و ۲.۵ برابر ریسک", abs((lng["tp1"] - lng["entry"]) / (lng["entry"] - lng["sl"]) - 1.5) < 1e-9)

# ── پایش آلارم (شبکه و اتاق شبیه‌سازی‌شده) ────────────────────────────────
ROOM = {"alarms": [
    {"sym": "HITUSDT", "price": 1.0, "dir": "LONG", "stage": "ARMED", "strategy": "pump"},
    {"sym": "FARUSDT", "price": 5.0, "dir": "LONG", "stage": "ARMED"},
    {"sym": "GONEUSDT", "price": 2.0, "dir": "LONG", "stage": "ARMED"},
    {"sym": "OLDUSDT", "price": 9.0, "stage": "TRIGGERED"},
]}
SAVED = {}


def fake_room_load(room, default=None):
    return json.loads(json.dumps(ROOM)) if room == "radar" else (default or {})


def fake_room_save(room, st):
    SAVED[room] = st


def fake_klines(sym, tf, n):
    # (t,o,h,l,c,v) — HIT ورود را لمس می‌کند، FAR دور است، GONE ۸٪ زیر ورود بسته
    px = {"HITUSDT": (0.98, 1.05, 1.02), "FARUSDT": (5.5, 5.9, 5.8),
          "GONEUSDT": (1.80, 1.86, 1.84)}[sym]
    lo, hi, c = px
    return [[i, c, hi, lo, c, 100] for i in range(3)]


_orig = (brain.room_load, brain.room_save, sources.klines)
brain.room_load, brain.room_save, sources.klines = fake_room_load, fake_room_save, fake_klines
cycle.brain.room_load, cycle.brain.room_save = fake_room_load, fake_room_save
cycle.sources.klines = fake_klines
fired = cycle.watch_alarms()
brain.room_load, brain.room_save, sources.klines = _orig
cycle.brain.room_load, cycle.brain.room_save = _orig[0], _orig[1]
cycle.sources.klines = _orig[2]

check("فقط آلارم لمس‌شده فعال شد", [a["sym"] for a in fired] == ["HITUSDT"])
kept = {a["sym"]: a for a in SAVED["radar"]["alarms"]}
check("فعال‌شده TRIGGERED شد", kept["HITUSDT"]["stage"] == "TRIGGERED")
check("دور هنوز مسلح است", kept["FARUSDT"]["stage"] == "ARMED")
check("۷٪ آن‌طرف ورود → باطل با دلیل", kept["GONEUSDT"]["stage"] == "DEAD" and "از دست رفت" in kept["GONEUSDT"]["why_dead"])
check("آلارم قبلاً فعال‌شده دست نخورد", kept["OLDUSDT"]["stage"] == "TRIGGERED")

# ── مرور دوساعته ───────────────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp())
_closed_orig = paper.CLOSED
paper.CLOSED = tmp / "closed.jsonl"
now = int(time.time() * 1000)
rows = [{"sym": "XUSDT", "dir": "LONG", "R": 1.5, "outcome": "target",
         "closed": now - 1000, "why": {"stage": "second"}},
        {"sym": "YUSDT", "dir": "LONG", "R": -1.0, "outcome": "stop",
         "closed": now - 2000, "why": {"stage": "practice"}},
        {"sym": "ZUSDT", "dir": "LONG", "R": None, "outcome": "expired",
         "closed": now - 3000, "why": {"stage": "second"}}]
paper.CLOSED.write_text("\n".join(json.dumps(r) for r in rows))

RSTATE = {}
def rl2(room, default=None):
    return RSTATE.get(room, default or {})
def rs2(room, st):
    RSTATE[room] = st
cycle.brain.room_load, cycle.brain.room_save = rl2, rs2
rv = cycle.review_cycle()
check("مرور اول اجرا شد و دو دفتر را جدا شمرد",
      rv and rv["closed"] == 2 and "second" in rv["books"] and "practice" in rv["books"])
check("منقضی شمرده نشد", rv and "expired" not in str(rv["books"]))
rv2 = cycle.review_cycle()
check("قبل از ۲ ساعت دوباره مرور نمی‌کند", rv2 is None)
cycle.brain.room_load, cycle.brain.room_save = _orig[0], _orig[1]
paper.CLOSED = _closed_orig

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های حلقهٔ ایجنت گذشتند")
