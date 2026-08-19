"""اندازه‌گیری ۳×‌شدن میز تمرین — نه ادعا، آزمایش (دستور حمید ۱۸ اوت).

فرض اول («نخ بیشتر بده») غلط از آب درآمد و همین آزمون ردش کرد: ۲۴ نخ در
برابر ۸ نخ فقط ۰.۹۹× شد، چون گلوگاه CPUی بازپخش است و GIL پایتون
نمی‌گذارد نخ‌ها روی CPU موازی شوند. رفعِ درست، دوفازی شد: fetch (شبکه)
با نخ، بازپخش (CPU) با پردازه. این آزمون دو چیز را هم‌زمان قفل می‌کند:

  ۱. توان عملیاتی مسیر جدید نسبت به مسیر قدیمی ≥ ۲.۵× (اندازه‌گیری واقعی
     روی ۳۰ ارز با fetch تأخیردار؛ آخرین عدد: ۳.۴۴×).
  ۲. **خروجی معامله‌به‌معامله یکسان است** — سرعتِ خریداری‌شده با تغییر
     رفتار، سرعت نیست، باگ است.

    python3 -m hamid.test_trainer_speed
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import memory, paper, trainer               # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


# ── ایزوله‌سازی کامل تولید (درس ۱۵ اوت) ────────────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="tspeed-"))
paper.CLOSED = tmp / "closed.jsonl"
trainer.STATE = tmp / "state.json"
memory.digest_closed = lambda rows: None
paper.brain.room_log = lambda *a, **k: None

# بازار ساختگی با ستاپ واقعی (همان الگوی test_bridge — روند + پولبک)
def market(seed):
    out, px = [], 100.0 + seed
    for i in range(500):
        px += 0.6 if (i + seed) % 10 < 7 else -0.5
        out.append({"t": 1_700_000_000_000 + i * 900_000, "o": px - 0.1,
                    "h": px + 0.4, "l": px - 0.4, "c": px,
                    "v": 100 + ((i + seed) % 10) * 40})
    return out


MKTS = {f"S{i}USDT": market(i) for i in range(30)}
FETCH_DELAY = 0.12                                    # ~تأخیر یک فراخوان صرافی


def slow_fetch(sym, tf, bars):
    time.sleep(FETCH_DELAY)
    return MKTS[sym]


def legacy_run():
    """مسیر قدیمی: fetch+بازپخش در یک نخ، ۸ کارگر — همان کدی که بود."""
    trainer.STATE.unlink(missing_ok=True)
    paper.CLOSED.unlink(missing_ok=True)
    st = {}
    t0 = time.time()
    out = []
    def one(sym):
        cd = slow_fetch(sym, "15m", 2000)
        return trainer.replay_symbol(sym, cd, after_ms=0, tf="15m")
    with ThreadPoolExecutor(max_workers=8) as pool:
        for trades, frontier in pool.map(one, list(MKTS)):
            out.extend(trades)
    return out, time.time() - t0


def new_run():
    trainer.STATE.unlink(missing_ok=True)
    paper.CLOSED.unlink(missing_ok=True)
    t0 = time.time()
    trades = trainer.run(symbols=list(MKTS), tfs=["15m"], quiet=True,
                         fetch=slow_fetch, budget_s=600)
    return trades, time.time() - t0


print("\n۱. توان عملیاتی — مسیر قدیمی (نخ ۸تایی) در برابر دوفازی (نخ+پردازه)")
tr8, t8 = legacy_run()
tr24, t24 = new_run()
speed = t8 / t24 if t24 > 0 else 0
print(f"   قدیمی: {t8:.1f}s · جدید: {t24:.1f}s · نسبت {speed:.2f}×")
check(f"دست‌کم ۲.۵× سریع‌تر (اندازه‌گیری: {speed:.2f}×)", speed >= 2.5)

print("\n۲. سرعت نباید رفتار را عوض کند")
key8 = sorted((t["sym"], t["opened"], t["dir"], t["R"]) for t in tr8)
key24 = sorted((t["sym"], t["opened"], t["dir"], t["R"]) for t in tr24)
check(f"خروجی معامله‌به‌معامله یکسان است ({len(tr8)} معامله)", key8 == key24)
check("معامله واقعاً ساخته شد (آزمونِ خالی بی‌ارزش است)", len(tr8) > 0)

print("\n۳. مقدار جدید در خود فایل نشسته است (نه فقط این آزمون)")
src = (Path(__file__).parent / "trainer.py").read_text()
check("فاز پردازه‌ای در trainer.py نشسته است",
      "ProcessPoolExecutor" in src and "_replay_job" in src)

print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
