"""تست یک‌باره: سیگنال تست با الگوی زنده + ریپلای دقیق روی همان پیام.

دستور حمید (۱۲ اوت). سه قید سخت:
  ۱. الگو واقعی باشد — از کندل زندهٔ همین لحظه با انجین patterns، نه ادعا.
  ۲. روی پیام و چارت، درشت نوشته شود «تست — ورود ممنوع».
  ۳. ریپلای دقیق: بدون allow_sending_without_reply؛ بعد از ارسال هم از
     جواب تلگرام چک می‌شود reply_to_message.message_id == پیام اول.
     هر خطا = خروج قرمز، نه موفقیت الکی.

هیچ‌چیز در SENT یا دفتر کاغذی ثبت نمی‌شود. اجرا فقط از ورک‌فلوی
test-pattern-signal.yml (توکن فقط در Secrets است).
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def main():
    import sources
    import telegram as tg
    import tg_batch
    from hamid import patterns, premortem
    from hamid.structure import atr
    from scan import top_by_48h

    token, chat = tg.creds()
    if not token or not chat:
        print("✗ TELEGRAM_BOT_TOKEN/CHAT_ID در Secrets نیست")
        return 1

    def cd_of(rows):
        return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4],
                 "v": k[5]} for k in rows]

    # ۱ — الگوی زندهٔ واقعی: ارزهای پرحجم را بگرد تا الگوی جهت‌دارِ تازه
    #     پیدا شود؛ اول ۱۵د، بعد ۱س. پیدا نشد → صادقانه شکست، نه الگوی جعلی.
    found = None
    for sym in top_by_48h(60):
        try:
            c15 = cd_of(sources.klines(sym, "15m", 120))
            if len(c15) < 60:
                continue
            ps = patterns.detect(c15)
            biased = [p for p in ps if p["bias"] in ("bull", "bear")]
            if biased:
                best = sorted(biased, key=lambda p: (p["status"] == "confirmed",
                                                     -p["age"]), reverse=True)[0]
                found = (sym, "15m", c15, best)
                break
            c1h = cd_of(sources.klines(sym, "1h", 500))
            biased = [p for p in patterns.detect(c1h)
                      if p["bias"] in ("bull", "bear")]
            if biased:
                best = sorted(biased, key=lambda p: (p["status"] == "confirmed",
                                                     -p["age"]), reverse=True)[0]
                found = (sym, "1h", c15, best)
                break
        except Exception as e:                        # noqa: BLE001
            print(f"  {sym}: {type(e).__name__}")
            continue
    if not found:
        print("✗ در ۶۰ ارز پرحجم الگوی جهت‌دارِ تازه‌ای نبود — سیگنال جعلی نمی‌سازیم")
        return 1
    sym, tf, c15, pat = found
    print(f"✓ الگوی زنده: {pat['fa']} ({pat['status']}) روی {sym} {tf} — "
          f"سوگیری {pat['bias']}")

    # ۲ — سیگنال تست در جهت الگو، سطح‌ها از ATR (فقط برای تست، ورود ممنوع)
    px = c15[-1]["c"]
    a = atr(c15) or px * 0.005
    d = "LONG" if pat["bias"] == "bull" else "SHORT"
    k = 1 if d == "LONG" else -1
    s = {"sym": sym, "tf": tf, "dir": d, "entry": px,
         "sl": px - k * 1.5 * a, "tp1": px + k * 2.25 * a,
         "tp2": px + k * 3.0 * a, "rr": 1.5,
         "strategy": "test",
         "strategyName": "🧪 تست انجین الگو — سیگنال واقعی نیست",
         "analyzed_at": int(time.time() * 1000)}
    pm = premortem.review(dict(s), c15)
    s["premortem"] = pm
    note = (pm.get("patterns") or {}).get("note")
    print(f"✓ بازجویی: {pm['note']} · 🧩 {note or '—'}")

    # کپشن فشردهٔ مخصوص تست — سقف تلگرام ۱۰۲۴ است و برشِ وسطِ تگ HTML
    # جواب 400 می‌دهد (اجرای اول همین‌جا سوخت). کوتاه و کامل، بدون برش.
    d_fa = "🟢 خرید (LONG)" if d == "LONG" else "🔴 فروش (SHORT)"
    st_fa = "تأییدشده" if pat["status"] == "confirmed" else "در حال شکل‌گیری"
    cap = "\n".join([
        "🧪 <b>تست — این سیگنال نیست، ورود ممنوع</b>",
        f"🏷 <b>{tg.PANEL_NAME}</b> · 🤖 <b>سیگنال کلود مکس</b>",
        f"<b>{d_fa} — {sym}</b>  <code>{tf}</code>",
        f"🧩 <i>الگوی کشف‌شدهٔ زنده: {pat['fa']} ({st_fa}) در {tf} — "
        "خط بنفش = سطح کلیدی الگو؛ نقطه‌چین بنفش = مسیر انتظاری به تارگت‌ها</i>",
        f"⚖️ <i>{pm['pro_w']} امتیاز تارگت / {pm['con_w']} امتیاز استاپ</i>",
        "",
        f"ورود    <code>{s['entry']:.10g}</code>",
        f"استاپ   <code>{s['sl']:.10g}</code>",
        f"تارگت۱  <code>{s['tp1']:.10g}</code>",
        f"تارگت۲  <code>{s['tp2']:.10g}</code>",
        "",
        f"🕐 ارسال <code>{tg.tehran()}</code> به وقت ایران",
        "<i>سطح‌ها فقط برای آزمایش از ATR ساخته شده‌اند — پیام بعدی، "
        "ریپلای همین پست است.</i>",
    ])

    _ob = (pm.get("ob_ctx") or {})
    buf = tg_batch.chart(sym, cd_of(sources.klines(sym, "5m", 96)),
                         s["entry"], s["sl"], s["tp1"], s["tp2"],
                         f"{d} — TEST",
                         ob=({"low": _ob["low"], "high": _ob["high"]}
                             if _ob.get("low") is not None else None),
                         pat={"key": pat.get("key"),
                              "label": pat["name"].upper().replace("_", " ")})
    resp = tg._post(token, "sendPhoto",
                    {"chat_id": chat, "caption": cap, "parse_mode": "HTML"},
                    {"photo": (f"{sym}-test.png", buf.read())})
    mid = ((resp or {}).get("result") or {}).get("message_id")
    if not (resp or {}).get("ok") or not mid:
        print(f"✗ ارسال سیگنال تست شکست: {resp}")
        return 1
    print(f"✓ سیگنال تست رفت — message_id={mid}")

    # ۳ — ریپلای دقیق: بدون allow_sending_without_reply؛ اگر پیام مرجع
    #     پیدا نشود تلگرام خطا می‌دهد و همان را می‌خواهیم، نه ارسال آزاد.
    txt = ("🧪 <b>این یک تست بود</b>\n"
           "سیگنال بالا ⬆️ فقط برای آزمایش انجین الگوها و سازوکار ریپلای "
           "فرستاده شد — <b>ورود ممنوع</b>.\n"
           f"<i>الگوی آزموده: {pat['fa']} در {tf} · "
           f"ساعت تهران {tg.tehran()}</i>")
    r2 = tg._post(token, "sendMessage",
                  {"chat_id": chat, "text": txt, "parse_mode": "HTML",
                   "reply_to_message_id": str(mid)})
    ref = (((r2 or {}).get("result") or {}).get("reply_to_message")
           or {}).get("message_id")
    if not (r2 or {}).get("ok"):
        print(f"✗ ریپلای شکست: {r2}")
        return 1
    if ref != mid:
        print(f"✗ ریپلای به پیام غلط چسبید: انتظار {mid}، شد {ref}")
        return 1
    print(f"✓✓ ریپلای دقیق تأیید شد: reply_to={ref} == سیگنال {mid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
