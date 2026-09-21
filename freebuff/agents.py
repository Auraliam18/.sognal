#!/usr/bin/env python3
"""ایجنت‌های خودکار پنل فری‌باف ۱ — هر ۵ دقیقه، با وب‌گردی و حافظه.

هر ایجنت یک مأموریت مشخص دارد، هر دور:
  ۱. از منابعِ مأمورش می‌خواند (رایگان، بدون کلید — و اگر کلید Tavily
     در Secrets باشد، جستجوی وب هم به دانشش اضافه می‌شود).
  ۲. نتیجه را به حافظهٔ خودش می‌چسباند (dedupe با اثر انگشت محتوا —
     خبر تکراری حافظه را نمی‌بلعد).
  ۳. اگر چیزی «داغ» باشد فلاگ می‌زند و پنل روشنش نشان می‌دهد.

ایجنت‌ها تصمیم سیگنال نمی‌گیرند — دادهٔ بهتر تولید می‌کنند تا گلوگاه
سیگنالِ پنل فری‌باف ۱ با چشم باز تصمیم بگیرد. حکم سیگنال همیشه از
موتور می‌آید، نه از ایجنت وب‌گرد.

قواعد ایمنی (قرض‌گرفته از درس‌های این مخزن):
  · هر ایجنت فایل حافظهٔ یکتای خودش را دارد — دو نویسنده روی یک فایل نیست.
  · هر دور با try/except کامل بسته می‌شود: مرگ یک ایجنت دورِ بقیه را
      نمی‌کشد، و مرگ کل دور خروجی قبلی را خراب نمی‌کند (نوشتن اتمیک).
  · سهمیهٔ وب‌گردی محدود است — ایجنت وب‌گرد در حالت بی‌کلید، ساکت رد
      می‌شود نه خطا.

    python3 freebuff/agents.py            # یک دور کامل
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "claude-liam-signal" / "python"))

ROOT = HERE.parent
SIGNALS = ROOT / "signals" / "freebuff"
MEMORY = ROOT / "brain" / "freebuff"
STEP_MS = 5 * 60 * 1000
MAX_MEM_ITEMS = 120                     # هر حافظه؛ قدیمی‌ها بی‌رحمانه بیرون

TAVILY_KEY = os.getenv("TAVILY_API_KEY") or ""


# ── زیرساخت مشترک ─────────────────────────────────────────────────────────

def _fingerprint(obj):
    """اثر انگشت محتوا — برای dedupe حافظه. خبرِ تکراری نباید جا بگیرد."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:                                # noqa: BLE001
        return default


def append_memory(path, items):
    """چسباندن به حافظهٔ ایجنت — dedupe با اثر انگشت، سقف طول، مهر زمانی.

    فقط موارد تازه اضافه می‌شوند؛ تعدادشان برمی‌گردد تا گزارش دور صادق
    باشد («۳ مورد تازه» نه «۳ مورد» تکراریِ همیشه)."""
    mem = load_json(path, [])
    seen = {m.get("fp") for m in mem}
    added = 0
    for it in items:
        fp = _fingerprint(it.get("data"))
        if fp in seen:
            continue
        seen.add(fp)
        mem.append({"fp": fp, "t": int(time.time() * 1000),
                    "data": it["data"]})
        added += 1
    mem = mem[-MAX_MEM_ITEMS:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mem, ensure_ascii=False, separators=(",", ":")))
    return added


def _tavily(query, max_results=3):
    """جستجوی وب — فقط با کلید؛ بی‌کلید None تا ایجنت ساکت رد شود."""
    if not TAVILY_KEY:
        return None
    import urllib.request
    body = json.dumps({"query": query, "max_results": max_results}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {TAVILY_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.load(r)
        return [{"title": x.get("title"), "url": x.get("url"),
                 "snippet": (x.get("content") or "")[:200]}
                for x in (j.get("results") or [])]
    except Exception:                                # noqa: BLE001
        return None


# ── ایجنت‌ها ───────────────────────────────────────────────────────────────

def agent_structure(ctx):
    """ایجنت ساختار بازار — اسکن سریع فیوچرز نمادهای اصلی، رادار فشرده."""
    from freebuff import futures
    rows = []
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        try:
            kl = futures.klines(sym, "15m", 60)
            closes = [k[4] for k in kl]
            chg = (closes[-1] - closes[0]) / closes[0] * 100
            rows.append({"symbol": sym, "chg_15m_x40": round(chg, 2),
                         "last": closes[-1]})
        except Exception as e:                       # noqa: BLE001
            rows.append({"symbol": sym, "error": type(e).__name__})
    hot = [r for r in rows if r.get("chg_15m_x40") is not None
           and abs(r["chg_15m_x40"]) > 2.0]
    return {"rows": rows,
            "flag": "حرکت بزرگ فیوچرز: " + ", ".join(
                f"{r['symbol']} {r['chg_15m_x40']:+.1f}%" for r in hot) if hot else None,
            "memory_items": [{"data": r} for r in rows]}


def agent_derivatives(ctx):
    """ایجنت مشتقات — OI، فاندینگ، لانگ/شورت؛ همان فایل فری‌باف/فیوچرز."""
    from freebuff import futures
    out = {}
    try:
        h = futures.oi_history("BTCUSDT")
        out["oi"] = futures.oi_pulse(h)
    except Exception as e:                           # noqa: BLE001
        out["oi"] = {"verdict": f"OI نیامد ({type(e).__name__})"}
    try:
        f = futures.funding(30)
        out["funding"] = futures.funding_verdict(f)
    except Exception as e:                           # noqa: BLE001
        out["funding"] = {"verdict": f"فاندینگ نیامد ({type(e).__name__})"}
    try:
        out["longshort"] = futures.longshort_verdict(futures.longshort())
    except Exception as e:                           # noqa: BLE001
        out["longshort"] = f"نسبت نیامد ({type(e).__name__})"

    items = [{"data": {"oi": out["oi"]["verdict"],
                       "funding": out["funding"]["verdict"],
                       "longshort": out["longshort"]}}]
    flag = None
    if out["oi"].get("chg_pct") is not None and abs(out["oi"]["chg_pct"]) > 3:
        flag = out["oi"]["verdict"]
    return {"rows": [], "summary": out, "flag": flag, "memory_items": items}


def agent_news(ctx):
    """ایجنت خبر — RSS کریپتو + ترندینگ؛ داغ‌ها فلاگ می‌خورند."""
    from hamid import intel
    n = intel.news()
    tr = []
    try:
        tr = intel.trending()
    except Exception:                                # noqa: BLE001
        pass
    headlines = [h["title"] for h in n.get("headlines", [])]
    # وب‌گردی: اگر کلید هست، یک سؤال داغ را عمیق‌تر بپرس
    web = None
    if n.get("hot"):
        web = _tavily(f"crypto market news today {n['hot'][0]['title'][:60]}")
    items = [{"data": {"src": h["source"], "title": h["title"]}}
             for h in n.get("headlines", [])[:20]]
    return {"rows": headlines[:8], "trending": tr[:5],
            "hot": [h["title"] for h in n.get("hot", [])],
            "web": web,
            "flag": n["hot"][0]["title"] if n.get("hot") else None,
            "memory_items": items}


def agent_macro(ctx):
    """ایجنت کلان — تقویم اقتصادی + ترس‌وطمع؛ همان منابع اتاق دامیننس."""
    from hamid import intel
    from freebuff import dominance as dom
    cal = []
    try:
        cal = intel.calendar().get("next_48h", [])
    except Exception:                                # noqa: BLE001
        pass
    fg = dom.fear_greed()
    flag = cal[0]["title"] + f" ({cal[0]['in_hours']}h)" if cal and cal[0]["in_hours"] <= 4 else None
    items = [{"data": {"event": e["title"], "in_hours": e["in_hours"]}} for e in cal]
    if fg:
        items.append({"data": {"fear_greed": fg}})
    return {"rows": [f"{e['title']} ({e['in_hours']}h)" for e in cal[:5]],
            "fear_greed": fg, "flag": flag, "memory_items": items}


AGENTS = {
    "structure": agent_structure,
    "derivatives": agent_derivatives,
    "news": agent_news,
    "macro": agent_macro,
}

DESCRIPTIONS = {
    "structure": "اسکن ساختار فیوچرز نمادهای اصلی",
    "derivatives": "OI/فاندینگ/لانگ‌شورت — سوخت لیکویید کدام سمت است",
    "news": "خبرهای داغ کریپتو + ترندینگ + وب‌گردی عمیق",
    "macro": "تقویم کلان و سناریوسازی بازار — پنجرهٔ ریسک",
}


# ── دور کامل ──────────────────────────────────────────────────────────────

def run_round(force=False):
    """یک دور کامل از همهٔ ایجنت‌ها؛ خروجی اتمیک — مرگ نیمه‌راه دورِ
    قبلی را خراب نمی‌کند."""
    SIGNALS.mkdir(parents=True, exist_ok=True)
    state_path = SIGNALS / "round-state.json"
    state = load_json(state_path, {})
    now_ms = int(time.time() * 1000)

    # ضدتکرار دور: بدون force، زودتر از ۴.۵ دقیقه دوباره نچرخ
    last = state.get("generated") or 0
    if not force and now_ms - last < STEP_MS * 0.9:
        return state

    results = {}
    for name, fn in AGENTS.items():
        t0 = time.time()
        entry = {"agent": name, "desc": DESCRIPTIONS.get(name, ""), "at": now_ms}
        try:
            r = fn({})
            added = append_memory(MEMORY / f"agent-{name}.json",
                                  r.pop("memory_items", []))
            entry.update(r)
            entry["memory_added"] = added
            entry["ok"] = True
        except Exception as e:                       # noqa: BLE001
            entry["ok"] = False
            entry["error"] = f"{type(e).__name__}: {e}"[:200]
        entry["took_s"] = round(time.time() - t0, 1)
        results[name] = entry

    # وب‌گردی فعال بود؟ صادقانه ثبت می‌شود، برند ندارد
    web_active = bool(TAVILY_KEY)
    out = {
        "panel": "پنل فری‌باف ۱",
        "generated": now_ms,
        "generated_iso": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "web_research": "فعال" if web_active else "غیرفعال (کلید Tavily در Secrets نیست — ایجنت‌ها فقط منابع رایگان را می‌خوانند)",
        "agents": results,
        "flags": [v["flag"] for v in results.values() if v.get("flag")],
    }
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    tmp.replace(state_path)
    print(f"دور کامل شد — {sum(1 for v in results.values() if v.get('ok'))}/{len(results)} ایجنت سبز")
    return out


if __name__ == "__main__":
    force = "--force" in sys.argv
    run_round(force=force)
