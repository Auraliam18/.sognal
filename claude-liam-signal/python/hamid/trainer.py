"""میز تمرین ۲۰۰تایی — بازپخش تاریخی با استراتژی یادگرفته (دستور حمید ۱۴ اوت).

«هر یک ساعت باید حداقل ۲۰۰ ترید کاغذی انجام شود؛ چه لایو روی چارت و چه
برگشتن به گذشتهٔ چارت ارزها و ترید بر اساس اوردر بلاک‌ها و استراتژی‌هایی
که یاد گرفتی. هر یک ساعت ۱۰۰ ارز برتر را شناسایی می‌کنی و بلافاصله تا یک
ساعت این ترید کاغذی ادامه دارد و با هر نتیجه و علت‌یابی، ایجنت درس جدیدی
یاد می‌گیرد.»

طرز کار:
  ۱. ۱۰۰ ارز برتر به حجم، از همان صرافی‌های چرخه (نه لیست دستی)
  ۲. برای هر ارز، کندل ۱۵د تاریخی؛ بازپخش کندل‌به‌کندل **بدون look-ahead**:
     تصمیمِ کندل i فقط پنجرهٔ [0..i] را می‌بیند — همان قانونی که بک‌تست
     شبانه دارد. ورود با کتابچهٔ یادگرفته: روند + اردر بلاک معتبر
     (انجین orderblocks — واکنش/هانت/تازگی) + استاپ ساختاری پشت باکس.
  ۳. تسویه با کندل‌های بعد؛ برخورد استاپ و تارگت در یک کندل = استاپ
     (بدخیم‌ترین فرض — بدون خوش‌بینی درون-کندلی، همان قانون paper.mark).
  ۴. هر معامله در دفتر practice ثبت می‌شود (why.stage="practice" — همان
     دفتری که در ترازوی سیگنال‌شده شمرده نمی‌شود ولی در حافظهٔ انباشته و
     ماشین بونفرونی شبانه هست) و درسش با memory.digest_closed می‌رود.
  ۵. وضعیت هر ارز (تا کجای تاریخ ترید شده) می‌ماند تا اجرای بعدی همان
     پنجره را دوباره ترید نکند — نمونهٔ متورمِ تکراری یادگیری نیست.

سیگنال نیست و تلگرام ندارد؛ خروجی‌اش فقط تجربه است.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
STATE = ROOT / "brain" / "paper" / "trainer-state.json"

TARGET = 200          # کف معامله در هر اجرا — دستور صریح حمید
TOP_N = 100           # ۱۰۰ ارز برتر
BARS = 800            # ~۸ روز کندل ۱۵د
WARMUP = 160          # قبل از این، پنجره برای ساختار/OB کوتاه است
MAX_HOLD = 96         # حداکثر ۲۴ ساعت؛ بعدش با قیمت روز بسته می‌شود
RR = 2.0              # تارگت = ۲R — قانون ثابت میز تمرین


def top_symbols(n=TOP_N):
    """۱۰۰ ارز برتر به حجم از صرافی‌های خود چرخه. استیبل/تکراری حذف."""
    import sources
    rows = sources.tickers()
    skip = ("USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDE", "USD1")
    out = []
    for r in sorted(rows, key=lambda x: -float(x.get("quoteVolume") or 0)):
        s = r.get("symbol") or ""
        if not s.endswith("USDT") or any(s.startswith(k) for k in skip):
            continue
        out.append(s)
        if len(out) >= n:
            break
    return out


def _load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:                                 # noqa: BLE001 - اولین اجرا
        return {}


def _save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))


def decide(window):
    """تصمیم روی آخرین کندلِ پنجره — فقط با گذشته. None یعنی ورود نکن.

    دو ورودِ کتابچهٔ یادگرفته (هر دو در جهت روند — قانون حمید):
      A) پولبک به اردر بلاک معتبر: قیمت داخل/چسبیده به باکس نشکستهٔ
         هم‌جهت؛ استاپ پشت باکس با بافر.
      B) ادامهٔ BOS: بستنِ بالای سقف ۲۰ کندل (یا زیر کفش برای شورت)؛
         استاپ پشت سوینگ اخیر.
    تارگت هر دو ۲R. ماشین بونفرونی شبانه با فیلد setup فرقشان را می‌سنجد —
    این خودش همان «کشف نقطهٔ ضعف/قوت استراتژی از تکرار» است.
    """
    from hamid.orderblocks import near
    from hamid.structure import trend

    t = trend(window)
    if t not in ("up", "down"):
        return None
    px = window[-1]["c"]
    long = t == "up"

    def pack(d, sl, setup, ob=None):
        if (long and sl >= px) or (not long and sl <= px):
            return None
        tp = px + (px - sl) * RR if long else px - (sl - px) * RR
        stop_pct = abs(px - sl) / px * 100
        if not 0.15 <= stop_pct <= 6:                 # نه در نویز، نه بی‌معنا
            return None
        why = {"stage": "practice", "trainer": 1, "setup": setup,
               "trend_4h": t, "stop_pct": round(stop_pct, 2),
               "ob_align": "with" if ob else None}
        if ob:
            why.update({"reactions": ob.get("reactions"),
                        "ob_hunts": ob.get("hunts"),
                        "ob_fresh": ob.get("fresh")})
        return {"dir": d, "entry": px, "sl": sl, "tp1": tp, "why": why}

    # A) پولبک به اردر بلاک (داخل یا نزدیک ≤۲×ATR — خروجی near)
    b_in, b_near = near(window, tf="15m")
    box = b_in or b_near
    if box and not box.get("broken") and box.get("move") in (None, t):
        lo, hi = box["low"], box["high"]
        height = max(hi - lo, px * 1e-4)
        sl = lo - height * 0.25 if long else hi + height * 0.25
        s = pack("LONG" if long else "SHORT", sl, "ob_pullback", ob=box)
        if s:
            return s

    # B) ادامهٔ BOS — شکست سقف/کف ۲۰ کندل با بستنِ بدنه
    look = window[-21:-1]
    if len(look) == 20:
        if long and px > max(c["h"] for c in look):
            sl = min(c["l"] for c in window[-8:])
            s = pack("LONG", sl, "bos_continuation")
            if s:
                return s
        if not long and px < min(c["l"] for c in look):
            sl = max(c["h"] for c in window[-8:])
            s = pack("SHORT", sl, "bos_continuation")
            if s:
                return s
    return None


def resolve(c15, i, s):
    """از کندل i+1 جلو برو تا استاپ/تارگت/تایم‌اوت. برخورد هم‌زمان = استاپ."""
    e, sl, tp = s["entry"], s["sl"], s["tp1"]
    long = s["dir"] == "LONG"
    for j in range(i + 1, min(i + 1 + MAX_HOLD, len(c15))):
        c = c15[j]
        hit_sl = (c["l"] <= sl) if long else (c["h"] >= sl)
        hit_tp = (c["h"] >= tp) if long else (c["l"] <= tp)
        if hit_sl:                                    # هم‌زمان → بدخیم‌ترین فرض
            return j, "stop", -1.0
        if hit_tp:
            return j, "target", RR
        # قانون تریل حمید (⅓ مسیر → استاپ در سود) — ساده‌شدهٔ میز تمرین:
        # اگر ⅓ مسیر رفت و بعد به ورود برگشت، خروج سربه‌سرِ کارمزددار
        third = e + (tp - e) / 3
        reached = (c["h"] >= third) if long else (c["l"] <= third)
        if reached:
            for k in range(j + 1, min(i + 1 + MAX_HOLD, len(c15))):
                ck = c15[k]
                if (ck["h"] >= tp) if long else (ck["l"] <= tp):
                    return k, "target", RR
                if (ck["l"] <= e) if long else (ck["h"] >= e):
                    return k, "trail", 0.15           # سود کارمزددار — قانون ۱۲ اوت
            k = min(i + MAX_HOLD, len(c15) - 1)
            px = c15[k]["c"]
            r = (px - e) / (e - sl) if long else (e - px) / (sl - e)
            return k, "timeout", round(r, 3)
    j = min(i + MAX_HOLD, len(c15) - 1)
    px = c15[j]["c"]
    r = (px - e) / (e - sl) if long else (e - px) / (sl - e)
    return j, "timeout", round(r, 3)


def replay_symbol(sym, c15, after_ms=0, cap=40):
    """بازپخش یک ارز؛ فقط کندل‌های بعد از after_ms (ضدتکرار بین اجراها).

    خروجی: (معامله‌ها، مرز پیشروی). مرز = تا کجای تاریخ «بررسی» شد — نه
    فقط آخرین معامله. اگر تا ته سری رفتیم، مرز ته سری است؛ همین است که
    اجرای بعدی روی همان داده هیچ تکراری نمی‌سازد.
    """
    trades = []
    i = WARMUP
    while i < len(c15) - 2 and len(trades) < cap:
        if c15[i]["t"] <= after_ms:
            i += 1
            continue
        s = decide(c15[:i + 1])
        if not s:
            i += 1
            continue
        j, outcome, r = resolve(c15, i, s)
        trades.append({"sym": sym, "dir": s["dir"], "entry": s["entry"],
                       "sl": s["sl"], "tp1": s["tp1"], "tp2": None,
                       "opened": c15[i]["t"], "filled": c15[i]["t"],
                       "why": s["why"], "outcome": outcome, "R": r,
                       "closed": c15[j]["t"]})
        i = j + 1                                     # بدون معاملهٔ هم‌پوشان
    frontier = c15[min(i, len(c15) - 1)]["t"] if len(trades) < cap \
        else trades[-1]["closed"]
    return trades, frontier


def run(symbols=None, fetch_c15=None, target=TARGET, quiet=False):
    """یک نوبت تمرین: ۱۰۰ ارز، تا رسیدن به کف ۲۰۰ معامله یا ته دادهٔ تازه."""
    from hamid import memory, paper

    if symbols is None:
        symbols = top_symbols()
    if fetch_c15 is None:
        import sources

        def fetch_c15(sym):
            rows = sources.klines(sym, "15m", BARS)
            return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                     "c": k[4], "v": k[5]} for k in rows]

    st = _load_state()
    started = time.time()

    def one(sym):
        try:
            c15 = fetch_c15(sym)
        except Exception:                             # noqa: BLE001 - یک ارز خراب، بقیه نه
            return sym, [], None
        if len(c15) < WARMUP + 50:
            return sym, [], None
        trades, frontier = replay_symbol(sym, c15, after_ms=st.get(sym, 0))
        return sym, trades, frontier

    # سقف نداریم و break هم نداریم: درس عیب‌یابی همین تست — break وسط حلقه
    # مرز پیشرویِ ارزهای باقی‌مانده را ثبت‌نشده رها می‌کرد و اجرای بعد
    # دوباره همان‌ها را ترید می‌کرد (نمونهٔ متورم تکراری). سقف واقعی همان
    # cap هر ارز است: ۱۰۰ ارز × ۴۰؛ عملاً هر ارز در ۸ روز کندل ~۵ ستاپ می‌دهد.
    all_trades = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for sym, trades, frontier in pool.map(one, symbols):
            if trades:
                all_trades.extend(trades)
            if frontier:
                st[sym] = max(st.get(sym, 0), frontier)

    for t in all_trades:
        paper._append(paper.CLOSED, t)
    if all_trades:
        try:
            memory.digest_closed(all_trades)
        except Exception as e:                        # noqa: BLE001 - درس نباید دفتر را بکشد
            print(f"⚠ digest نشد: {type(e).__name__}")
    _save_state(st)

    n = len(all_trades)
    wins = sum(1 for t in all_trades if (t["R"] or 0) > 0)
    took = round(time.time() - started, 1)
    if not quiet:
        print(f"میز تمرین: {n} معامله از {len(symbols)} ارز در {took}s — "
              f"برد {round(wins / n * 100, 1) if n else 0}٪")
        if n < target:
            print(f"⚠ کمتر از کف {target} — دادهٔ تازه از اجرای قبل کم بود "
                  "(ضدتکرار درست کار می‌کند؛ کندل جدید که بیاید جبران می‌شود)")
    return all_trades


if __name__ == "__main__":
    run()
