#!/usr/bin/env python3
"""Sends a signal to Telegram as a chart with the numbers written on it.

The panel already sends signals from the browser when it is open and can reach
the exchange. This is the other path: the scan runs on a GitHub runner every ten
minutes whether anything is open or not, and this delivers what it finds.

Two rules that matter more than the formatting.

A signal is sent once. The scan re-runs every ten minutes and the same setup
will still be there on the next pass, so without a memory of what has gone out
the same trade would arrive six times an hour. `signals/sent.json` is that
memory, keyed on symbol, timeframe, direction and the entry price rounded, and
it forgets an entry after twelve hours so a genuinely new setup on the same pair
can still arrive.

Nothing is sent without credentials. No token means no delivery and a printed
line saying so — never a silent success.

    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 scan.py --telegram
"""
import json, os, time, urllib.error, urllib.request, uuid
from pathlib import Path

API = "https://api.telegram.org"
SENT = Path(__file__).resolve().parent.parent.parent / "signals" / "sent.json"
TGLOG = Path(__file__).resolve().parent.parent.parent / "signals" / "telegram-log.json"
TTL_MS = 12 * 3600 * 1000


def _log_final(s):
    """«سیگنال نهایی» — هر چه واقعاً به تلگرام رفت، برای نمایش در پنل هم ثبت
    می‌شود. یک فایل مشترک با tg_batch، که پنل یک منبع حقیقت داشته باشد."""
    try:
        log = json.loads(TGLOG.read_text()).get("sent", []) if TGLOG.exists() else []
    except Exception:                                  # noqa: BLE001
        log = []
    log.insert(0, {"at": int(time.time() * 1000),
                   "sym": s.get("sym"), "dir": s.get("dir"), "tf": s.get("tf"),
                   "entry": s.get("entry"), "sl": s.get("sl"),
                   "tp1": s.get("tp1"), "tp2": s.get("tp2"),
                   "name": s.get("strategyName") or s.get("name") or "",
                   "elite": bool(s.get("elite"))})
    TGLOG.parent.mkdir(parents=True, exist_ok=True)
    TGLOG.write_text(json.dumps({"generated": int(time.time() * 1000),
                                 "sent": log[:40]}, ensure_ascii=False, indent=1))


def creds():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return (tok, chat) if tok and chat else (None, None)


def creds2():
    """مقصد دوم — دستور حمید (۱۴ اوت): «همزمان هم به قبلی و هم به این».

    از محیط خوانده می‌شود، نه از کد. توکن هرگز داخل مخزن نمی‌نشیند
    (قانون ۰۵: «Secretها فقط در Backend secret store یا environment امن؛
    نه Git، Prompt، HTML، localStorage یا Log»). اگر تنظیم نشده باشد،
    هیچ اتفاقی نمی‌افتد و مسیر اصلی دست‌نخورده کار می‌کند.
    """
    tok = os.environ.get("TELEGRAM_BOT_TOKEN_2", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID_2", "").strip()
    return (tok, chat) if tok and chat else (None, None)


def scrub(text):
    """Remove the bot token from anything about to be printed.

    urllib puts the request URL into its exception text, and the Telegram URL is
    https://api.telegram.org/bot<TOKEN>/sendMessage — so a plain network failure
    printed the full token. Inside GitHub Actions the registered secret gets
    masked, which is why this was survivable; but the same code runs from a
    laptop, from n8n, from anywhere, and there the token would land in the
    output in the clear. Relying on someone else's masking for a secret we
    already hold is not a safety property, it is luck.
    """
    out = str(text)
    # هر دو مقصد پاک می‌شوند — بات دوم هم همان‌قدر راز است که اولی
    for tok in (os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
                os.environ.get("TELEGRAM_BOT_TOKEN_2", "").strip()):
        if not tok:
            continue
        out = out.replace(tok, "***")
        # the numeric prefix alone identifies the bot, so hide bot<id>: too
        head = tok.split(":")[0]
        if head:
            out = out.replace(f"bot{head}", "bot***")
    return out


def _load_sent():
    try:
        d = json.loads(SENT.read_text())
        now = time.time() * 1000
        return {k: v for k, v in d.items() if now - v < TTL_MS}
    except Exception:                                # noqa: BLE001 - a missing or torn file is an empty memory
        return {}


def _key(s):
    """بدون قیمت ورود. قیمت دقیق در کلید بود و بین دو چرخه چند دهم درصد
    جابه‌جا می‌شد (TAO: ‏205.3 → 206.6) — کلید عوض می‌شد و همان سیگنال دوباره
    می‌رفت؛ حمید سه تکرار را دید. حالا همان ارز/تایم‌فریم/جهت/استراتژی تا
    ۱۲ ساعت فقط یک بار می‌رود — نرسیدنِ یک ستاپ تازهٔ همان جفت در همان روز،
    ارزان‌تر از پیام تکراری است."""
    return f"{s.get('strategy','?')}|{s['sym']}|{s['tf']}|{s['dir']}"


# متدهایی که آینه می‌شوند. getMe/getUpdates و هر چیز خواندنی آینه نمی‌شود —
# فقط چیزی که واقعاً پیام است.
MIRROR_METHODS = {"sendMessage", "sendPhoto", "sendDocument", "sendMediaGroup"}

# فیلدهای ریپلای به شناسهٔ پیام در چتِ *اول* اشاره می‌کنند و در چت دوم
# بی‌معنا (و خطاساز) اند. در آینه حذف می‌شوند و به‌جایش پیام دوم مستقل
# می‌رود — نتیجه‌ها در چت دوم ریپلای نمی‌شوند ولی می‌رسند.
_REPLY_FIELDS = ("reply_to_message_id", "reply_parameters",
                 "allow_sending_without_reply")


def _mirror(method, fields, files=None):
    """همان پیام را به مقصد دوم هم بفرست — بهترین‌تلاش، بی‌صدا در خطا.

    آینه هرگز نباید مسیر اصلی را بشکند: اگر بات دوم توکن غلط داشته باشد،
    بلاک شده باشد یا شبکه‌اش قطع باشد، سیگنالِ مقصد اول باید رفته باشد.
    برای همین خروجی‌اش دور ریخته می‌شود و استثنا بالا نمی‌رود.
    """
    tok2, chat2 = creds2()
    if not tok2:
        return None
    f2 = {k: v for k, v in (fields or {}).items() if k not in _REPLY_FIELDS}
    f2["chat_id"] = chat2
    try:
        r = _post_once(tok2, method, f2, files)
        if not (r or {}).get("ok"):
            print(f"  ⚠ آینهٔ تلگرام نپذیرفت: {scrub(str(r))[:160]}", flush=True)
        return r
    except Exception as e:                            # noqa: BLE001 - آینه هرگز مسیر اصلی را نمی‌کشد
        print(f"  ⚠ آینهٔ تلگرام نرفت: {scrub(f'{type(e).__name__}: {e}')[:160]}",
              flush=True)
        return None


def _post(token, method, fields, files=None, mirror=True):
    """ارسال به مقصد اول، و اگر مقصد دومی تنظیم شده باشد، آینه به آن.

    خروجی همیشه پاسخ مقصد *اول* است — چون message_id ذخیره‌شده، دفتر
    ضدتکرار و ریپلای نتیجه همه به همان چت وابسته‌اند و نباید عوض شوند.
    """
    resp = _post_once(token, method, fields, files)
    if mirror and method in MIRROR_METHODS:
        _mirror(method, fields, files)
    return resp


def _post_once(token, method, fields, files=None):
    """multipart/form-data by hand — sendPhoto needs it and stdlib has no helper."""
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                 f"{v}\r\n").encode()
    for k, (name, blob) in (files or {}).items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                 f"filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode()
        body += blob + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/bot{token}/{method}", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


PANEL_NAME = "حمید کلود مکس پنل"


def tehran(ms=None):
    """ساعت تهران (UTC+3:30) — حمید باید ببیند بین تحلیل و ارسال تأخیری نبوده."""
    t = time.gmtime(((ms if ms else time.time() * 1000) / 1000) + 3.5 * 3600)
    return time.strftime("%H:%M", t)


def caption(s):
    dir_fa = "🟢 خرید (LONG)" if s["dir"] == "LONG" else "🔴 فروش (SHORT)"
    # نام پنل بالای هر پیام — چند هوش مصنوعی دیگر هم سیگنال می‌فرستند و حمید
    # باید بداند هر سیگنال از کدام است تا ضعیف‌ها را حذف کند.
    # شناسهٔ یکتای سیگنال (دستور حمید ۱۳ اوت) — قابل ارجاع در نتیجه/گفتگو
    sid = time.strftime("CM-%m%d-%H%M", time.gmtime(time.time() + 3.5 * 3600))
    L = [f"🏷 <b>{PANEL_NAME}</b> · 🤖 <b>سیگنال کلود مکس</b> · 🆔 <code>{sid}-{s['sym'].replace('USDT','')}</code>",
         f"<b>{dir_fa} — {s['sym']}</b>  <code>{s['tf']}</code>"]
    # Which strategy produced this. Two strategies run side by side and a signal
    # that does not say which one it came from cannot be judged or learned from.
    if s.get("strategyName"):
        L.append(f"استراتژی: <b>{s['strategyName']}</b>")
    # حافظهٔ ایجنت — «اگر شباهت قوی با گذشته پیدا کردی صریح ذکر کن»: جملهٔ
    # عددی حافظه دربارهٔ همین ارز/جهت، روی خود پیام، تا تصمیم با تجربه باشد.
    if s.get("memory"):
        L.append(f"🧠 <i>{s['memory']}</i>")
    if s.get("liq_note"):
        L.append(f"💧 <i>{s['liq_note']}</i>")
    # نقشهٔ لیکوییدیشن — خوشه‌های تخمینی از کندل واقعی، سبک نقشهٔ kCEX
    if s.get("liqmap_note"):
        L.append(f"<i>{s['liqmap_note']}</i>")
    # بازجویی پیش از صدور — سیگنال فقط با دلایلِ تارگتِ بیشتر رسیده اینجا
    pm = s.get("premortem")
    if pm:
        # انجین الگوهای کلاسیک — الگوهای زندهٔ ۱۵د/۱س/۴س روی خود پیام
        if (pm.get("patterns") or {}).get("note"):
            L.append(f"🧩 <i>الگو: {pm['patterns']['note']}</i>")
        # انجین اردر بلاک — باکس معتبر با شمارش واکنش/هانت روی خود پیام
        if (pm.get("ob_ctx") or {}).get("note"):
            L.append(f"🧱 <i>{pm['ob_ctx']['note']}</i>")
        L.append(f"⚖️ <i>{len(pm['pro'])} دلیل تارگت / {len(pm['con'])} دلیل استاپ"
                 + (f" — مهم‌ترین: {pm['pro'][0]}" if pm["pro"] else "") + "</i>")
        if pm["con"]:
            L.append(f"⚠️ <i>ریسک شمرده‌شده: {pm['con'][0]}</i>")
        # منشور LIAM بند ۱۹: هر سیگنال باید بگوید چه چیزی باطلش می‌کند
        L.append(f"⛔ <i>باطل‌کننده: بسته‌شدن {s.get('tf','15m')} "
                 f"{'زیر' if s['dir'] == 'LONG' else 'بالای'} "
                 f"<code>{s['sl']:.10g}</code> — فرضیه شکست خورده، نه بدشانسی</i>")
    # قانون تریل حمید — روی خود پیام، تا مو به مو همان اجرا شود
    if s.get("tp1") and s.get("entry"):
        third = s["entry"] + (s["tp1"] - s["entry"]) / 3
        L.append(f"🪜 <i>قانون تریل: با رسیدن قیمت به <code>{third:.10g}</code> "
                 f"(⅓ مسیر تارگت)، استاپ را بیاور در سودِ کارمزددار؛ در ⅔ مسیر، "
                 f"استاپ به همان ⅓. دفتر کاغذی همین را خودکار حساب می‌کند.</i>")
    # هم‌زمانی — قیمت لحظهٔ ارسال از کندل ۵ دقیقه، تا حمید ببیند ورود نگذشته
    sy = s.get("sync")
    if sy:
        L.append(f"⏱ <i>قیمت لحظهٔ ارسال <code>{sy['price']:.10g}</code> — "
                 f"فاصله تا ورود {sy['dist_pct']:+}٪</i>")
    # ساعت تحلیل و ساعت ارسال، به وقت ایران — تا تأخیر قابل راستی‌آزمایی باشد
    an = s.get("analyzed_at")
    L.append((f"🕐 تحلیل <code>{tehran(an)}</code> · " if an else "🕐 ")
             + f"ارسال <code>{tehran()}</code> — به وقت ایران")
    L.append("")
    L.append(f"ورود    <code>{s['entry']:.10g}</code>")
    L.append(f"استاپ   <code>{s['sl']:.10g}</code>")
    L.append(f"تارگت۱  <code>{s['tp1']:.10g}</code>")
    if s.get("tp2") is not None:
        L.append(f"تارگت۲  <code>{s['tp2']:.10g}</code>")
    line = f"ریسک/ریوارد <b>{s['rr']}</b>"
    if s.get("conf") is not None:
        line += f" · اعتماد <b>{s['conf']}%</b>"
    if s.get("ev") is not None:
        line += f" · انتظار <b>{s['ev']:.2f}R</b>"
    if s.get("quality") is not None:
        line += f" · کیفیت <b>{s['quality']}</b>"
    L += ["", line]
    if s.get("ob"):
        L.append(f"اردر بلاک <code>{s['ob']['low']:.10g} — {s['ob']['high']:.10g}</code>")
    if s.get("channel"):
        L.append(f"کانال {s['channel']['dir']} ({s['channel']['drift']}%)")
    bits = []
    if s.get("fvg"):
        bits.append("FVG هم‌جهت ✓")
    if s.get("level"):
        bits.append(f"روی {'مقاومت' if s['level']['type']=='R' else 'حمایت'} "
                    f"({s['level']['touches']} برخورد)")
    if s.get("swept"):
        bits.append(f"نقدینگی جمع شد ({s['swept']['n']} برخورد)")
    if s.get("adx") is not None:
        bits.append(f"ADX {s['adx']}")
    if bits:
        L.append(" · ".join(bits))
    L += ["", "<i>اسکن از راه دور روی کندل واقعی — قبل از ورود خودت هم چارت را ببین.</i>"]
    # Each strategy carries its own measured record. Attaching one strategy's
    # win rate to another's signal would be worse than attaching none: it reads
    # as evidence and is not. A signal that supplies no footer gets the figure
    # measured for the original engine, which is the only one it can be.
    L.append(s.get("footer") or
             "<i>وین‌ریت اندازه‌گیری‌شدهٔ این استراتژی روی کندل واقعی ۲۲.۷٪ با انتظار +۰.۰۶۹R "
             "است: بردها بزرگ‌اند و بیشتر تریدها استاپ می‌خورند. سایز را ثابت نگه دار.</i>")
    return "\n".join(L)


def send_signals(signals, render_chart, limit=8):
    """render_chart(setup, path) -> path, or None when a chart cannot be drawn."""
    token, chat = creds()
    if not token:
        print("telegram: no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID — nothing sent", flush=True)
        return 0
    sent = _load_sent()
    now_ms = time.time() * 1000
    # ضدتکرار بین‌استراتژی — شکایت حمید: همان ستاپ یک بار با برچسب اسکن و
    # یک بار با برچسب آلارم می‌رسید؛ کلید بدون استراتژی با پنجرهٔ ۳ ساعته.
    def _dup_any(s):
        return now_ms - sent.get(f"any|{s['sym']}|{s['tf']}|{s['dir']}", 0) < 3 * 3600 * 1000

    def _sym_worn(s):
        # تنوع (شکایت حمید): یک ارز حداکثر ۲ بار در پنجرهٔ ۱۲ ساعته —
        # کانال باید بازار را بگردد، نه دور یک ارز بچرخد.
        return sum(1 for k in sent if k.startswith(f"any|{s['sym']}|")) >= 2
    def _stable(s):
        # استیبل/رپد سیگنال نمی‌شود — کشف ۱۲ اوت: RLUSD دو جای سهمیهٔ ۱۶تایی
        # را سوزاند. حرکت استیبل چند صدم درصد است؛ «سیگنال» رویش یعنی سهمیهٔ
        # کمتر برای ارز واقعی. همان فیلتر دفتر کاغذی، این‌جا در گلوگاه ارسال.
        try:
            from hamid.universe import STABLES, WRAPPED
            base = s["sym"][:-4] if s["sym"].endswith("USDT") else s["sym"]
            return base in STABLES or base in WRAPPED
        except Exception:                            # noqa: BLE001
            return False
    fresh = [s for s in signals
             if _key(s) not in sent and f"skip|{_key(s)}" not in sent
             and not _dup_any(s) and not _sym_worn(s) and not _stable(s)][:limit]
    if not fresh:
        print(f"telegram: {len(signals)} signals, all already sent", flush=True)
        return 0
    # سهمیه — دستور حمید (۱۲ اوت): «۱۶ را برای مثال گفتم؛ تا وقتی سیگنال هست
    # باید پیدا کنی و ارسالش کنی.» پس سقف، سهمیه نیست: ۴۰ فقط تور ایمنی در
    # برابر خطای نرم‌افزاری (حلقهٔ خراب) است. کیفیت را دروازه‌ها نگه می‌دارند:
    # هم‌زمانی، بازجویی وزنی، ضدتکرار، سقف ۲/ارز، و دروازهٔ استاپ-در-نویز.
    n_sent_real = len([k for k in sent if not k.startswith(("any|", "skip|"))])
    if n_sent_real >= 40:
        print(f"telegram: تور ایمنی ({n_sent_real} در ۱۲ ساعت) — احتمال حلقهٔ خراب، هیچ ارسالی", flush=True)
        return 0
    if n_sent_real >= 24:
        keep = [s for s in fresh
                if s.get("elite") or s.get("strategy") in ("alarm", "pump-radar")]
        if len(keep) < len(fresh):
            print(f"telegram: سهمیهٔ روز پر است ({n_sent_real} در ۱۲ ساعت) — "
                  f"{len(fresh) - len(keep)} سیگنال غیرالیت نگه داشته شد", flush=True)
        fresh = keep
        if not fresh:
            return 0

    ok = 0
    tmp = Path(__file__).resolve().parent / ".charts"
    tmp.mkdir(exist_ok=True)
    for s in fresh:
        # هم‌زمانی با نقطهٔ ورود — شکایت حمید: سیگنال یا از ورود رد شده بود
        # یا فاصلهٔ زیادی داشت. همین لحظه آخرین کندل ۵ دقیقه خوانده می‌شود؛
        # ردشده یا دورتر از حد → ارسال نمی‌شود، بی‌استثنا.
        try:
            import sources as _src0
            _k5 = _src0.klines(s["sym"], "5m", 3)
            _px = float(_k5[-1][4])
        except Exception as e:                        # noqa: BLE001
            _px = None
            print(f"  قیمت لحظهٔ {s['sym']} در دسترس نبود ({type(e).__name__}) — "
                  f"دروازهٔ هم‌زمانی رد شد", flush=True)
        if _px is not None and s.get("entry") and s.get("sl"):
            _stop_frac = abs(s["entry"] - s["sl"]) / s["entry"]
            _signed = ((_px - s["entry"]) / s["entry"] if s["dir"] == "LONG"
                       else (s["entry"] - _px) / s["entry"])
            if _signed < -0.5 * _stop_frac:
                print(f"  ⏱ {s['sym']} صادر نشد — قیمت از نقطهٔ ورود رد شده "
                      f"({_signed*100:+.2f}٪ به سمت استاپ)؛ سیگنالِ دیر نمی‌فرستیم", flush=True)
                sent[f"skip|{_key(s)}"] = now_ms
                continue
            if _signed > 0.025:
                print(f"  ⏱ {s['sym']} صادر نشد — فاصله تا ورود {_signed*100:.2f}٪ "
                      f"است؛ سیگنال ناهم‌زمان نمی‌فرستیم", flush=True)
                sent[f"skip|{_key(s)}"] = now_ms
                continue
            s["sync"] = {"price": _px, "dist_pct": round(_signed * 100, 2)}
        # بازجویی پیش از صدور — قانون حمید: اول در ۱۵ دقیقه ببین چه چیزهایی
        # می‌تواند استاپت کند؛ فقط با دلایلِ تارگتِ بیشتر صادر کن. سیگنالِ
        # ردشده به دفتر vetoed می‌رود تا خود دروازه نمره بگیرد. خطای زیرساخت
        # (شبکه/ایمپورت) جلوی ارسال را نمی‌گیرد — دروازه تحلیل است نه بهانه.
        try:
            import sources as _src
            from hamid import premortem as _pm
            _c15 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                    for k in _src.klines(s["sym"], "15m", 120)]
            pm = _pm.review(s, _c15) if len(_c15) >= 40 else None
        except Exception as e:                        # noqa: BLE001
            pm = None
            print(f"  بازجویی {s['sym']} در دسترس نبود ({type(e).__name__}) — "
                  f"سیگنال بدون دروازه می‌رود", flush=True)
        if pm:
            s["premortem"] = pm
            if not pm["issue"]:
                print(f"  ⚖️ {s['sym']} صادر نشد — {len(pm['con'])} دلیل استاپ در برابر "
                      f"{len(pm['pro'])} دلیل تارگت: {pm['con'][0] if pm['con'] else ''}",
                      flush=True)
                sent[f"skip|{_key(s)}"] = time.time() * 1000  # ضدتکرار بازجویی، بدون خوردن سهمیه
                try:
                    from hamid import paper as _paper
                    _paper.open_from([{"symbol": s["sym"], "dir": s["dir"],
                                       "entry": s["entry"], "sl": s["sl"],
                                       "tp1": s.get("tp1") or s["entry"],
                                       "tp2": s.get("tp2"), "stage_tag": "vetoed"}],
                                     {"veto_why": "premortem", "pm_con": pm["con"][:3],
                                      "pm_pro": pm["pro"][:3],
                                      "pattern_align": (pm.get("patterns") or {}).get("align"),
                                      "patterns": (pm.get("patterns") or {}).get("by_tf")})
                    from hamid import memory as _mem
                    _mem.remember("بررسی", s["sym"],
                                  f"بازجویی ۱۵د جلوی {s['sym']} {s['dir']} را گرفت: "
                                  + "؛ ".join(pm["con"][:2]))
                except Exception:                     # noqa: BLE001
                    pass
                continue
        png = None
        try:
            png = render_chart(s, str(tmp / f"{s['sym']}-{s['tf']}.png"))
        except Exception as e:                        # noqa: BLE001 - a chart failure must not lose the signal
            print(f"  chart failed for {s['sym']}: {e}", flush=True)
        try:
            if png:
                with open(png, "rb") as f:
                    blob = f.read()
                resp = _post(token, "sendPhoto",
                             {"chat_id": chat, "caption": caption(s), "parse_mode": "HTML"},
                             {"photo": (f"{s['sym']}.png", blob)})
            else:
                resp = _post(token, "sendMessage",
                             {"chat_id": chat, "text": caption(s), "parse_mode": "HTML",
                              "disable_web_page_preview": "true"})
            # شناسهٔ پیام — خواست حمید: اعلام نتیجه باید «ریپلایِ» همین پیام
            # باشد تا با سیگنال دیگری اشتباه نشود. روی خود دیکشنری سیگنال هم
            # می‌نشیند تا فراخوان (مثل مسیر آلارم در چرخه) در دفتر خودش ثبت
            # کند — درس TAO: دفتر آلارم شناسه نداشت و نتیجه ریپلای نشد.
            tg_mid = ((resp or {}).get("result") or {}).get("message_id")
            s["tg_msg_id"] = tg_mid
            sent[_key(s)] = time.time() * 1000
            sent[f"any|{s['sym']}|{s['tf']}|{s['dir']}"] = time.time() * 1000
            ok += 1
            print(f"  sent {s['sym']} {s['tf']} {s['dir']}{'' if png else ' (text only)'}", flush=True)
            _log_final(s)
            # هر سیگنالِ رفته باید درس هم بشود — استاپ زاما در هیچ دفتری نبود
            # چون ارسالی‌های اسکن کاغذی نمی‌شدند. حالا هر ارسال، اگر قبلاً در
            # دفتر نیست، با برچسب sig-<استراتژی> ثبت و تا نتیجه دنبال می‌شود.
            try:
                from hamid import paper as _paper
                _paper.open_from([{"symbol": s["sym"], "dir": s["dir"],
                                   "entry": s["entry"], "sl": s["sl"],
                                   "tp1": s.get("tp1") or s["entry"], "tp2": s.get("tp2"),
                                   "stage_tag": f"sig-{s.get('strategy', '?')}",
                                   "tg_msg_id": tg_mid}],
                                 {"sent_at": int(time.time() * 1000),
                                  "tg_msg_id": tg_mid,
                                  "pattern_align": ((s.get("premortem") or {}).get("patterns") or {}).get("align"),
                                  "patterns": ((s.get("premortem") or {}).get("patterns") or {}).get("by_tf"),
                                  "ob_align": ((s.get("premortem") or {}).get("ob_ctx") or {}).get("align"),
                                  "ob_hunts": ((s.get("premortem") or {}).get("ob_ctx") or {}).get("hunts"),
                                  # دستور حمید: تی‌پی‌های تجربه‌محور باید قابل شمارش باشند —
                                  # دلایل صدور روی پرونده می‌ماند تا «با تجربه» اثبات‌پذیر باشد
                                  "pm_pro": (s.get("premortem") or {}).get("pro", [])[:3],
                                  "exp_used": any(("تمرین تاریخی" in x or "حافظه" in x
                                                   or "قانون تأییدشده" in x)
                                                  for x in (s.get("premortem") or {}).get("pro", []))})
            except Exception as e:                    # noqa: BLE001 - ثبت نشدن، ارسال را نمی‌کشد
                print(f"  paper log failed for {s['sym']}: {type(e).__name__}", flush=True)
        except urllib.error.HTTPError as e:
            print(f"  telegram rejected {s['sym']}: {e.code} {scrub(e.read()[:200])}", flush=True)
        except Exception as e:                        # noqa: BLE001 - one failure must not stop the rest
            print(f"  telegram failed for {s['sym']}: {scrub(e)}", flush=True)

    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(sent, indent=1))
    print(f"telegram: {ok} of {len(fresh)} new signals delivered", flush=True)
    return ok
