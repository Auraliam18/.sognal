"""جدول تاریخچهٔ هر ارز — پامپ/دامپ، بستر بیت‌کوین و دامیننس در همان لحظه.

دستور حمید (۱۶ اوت):

  «گذشتهٔ همهٔ ارزهایی که پایش می‌شوند از روز اولی که لانچ شدند تا لحظه‌ای
   که پایش می‌شوند در تایم ۱۵ دقیقه چک می‌شود که در چه تاریخ‌هایی پامپ یا
   دامپ شده‌اند … هر ارز می‌تواند یک جدول اطلاعات داشته باشد که زمان‌هایی
   که نوسان داده در آن ثبت شود، قیمت همان لحظهٔ بیت‌کوین ثبت شود، دامیننس
   تتر ثبت شود … و بعد به مرور فقط ارزهای جدید تاریخچه‌شان ثبت می‌شود، که
   وقتی نیاز به پایش شد اول یک سر به تاریخچه می‌زنی.»

## چرا این با چیزی که داریم فرق دارد

`pump_study` رویدادهای پامپِ **همین حالا** را می‌سنجد. این‌جا سؤال دیگری
است: «این ارز در تمام عمرش کِی و چند بار تکان خورده، و آن لحظه بازار چه
شکلی بود؟» — یعنی یک پروندهٔ دائمی برای هر ارز، نه یک عکس لحظه‌ای.

## ساختار هر رکورد نوسان

هر رویداد این‌هاست و همه از کندل واقعی می‌آیند:

    at            زمان رویداد (UTC)
    kind          pump یا dump
    move_pct      اندازهٔ حرکت روی پنجرهٔ ۱۵دقیقه‌ای
    bars          چند کندل طول کشید
    vol_x         حجم نسبت به میانگین — پامپِ بی‌حجم پامپ نیست
    btc_price     قیمت بیت‌کوین در همان لحظه
    btc_move_pct  بیت‌کوین در همان پنجره چه کرد (کل بازار بود یا این ارز؟)
    usdt_dom      دامیننس تتر در همان لحظه
    retrace_pct   چقدرش را پس داد (تا ۲۴ کندل بعد)

`btc_move_pct` مهم‌ترین ستون است و عمداً کنار move_pct نشسته: ارزی که
۸٪ رفته وقتی کل بازار ۷٪ رفته، پامپ نکرده — با بازار بالا آمده. بدون
این ستون، جدول پر می‌شود از رویدادهایی که فقط بازار بودند.

## انباشتگی و «فقط ارزهای جدید»

هر ارز یک مرز پیشروی دارد. اجرای اول کل تاریخِ دردسترس را می‌خواند؛
اجراهای بعد فقط از مرز به بعد. یعنی همان چیزی که حمید خواست: تاریخچه
یک بار ساخته می‌شود و بعد فقط ارزهای تازه و کندل‌های تازه اضافه می‌شوند.

## محدودیت صادقانه

«از روز لانچ» به آن‌چه صرافی می‌دهد محدود است. اکثر منابع رایگان روی
۱۵دقیقه چند هزار کندل می‌دهند (~۱ تا ۲ ماه)، نه کل عمر ارز. این فایل
هرچه در دسترس باشد می‌گیرد و در `covers_from` می‌نویسد از کِی پوشش دارد
— تا کسی این را با «کل عمر ارز» اشتباه نگیرد.

اجرا:
    python3 -m hamid.coin_history --symbols 200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
DB = ROOT / "brain" / "coins"

PUMP_PCT = 4.0          # حرکت خالص در پنجره تا «رویداد» شمرده شود
WINDOW = 8              # پنجرهٔ ۸ کندلِ ۱۵دقیقه‌ای = دو ساعت
RETRACE_BARS = 24       # تا شش ساعت بعد، چقدر پس داد
MAX_EVENTS = 400        # سقف رویداد در هر ارز


def _path(sym):
    return DB / f"{sym}.json"


def load(sym):
    try:
        return json.loads(_path(sym).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001 - اولین بار
        return {"symbol": sym, "events": [], "frontier": 0,
                "covers_from": None, "runs": 0}


def save(sym, j):
    DB.mkdir(parents=True, exist_ok=True)
    _path(sym).write_text(json.dumps(j, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def _nearest(series, t):
    """مقدار سری کمکی (بیت‌کوین/دامیننس) نزدیک‌ترین به این زمان.

    سری کمکی ممکن است کندل کم داشته باشد؛ اگر فاصله از دو کندل بیشتر شد
    None برمی‌گردد — عدد تقریبیِ دور، بدتر از نبودِ عدد است.
    """
    if not series:
        return None
    best, gap = None, None
    for c in series:
        d = abs(c["t"] - t)
        if gap is None or d < gap:
            best, gap = c, d
    if best is None:
        return None
    step = (series[1]["t"] - series[0]["t"]) if len(series) > 1 else 0
    if step and gap > step * 2:
        return None
    return best


def find_events(cd, btc=None, dom=None, pump_pct=PUMP_PCT, window=WINDOW):
    """رویدادهای نوسان در این سری، با بستر بازار در همان لحظه."""
    out = []
    if len(cd) < window + 2:
        return out
    vols = [c.get("v") or 0 for c in cd]
    i = window
    while i < len(cd):
        a, b = cd[i - window], cd[i]
        if not a["o"]:
            i += 1
            continue
        move = (b["c"] - a["o"]) / a["o"] * 100
        if abs(move) < pump_pct:
            i += 1
            continue
        base = vols[max(0, i - 60):i - window] or [1]
        avg = sum(base) / len(base) or 1
        vwin = sum(vols[i - window:i + 1]) / (window + 1)
        # پس‌دادن: تا شش ساعت بعد چقدر از حرکت برگشت
        tail = cd[i + 1:i + 1 + RETRACE_BARS]
        if tail:
            ext = (min(c["l"] for c in tail) if move > 0
                   else max(c["h"] for c in tail))
            retr = abs(b["c"] - ext) / abs(b["c"] - a["o"]) * 100 \
                if b["c"] != a["o"] else 0
        else:
            retr = None
        bc = _nearest(btc or [], b["t"])
        ba = _nearest(btc or [], a["t"])
        dc = _nearest(dom or [], b["t"])
        out.append({
            "at": b["t"],
            "kind": "pump" if move > 0 else "dump",
            "move_pct": round(move, 2),
            "bars": window,
            "vol_x": round(vwin / avg, 2) if avg else None,
            "btc_price": round(bc["c"], 2) if bc else None,
            "btc_move_pct": (round((bc["c"] - ba["o"]) / ba["o"] * 100, 2)
                             if bc and ba and ba["o"] else None),
            "usdt_dom": round(dc["c"], 3) if dc else None,
            "retrace_pct": round(retr, 1) if retr is not None else None,
        })
        i += window                                  # رویدادهای هم‌پوشان نه
    return out


def update(sym, cd, btc=None, dom=None):
    """تاریخچهٔ این ارز را با کندل‌های تازه جلو ببر."""
    j = load(sym)
    if not cd:
        return j
    fresh = [c for c in cd if c["t"] > (j.get("frontier") or 0)]
    if not fresh and j.get("runs"):
        return j
    evs = find_events(fresh or cd, btc, dom)
    have = {e["at"] for e in j["events"]}
    for e in evs:
        if e["at"] not in have:
            j["events"].append(e)
            have.add(e["at"])
    j["events"].sort(key=lambda e: e["at"])
    j["events"] = j["events"][-MAX_EVENTS:]
    j["frontier"] = max(j.get("frontier") or 0, cd[-1]["t"])
    if j.get("covers_from") is None:
        j["covers_from"] = cd[0]["t"]
    j["covers_from"] = min(j["covers_from"], cd[0]["t"])
    j["runs"] = (j.get("runs") or 0) + 1
    j["updated"] = int(time.time() * 1000)
    j["summary"] = summarize(j["events"])
    save(sym, j)
    return j


def summarize(events):
    """چکیده‌ای که ایجنت قبل از تحلیل می‌خواند — «این ارز چه‌جور ارزی است»."""
    if not events:
        return {"n": 0}
    pumps = [e for e in events if e["kind"] == "pump"]
    dumps = [e for e in events if e["kind"] == "dump"]
    # رویداد «مستقل» یعنی حرکتِ خودِ ارز، نه سواری روی بازار
    solo = [e for e in events
            if e.get("btc_move_pct") is not None
            and abs(e["move_pct"]) > abs(e["btc_move_pct"]) * 2]
    retr = [e["retrace_pct"] for e in events if e.get("retrace_pct") is not None]
    vx = [e["vol_x"] for e in events if e.get("vol_x")]
    return {
        "n": len(events),
        "pumps": len(pumps), "dumps": len(dumps),
        "solo_moves": len(solo),
        "solo_pct": round(100 * len(solo) / len(events), 1),
        "median_move_pct": round(sorted(abs(e["move_pct"]) for e in events)
                                 [len(events) // 2], 2),
        "median_retrace_pct": (round(sorted(retr)[len(retr) // 2], 1)
                               if retr else None),
        "median_vol_x": round(sorted(vx)[len(vx) // 2], 2) if vx else None,
    }


def brief(sym):
    """یک خط برای ایجنت، قبل از تحلیل — «اول یک سر به تاریخچه بزن»."""
    j = load(sym)
    s = j.get("summary") or {}
    if not s.get("n"):
        return f"{sym}: تاریخچه‌ای ثبت نشده"
    return (f"{sym}: {s['n']} نوسان ثبت‌شده ({s['pumps']} پامپ / {s['dumps']} دامپ) · "
            f"{s['solo_pct']}٪ مستقل از بیت‌کوین · "
            f"میانهٔ حرکت {s['median_move_pct']}٪ · "
            f"میانهٔ پس‌دادن {s['median_retrace_pct']}٪")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=200)
    ap.add_argument("--bars", type=int, default=1000)
    a = ap.parse_args()
    import sources
    from hamid.trainer import top_symbols

    def candles(sym, tf, n):
        return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4],
                 "v": k[5]} for k in sources.klines(sym, tf, n)]

    btc = dom = []
    try:
        btc = candles("BTCUSDT", "15m", a.bars)
    except Exception as e:                           # noqa: BLE001
        print(f"بیت‌کوین نیامد: {type(e).__name__} — ستون بستر خالی می‌ماند")
    try:
        from hamid import dominance as _dm
        dom = _dm.series("USDT.D", "15m", a.bars)
    except Exception:                                # noqa: BLE001
        pass

    syms = top_symbols(a.symbols)
    known = {p.stem for p in DB.glob("*.json")} if DB.exists() else set()
    new = [s for s in syms if s not in known]
    print(f"{len(syms)} ارز · {len(new)} تازه (تاریخچه ندارند) · "
          f"{len(syms) - len(new)} فقط به‌روزرسانی")
    tot = {"events": 0, "solo": 0}
    for sym in syms:
        try:
            cd = candles(sym, "15m", a.bars)
            j = update(sym, cd, btc, dom)
            s = j.get("summary") or {}
            tot["events"] += s.get("n") or 0
            tot["solo"] += s.get("solo_moves") or 0
        except Exception as e:                       # noqa: BLE001
            print(f"{sym}: {type(e).__name__}")
    print(f"مجموع نوسان ثبت‌شده: {tot['events']} · مستقل از بیت‌کوین: {tot['solo']}")
    print(f"→ {DB}")


if __name__ == "__main__":
    main()
