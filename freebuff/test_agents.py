#!/usr/bin/env python3
"""آزمون آفلاین ایجنت‌ها — حافظه، dedupe، ضدتکرار دور، مقاومت به خطا.

هیچ شبکه‌ای صدا زده نمی‌شود؛ توابع ایجنت با monkeypatch ایزوله می‌شوند.

    python3 freebuff/test_agents.py
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freebuff import agents as ag                         # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'OK' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)

    # ── حافظه: append + dedupe + سقف ─────────────────────────────────────
    mem = tmp / "agent-test.json"
    n1 = ag.append_memory(mem, [{"data": {"t": "خبر A"}},
                                {"data": {"t": "خبر B"}}])
    check("دو مورد تازه اضافه شد", n1 == 2)
    n2 = ag.append_memory(mem, [{"data": {"t": "خبر A"}},   # تکراری
                                {"data": {"t": "خبر C"}}])  # تازه
    check("تکراری اضافه نمی‌شود، تازه اضافه می‌شود", n2 == 1)
    j = json.loads(mem.read_text())
    check("حافظه سه مورد دارد", len(j) == 3)
    check("هر مورد اثر انگشت و مهر زمانی دارد",
          all("fp" in m and "t" in m and "data" in m for m in j))

    # سقف طول: قدیمی‌ها بیرون می‌افتند
    for i in range(ag.MAX_MEM_ITEMS + 15):
        ag.append_memory(mem, [{"data": {"n": f"x{i}"}}])
    j = json.loads(mem.read_text())
    check("سقف حافظه رعایت شد", len(j) == ag.MAX_MEM_ITEMS,
          f"{len(j)} items")

    # ── فایل خراب → پیش‌فرض سالم ─────────────────────────────────────────
    bad = tmp / "bad.json"
    bad.write_text("{نه json هست")
    check("فایل خراب = پیش‌فرض، نه کرش",
          ag.load_json(bad, []) == [])

    # ── run_round: همهٔ ایجنت‌ها با منابع مصنوعی ─────────────────────────
    real_agents = dict(ag.AGENTS)
    calls = []

    def fake_ok(ctx):
        calls.append("ok")
        return {"rows": ["r1"], "flag": None,
                "memory_items": [{"data": {"k": calls[0]}}]}

    def fake_boom(ctx):
        raise RuntimeError("صرافی جواب نداد")

    ag.AGENTS.clear()
    ag.AGENTS["good"] = fake_ok
    ag.AGENTS["bad"] = fake_boom
    ag.SIGNALS = tmp / "signals"
    ag.MEMORY = tmp / "brain"

    out = ag.run_round(force=True)
    check("دور کامل شد با هر دو ایجنت", set(out["agents"]) == {"good", "bad"})
    check("ایجنت سالم سبز", out["agents"]["good"]["ok"] is True)
    check("ایجنت مرده قرمز ولی دور نمرده", out["agents"]["bad"]["ok"] is False
          and "RuntimeError" in out["agents"]["bad"]["error"])
    check("خروجی دور روی دیسک است", (tmp / "signals" / "round-state.json").exists())
    check("امضای پنل روی خروجی", out["panel"] == "پنل فری‌باف ۱")
    mem_good = json.loads((tmp / "brain" / "agent-good.json").read_text())
    check("حافظهٔ ایجنت سالم پر شد", len(mem_good) == 1)
    check("حافظهٔ ایجنت مرده ساخته نشد یا خالی است",
          not (tmp / "brain" / "agent-bad.json").exists())

    # ── ضدتکرار دور: بلافاصله دوباره = همان خروجی ────────────────────────
    calls.clear()
    out2 = ag.run_round(force=False)
    check("دور زودهنگام نچرخید", not calls)
    check("خروجی همان قبلی است", out2["generated"] == out["generated"])

    # ولی force می‌چرخاند
    out3 = ag.run_round(force=True)
    check("دور forced می‌چرخد", len(calls) == 1)

    # نوشتن اتمیک: فایل tmp وسط کار باقی نمی‌ماند
    leftovers = list((tmp / "signals").glob("*.tmp"))
    check("فایل موقتی تمیز شد", not leftovers)

    ag.AGENTS.update(real_agents)

    # ── وب‌گردی بی‌کلید: ساکت رد می‌شود، نه خطا ──────────────────────────
    old_key = ag.TAVILY_KEY
    ag.TAVILY_KEY = ""
    check("بی‌کلید: None، بدون کرش", ag._tavily("btc news") is None)

print(f"\n{'همهٔ آزمون‌ها سبز' if FAIL == 0 else f'{FAIL} آزمون قرمز'}")
sys.exit(1 if FAIL else 0)
