#!/usr/bin/env python3
"""اجراکنندهٔ تحلیل عمیق تک‌نماد — تحلیل + چارت + تلگرام + خوراک پنل.

دستور حمید (۱۴ اوت): «ارسال سیگنال و پیدا کردن سیگنال را با دقت انجام بده.»

پس مرز اینجا سفت است و عمداً سفت می‌ماند:

  **تحلیل عمیق، سیگنال نیست.** این ابزار وقتی اجرا می‌شود که حمید یک نماد
  را بپرسد. جواب همیشه می‌آید — حتی وقتی ستاپی نیست، چون «NO TRADE تصمیم
  حرفه‌ای معتبر است». ولی چیزی که می‌آید برچسب 🔍 تحلیل دارد، نه 🟢 سیگنال.

  یک تحلیل فقط وقتی «ستاپ آماده» اعلام می‌شود که موتور روش حمید ستاپ
  برگردانده باشد **و** بازجویی premortem با pro > con رد شده باشد **و**
  دادهٔ لحظهٔ ارسال تازه باشد. حتی آن‌وقت هم در دفتر ضدتکرارِ چرخه ثبت
  نمی‌شود و معاملهٔ کاغذی باز نمی‌کند — چون این مسیر دستی است و نباید
  آمار خودکار را آلوده کند. (قانون ۹: پیپر/شدو/لایو دفتر جدا دارند.)

اجرا:
    python3 deep_run.py BTCUSDT            # تحلیل + ذخیره + تلگرام
    python3 deep_run.py BTCUSDT --no-tg    # فقط تحلیل و ذخیره
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import telegram as tg                                          # noqa: E402
from hamid import deep                                         # noqa: E402

MAX_AGE_MIN = 12.0        # کندل کهنه‌تر از این → تحلیل ارسال می‌شود ولی «ستاپ آماده» نه


def _fmt(v):
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1000:
        return f"{v:,.2f}"
    if a >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if a >= 0.001:
        return f"{v:.6f}".rstrip("0").rstrip(".")
    return f"{v:.8f}".rstrip("0").rstrip(".")


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%"


def caption(d):
    """کپشن فارسی — هر عدد از یک انجین می‌آید و می‌گوید از کجا."""
    sym = d["symbol"]
    px = d.get("price")
    st = d.get("setup") or {}
    stru = d.get("structure") or {}
    h4 = stru.get("h4") or {}
    h1 = stru.get("h1") or {}
    m15 = stru.get("m15") or {}
    pm = d.get("premortem") or {}

    ready = bool(st) and _gate_ok(d)
    head = ("🎯 <b>ستاپ آماده</b>" if ready else
            "🔍 <b>تحلیل عمیق</b>" if st else "🔍 <b>تحلیل عمیق — بدون ستاپ</b>")

    L = [tg.BRAND,
         "",
         f"{head} — <code>{sym}</code>",
         f"⏱ قیمت لحظهٔ تحلیل: <code>{_fmt(px)}</code>"]

    fa_trend = {"up": "صعودی", "down": "نزولی", "range": "رنج"}
    L.append(f"📐 ساختار: ۴س <b>{fa_trend.get(h4.get('trend'), '؟')}</b> · "
             f"۱س <b>{fa_trend.get(h1.get('trend'), '؟')}</b> · "
             f"۱۵د <b>{fa_trend.get(m15.get('trend'), '؟')}</b>")

    ch = h1.get("channel") or {}
    if ch.get("position") is not None:
        where = ("نزدیک سقف" if ch["position"] > 0.75 else
                 "نزدیک کف" if ch["position"] < 0.25 else "میانه")
        L.append(f"📊 کانال ۱س: {where} (شیب {ch.get('slope', '؟')})")

    # اردر بلاک — نزدیک‌ترین معتبر
    obs = d.get("order_blocks") or {}
    best = None
    for tf in ("15m", "1h", "4h"):
        for b in (obs.get(tf) or []):
            if b.get("grade") in ("A", "B") and not b.get("broken"):
                if best is None or abs(b.get("dist_pct") or 99) < abs(best[1].get("dist_pct") or 99):
                    best = (tf, b)
    if best:
        tf, b = best
        L.append(f"🧱 اردر بلاک {tf}: گرید <b>{b['grade']}</b> · "
                 f"{b.get('state', '؟')} · فاصله {_pct(b.get('dist_pct'))}")

    lq = d.get("liquidity") or {}
    if lq.get("side"):
        fa = {"above": "بالا", "below": "پایین", "none": "خنثی"}.get(lq["side"], lq["side"])
        L.append(f"💧 آهن‌ربای نقدینگی: {fa}")

    ll = d.get("lead_lag") or {}
    if ll.get("fa"):
        L.append(f"🔗 {ll['fa']}")

    dom = d.get("dominance") or {}
    if isinstance(dom, dict) and dom.get("regime"):
        L.append(f"🌐 رژیم USDT.D: <b>{dom['regime']}</b>")
    elif isinstance(dom, dict) and dom.get("note"):
        L.append(f"🌐 دامیننس: {dom['note']}")

    if st:
        L += ["",
              f"{'🟢 خرید (LONG)' if st.get('dir') == 'LONG' else '🔴 فروش (SHORT)'}"
              f" · {st.get('strategy', '—')}",
              f"ورود <code>{_fmt(st.get('entry'))}</code> · "
              f"استاپ <code>{_fmt(st.get('sl'))}</code>",
              f"تارگت۱ <code>{_fmt(st.get('tp1'))}</code> · "
              f"تارگت۲ <code>{_fmt(st.get('tp2'))}</code> · "
              f"RR <b>{st.get('rr', '—')}</b>"]
        e, s1, t1 = st.get("entry"), st.get("sl"), st.get("tp1")
        if e and t1:
            third = e + (t1 - e) / 3
            L.append(f"🪜 تریل: با رسیدن به <code>{_fmt(third)}</code> "
                     f"(⅓ مسیر) استاپ می‌آید در سودِ کارمزددار")
        if pm.get("pro"):
            L.append("⚖️ " + "؛ ".join(pm["pro"][:2]))
        if pm.get("con"):
            L.append("⚠️ " + "؛ ".join(pm["con"][:2]))
        if not ready:
            L.append("⛔ <b>هنوز ستاپ آماده نیست</b> — " + _gate_why(d))
    else:
        L += ["", "⛔ ستاپ معتبری پیدا نشد. NO TRADE تصمیم حرفه‌ای معتبر است."]

    ok = d.get("engines_ok")
    L += ["",
          f"🧠 {ok}/9 انجین اجرا شد · عمق ۱س {d.get('depth', {}).get('h1_bars')} کندل · "
          f"منبع <code>{d.get('source', '؟')}</code>",
          f"🕐 <code>{tg.tehran()}</code> به وقت ایران"]

    errs = d.get("errors") or {}
    if errs:
        L.append(f"⚠️ انجین‌های ناموفق: {', '.join(errs.keys())}")

    return tg.scrub("\n".join(L))


def _gate_ok(d):
    """آیا این تحلیل حق دارد «ستاپ آماده» صدا شود؟"""
    return not _gate_why(d)


def _gate_why(d):
    """اگر ستاپ آماده نیست، دقیقاً چرا — رشتهٔ خالی یعنی آماده است."""
    st = d.get("setup") or {}
    if not st:
        return "ستاپی نیست"
    age = d.get("candle_age_min")
    if age is None or age > MAX_AGE_MIN:
        return f"دادهٔ لحظهٔ ارسال کهنه است ({age} دقیقه)"
    pm = d.get("premortem") or {}
    npro, ncon = len(pm.get("pro") or []), len(pm.get("con") or [])
    if pm and npro <= ncon:
        return f"بازجویی ۱۵د رد کرد (دلیل استاپ {ncon} ≥ دلیل تارگت {npro})"
    return ""


def run(sym, send=True):
    d, cds = deep.analyze(sym)
    path = deep.save(d)
    print(f"→ {path}")

    png = None
    try:
        import deep_chart
        tmp = Path(tempfile.mkdtemp())
        png = deep_chart.render(d, cds, str(tmp / f"deep-{d['symbol']}.png"))
        print(f"→ چارت: {png}")
    except Exception as e:                            # noqa: BLE001 - چارت نباید تحلیل را بکشد
        print(f"⚠ چارت ساخته نشد: {type(e).__name__}: {e}")

    if not send:
        return d

    token, chat = tg.creds()
    if not token or not chat:
        print("⚠ توکن تلگرام نیست — فقط ذخیره شد")
        return d

    cap = caption(d)
    if png:
        with open(png, "rb") as f:
            blob = f.read()
        resp = tg._post(token, "sendPhoto",
                        {"chat_id": chat, "caption": cap, "parse_mode": "HTML"},
                        {"photo": (f"{d['symbol']}-deep.png", blob)})
    else:
        resp = tg._post(token, "sendMessage",
                        {"chat_id": chat, "text": cap, "parse_mode": "HTML",
                         "disable_web_page_preview": "true"})
    if not (resp or {}).get("ok"):
        raise RuntimeError(f"تلگرام نپذیرفت: {resp}")
    mid = ((resp or {}).get("result") or {}).get("message_id")
    print(f"✓ رفت به تلگرام (message_id={mid})")
    d["tg_msg_id"] = mid
    deep.save(d)
    return d


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sym = args[0] if args else os.environ.get("SYMBOL", "BTCUSDT")
    run(sym, send="--no-tg" not in sys.argv)
