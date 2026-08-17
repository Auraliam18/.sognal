"""کیل‌سوییچ چندماشه — پیش‌نیاز ۳ از آستانهٔ پول واقعی (CLAUDE.md).

درس VERIFIED کتابخانه (bot-killswitch): «کیل‌سوییچ تک‌ماشه کافی نیست» —
ماشه‌های مستقل، هر یک برای یک کلاس خرابی جدا:

  LOSS      سقف ضرر تجمعی روز (R) — استراتژیِ بد یا بازارِ بد
  RATE      نرخ غیرعادی سفارش/سیگنال — نشانهٔ لوپ نرم‌افزاری
  DEVIATION انحراف قیمت اجرا از انتظار — دادهٔ خراب یا لغزش وحشی
  DEADMAN   سکوت ضربان — سرویس مرده ولی سفارش‌ها زنده‌اند
  RECONCILE ناهمخوانی پوزیشن صرافی با دفترها — بی‌خبری = رفتار امن

وضعیت در brain/killswitch.json ماندگار است؛ trip شدن:
  فاز فعلی (LIVE_EXECUTION=false): توقف ارسال سیگنال + آلارم ثانیه‌ای.
  فاز لایو: + لغو همهٔ سفارش‌ها و بستن پوزیشن‌ها (اجراکنندهٔ بیت‌یونیکس
  موظف است قبل از هر سفارش guard() را صدا بزند).
ریست فقط دستی است — با تأیید حمید (reset(who="hamid"))؛ ریست خودکار یعنی
لوپِ خراب دوباره روشن می‌شود.
"""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
STATE = ROOT / "brain" / "killswitch.json"
CFG = ROOT / "config" / "risk.json"

DEFAULTS = {
    "daily_loss_limit_r": 5.0,          # سقف ضرر تجمعی روز بر حسب R
    "max_orders_per_min": 6,            # بیشتر = لوپ نرم‌افزاری محتمل
    "max_price_deviation_pct": 1.5,     # اجرا دورتر از این از انتظار = داده/لغزش خراب
    "deadman_max_silence_s": 180,       # سکوت ضربان بیش از این = سرویس مرده
}


def _cfg():
    c = dict(DEFAULTS)
    try:
        c.update(json.loads(CFG.read_text()).get("killswitch", {}))
    except Exception:                                # noqa: BLE001
        pass
    return c


def _load():
    try:
        return json.loads(STATE.read_text())
    except Exception:                                # noqa: BLE001
        return {"tripped": None, "day": None, "loss_r": 0.0, "orders": []}


def _save(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1))


def _alarm(reason):
    txt = (f"🛑 کیل‌سوییچ فعال شد — {reason}\n"
           f"همهٔ ارسال‌ها متوقف؛ ریست فقط دستی با تأیید حمید.")
    print(txt, flush=True)
    try:
        import telegram as tg
        token, chat = tg.creds()
        if token:
            tg._post(token, "sendMessage",
                     {"chat_id": chat, "text": f"🏷 {tg.PANEL_NAME}\n{txt}"})
    except Exception:                                # noqa: BLE001
        pass


def trip(reason, now_ms=None):
    s = _load()
    if s.get("tripped"):
        return s
    s["tripped"] = {"reason": reason, "at": now_ms or int(time.time() * 1000)}
    _save(s)
    _alarm(reason)
    return s


def reset(who):
    """فقط دستی. who ثبت می‌شود — ریستِ بی‌نام پذیرفته نیست."""
    if not who:
        raise ValueError("ریست بدون نام مجاز نیست")
    s = _load()
    s["tripped"] = None
    s["loss_r"] = 0.0
    s["orders"] = []
    s["reset_by"] = {"who": who, "at": int(time.time() * 1000)}
    _save(s)
    return s


def guard():
    """قبل از هر ارسال/سفارش صدا زده می‌شود. True = مجاز."""
    t = _load().get("tripped")
    if t:
        print(f"کیل‌سوییچ فعال است ({t['reason']}) — عمل رد شد", flush=True)
        return False
    return True


def record_result(r, now_ms=None):
    """نتیجهٔ هر معامله (R منفی/مثبت). عبور از سقف روز = LOSS trip."""
    now_ms = now_ms or int(time.time() * 1000)
    s = _load()
    day = time.strftime("%Y-%m-%d", time.gmtime(now_ms / 1000))
    if s.get("day") != day:
        s["day"], s["loss_r"] = day, 0.0
    if r < 0:
        s["loss_r"] = round(s.get("loss_r", 0.0) + (-r), 3)
    _save(s)
    c = _cfg()
    if s["loss_r"] >= c["daily_loss_limit_r"]:
        trip(f"سقف ضرر روز: {s['loss_r']}R ≥ {c['daily_loss_limit_r']}R", now_ms)
        return False
    return True


def record_order(now_ms=None):
    """هر سفارش/سیگنال خروجی ثبت می‌شود؛ نرخ غیرعادی = RATE trip."""
    now_ms = now_ms or int(time.time() * 1000)
    s = _load()
    s["orders"] = [t for t in s.get("orders", []) if now_ms - t < 60_000]
    s["orders"].append(now_ms)
    _save(s)
    c = _cfg()
    if len(s["orders"]) > c["max_orders_per_min"]:
        trip(f"نرخ غیرعادی: {len(s['orders'])} سفارش در دقیقه "
             f"(سقف {c['max_orders_per_min']}) — لوپ نرم‌افزاری محتمل", now_ms)
        return False
    return True


def check_deviation(expected, actual, now_ms=None):
    """انحراف قیمت اجرا از انتظار — بالای سقف = DEVIATION trip."""
    if not expected:
        return True
    dev = abs(actual - expected) / expected * 100
    c = _cfg()
    if dev > c["max_price_deviation_pct"]:
        trip(f"انحراف قیمت {dev:.2f}٪ > {c['max_price_deviation_pct']}٪ "
             f"(انتظار {expected}، اجرا {actual})", now_ms)
        return False
    return True


def check_deadman(heartbeat_ms, now_ms=None):
    """سکوت ضربان (heartbeat سرویس زنده) بیش از سقف = DEADMAN trip."""
    now_ms = now_ms or int(time.time() * 1000)
    c = _cfg()
    silence = (now_ms - heartbeat_ms) / 1000
    if silence > c["deadman_max_silence_s"]:
        trip(f"dead-man: {silence:.0f}s سکوت ضربان "
             f"(سقف {c['deadman_max_silence_s']}s)", now_ms)
        return False
    return True
