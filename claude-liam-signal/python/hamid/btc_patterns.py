"""پایش دائمی الگوی بیت‌کوین و دامیننس — دستور حمید (۱۳ اوت):

    «الگو روی تایم‌های ۱ساعته و ۴ساعتهٔ بیت‌کوین باید به‌صورت دائم تکرار و
    بررسی دقیق شود؛ بیت‌کوین در ۴ساعته و یک‌روزه و دامیننس تتر از الگوهای
    خاصی پیروی می‌کنند.»

هر اجرا (سوار زنجیرهٔ چند-دقیقه‌ای):
  · BTC در ۱س، ۴س (ساخته از ۱س) و ۱روزه — با همان انجین الگوی قطعی
  · USDT.D و BTC.D از سری خودمان (کندل‌سازی dominance._bars) — با دروازهٔ
    صداقت داده: زیر ۶۰ کندل، «INSUFFICIENT» نه حدس
  · خروجی signals/btc-patterns.json برای پنل و بازجویی
  · الگوی «تأییدشدهٔ» تازه در ۴س/۱روزهٔ BTC → پیام تلگرام (ضدتکرار) +
    درس حافظه — یادگیری دائمی، قانون پیش‌فرض هر انجین جدید

بخش شبکه‌های اجتماعی/تریدینگ‌ویو (X/TV) از مسیر research.search با بودجهٔ
ماهانه انجام می‌شود — روزی یک بار، نه هر دور؛ نتیجه فقط «نقل‌قول با
منبع» است و هیچ‌وقت جای اندازه‌گیری خودمان نمی‌نشیند.

    python3 -m hamid.btc_patterns
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "btc-patterns.json"
SERIES = ROOT / "brain" / "dominance-series.json"


def _cd(rows):
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def _fa(ps):
    return [f"{p['fa']}" + (" (تأییدشده)" if p["status"] == "confirmed" else "")
            for p in ps]


def snapshot():
    """الگوهای همین لحظه، همهٔ تایم‌فریم‌ها — قطعی و بدون شبکهٔ اجتماعی."""
    import sources
    from hamid import patterns
    from hamid.lagcorr import _to4h
    from hamid.dominance import _bars

    out = {"generated": int(time.time() * 1000), "btc": {}, "usdt_d": {},
           "btc_d": {}}
    b1h = _cd(sources.klines("BTCUSDT", "1h", 500))
    if len(b1h) >= 60:
        out["btc"]["1h"] = patterns.detect(b1h)
        b4h = _to4h(b1h)
        if len(b4h) >= 60:
            out["btc"]["4h"] = patterns.detect(b4h)
    try:
        b1d = _cd(sources.klines("BTCUSDT", "1d", 400))
        if len(b1d) >= 60:
            out["btc"]["1d"] = patterns.detect(b1d)
    except Exception:                                # noqa: BLE001 - 1d همه‌جا نیست
        pass
    try:
        pts = json.loads(SERIES.read_text()).get("points") or []
        for key, slot in (("u", "usdt_d"), ("b", "btc_d")):
            bars1 = _bars(pts, key)
            if len(bars1) >= 60:
                out[slot]["1h"] = patterns.detect(bars1)
            else:
                out[slot]["note"] = (f"دادهٔ ساختاری کافی نیست ({len(bars1)} "
                                     "کندل ۱س از ۶۰) — حکم الگویی صادر نمی‌شود")
            bars4 = _bars(pts, key, 4 * 3_600_000)
            if len(bars4) >= 60:
                out[slot]["4h"] = patterns.detect(bars4)
    except Exception:                                # noqa: BLE001
        pass
    return out


def run():
    snap = snapshot()
    try:
        prev = json.loads(OUT.read_text())
    except Exception:                                # noqa: BLE001
        prev = {}
    announced = set(prev.get("announced") or [])

    # الگوی تأییدشدهٔ تازه در ۴س/۱روزهٔ BTC — کم‌تکرار و مهم؛ اعلام + حافظه
    fresh_msgs = []
    for tf in ("4h", "1d"):
        for p in (snap["btc"].get(tf) or []):
            if p["status"] != "confirmed" or p["bias"] not in ("bull", "bear"):
                continue
            key = f"{tf}|{p['name']}|{p['bias']}"
            if key in announced:
                continue
            announced.add(key)
            fresh_msgs.append(
                f"🧩 <b>الگوی تأییدشده روی BTC {tf}</b>: {p['fa']} — "
                f"سوگیری {'صعودی' if p['bias'] == 'bull' else 'نزولی'}")
            try:
                from hamid import memory
                memory.remember("تحلیل", "BTCUSDT",
                                f"الگوی {p['fa']} در {tf} بیت‌کوین تأیید شد "
                                f"(سوگیری {p['bias']})")
            except Exception:                        # noqa: BLE001
                pass
    # اعلام‌شده‌های قدیمی که دیگر روی چارت نیستند، از دفتر ضدتکرار پاک شوند
    live = {f"{tf}|{p['name']}|{p['bias']}" for tf in ("4h", "1d")
            for p in (snap["btc"].get(tf) or [])}
    announced &= live | {k for k in announced if k.split("|")[0] not in ("4h", "1d")}

    fa_lines = []
    for tf in ("1h", "4h", "1d"):
        ps = snap["btc"].get(tf)
        if ps:
            fa_lines.append(f"BTC {tf}: " + "، ".join(_fa(ps)))
    for slot, label in (("usdt_d", "USDT.D"), ("btc_d", "BTC.D")):
        for tf in ("1h", "4h"):
            ps = snap[slot].get(tf)
            if ps:
                fa_lines.append(f"{label} {tf}: " + "، ".join(_fa(ps)))
    snap["notes_fa"] = fa_lines or ["الگوی زنده‌ای دیده نمی‌شود — جواب معتبر است"]
    snap["announced"] = sorted(announced)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1))
    print("\n".join(snap["notes_fa"]))

    if fresh_msgs:
        try:
            import telegram as tg
            tok, chat = tg.creds()
            if tok:
                tg._post(tok, "sendMessage",
                         {"chat_id": chat, "parse_mode": "HTML",
                          "text": (f"{tg.BRAND}\n"
                                   + "\n".join(fresh_msgs)
                                   + f"\n🕐 <code>{tg.tehran()}</code> به وقت ایران")})
                print(f"اعلام {len(fresh_msgs)} الگوی تازهٔ BTC به تلگرام")
        except Exception as e:                       # noqa: BLE001
            print(f"اعلام تلگرام نشد: {type(e).__name__}")
    return snap


if __name__ == "__main__":
    run()
