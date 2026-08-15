"""دفتر انتظار پامپ — حلقهٔ گمشده‌ای که ۶۳ بار «دیر رسید» ساخت.

ریشهٔ مشکل (اندازه‌گیری ۱۵ اوت): کشفِ دنباله‌رو درست کار می‌کرد، ولی بین
اجراها فراموش می‌شد. رهبر بعد از چند ساعت «کهنه» می‌شود و دیگر ماشه نیست،
در حالی که پنجرهٔ تاریخی دنباله‌روها (میانه ~۱۱ ساعت) هنوز باز است. نتیجه:
رادار دنباله‌روی هنوز-ساکت را می‌شناخت، رهایش می‌کرد، و وقتی می‌پرید فقط
می‌نوشت «دیر است» — ۶۳ بار همین درس تکراری در حافظه.

قانون حمید، عین جمله: «باید پیشنهاد بدی که این ارز باید پامپ می‌شده و هنوز
پامپ نشده و به محض اینکه حجم بخوره و شروع به حرکت بکنه سیگنالش می‌کنم.»

چرخهٔ دفتر:
  ثبت    — هر کاندیدای رابطه‌دارِ هنوز-ساکت با پنجرهٔ باز، از هر اجرا.
  پایش   — هر اجرا (هر ~۳ دقیقه) حجم و حرکت ۱۵ دقیقه‌ای تک‌تک ورودی‌ها.
  شلیک   — حجم ≥ ۲.۵× میانگین + حرکت ۱.۵٪ تا ۱۰٪ و هنوز-نپریده → سیگنال
           فوری به پنل و تلگرام، با علامت یادگیری و دلیل تاریخی (قانون ۲
           حمید: سیگنالِ حاصل از یادگیری بدون توضیح ناقص است).
  انقضا  — پنجرهٔ تاریخی بست، یا بدون ما پرید → حذف با درسِ ثبت‌شده،
           فقط یک بار (نه ۶۳ بار).
"""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
WL = ROOT / "brain" / "pump-watchlist.json"

# شلیک: حجم و حرکتِ شروع — نه پامپ تمام‌شده
IGNITE_VOL_X = 2.5          # حجم ۱۵د آخر نسبت به میانگین ۳۰ کندل قبل
IGNITE_MOVE_LO = 1.5        # کمتر از این هنوز «شروع حرکت» نیست
IGNITE_MOVE_HI = 10.0       # بیشتر از این یعنی بدون ما پرید — دیگر سیگنال نیست
MISSED_PCT = 10.0           # بالای این در ۲۴س = از دست رفت، درس بنویس
MAX_AGE_H = 48              # سقف مطلق عمر ورودی، حتی با پنجرهٔ باز


def _load():
    try:
        d = json.loads(WL.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:                                # noqa: BLE001
        return {}


def _save(d):
    WL.parent.mkdir(parents=True, exist_ok=True)
    WL.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def add_candidates(blocks, picks, now_ms=None):
    """هر کاندیدای «رابطهٔ اثبات‌شده + هنوز-ساکت + پنجرهٔ باز» وارد دفتر
    می‌شود — چه pick نهایی شده باشد چه نه. picks خودشان هم ثبت می‌شوند تا
    لحظهٔ حجم خوردنشان از دست نرود."""
    now_ms = now_ms or int(time.time() * 1000)
    wl = _load()
    pick_syms = {p["symbol"] for p in picks or []}
    added = []
    bmap = {b["symbol"]: b for b in blocks or []}

    def _put(sym, leader, window_end, reasons, entry=None, sl=None, src="pick"):
        if not sym or sym in wl:
            # تمدید پنجره اگر شاهد تازه پنجرهٔ بلندتر می‌دهد
            if sym in wl and window_end and window_end > wl[sym].get("expires_at", 0):
                wl[sym]["expires_at"] = window_end
            return
        wl[sym] = {"leader": leader, "added_at": now_ms,
                   "expires_at": int(window_end) if window_end else
                   int(now_ms + 12 * 3600e3),
                   "reasons": (reasons or [])[:3], "entry": entry, "sl": sl,
                   "src": src}
        added.append(sym)

    for p in picks or []:
        b = bmap.get(p["symbol"]) or {}
        leader = (p.get("lag") or {}).get("leader") or b.get("via")
        _put(p["symbol"], leader, p.get("expires_at"),
             p.get("reasons"), p.get("entry"), p.get("sl"), "pick")

    for b in blocks or []:
        sym = b.get("symbol")
        if sym in pick_syms or b.get("skipped", "").startswith("هنوز-نپریده نیست"):
            continue
        proven = (b.get("event_leaders") or b.get("lag_corr_leaders") or
                  [l for l in (b.get("leaders") or []) if (l.get("n") or 0) >= 2])
        if not proven:
            continue
        al = b.get("alarm") or {}
        why = [x.get("reason") for x in (b.get("event_leaders") or [])[:1] if x.get("reason")] \
            or [x.get("reason") for x in (b.get("lag_corr_leaders") or [])[:1] if x.get("reason")]
        leader = (proven[0] or {}).get("symbol") or b.get("via")
        _put(sym, leader, None, why, al.get("entry"), al.get("sl"), "candidate")

    if added:
        _save(wl)
    return wl, added


def sweep(kc, now_ms=None):
    """پایش هر اجرا: شلیک (حجم+حرکت شروع)، انقضا، یا از-دست-رفتن.
    خروجی: (ignited, expired_notes) — ignited برای سیگنال فوری."""
    now_ms = now_ms or int(time.time() * 1000)
    wl = _load()
    if not wl:
        return [], []
    ignited, notes, drop = [], [], []
    for sym, e in wl.items():
        age_h = (now_ms - e.get("added_at", now_ms)) / 3600e3
        c = kc.get(sym, "15m", 40)
        if len(c) < 32:
            continue
        r15 = (c[-1]["c"] / c[-2]["c"] - 1) * 100
        r30 = (c[-1]["c"] / c[-3]["c"] - 1) * 100
        c24 = kc.get(sym, "1h", 26)
        r24 = (c24[-1]["c"] / c24[-25]["c"] - 1) * 100 if len(c24) >= 26 else 0.0
        vols = [x["v"] for x in c[-32:-1]]
        vm = sum(vols) / len(vols) if vols else 0
        vol_x = (c[-1]["v"] / vm) if vm > 0 else 0.0

        if r24 >= MISSED_PCT or max(r15, r30) > IGNITE_MOVE_HI:
            notes.append(f"{sym} بدون ما پرید ({max(r15, r30, r24):+.1f}٪) — "
                         f"در دفتر انتظار بود ولی شلیک قبل از پایش رخ داد")
            drop.append(sym)
            continue
        if now_ms > e.get("expires_at", 0) or age_h > MAX_AGE_H:
            notes.append(f"{sym} پنجرهٔ تاریخی‌اش بسته شد بی‌آنکه بپرد — "
                         f"طبق سابقهٔ خودش دیگر احتمالاً نمی‌پرد")
            drop.append(sym)
            continue
        move = max(r15, r30)
        if vol_x >= IGNITE_VOL_X and IGNITE_MOVE_LO <= move <= IGNITE_MOVE_HI:
            ignited.append({"symbol": sym, "leader": e.get("leader"),
                            "move_pct": round(move, 1), "vol_x": round(vol_x, 1),
                            "price": c[-1]["c"], "entry": e.get("entry"),
                            "sl": e.get("sl"), "reasons": e.get("reasons") or [],
                            "waited_h": round(age_h, 1)})
            drop.append(sym)
    for s in drop:
        wl.pop(s, None)
    _save(wl)
    return ignited, notes


def tg_ignition(ig):
    """پیام سیگنال شلیک — با علامت یادگیری و دلیل، قانون ۲ حمید."""
    why = ("؛ ".join(ig["reasons"]) if ig["reasons"] else
           f"دنباله‌روی تاریخی {ig['leader'] or '؟'}")
    lines = [f"🧠⚡ <b>سیگنال از یادگیری — {ig['symbol']}</b>",
             f"در دفتر انتظار بود ({ig['waited_h']}س) چون: {why}",
             f"الان حجم خورد (×{ig['vol_x']}) و حرکت شروع شد "
             f"({ig['move_pct']:+}٪) — همان لحظه‌ای که قرار بود بگیریم.",
             f"قیمت: {ig['price']}"]
    if ig.get("entry"):
        lines.append(f"ورود: {ig['entry']} · استاپ: {ig.get('sl') or '—'}")
    lines.append("(علامت 🧠 یعنی این سیگنال از تحلیل تاریخچه/یادگیری است، "
                 "نه اسکن لحظه‌ای)")
    return "\n".join(lines)


def send_ignitions(ignited, kc=None):
    if not ignited:
        return 0
    try:
        import telegram as tg
        token, chat = tg.creds()
    except Exception:                                # noqa: BLE001
        token = None
    n = 0
    for ig in ignited:
        msg = tg_ignition(ig)
        print(msg.replace("<b>", "").replace("</b>", ""))
        if token:
            try:
                tg._post(token, "sendMessage",
                         {"chat_id": chat, "text": msg, "parse_mode": "HTML",
                          "disable_web_page_preview": "true"})
                tg._log_final({"sym": ig["symbol"], "dir": "LONG", "tf": "15m",
                               "entry": ig.get("entry") or ig["price"],
                               "sl": ig.get("sl"), "tp1": None,
                               "strategyName": "دفتر انتظار پامپ 🧠"})
                n += 1
            except Exception as e:                   # noqa: BLE001
                print(f"تلگرام شلیک {ig['symbol']}: {type(e).__name__}")
        try:
            from hamid import memory as mem
            mem.remember("سیگنال", ig["symbol"],
                         f"شلیک دفتر انتظار: {ig['symbol']} بعد از "
                         f"{ig['waited_h']}س انتظار با حجم ×{ig['vol_x']} "
                         f"و {ig['move_pct']:+}٪ سیگنال شد",
                         {"leader": ig.get("leader"), "vol_x": ig["vol_x"]})
        except Exception:                            # noqa: BLE001
            pass
    return n
