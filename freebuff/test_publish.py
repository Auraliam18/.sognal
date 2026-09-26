#!/usr/bin/env python3
"""آزمون آفلاین لایهٔ انتشار — اثبات اینکه باگ کهنه‌خوردن برنمی‌گردد.

    python3 freebuff/test_publish.py

این آزمون عمداً منطق قدیمی (`cp -r` روی یک نام مشترک) را هم بازسازی
می‌کند و نشان می‌دهد کهFRESH را می‌بلعد — بعد نشان می‌دهد منطق جدید
همان ورودی را سالم رد می‌کند. اگر کسی روزی به الگوی قدیمی برگردد،
همین آزمون می‌ایستد.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freebuff import publish                          # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'OK' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


def _tree(root):
    """(signals, brain) با فایل‌های هم‌نام — همان شکلی که روی main بود."""
    sig = root / "signals" / "freebuff"
    mem = root / "brain" / "freebuff"
    for d in (sig, mem):
        d.mkdir(parents=True, exist_ok=True)
    # فایل‌های هم‌نام: این دقیقاً همان چیزی است که cp -r را خراب می‌کرد
    (sig / "dominance.json").write_text('{"gen":"FRESH","series_points":1400}')
    (sig / "futures.json").write_text('{"gen":"FRESH"}')
    (mem / "dominance.json").write_text('{"gen":"OLD","series_points":2}')
    (mem / "futures.json").write_text('{"gen":"OLD"}')
    (mem / "dominance-series.json").write_text('[{"t":1},{"t":2}]')
    return sig, mem


def _simulate_old_cp(tmp):
    """همان سه خط ورک‌فلو قبلی — عمداً غلط."""
    sig, mem = _tree(tmp)
    bk = tmp / "bk"
    bk.mkdir()
    shutil.copytree(sig, bk / "freebuff")
    shutil.copytree(mem, bk / "freebuff", dirs_exist_ok=True)   # بازنویسی هم‌نام‌ها
    return bk / "freebuff" / "dominance.json"


print("── اثبات باگ منطق قدیمی ──")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    old = json.loads(_simulate_old_cp(tmp).read_text())
    check("منطق قدیمی واقعاً FRESH را می‌بلعد (اثبات ریشه)",
          old["gen"] == "OLD",
          f"انتظار OLD گرفتیم، دیدیم {old['gen']}")
    check("منطق قدیمی points را ۲ نگه می‌دارد، نه ۱۴۰۰",
          old["series_points"] == 2)

print("── رفتار منطق جدید ──")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    sig, mem = _tree(tmp)
    root, stages = publish.snapshot_outputs(signals=sig, memory=mem)

    # فایل‌های هم‌نام نباید در پشتیبان قاطی شوند
    check("پشتیبان signals و brain جداست (بدون هم‌نام)",
          stages[sig] != stages[mem])
    check("نسخهٔ signals در پشتیبان خودش FRESH است",
          json.loads((stages[sig] / "dominance.json").read_text())["gen"] == "FRESH")
    check("نسخهٔ brain در پشتیبان خودش OLD است",
          json.loads((stages[mem] / "dominance.json").read_text())["gen"] == "OLD")

    # شبیه‌سازی reset --hard: درخت به حالت ریموت (کهنه) برمی‌گردد،
    # بعد باید دوباره بنشیند
    for f in list(sig.iterdir()) + list(mem.iterdir()):
        f.unlink()
    (mem / "dominance.json").write_text('{"gen":"OLD","series_points":2}')

    counts = publish.reapply(root, stages, signals=sig, memory=mem)
    check("بازگردانی چیزی برگرداند", sum(counts.values()) > 0, str(counts))
    check("نوشتهٔ تازهٔ signals سر جایش ماند",
          json.loads((sig / "dominance.json").read_text())["series_points"] == 1400)
    check("سری فقط در brain ماند",
          (mem / "dominance-series.json").exists() and
          not (sig / "dominance-series.json").exists())

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    sig, mem = _tree(tmp)
    a = publish.audit(signals=sig, memory=mem)
    check("audit ساختار تکراری بین درخت‌ها را می‌گیرد",
          not a["ok"] and any("تکراری" in p for p in a["problems"]),
          str(a["problems"]))

    for f in list(sig.iterdir()):
        f.unlink()
    for f in list(mem.iterdir()):
        f.unlink()
    a = publish.audit(signals=sig, memory=mem)
    check("audit روی درخت خالی ساکت است", a["ok"], str(a["problems"]))

print("── محافظ تازگی ──")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    sig, mem = _tree(tmp)
    root, stages = publish.snapshot_outputs(signals=sig, memory=mem)
    # فایل مقصد تازه‌تر از پشتیبان است (اجرای هم‌زمان) → نباید بمالانده شود
    (sig / "dominance.json").write_text('{"gen":"NEWEST","series_points":1500}')
    future = time.time() + 120
    import os
    os.utime(sig / "dominance.json", (future, future))
    publish.reapply(root, stages, signals=sig, memory=mem)
    got = json.loads((sig / "dominance.json").read_text())["gen"]
    check("فایلِ تازه‌تر از پشتیبان بازنویسی نمی‌شود", got == "NEWEST", got)

print("── JSON خراب و کهنگی ──")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    sig, mem = _tree(tmp)
    (sig / "dominance.json").write_text("{این JSON نیست")
    a = publish.audit(signals=sig, memory=mem)
    check("audit خرابی JSON را می‌گیرد",
          any("JSON خراب" in p for p in a["problems"]), str(a["problems"]))

    (sig / "dominance.json").write_text('{"ok":1}')
    old_t = time.time() - 7200
    os.utime(sig / "dominance.json", (old_t, old_t))
    a = publish.audit(signals=sig, memory=mem, stale_after_s=1800)
    check("audit کهنگی را می‌گیرد",
          any("کهنه" in p for p in a["problems"]), str(a["problems"]))

print("── اجرای مستقیم ماژول ──")
with tempfile.TemporaryDirectory() as td:
    r = subprocess.run([sys.executable, str(HERE / "publish.py"), "audit"],
                       capture_output=True, text=True, timeout=60)
    check("publish.py audit روی درخت واقعی پروژه اجرا می‌شود",
          r.returncode in (0, 1), f"rc={r.returncode} {r.stderr[:200]}")
    check("خروجی قابل خواندن است", "انتشار" in r.stdout, r.stdout[:200])

    r = subprocess.run([sys.executable, str(HERE / "publish.py"), "bogus"],
                       capture_output=True, text=True, timeout=60)
    check("فرمان ناشناخته خطای روشن می‌دهد",
          r.returncode == 2 and "usage" in r.stderr, r.stderr[:200])

print("── حالت ذخیره‌شده (پل بین stage و reapply) ──")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    sig, mem = _tree(tmp)
    state = tmp / "state.json"
    root, stages = publish.snapshot_outputs(signals=sig, memory=mem, state=state)
    check("state روی دیسک نوشته شد", state.exists())
    for f in list(sig.iterdir()) + list(mem.iterdir()):
        f.unlink()
    loaded_root, loaded_stages = publish.load_state(state)
    check("state خوانده می‌شود و به همان مسیرها اشاره دارد",
          loaded_root == root and set(map(str, loaded_stages)) == set(map(str, stages)))
    counts = publish.reapply(loaded_root, loaded_stages, signals=sig, memory=mem)
    check("سری بعد از round-trip کامل هنوز در brain هست",
          (mem / "dominance-series.json").exists())
    check("خروجی تازه بعد از round-trip کامل سالم است",
          json.loads((sig / "dominance.json").read_text())["series_points"] == 1400)
    # فایل state نباید به ریشهٔ پروژه نشت کند
    check("statefile موقت در ریشهٔ پروژه ساخته نشد",
          not (publish.ROOT / "fb-bk-state.json").exists())

print("── reapply بدون پشتیبان نباید ران را بیندازد ──")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    state = tmp / "missing.json"
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys,pathlib;sys.path.insert(0,'.');from freebuff import publish;"
         "publish.STATE=pathlib.Path(sys.argv[2]);"
         "sys.argv=['publish.py','reapply'];"
         "sys.exit(publish.main())", "x", str(state)],
        capture_output=True, text=True, timeout=60)
    check("reapply بدون پشتیبان خطا نمی‌دهد", r.returncode == 0, r.stderr[:300])
    check("و هشدار روشن می‌دهد", "پشتیبانی نبود" in r.stdout, r.stdout[:200])

print()
if FAIL:
    print(f"{FAIL} آزمون شکست خورد")
    sys.exit(1)
print("همهٔ آزمون‌ها سبز")
