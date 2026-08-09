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
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    out = str(text)
    if tok:
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


def _post(token, method, fields, files=None):
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


def caption(s):
    dir_fa = "🟢 خرید (LONG)" if s["dir"] == "LONG" else "🔴 فروش (SHORT)"
    # نام پنل بالای هر پیام — چند هوش مصنوعی دیگر هم سیگنال می‌فرستند و حمید
    # باید بداند هر سیگنال از کدام است تا ضعیف‌ها را حذف کند.
    L = [f"🏷 <b>{PANEL_NAME}</b>",
         f"<b>{dir_fa} — {s['sym']}</b>  <code>{s['tf']}</code>"]
    # Which strategy produced this. Two strategies run side by side and a signal
    # that does not say which one it came from cannot be judged or learned from.
    if s.get("strategyName"):
        L.append(f"استراتژی: <b>{s['strategyName']}</b>")
    # حافظهٔ ایجنت — «اگر شباهت قوی با گذشته پیدا کردی صریح ذکر کن»: جملهٔ
    # عددی حافظه دربارهٔ همین ارز/جهت، روی خود پیام، تا تصمیم با تجربه باشد.
    if s.get("memory"):
        L.append(f"🧠 <i>{s['memory']}</i>")
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
    fresh = [s for s in signals if _key(s) not in sent][:limit]
    if not fresh:
        print(f"telegram: {len(signals)} signals, all already sent", flush=True)
        return 0

    ok = 0
    tmp = Path(__file__).resolve().parent / ".charts"
    tmp.mkdir(exist_ok=True)
    for s in fresh:
        png = None
        try:
            png = render_chart(s, str(tmp / f"{s['sym']}-{s['tf']}.png"))
        except Exception as e:                        # noqa: BLE001 - a chart failure must not lose the signal
            print(f"  chart failed for {s['sym']}: {e}", flush=True)
        try:
            if png:
                with open(png, "rb") as f:
                    blob = f.read()
                _post(token, "sendPhoto",
                      {"chat_id": chat, "caption": caption(s), "parse_mode": "HTML"},
                      {"photo": (f"{s['sym']}.png", blob)})
            else:
                _post(token, "sendMessage",
                      {"chat_id": chat, "text": caption(s), "parse_mode": "HTML",
                       "disable_web_page_preview": "true"})
            sent[_key(s)] = time.time() * 1000
            ok += 1
            print(f"  sent {s['sym']} {s['tf']} {s['dir']}{'' if png else ' (text only)'}", flush=True)
            _log_final(s)
        except urllib.error.HTTPError as e:
            print(f"  telegram rejected {s['sym']}: {e.code} {scrub(e.read()[:200])}", flush=True)
        except Exception as e:                        # noqa: BLE001 - one failure must not stop the rest
            print(f"  telegram failed for {s['sym']}: {scrub(e)}", flush=True)

    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(sent, indent=1))
    print(f"telegram: {ok} of {len(fresh)} new signals delivered", flush=True)
    return ok
