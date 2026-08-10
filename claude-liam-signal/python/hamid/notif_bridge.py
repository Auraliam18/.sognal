"""پل ناتیفیکیشن بیت‌یونیکس — تحقیق فوری روی هر ناتیفی که حمید فوروارد کند.

بیت‌یونیکس API ناتیفیکیشن ندارد؛ راه صادقانه همین است: حمید هر ناتیف
(«X رفت بالا/پایین») را به ربات فوروارد می‌کند، چرخهٔ بعدی اینجا صندوق
ربات را می‌خواند (getUpdates)، نماد را در متن پیدا می‌کند و همان‌جا یک
گزارش فوری برمی‌گرداند: تغییرات الان، نقش خوشه‌ای از آخرین رادار، سابقهٔ
پامپ، و درس‌های حافظه دربارهٔ همان ارز.

آفستِ خوانده‌شده در brain/tg-inbox.json می‌ماند تا پیامی دو بار جواب
نگیرد؛ سقف ۳ پاسخ در هر چرخه تا سهمیهٔ تلگرام را نخورد.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
INBOX = ROOT / "brain" / "tg-inbox.json"
RADAR = ROOT / "signals" / "pump-radar.json"


def _state():
    try:
        return json.loads(INBOX.read_text())
    except Exception:                                # noqa: BLE001
        return {"offset": 0}


def _symbols_in(text, known):
    """نمادهای شناخته‌شده داخل متن ناتیف — با مرز کلمه، بی‌حساسیت به حروف."""
    up = text.upper()
    hits = []
    for sym in known:
        base = sym[:-4] if sym.endswith("USDT") else sym
        if len(base) < 2:
            continue
        if re.search(r"(?<![A-Z0-9])" + re.escape(base) + r"(?![A-Z0-9])", up):
            hits.append(sym)
    return hits


def _brief(sym, radar, kc=None):
    """گزارش فوری فارسی برای یک نماد — هر عدد از داده، نه از حدس."""
    L = [f"🔎 <b>{sym.replace('USDT', '')}</b> — تحقیق فوری ناتیف"]
    b = next((c for c in (radar.get("coins") or []) if c.get("symbol") == sym), None)
    if b:
        L.append(f"نقش خوشه‌ای (آخرین رادار): <b>{b.get('role') or '?'}</b>")
        if b.get("pump_note"):
            L.append(b["pump_note"])
        leaders = [x.get("symbol") for x in (b.get("leaders") or []) if x.get("n", 0) >= 2]
        if leaders:
            L.append("سردسته‌های تاریخی‌اش: " + "، ".join(leaders[:3]))
    else:
        L.append("در آخرین رادار پامپ نبود — یعنی جزو متحرک‌های ساعت اخیر نبوده")
    if kc is not None:
        try:
            from hamid.analyze_pump import pumps, rsi
            c1h = kc.get(sym, "1h", 1000)
            if len(c1h) >= 30:
                chg1 = (c1h[-1]["c"] / c1h[-2]["c"] - 1) * 100
                L.append(f"یک ساعت اخیر: {chg1:+.1f}٪ · RSI ساعتی {rsi(c1h) or '?'}")
                if len(c1h) >= 25:
                    chg24 = (c1h[-1]["c"] / c1h[-25]["c"] - 1) * 100
                    L.append(f"تغییر ۲۴س: <b>{chg24:+.1f}٪</b>")
                eps = pumps(c1h)
                if eps:
                    L.append(f"سابقهٔ پامپ: {len(eps)} بار، بزرگ‌ترین "
                             f"+{max(e['ret_4h_pct'] for e in eps)}٪")
        except Exception:                            # noqa: BLE001
            pass
    try:
        from hamid import memory as mem
        for l in mem.lessons(sym=sym, limit=2):
            L.append(f"🧠 {l['text'][:120]}")
    except Exception:                                # noqa: BLE001
        pass
    L.append("قانون سر جایش است: پریده = ماشه، نه سیگنال.")
    return "\n".join(L)


def poll(kc=None, cap=3):
    """صندوق ربات را بخوان و به ناتیف‌های فورواردشده جواب بده."""
    import telegram as tg
    tok, chat = tg.creds()
    if not tok:
        return 0
    st = _state()
    url = (f"{tg.API}/bot{tok}/getUpdates?timeout=0&"
           + urllib.parse.urlencode({"offset": st.get("offset", 0) + 1,
                                     "allowed_updates": '["message"]'}))
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            ups = json.loads(r.read()).get("result") or []
    except Exception as e:                           # noqa: BLE001
        print(f"پل ناتیف: getUpdates {type(e).__name__}")
        return 0
    if not ups:
        return 0
    st["offset"] = max(u["update_id"] for u in ups)

    try:
        import sources
        known = [s["symbol"] for s in sources.tickers()
                 if str(s.get("symbol", "")).endswith("USDT")]
    except Exception:                                # noqa: BLE001
        known = []
    try:
        radar = json.loads(RADAR.read_text())
    except Exception:                                # noqa: BLE001
        radar = {}

    answered = 0
    for u in ups:
        if answered >= cap:
            break
        msg = u.get("message") or {}
        # فقط چت خود حمید — پیام غریبه جواب نمی‌گیرد
        if chat and str((msg.get("chat") or {}).get("id")) != str(chat):
            continue
        text = msg.get("text") or msg.get("caption") or ""
        if not text:
            continue
        syms = _symbols_in(text, known)[:2]
        if not syms:
            continue
        for sym in syms:
            body = _brief(sym, radar, kc=kc)
            tg._post(tok, "sendMessage",
                     {"chat_id": chat, "parse_mode": "HTML",
                      "reply_to_message_id": msg.get("message_id"),
                      "text": (f"🏷 <b>{tg.PANEL_NAME}</b>\n{body}\n"
                               f"🕐 <code>{tg.tehran()}</code> به وقت ایران")})
        answered += 1

    INBOX.parent.mkdir(exist_ok=True)
    INBOX.write_text(json.dumps(st, indent=1))
    if answered:
        print(f"پل ناتیف: {answered} ناتیف فورواردشده جواب گرفت")
    return answered
