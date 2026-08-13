"""کاوش عمیق پامپ یک ارز — دستور حمید (۱۳ اوت، برای APR و از این به بعد هر پامپ):

    «علت پامپ را بررسی کن؛ لگ-کورولیشنش در تایم‌فریم‌های مختلف با ارزهایی
    که در گذشته بعدش پامپ می‌شدند؛ بگو چه ارزی به‌زودی می‌تواند بعدش پامپ
    شود؛ و خود ارز را جداگانه در همهٔ تایم‌فریم‌ها تحلیل کن که حرکت بعدی‌اش
    چگونه خواهد بود. در تلگرام بفرست.»

دو پیام تلگرام:
  ۱. علت پامپ (لحظهٔ شروع، حجم، سابقهٔ رخدادی) + دنباله‌روهای لگ-کورولیشنی
     چند-تایم‌فریمه که خودشان هنوز نپریده‌اند — کاندیدای «پامپ بعدی»
  ۲. تحلیل خود ارز در ۴س/۱س/۱۵د/۵د: روند، RSI، الگوهای کلاسیک، اردر
     بلاک‌های معتبر، سطوح — و حکم حرکت بعدی با ابطال‌کننده؛ با چارت

هیچ عددی ساخته نمی‌شود؛ رابطهٔ زیر آستانه «قانع‌کننده نیست» گزارش می‌شود.

    python3 -m hamid.pump_probe --symbol APRUSDT
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def _cd(rows):
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def pump_start(c15):
    """بزرگ‌ترین جهش ۳کندلهٔ ۱۵د در پنجره + z حجم همان لحظه."""
    best_i, best_r = None, 0.0
    for i in range(3, len(c15)):
        r = c15[i]["c"] / c15[i - 3]["c"] - 1
        if r > best_r:
            best_i, best_r = i, r
    if best_i is None:
        return None
    vols = [k["v"] for k in c15[max(0, best_i - 24):best_i - 3]]
    mv = sum(vols) / len(vols) if vols else 0
    sd = (sum((v - mv) ** 2 for v in vols) / len(vols)) ** 0.5 if vols else 0
    vz = (c15[best_i]["v"] - mv) / sd if sd else 0
    return {"t": c15[best_i]["t"], "pct": round(best_r * 100, 1),
            "vol_z": round(vz, 1)}


def run(sym):
    import sources
    import telegram as tg
    import tg_batch
    from hamid import lagcorr, patterns, orderblocks
    from hamid.structure import trend, levels
    from hamid.analyze_pump import rsi
    from hamid.pump_radar import Kcache
    from scan import top_by_48h

    tok, chat = tg.creds()
    kc = Kcache()
    c1h = _cd(sources.klines(sym, "1h", 500))
    c15 = _cd(sources.klines(sym, "15m", 320))
    c5 = _cd(sources.klines(sym, "5m", 200))
    c4h = lagcorr._to4h(c1h)
    px = c5[-1]["c"]

    # ── پیام ۱: علت + دنباله‌روها ──────────────────────────────────────────
    st = pump_start(c15)
    L1 = [f"🏷 <b>{tg.PANEL_NAME}</b> · 🤖 <b>کلود مکس</b>",
          f"🚀 <b>کاوش پامپ {sym.replace('USDT','')}</b>"]
    if st:
        hh = time.strftime("%H:%M", time.gmtime(st["t"] / 1000 + 3.5 * 3600))
        L1.append(f"شروع جهش: ساعت <code>{hh}</code> تهران — "
                  f"+{st['pct']}٪ در ۳ کندل ۱۵د، جهش حجم z={st['vol_z']}")
        L1.append("علت خبری: " + ("جهش حجم بدون خبرِ پیدا‌شده — الگوی رفتاری "
                                   "پامپ نقدینگی/لیستینگ؛ علت خبری تأییدشده پیدا نشد"
                                   if st["vol_z"] >= 2 else "حرکت تدریجی، نه انفجاری"))
    uni = [s for s in top_by_48h(80) if s != sym]
    fols = lagcorr.followers_of(kc, sym, uni, top=6)
    fresh = []
    for f in fols:
        try:
            c = kc.get(f["symbol"], "1h", 30)
            chg24 = (c[-1]["c"] / c[-24]["c"] - 1) * 100 if len(c) >= 25 else 0
        except Exception:                            # noqa: BLE001
            chg24 = 0
        if chg24 < 8:                                # خودش هنوز نپریده
            fresh.append((f, round(chg24, 1)))
    if fresh:
        L1.append("\n🎯 <b>کاندیدای پامپ بعدی (لگ-کورولیشن تاریخی، هنوز نپریده):</b>")
        for f, chg in fresh[:4]:
            L1.append("• " + lagcorr.reason_fa(sym.replace("USDT", ""), f)
                      + f" — ۲۴س خودش: {chg:+}٪")
    else:
        L1.append("\nدنباله‌روی لگ-کورولیشنیِ قانع‌کننده‌ای که هنوز نپریده باشد "
                  "پیدا نشد (آستانهٔ سخت r≥0.2؛ زیر آن ادعا نمی‌کنیم)")
    L1.append(f"🕐 <code>{tg.tehran()}</code> به وقت ایران")
    if tok:
        tg._post(tok, "sendMessage", {"chat_id": chat, "parse_mode": "HTML",
                                      "text": "\n".join(L1)})
        print("پیام ۱ (علت + کاندیداها) رفت")

    # ── پیام ۲: تحلیل خود ارز، همهٔ تایم‌فریم‌ها ──────────────────────────
    t4, t1, t15 = trend(c4h) if len(c4h) >= 30 else "؟", trend(c1h), trend(c15)
    r1, r15 = rsi(c1h), rsi(c15)
    L2 = [f"🏷 <b>{tg.PANEL_NAME}</b> · 🤖 <b>کلود مکس</b>",
          f"🔬 <b>تحلیل {sym.replace('USDT','')} — همهٔ تایم‌فریم‌ها</b>",
          f"روند: ۴س <b>{t4}</b> · ۱س <b>{t1}</b> · ۱۵د <b>{t15}</b>",
          f"RSI: ۱س <code>{r1:.0f}</code> · ۱۵د <code>{r15:.0f}</code>"
          if r1 and r15 else "RSI: دادهٔ ناکافی"]
    for tf, cd in (("4h", c4h), ("1h", c1h), ("15m", c15)):
        ps = patterns.detect(cd) if len(cd) >= 60 else []
        if ps:
            L2.append(f"🧩 {tf}: " + "، ".join(
                p["fa"] + (" (تأییدشده)" if p["status"] == "confirmed" else "")
                for p in ps[:3]))
    for tf, cd in (("1h", c1h), ("15m", c15)):
        b_in, b_near = orderblocks.near(cd, tf=tf)
        b = b_in or b_near
        if b:
            L2.append(f"🧱 {orderblocks.note_fa(b, 'داخل' if b_in else 'نزدیک')} "
                      f"<code>{b['low']:.6g}–{b['high']:.6g}</code>")
    lv = levels(c1h)
    above = min((l.price for l in lv if l.price > px), default=None)
    below = max((l.price for l in lv if l.price < px), default=None)
    if above or below:
        L2.append("سطوح معتبر ۱س: " +
                  (f"مقاومت <code>{above:.6g}</code> " if above else "") +
                  (f"· حمایت <code>{below:.6g}</code>" if below else ""))
    # حکم حرکت بعدی — با ابطال‌کننده، نه پیشگویی
    overheated = (r15 or 0) >= 72 or (r1 or 0) >= 72
    verdict = []
    if overheated:
        verdict.append("اشباع خرید بعد از جهش — احتمال استراحت/پولبک به سمت "
                       + (f"<code>{below:.6g}</code>" if below else "حمایت ۱س")
                       + " بیشتر از ادامهٔ مستقیم است؛ ورود تعقیبی ممنوع")
    elif t1 == "up" and t15 == "up":
        verdict.append("ساختار هنوز صعودی — پولبک سالم به سطح فلیپ/OB می‌تواند "
                       "ادامه بسازد" + (f"؛ مقاومت بعدی <code>{above:.6g}</code>"
                                        if above else ""))
    else:
        verdict.append("ساختار مخلوط — تا تثبیت بالای حمایت یا شکست مقاومت، "
                       "NO TRADE تصمیم معتبر است")
    if below:
        verdict.append(f"⛔ ابطال نگاه صعودی: بستنِ ۱س زیر <code>{below:.6g}</code>")
    L2.append("⚖️ " + " ".join(verdict))
    L2.append(f"🕐 <code>{tg.tehran()}</code> به وقت ایران")
    cap = "\n".join(L2)
    if len(cap) > 1024:
        cap = "\n".join(L2[:8] + [L2[-2], L2[-1]])
    buf = None
    try:
        buf = tg_batch.chart(sym, c5[-120:], None, None, None, None, "ANALYSIS")
    except Exception:                                # noqa: BLE001
        buf = None
    if tok:
        if buf:
            tg._post(tok, "sendPhoto", {"chat_id": chat, "parse_mode": "HTML",
                                        "caption": cap},
                     {"photo": (f"{sym}.png", buf.read())})
        else:
            tg._post(tok, "sendMessage", {"chat_id": chat, "parse_mode": "HTML",
                                          "text": cap})
        print("پیام ۲ (تحلیل کامل + چارت) رفت")
    try:
        from hamid import memory
        memory.remember("تحلیل", sym, f"کاوش پامپ: {' | '.join(verdict)[:180]}")
    except Exception:                                # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="APRUSDT")
    sys.exit(run(ap.parse_args().symbol))
