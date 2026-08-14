"""آزمون آینهٔ تلگرام — ارسال هم‌زمان به مقصد دوم (دستور حمید ۱۴ اوت).

بدون شبکه: خودِ `_post_once` جایگزین می‌شود تا ببینیم چه چیزی، به کجا،
با چه فیلدهایی می‌رفت.

چیزی که اثبات می‌شود:
  ۱. یک ارسال، دو مقصد — و خروجی همیشه پاسخ مقصد اول است
  ۲. بدون تنظیم مقصد دوم، رفتار دقیقاً مثل قبل است (هیچ ارسال اضافه)
  ۳. فیلدهای ریپلای در آینه حذف می‌شوند (شناسهٔ پیامِ چت اول در چت دوم
     بی‌معناست و خطا می‌دهد)
  ۴. **شکست آینه هرگز مسیر اصلی را نمی‌کشد** — مهم‌ترین آزمون این فایل
  ۵. متدهای خواندنی (getMe) آینه نمی‌شوند
  ۶. توکن مقصد دوم هم در scrub پاک می‌شود
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import telegram as tg                                          # noqa: E402

ok = 0
fail = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


class Spy:
    """جای _post_once می‌نشیند و هر تماس را ثبت می‌کند."""

    def __init__(self, fail_on_token=None):
        self.calls = []
        self.fail_on_token = fail_on_token

    def __call__(self, token, method, fields, files=None):
        self.calls.append({"token": token, "method": method,
                           "fields": dict(fields), "files": files})
        if self.fail_on_token and token == self.fail_on_token:
            raise RuntimeError("بات دوم جواب نداد")
        return {"ok": True, "result": {"message_id": 100 + len(self.calls)}}


def with_spy(env, spy):
    """محیط و جاسوس را بگذار، تابع را برگردان."""
    import os
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
              "TELEGRAM_BOT_TOKEN_2", "TELEGRAM_CHAT_ID_2"):
        os.environ.pop(k, None)
    os.environ.update(env)
    tg._post_once = spy


print("── آینهٔ تلگرام ──")

TOK1, CHAT1 = "111:AAA", "-100111"
TOK2, CHAT2 = "222:BBB", "7246007795"
real_post_once = tg._post_once

# ── ۱. یک ارسال، دو مقصد ───────────────────────────────────────────────────
spy = Spy()
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1,
          "TELEGRAM_BOT_TOKEN_2": TOK2, "TELEGRAM_CHAT_ID_2": CHAT2}, spy)
resp = tg._post(TOK1, "sendMessage", {"chat_id": CHAT1, "text": "سیگنال تست"})

check("دو ارسال انجام شد (اصلی + آینه)", len(spy.calls) == 2)
check("اولی به بات اول رفت", spy.calls[0]["token"] == TOK1)
check("دومی به بات دوم رفت", spy.calls[1]["token"] == TOK2)
check("چت دوم درست جایگزین شد", spy.calls[1]["fields"]["chat_id"] == CHAT2)
check("متن هر دو یکی است",
      spy.calls[0]["fields"]["text"] == spy.calls[1]["fields"]["text"] == "سیگنال تست")
check("خروجی، پاسخ مقصد *اول* است (message_id نباید عوض شود)",
      resp["result"]["message_id"] == 101)

# ── ۲. عکس هم آینه می‌شود ──────────────────────────────────────────────────
spy = Spy()
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1,
          "TELEGRAM_BOT_TOKEN_2": TOK2, "TELEGRAM_CHAT_ID_2": CHAT2}, spy)
tg._post(TOK1, "sendPhoto", {"chat_id": CHAT1, "caption": "چارت"},
         {"photo": ("x.png", b"\x89PNG-fake")})
check("عکس هم به هر دو مقصد رفت", len(spy.calls) == 2)
check("خودِ بایت عکس هم به مقصد دوم رفت",
      spy.calls[1]["files"]["photo"][1] == b"\x89PNG-fake")

# ── ۳. بدون مقصد دوم، رفتار دقیقاً مثل قبل ─────────────────────────────────
spy = Spy()
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1}, spy)
tg._post(TOK1, "sendMessage", {"chat_id": CHAT1, "text": "تنها"})
check("بدون تنظیم مقصد دوم، فقط یک ارسال", len(spy.calls) == 1)

# ── ۴. فیلد ریپلای در آینه حذف می‌شود ──────────────────────────────────────
spy = Spy()
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1,
          "TELEGRAM_BOT_TOKEN_2": TOK2, "TELEGRAM_CHAT_ID_2": CHAT2}, spy)
tg._post(TOK1, "sendMessage",
         {"chat_id": CHAT1, "text": "🎯 تارگت خورد",
          "reply_to_message_id": 5555, "allow_sending_without_reply": "false"})
check("ریپلای در مقصد اول حفظ شد",
      spy.calls[0]["fields"].get("reply_to_message_id") == 5555)
check("ریپلای از آینه حذف شد (شناسهٔ چت اول در چت دوم بی‌معناست)",
      "reply_to_message_id" not in spy.calls[1]["fields"]
      and "allow_sending_without_reply" not in spy.calls[1]["fields"])
check("ولی متن نتیجه به مقصد دوم رسید",
      spy.calls[1]["fields"]["text"] == "🎯 تارگت خورد")

# ── ۵. مهم‌ترین: شکست آینه، مسیر اصلی را نمی‌کشد ───────────────────────────
spy = Spy(fail_on_token=TOK2)
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1,
          "TELEGRAM_BOT_TOKEN_2": TOK2, "TELEGRAM_CHAT_ID_2": CHAT2}, spy)
crashed = False
try:
    resp = tg._post(TOK1, "sendMessage", {"chat_id": CHAT1, "text": "سیگنال مهم"})
except Exception:                                     # noqa: BLE001
    crashed = True
check("خرابی بات دوم استثنا بالا نمی‌آورد", not crashed)
check("سیگنال مقصد اول با وجود خرابی آینه رفت",
      resp and resp.get("ok") and spy.calls[0]["token"] == TOK1)

# ── ۶. متد خواندنی آینه نمی‌شود ────────────────────────────────────────────
spy = Spy()
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1,
          "TELEGRAM_BOT_TOKEN_2": TOK2, "TELEGRAM_CHAT_ID_2": CHAT2}, spy)
tg._post(TOK1, "getMe", {})
check("getMe آینه نمی‌شود", len(spy.calls) == 1)

# ── ۷. mirror=False احترام گذاشته می‌شود ───────────────────────────────────
spy = Spy()
with_spy({"TELEGRAM_BOT_TOKEN": TOK1, "TELEGRAM_CHAT_ID": CHAT1,
          "TELEGRAM_BOT_TOKEN_2": TOK2, "TELEGRAM_CHAT_ID_2": CHAT2}, spy)
tg._post(TOK1, "sendMessage", {"chat_id": CHAT1, "text": "فقط اولی"}, mirror=False)
check("mirror=False آینه را خاموش می‌کند", len(spy.calls) == 1)

# ── ۸. توکن دوم هم پاک می‌شود ──────────────────────────────────────────────
import os                                                       # noqa: E402
os.environ["TELEGRAM_BOT_TOKEN"] = TOK1
os.environ["TELEGRAM_BOT_TOKEN_2"] = TOK2
s = tg.scrub(f"خطا در https://api.telegram.org/bot{TOK2}/sendMessage و {TOK1}")
check("توکن مقصد دوم در لاگ پاک می‌شود", TOK2 not in s and "***" in s)
check("توکن مقصد اول هم همچنان پاک می‌شود", TOK1 not in s)

# ── ۹. creds2 بدون محیط، خاموش است ─────────────────────────────────────────
os.environ.pop("TELEGRAM_BOT_TOKEN_2", None)
os.environ.pop("TELEGRAM_CHAT_ID_2", None)
check("creds2 بدون محیط (None, None) می‌دهد", tg.creds2() == (None, None))

tg._post_once = real_post_once
print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون آینهٔ تلگرام گذشت")
