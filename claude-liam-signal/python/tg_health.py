#!/usr/bin/env python3
"""سلامت‌سنجی هر دو مقصد تلگرام — دستور حمید (۱۴ اوت).

«یک پیام تست بفرست که برای هر دو برود و بدونم که سالم هست.»

برای هر مقصد جداگانه و صریح گزارش می‌دهد:
  · بات معتبر است؟ (getMe)
  · چت در دسترس است؟ (getChat)
  · پیام واقعاً رسید؟ (sendMessage + شناسهٔ پیام برگشتی)

چرا جدا از آینه تست می‌شود: آینه عمداً بی‌صداست تا سیگنال اصلی را نکشد.
آن رفتار در تولید درست است، ولی برای «بدانم سالم است» بی‌فایده — اینجا
هر خطا با علتش چاپ می‌شود.

هیچ توکنی چاپ نمی‌شود؛ همه‌چیز از scrub رد می‌شود.

    python3 tg_health.py            # سلامت + پیام تست به هر دو
    python3 tg_health.py --check    # فقط سلامت، بدون ارسال پیام
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import telegram as tg                                          # noqa: E402

API = "https://api.telegram.org"


def _call(token, method, data=None):
    url = f"{API}/bot{token}/{method}"
    try:
        if data:
            body = urllib.parse.urlencode(data).encode()
            r = urllib.request.urlopen(url, body, timeout=30)
        else:
            r = urllib.request.urlopen(url, timeout=30)
        return json.load(r)
    except Exception as e:                            # noqa: BLE001
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = json.loads(e.read().decode()).get("description", "")
            except Exception:                         # noqa: BLE001
                pass
        return {"ok": False, "error": tg.scrub(detail or f"{type(e).__name__}: {e}")}


def probe(label, token, chat, send=True, text=None):
    """یک مقصد را کامل بسنج و نتیجهٔ خوانا برگردان."""
    print(f"\n── {label} ──")
    if not token or not chat:
        print("  ⚠ تنظیم نشده (سکرتش در گیت‌هاب نیست) — این مقصد خاموش است")
        return {"configured": False, "ok": False}

    out = {"configured": True}

    me = _call(token, "getMe")
    if me.get("ok"):
        b = me["result"]
        out["bot"] = b.get("username")
        print(f"  ✓ بات معتبر: @{b.get('username')} ({b.get('first_name')})")
    else:
        print(f"  ✗ بات نامعتبر: {me.get('error')}")
        out["ok"] = False
        return out

    ch = _call(token, "getChat", {"chat_id": chat})
    if ch.get("ok"):
        c = ch["result"]
        name = c.get("title") or c.get("username") or c.get("first_name") or "—"
        out["chat"] = name
        print(f"  ✓ چت در دسترس: {name} (نوع {c.get('type')})")
    else:
        err = ch.get("error", "")
        print(f"  ✗ چت در دسترس نیست: {err}")
        if "not found" in err.lower():
            print("     → معمولاً یعنی هنوز به بات /start نداده‌ای، یا شناسهٔ چت غلط است")
        out["ok"] = False
        return out

    if not send:
        out["ok"] = True
        return out

    r = _call(token, "sendMessage",
              {"chat_id": chat, "parse_mode": "HTML", "text": text})
    if r.get("ok"):
        mid = r["result"]["message_id"]
        out["message_id"] = mid
        out["ok"] = True
        print(f"  ✓ پیام رسید — شناسهٔ پیام {mid}")
    else:
        print(f"  ✗ پیام نرفت: {r.get('error')}")
        out["ok"] = False
    return out


def main():
    send = "--check" not in sys.argv
    t1, c1 = tg.creds()
    t2, c2 = tg.creds2()

    text = (f"🏷 <b>{tg.PANEL_NAME}</b> · 🤖 <b>کلود مکس</b>\n\n"
            "🧪 <b>پیام تست دو‌مقصدی</b>\n\n"
            "اگر این پیام را می‌بینی، این مقصد سالم است و از این به بعد "
            "همهٔ سیگنال‌ها، چارت‌ها و نتیجه‌ها هم‌زمان به همین‌جا هم می‌رسند.\n\n"
            f"🕐 <code>{tg.tehran()}</code> به وقت ایران")

    print("═" * 52)
    print("سلامت‌سنجی مقصدهای تلگرام")
    print("═" * 52)

    r1 = probe("مقصد ۱ — کانال اصلی", t1, c1, send, text)
    r2 = probe("مقصد ۲ — بات جدید", t2, c2, send, text)

    print("\n" + "═" * 52)
    if r1.get("ok") and r2.get("ok"):
        print("✅ هر دو مقصد سالم‌اند — ارسال هم‌زمان فعال است")
        return 0
    if r1.get("ok") and not r2.get("configured"):
        print("⚠️  مقصد ۱ سالم است؛ مقصد ۲ هنوز تنظیم نشده.")
        print("   دو سکرت را اضافه کن: TELEGRAM_BOT_TOKEN_2 و TELEGRAM_CHAT_ID_2")
        return 2
    if r1.get("ok") and not r2.get("ok"):
        print("⚠️  مقصد ۱ سالم است ولی مقصد ۲ ایراد دارد (بالا نوشته چرا).")
        print("   سیگنال‌ها همچنان به مقصد ۱ می‌روند — آینه هرگز مسیر اصلی را نمی‌کشد.")
        return 3
    print("❌ مقصد اصلی سالم نیست — این جدی است.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
