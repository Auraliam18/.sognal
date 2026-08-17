"""زنجیرهٔ نهایی پیش از اجرا + دفتر قصدها — پل پنل ↔ داشبورد بیت‌یونیکس.

داشبورد حمید (سمت صرافی) فقط یک چیز از ما می‌خواند:
`signals/exec-outbox.json` — دفترِ قصدهای اجرا. هر ورودی سیگنالی است که
از تمام دروازه‌ها گذشته و همهٔ اعداد اجرایش از قبل حساب و نوشته شده.

زنجیره (ترتیب مهم است):
  ۱. کیل‌سوییچ  — tripped = هیچ قصدی صادر نمی‌شود (قرارداد: داشبورد هم
                  موظف است پیش از هر سفارش killswitch.json را چک کند)
  ۲. روند       — سیگنال باید از دروازهٔ روند رد شده باشد (مهر trend4/1)
  ۳. کارمزد     — RR خالص از کارمزد+لغزش باید از حد بگذرد (fees.gate)
  ۴. سایز       — سقف‌های سخت (sizing.position) روی سرمایهٔ مرجع 10k$؛
                  داشبورد با سرمایهٔ واقعی همین تابع را صدا می‌زند —
                  qty این‌جا «پیشنهاد بر 10k» است نه دستور نهایی.

وضعیت قصد: PENDING (منتظر داشبورد) — این سیستم LIVE_EXECUTION ندارد؛
اجرا و تأیید نهایی همیشه سمت داشبورد/حمید است (قانون ۱۰).
"""
import json
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUTBOX = ROOT / "signals" / "exec-outbox.json"
REF_EQUITY = 10_000.0                 # مرجع محاسبهٔ پیشنهاد سایز
MAX_ITEMS = 60


def evaluate(s):
    """سیگنالِ گذشته از گلوگاه ارسال → قصد اجرا یا ردِ دلیل‌دار."""
    from hamid import killswitch, fees, sizing
    sym, d = s.get("sym"), s.get("dir")
    entry, sl = s.get("entry"), s.get("sl")
    tp1 = s.get("tp1")
    out = dict(ok=False, intent=None, reason="")
    if not killswitch.guard():
        out["reason"] = "کیل‌سوییچ فعال است — قصد اجرا صادر نمی‌شود"
        return out
    if not all([sym, d, entry, sl]):
        out["reason"] = "سیگنال ناقص (sym/dir/entry/sl)"
        return out
    fg = fees.gate(entry, sl, tp1 or entry, symbol=sym) if tp1 else \
        dict(ok=True, fee_r=fees.cost_in_r(entry, sl, sym), net_rr=None,
             reason="بدون tp1 — فقط کارمزد ثبت شد")
    if not fg["ok"]:
        out["reason"] = f"دروازهٔ کارمزد: {fg['reason']}"
        return out
    sz = sizing.position(REF_EQUITY, entry, sl, leverage=5)
    if not sz["ok"]:
        out["reason"] = f"دروازهٔ سایز: {sz['reason']}"
        return out
    out.update(ok=True, intent={
        "id": f"LIAM9-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-"
              f"{sym.replace('USDT', '')}-{uuid.uuid4().hex[:8]}",
        "panel": "لیام تریدر ۹",
        "created_at": int(time.time() * 1000),
        "status": "PENDING",
        "symbol": sym, "direction": d, "tf": s.get("tf"),
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": s.get("tp2"),
        "strategy": s.get("strategyName") or s.get("name") or "",
        "trend4": s.get("trend4"), "trend1": s.get("trend1"),
        "counter_trend": bool(s.get("counter_trend_note")),
        "fees": {"fee_r": fg.get("fee_r"), "net_rr": fg.get("net_rr")},
        "sizing_ref_10k": {"qty": sz["qty"], "notional_usd": sz["notional_usd"],
                           "risk_usd": sz["risk_usd"],
                           "note": "پیشنهاد بر مبنای 10k$ — داشبورد با سرمایهٔ "
                                   "واقعی sizing.position را صدا بزند"},
        "gates_passed": ["killswitch", "trend", "fees", "sizing",
                         "dedupe", "concurrency", "premortem"],
    })
    return out


def push(s):
    """سیگنالِ واقعاً ارسال‌شده → اگر از زنجیره گذشت، در دفتر قصدها بنشیند.
    شکستِ این مسیر هرگز ارسال سیگنال را نمی‌کشد (اولویت با تلگرام حمید)."""
    try:
        r = evaluate(s)
        if not r["ok"]:
            print(f"  دفتر قصد {s.get('sym')}: {r['reason']}", flush=True)
            return None
        try:
            box = json.loads(OUTBOX.read_text())
            assert isinstance(box, list)
        except Exception:                            # noqa: BLE001
            box = []
        box.insert(0, r["intent"])
        OUTBOX.parent.mkdir(exist_ok=True)
        OUTBOX.write_text(json.dumps(box[:MAX_ITEMS], ensure_ascii=False,
                                     indent=1))
        print(f"  دفتر قصد: {r['intent']['id']} ثبت شد", flush=True)
        return r["intent"]
    except Exception as e:                           # noqa: BLE001
        print(f"  دفتر قصد: {type(e).__name__} — ارسال سیگنال ادامه دارد",
              flush=True)
        return None
