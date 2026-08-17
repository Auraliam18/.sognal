#!/usr/bin/env python3
"""ارسال دسته‌ای سیگنال + چارت به تلگرام، با دفترچهٔ «چی قبلاً رفته».

از فایل‌های منتشرشدهٔ همین مخزن می‌خواند (همان‌که پنل می‌خواند)، هر سیگنالی
که قبلاً نفرستاده باشد را با چارت می‌فرستد، و کلیدش را در
brain/telegram-sent.json ثبت می‌کند تا هیچ سیگنالی دو بار نرود.

توکن فقط از env می‌آید (Secret یا ورودی workflow_dispatch) — هرگز در فایل.
بدون توکن، ساکت و سبز خارج می‌شود تا کرونِ بی‌Secret قرمز نزند.
"""
import io, json, os, sys, time, urllib.request
from pathlib import Path

# برند از یک منبع حقیقت (PANEL_NAME). نام مستعار عمداً tg نیست:
# این فایل یک تابع محلی `tg()` دارد که هر import هم‌نامی را سایه
# می‌زند — نسخهٔ اول همین اشتباه را داشت و main در اولین پیام
# AttributeError می‌گرفت؛ تستِ import-فقط آن را نمی‌دید.
import telegram as _brand

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SENT = ROOT / "brain" / "telegram-sent.json"
TGLOG = ROOT / "signals" / "telegram-log.json"   # «سیگنال نهایی» — پنل همین را نشان می‌دهد
CAP = 5                        # سقف هر اجرا — سیل پیام اعتماد را می‌کشد


def tg(method, payload=None, files=None, tok=""):
    url = f"https://api.telegram.org/bot{tok}/{method}"
    if files:
        import requests                                # فقط وقتی عکس هست لازم می‌شود
        r = requests.post(url, data=payload, files=files, timeout=30)
        return r.json()
    req = urllib.request.Request(url, data=json.dumps(payload or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def klines(sym, tf="15m", n=96):
    u = f"https://api.mexc.com/api/v3/klines?symbol={sym}&interval={tf}&limit={n}"
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "tg/1"}), timeout=20) as r:
        return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
                 "l": float(k[3]), "c": float(k[4])} for k in json.loads(r.read())]


def tehran(ms=None):
    """ساعت تهران — تحلیل و ارسال روی هر پیام تا تأخیر قابل راستی‌آزمایی باشد."""
    t = time.gmtime((((ms if ms else time.time() * 1000)) / 1000) + 3.5 * 3600)
    return time.strftime("%H:%M", t)


def watermark(ax):
    """امضای کانال حمید — Trade_Osuli — پشت کندل‌ها، کم‌رنگ و تمیز؛ تبلیغ
    هست ولی دید چارت را اشغال نمی‌کند (خواستهٔ خودش، کلمه به کلمه)."""
    ax.text(0.5, 0.5, "@Trade_Osuli", transform=ax.transAxes,
            fontsize=40, color="#9aa4b5", alpha=0.18, ha="center", va="center",
            rotation=15, fontweight="bold", zorder=0)


def chart(sym, cd, entry, sl, tp1, tp2, dir_, ob=None, pat=None, htf=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # تم تیرهٔ تریدینگ‌ویو — همان چیزی که حمید هر روز می‌بیند؛ تمیز و بی‌شلوغی
    fig, ax = plt.subplots(figsize=(9, 5), dpi=110, facecolor="#131722")
    ax.set_facecolor("#131722")
    for sp in ax.spines.values():
        sp.set_color("#2a2e39")
    ax.tick_params(colors="#b2b5be", labelsize=8.5)
    watermark(ax)
    # کندل‌ها واضح‌تر (دستور حمید، ۱۵ اوت). چهار چیز عوض شد و هر کدام
    # دلیل دارد: بدنه پهن‌تر (۰.۶۶ → ۰.۸۰) تا از دور خوانده شود؛ ویک
    # هم‌رنگ خودِ کندل و ضخیم‌تر به‌جای خاکستریِ محو، چون رنگِ ویک همان
    # اطلاعاتی است که رد شدن یا نشدن را نشان می‌دهد؛ لبهٔ تیره دور بدنه
    # تا کندل‌های چسبیده از هم جدا دیده شوند؛ و کفِ ارتفاع برای دوجی تا
    # کندلِ بی‌بدنه به‌جای یک خط نامرئی، یک نوار نازکِ دیدنی باشد.
    span = max(k["h"] for k in cd) - min(k["l"] for k in cd) if cd else 0
    floor_h = (span or 1) * 0.0016
    for i, k in enumerate(cd):
        up = k["c"] >= k["o"]
        col = "#26a69a" if up else "#ef5350"
        ax.plot([i, i], [k["l"], k["h"]], color=col, lw=1.1, zorder=2,
                solid_capstyle="round")
        ax.add_patch(plt.Rectangle((i - 0.40, min(k["o"], k["c"])), 0.80,
                     max(abs(k["c"] - k["o"]), floor_h),
                     facecolor=col, edgecolor="#0d1017", linewidth=0.35,
                     zorder=3))
    # دستور حمید (۱۲ اوت): «سیگنال با خط روندهای معتبر در چارت باشد و اردر
    # بلاک هم مشخص باشد.» سطوح معتبر (همان قاعدهٔ ≥۲ واکنش + کف نویز خودش)
    # و کانالِ فیت‌شده روی سوینگ‌ها، از همین پنجرهٔ کندل کشیده می‌شوند —
    # اگر سطح/کانال معتبری نبود، چیزی کشیده نمی‌شود؛ خط تزئینی ممنوع.
    try:
        from hamid import structure as _st
        for lv in _st.levels(cd)[:4]:
            ax.axhline(lv.price, color="#787b86", lw=0.9, ls=":", zorder=1)
            ax.text(-0.5, lv.price, f"{'R' if lv.kind == 'high' else 'S'}{lv.reactions}",
                    color="#787b86", fontsize=7, va="bottom", ha="left")
        ch = _st.channel(cd)
        if ch:
            xs = list(range(len(cd)))
            ax.plot(xs, [ch.upper[0] * i + ch.upper[1] for i in xs],
                    color="#5d8ecb", lw=1.0, ls="-", alpha=0.8, zorder=1)
            ax.plot(xs, [ch.lower[0] * i + ch.lower[1] for i in xs],
                    color="#5d8ecb", lw=1.0, ls="-", alpha=0.8, zorder=1)
    except Exception:                                  # noqa: BLE001 - تحلیل روی چارت اختیاری است
        pass
    # ── خط روند ۱ساعته و ۴ساعته (دستور حمید، ۱۵ اوت) ──────────────────────
    #
    # خط روی کندل تایم بالا محاسبه می‌شود ولی روی همین محور ۵دقیقه کشیده
    # می‌شود — نگاشت با **timestamp** انجام می‌گیرد نه با ایندکس، وگرنه خط
    # ۴ساعته چند برابر جابه‌جا می‌افتد و عددی نشان می‌دهد که هیچ‌جا نیست.
    #
    # خطِ شکسته‌شده پاک نمی‌شود، نقطه‌چین می‌شود: قانون «خط معتبر حذف
    # نمی‌شود؛ وضعیتش عوض می‌شود» در سند شخصی‌سازی حمید.
    _lo = min(k["l"] for k in cd)
    _hi = max(k["h"] for k in cd)
    for _v in (entry, sl, tp1, tp2):
        if _v:
            _lo, _hi = min(_lo, _v), max(_hi, _v)
    if ob and ob.get("low") is not None:
        _lo, _hi = min(_lo, ob["low"]), max(_hi, ob["high"])
    _pad = (_hi - _lo) * 0.06 or _hi * 0.01
    _lo, _hi = _lo - _pad, _hi + _pad
    for lbl, tl, hcd, col in (htf or []):
        try:
            xs = [0, len(cd) - 1]
            ys = [tl.at_t(cd[0]["t"], hcd), tl.at_t(cd[-1]["t"], hcd)]
            if None in ys:
                continue
            # خطی که تمامش بیرون کادر است هیچ اطلاعاتی نمی‌دهد و فقط
            # برچسبش بیرون چارت شناور می‌شود. کشیده نمی‌شود.
            if (max(ys) < _lo) or (min(ys) > _hi):
                continue
            ax.plot(xs, ys, color=col, lw=1.6 if not tl.broken else 1.1,
                    ls="-" if not tl.broken else (0, (5, 3)), alpha=0.95, zorder=4)
            ax.text(1, min(max(ys[0], _lo), _hi),
                    f"{lbl} {'TL' if not tl.broken else 'TL✕'} ·{tl.touches}",
                    color=col, fontsize=7.5, va="bottom", ha="left",
                    fontweight="bold")
        except Exception:                              # noqa: BLE001 - یک خط نباید چارت را ببرد
            continue
    if ob and ob.get("low") is not None and ob.get("high") is not None:
        ax.axhspan(ob["low"], ob["high"], color="#f0a92e", alpha=0.14, zorder=0)
        ax.text(len(cd) + 1, (ob["low"] + ob["high"]) / 2, "OB",
                color="#f0a92e", fontsize=8, va="center")
    # برچسب لاتین عمداً: matplotlib شکل‌دهی عربی ندارد و فارسی حروف‌جدا و
    # برعکس می‌افتد (در عکس تست دیده شد). فارسی در کپشن زیر عکس هست.
    for v, c, lb in [(entry, "#42a5f5", "ENTRY"), (sl, "#ef5350", "SL"),
                     (tp1, "#26a69a", "TP1"), (tp2, "#66bb6a", "TP2")]:
        if v:
            ax.axhline(v, color=c, lw=1.1, ls="--")
            ax.text(len(cd) + 1, v, lb, color=c, fontsize=8, va="center")
    ax.set_title(f"{sym}  {dir_}", loc="left", color="#d1d4dc", fontweight="bold")
    ax.set_xlim(-1, len(cd) + 8)
    # الگوی کشف‌شده (دستور حمید): خط کلیدی الگو + مسیر انتظاریِ حرکت بعدی
    # به سمت تارگت‌ها — نقطه‌چین، تا با حرکت واقعی اشتباه نشود.
    if pat and pat.get("key"):
        ax.axhline(pat["key"], color="#ab47bc", lw=1.0, ls=":")
        ax.text(len(cd) + 1, pat["key"], pat.get("label", "PATTERN"),
                color="#ab47bc", fontsize=8, va="center")
    # مسیر انتظاری تا تارگت‌ها روی «هر» سیگنال (دستور حمید ۱۳ اوت) — نقطه‌چین
    px0 = cd[-1]["c"]
    path_x, path_y = [len(cd) - 1], [px0]
    for tgt in (tp1, tp2):
        if tgt:
            path_x.append(path_x[-1] + 5)
            path_y.append(tgt)
    if len(path_x) > 1:
        ax.plot(path_x, path_y, color="#ab47bc", lw=1.4, ls="--",
                marker=">", markersize=5, alpha=0.9, zorder=4)
    # ── محور عمودی را کندل‌ها تعیین می‌کنند، نه خط‌ها ─────────────────────
    #
    # بدون این، یک خط روند تایم بالا که دور از قیمت است محور را می‌کشد و
    # کندل‌ها ریز می‌شوند — دقیقاً برعکس چیزی که حمید خواست. حالا بازه از
    # کندل‌ها و سطوح معامله (ورود/استاپ/تارگت) گرفته می‌شود و هر خطی که
    # بیرون بیفتد صرفاً بریده می‌شود، نه اینکه چارت را خراب کند.
    ax.set_ylim(_lo, _hi)
    ax.grid(alpha=0.18, color="#2a2e39")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def collect():
    """سیگنال‌های الان، از همان فایل‌هایی که پنل نشان می‌دهد."""
    out = []
    try:
        h = json.loads((ROOT / "signals" / "hamid-latest.json").read_text())
    except Exception:                                  # noqa: BLE001
        h = {}
    usdt = (((h.get("world") or {}).get("dominance")) or {}).get("usdt")
    for s in h.get("setups", []):
        if s.get("waiting"):
            continue
        out.append({"key": f"hamid|{s['symbol']}|{s['dir']}", "analyzed_at": h.get("generated"),
                    "sym": s["symbol"], "dir": s["dir"], "tf": "15m",
                    "entry": s["entry"], "sl": s["sl"], "tp1": s.get("tp1"), "tp2": s.get("tp2"),
                    "name": "روش حمید — پولبک دوم", "elite": False, "usdt": usdt})
    try:
        r = json.loads((ROOT / "signals" / "latest.json").read_text())
    except Exception:                                  # noqa: BLE001
        r = {}
    for s in r.get("signals", []):
        out.append({"key": f"{s.get('strategy')}|{s['sym']}|{s['tf']}|{s['dir']}", "analyzed_at": r.get("generated"),
                    "sym": s["sym"], "dir": s["dir"], "tf": s.get("tf", "15m"),
                    "entry": s["entry"], "sl": s["sl"], "tp1": s.get("tp1"), "tp2": s.get("tp2"),
                    "name": s.get("strategyName", ""), "elite": bool(s.get("elite")),
                    "usdt": usdt, "candles": s.get("candles")})
    return out


def main():
    tok = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not tok or not chat:
        print("توکن یا chat id نیست — تا Secret ثبت نشود این اجرا کاری نمی‌کند")
        return
    sent = []
    if SENT.exists():
        try:
            sent = json.loads(SENT.read_text())
        except Exception:                              # noqa: BLE001
            sent = []
    seen = set(sent)
    log = []
    if TGLOG.exists():
        try:
            log = json.loads(TGLOG.read_text()).get("sent", [])
        except Exception:                              # noqa: BLE001
            log = []
    new = [s for s in collect() if s["key"] not in seen]
    # ردهٔ مسابقه اول می‌رود — بهترین‌ها نباید پشت سقف ارسال بمانند
    new.sort(key=lambda s: (not s["elite"],))
    delivered = 0
    for s in new[:CAP]:
        cap = (f"🏷 {_brand.PANEL_NAME}\n"
               f"{'🏆 ' if s['elite'] else ''}🚨 {s['sym']} — "
               f"{'خرید' if s['dir'] == 'LONG' else 'فروش'} ({s['tf']})\n"
               f"استراتژی: {s['name']}\n"
               f"ورود: {s['entry']}\nاستاپ: {s['sl']}\n"
               f"تارگت۱: {s['tp1']}" + (f"\nتارگت۲: {s['tp2']}" if s.get("tp2") else "") +
               (f"\nدامیننس تتر: {s['usdt']}٪" if s.get("usdt") else "") +
               f"\n🕐 تحلیل {tehran(s.get('analyzed_at'))} · ارسال {tehran()} — به وقت ایران" +
               f"\n\nپنل: auraliam18.github.io/.sognal")
        try:
            # چارت ۵ دقیقه — خواستهٔ حمید؛ کندل‌های ضمیمه فقط جایگزین اضطراری
            cd = klines(s["sym"], "5m") or s.get("candles") or []
            png = chart(s["sym"], cd[-96:], s["entry"], s["sl"], s.get("tp1"), s.get("tp2"), s["dir"])
            j = tg("sendPhoto", {"chat_id": chat, "caption": cap},
                   {"photo": (f"{s['sym']}.png", png, "image/png")}, tok)
        except Exception as e:                         # noqa: BLE001 - fall back to text-only
            print(f"  چارت {s['sym']} نشد ({type(e).__name__}) — متنی می‌فرستم")
            try:
                j = tg("sendMessage", {"chat_id": chat, "text": cap}, tok=tok)
            except Exception as e2:                    # noqa: BLE001
                print(f"  ارسال {s['sym']} شکست: {type(e2).__name__}")
                continue
        if j.get("ok"):
            seen.add(s["key"])
            delivered += 1
            log.insert(0, {"at": int(time.time() * 1000),
                           "sym": s["sym"], "dir": s["dir"], "tf": s["tf"],
                           "entry": s["entry"], "sl": s["sl"], "tp1": s.get("tp1"),
                           "tp2": s.get("tp2"), "name": s["name"], "elite": s["elite"]})
            print(f"✓ {s['sym']} {s['dir']} رفت")
        else:
            print(f"✗ {s['sym']}: {j.get('description')}")
    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(list(seen)[-500:], ensure_ascii=False))
    TGLOG.write_text(json.dumps({"generated": int(time.time() * 1000),
                                 "sent": log[:40]}, ensure_ascii=False, indent=1))
    print(f"{delivered} سیگنال فرستاده شد · {len(new) - delivered if len(new) > CAP else 0} ماند برای اجرای بعد")


if __name__ == "__main__":
    main()
