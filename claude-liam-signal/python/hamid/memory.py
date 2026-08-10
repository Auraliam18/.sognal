"""حافظهٔ ایجنت — چرخه‌ای که حمید خواست، کلمه به کلمه:

    تحلیل → یادگیری → ذخیره در حافظه → استفاده در تحلیل بعدی → بهبود

دو لایه دارد:

۱. حافظهٔ آماری (brain.learn / recall): هر معاملهٔ بسته با شرایط لحظهٔ
   بازشدنش ثبت می‌شود و ایندکسِ (ارز، استراتژی، جهت) و «شکل ستاپ» ساخته
   می‌شود. قبل از صدور هر سیگنال همین پرسیده می‌شود — با عدد، نه حس.
۲. دفتر درس‌ها (brain/memory/lessons.json): روایت خوانا — چه شد، چرا،
   چه درسی. برد دلیلش ثبت می‌شود، باخت علتش؛ پنل و تلگرام همین را نشان
   می‌دهند تا «فهمیدن» قابل دیدن باشد، نه ادعا.

قانون صداقت همیشگی: زیر ۸ مورد مشابه، حافظه فقط «ذکر» می‌شود و روی
رتبه اثر نمی‌گذارد؛ وتو همچنان مال ناظر تجربه با کف ۱۲ معامله است.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import brain                                                  # noqa: E402

ROOT = HERE.parent.parent.parent
LESSONS = ROOT / "brain" / "memory" / "lessons.json"
CAP = 300


def _load():
    try:
        return json.loads(LESSONS.read_text())
    except Exception:                                # noqa: BLE001 - حافظهٔ خالی
        return {"lessons": []}


def remember(kind, sym, text, data=None):
    """یک درس/نتیجه/ضعف — ذخیرهٔ دائمی، جدیدترین اول."""
    j = _load()
    j["lessons"].insert(0, {"at": int(time.time() * 1000), "kind": kind,
                            "sym": sym, "text": text, "data": data or {}})
    j["lessons"] = j["lessons"][:CAP]
    j["updated"] = int(time.time() * 1000)
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    LESSONS.write_text(json.dumps(j, ensure_ascii=False, indent=1))


def lessons(sym=None, kind=None, limit=8):
    out = []
    for l in _load()["lessons"]:
        if sym and l.get("sym") != sym:
            continue
        if kind and l.get("kind") != kind:
            continue
        out.append(l)
        if len(out) >= limit:
            break
    return out


def digest_closed(trades):
    """یادگیری از هر معاملهٔ بسته — هم به حافظهٔ آماری، هم به دفتر درس‌ها.
    منقضی‌ها معامله نیستند. بعد از خوراک، ایندکس دوباره ساخته می‌شود تا
    تحلیل بعدی با دانش به‌روزتر شروع کند."""
    fed = 0
    for t in trades:
        if t.get("R") is None or t.get("outcome") == "expired":
            continue
        why = t.get("why") or {}
        brain.learn({"sym": t["sym"], "tf": "15m", "dir": t["dir"],
                     "strategy": why.get("stage") or "hamid",
                     "r": t.get("R") or 0, "outcome": t.get("outcome"),
                     "trend_4h": why.get("trend_4h"), "fear": why.get("fear"),
                     "funding": why.get("funding"), "stop_pct": why.get("stop_pct"),
                     "usdt_dom": why.get("usdt_dom"), "mode": why.get("mode"),
                     "liq": why.get("liq")})
        won = (t.get("R") or 0) > 0
        ctx = "، ".join(f"{k}={why.get(k)}" for k in
                        ("stage", "trend_4h", "fear") if why.get(k) is not None)
        remember("نتیجه", t["sym"],
                 f"{'✅ برد' if won else '❌ باخت'} {t['sym']} "
                 f"{'خرید' if t['dir'] == 'LONG' else 'فروش'} "
                 f"({(t.get('R') or 0):+.2f}R) — شرایط بازش: {ctx or '؟'}",
                 {"R": t.get("R"), "outcome": t.get("outcome")})
        fed += 1
    if fed:
        try:
            brain.build_index()
        except Exception:                            # noqa: BLE001 - ایندکس دفعهٔ بعد
            pass
    return fed


def consult(sym, direction, strategy="second"):
    """قبل از صدور سیگنال: حافظه دربارهٔ همین موقعیت چه می‌گوید.

    خروجی: note (جملهٔ صریح فارسی با عدد — همان «ذکر شباهت» که حمید خواست)،
    adj (اثر کوچک روی رتبه، فقط با نمونهٔ کافی)، و آخرین درس‌های همین ارز."""
    try:
        rec = brain.recall(sym=sym, strategy=strategy, direction=direction)
    except Exception:                                # noqa: BLE001 - بدون ایندکس، بدون ادعا
        rec = {"verdict": "thin"}
    ls = lessons(sym=sym, limit=3)
    note, adj = None, 0.0
    s = rec.get("symbol")
    if s:
        note = (f"حافظه: {s['n']} مورد مشابه همین ارز/جهت — "
                f"برد {s['hit']}٪، میانگین {s['ev']:+.2f}R")
        if s["n"] >= 8:
            if rec.get("verdict") == "good":
                adj = 0.05
            elif rec.get("verdict") == "bad":
                adj = -0.08
    elif ls:
        note = "حافظهٔ آماری نازک؛ آخرین تجربهٔ این ارز: " + ls[0]["text"][:90]
    return {"note": note, "adj": adj, "verdict": rec.get("verdict"),
            "lessons": [l["text"] for l in ls]}
