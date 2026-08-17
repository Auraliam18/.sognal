#!/usr/bin/env python3
"""رادار پامپ خوشه‌ای — همان تحلیلی که برای BICO دستی انجام شد، به شکل ایجنت.

    python3 -m hamid.pump_radar                # اجرای کامل
    python3 -m hamid.pump_radar --no-telegram  # بدون ارسال
    python3 -m hamid.pump_radar --reapply DIR  # فقط بازنشانی خروجی بعد از reset گیت

روال، دقیقاً به ترتیبی که حمید خواست:

۱. تاپ گینرزهای بیتیونیکس خوانده می‌شود (اگر بیتیونیکس جواب ندهد، از تیکر
   MEXC با محاسبهٔ صریح «آخرین/باز» — و منبع در گزارش نوشته می‌شود).
۲. برای هر گینر: پامپ‌های گذشتهٔ خودش (بازده ۴ساعته + جهش حجم)، و ارزهایی
   که یک روز قبل/بعد از آن پامپ‌ها حرکت کرده‌اند.
۳. نقش خوشه‌ای: «سردسته» است یا خودش «دنباله‌رو»ی پامپ ارز دیگری؟ ملاک:
   اگر ارزی به‌طور میانگین در ۲۴ ساعتِ قبل از پامپ‌هایش جهش بزرگ‌تری داشته
   تا آنچه بعدش در بقیه دیده می‌شود، این ارز دنباله‌رو است.
۴. شبیه‌ترین پامپ قبلی به وضعیت الان: همبستگی چارتِ ۴۸ کندل اخیر با پنجرهٔ
   قبل از هر پامپ تاریخی، و اینکه بعد از آن پامپ چه شد.
۵. لایهٔ دوم: دنباله‌روهای هر گینر هم همین‌طور تحلیل می‌شوند (پامپ‌های
   خودشان + نقطهٔ ورود)، و لایهٔ سوم: دنباله‌روهایِ دنباله‌روها، که گذشتهٔ
   آن‌ها هم چک می‌شود — یک قدم جلوتر از بازار.
۶. نقطهٔ ورود هر ارز: تازه‌ترین اردر بلاک خریدِ مصرف‌نشده روی ۱۵ دقیقه
   (سقف باکس = ورود، استاپ زیر باکس) — همان قاعدهٔ تحلیل‌گر پامپ.
۷. پیشنهاد نهایی با دلایل شفاف امتیازدهی می‌شود، آلارمش در اتاق رادار ثبت
   و اگر توکن تلگرام باشد با سرتیتر «گزینه‌های پامپ» فرستاده می‌شود.

هر عدد از کندل واقعی صرافی است. تعداد رخداد پامپ همیشه کم است، پس نتیجهٔ
خوشه‌ای «مشاهده» گزارش می‌شود، نه قانون — همان قاعده‌ای که جلوی نتیجه‌گیری
از تاپه دوستانه را گرفت.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                                # noqa: E402
from hamid.analyze_pump import cds, pumps, rsi                # noqa: E402
from hamid.structure import atr, channel, trend               # noqa: E402
from hamid import orderblock                                  # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "pump-radar.json"
SENT = ROOT / "brain" / "pump-radar-sent.json"
SENT_TTL_MS = 6 * 3600 * 1000        # همان نتیجه دوباره فرستاده نمی‌شود
BITUNIX_TICKERS = "https://fapi.bitunix.com/api/v1/futures/market/tickers"

# ── قانون تازگی رهبر (دستور حمید، ۱۴ اوت) ─────────────────────────────────
#
# «وقتی یهو یک ارزی میره بالای ۱۰ درصد و ۲ روز توی صدر پامپ‌ها می‌مونه نیاز
# نیست هر روز گزارش پامپشو بدی. تو باید تمرکزت روی ارزایی باشه که سریع حجم
# می‌خورن و بین ۵ تا ۱۰ درصد حرکت سریع دارند.»
#
# دو چیز جداست و قبلاً یکی گرفته می‌شد: ارزی که **الان** ۶٪ پریده رویدادِ
# تازه است؛ ارزی که دو روز است +۴۰٪ بالای جدول نشسته یک واقعیتِ کهنه است که
# هر اجرا دوباره کشف می‌شود. دومی ماشه نیست، فقط نویز گزارش است.
SEEN = ROOT / "brain" / "pump-leaders-seen.json"
STALE_PCT = 10.0                     # بالای این درصد «صدر جدول» حساب می‌شود
STALE_AFTER_H = 48                   # دو روز — عدد خودِ حمید
SWEET_LO, SWEET_HI = 5.0, 10.0       # حرکت سریعی که حمید می‌خواهد

# کاندیدای پیشنهاد باید **هنوز نپریده** باشد. آستانهٔ قبلی ۱۰٪ بود و شکایت
# حمید دقیقاً همین بود: «لیست ارزایی که دادی همشون توی پامپ بودن.» ارزی که
# ۸٪ بالا رفته از نظر جدول «زیر ۱۰٪» است ولی از نظر چشم، در حال پامپ.
QUIET_24H = 5.0
QUIET_60M = 3.0
QUIET_30M = 3.0


# ── تاپ گینرز ──────────────────────────────────────────────────────────────

def _parse_bitunix(rows):
    """اجرای دوم نشان داد این endpoint فیلد «درصد تغییر» ندارد — همه صفر خوانده
    شدند. پس اول تغییر را خودمان از «آخرین ÷ باز» حساب می‌کنیم (بدون ابهام
    مقیاس)؛ فقط اگر فیلد باز هم نبود سراغ فیلدهای درصدی می‌رویم، با تشخیص
    خودکار مقیاس کسری. نام فیلدهای حجم برعکس محتوایشان است (مشاهدهٔ پنل)."""
    out, used_open = [], 0
    for t in rows or []:
        s = str(t.get("symbol") or "")
        if not s.endswith("USDT"):
            continue
        try:
            last = float(t.get("lastPrice") or t.get("last") or t.get("markPrice") or 0)
            vol = float(t.get("quoteVol") or t.get("baseVol") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0:
            continue
        chg, opn = None, None
        for k in ("open", "openPrice", "open24h", "openUtc"):
            try:
                v = float(t.get(k) or 0)
            except (TypeError, ValueError):
                continue
            if v > 0:
                opn = v
                break
        if opn:
            chg = (last / opn - 1) * 100
            used_open += 1
        else:
            v = t.get("priceChangePercent")
            if v not in (None, ""):
                try:
                    chg = float(v)
                except (TypeError, ValueError):
                    chg = None
            if chg is None:
                v = t.get("change")                  # این فیلد کسر است (مشاهدهٔ پنل)
                if v not in (None, ""):
                    try:
                        chg = float(v) * 100
                    except (TypeError, ValueError):
                        chg = None
        if chg is None or abs(chg) > 500:            # عدد بی‌معنا = ردیف خراب
            continue
        out.append({"symbol": s, "change_pct": chg, "last": last, "vol": vol})
    # تشخیص مقیاس فقط برای مسیر فیلد درصدی: بین صدها جفت فیوچرز کریپتو همیشه
    # کسی بیش از ±۱.۵٪ در ۲۴ ساعت حرکت کرده؛ اگر بیشینه زیر ۱.۵ است فیلد کسر
    # بوده (0.27 یعنی ۲۷٪). مسیر «آخرین ÷ باز» ابهام مقیاس ندارد.
    if not used_open and len(out) >= 20 and max(abs(x["change_pct"]) for x in out) < 1.5:
        for x in out:
            x["change_pct"] *= 100
    for x in out:
        x["change_pct"] = round(x["change_pct"], 1)
    return out


TOOBIT_TICKERS = "https://api.toobit.com/quote/v1/ticker/24hr"


def _parse_toobit(rows):
    """پارس تیکر توبیت — شکل واقعی از لاگ اجرای زنده:
    ['c','h','l','o','pc','pcp','qv','s','si','t','v'].

    درس اجرای اول: محاسبه از c/o جفت‌های بی‌عمقِ تازه‌لیست را با +۲۹۰۰٪ صدر
    جدول می‌کرد و گینر واقعی را بیرون می‌انداخت. حالا pcp خود صرافی + فیلتر
    حجم qv و تشخیص مقیاس (کسری/درصد) مثل بیتیونیکس."""
    raw = []
    for t in rows:
        s = str(t.get("s") or t.get("symbol") or "")
        if not s.endswith("USDT"):
            continue
        try:
            last = float(t.get("c") or 0)
            qv = float(t.get("qv") or 0)
            pcp = float(t.get("pcp"))
        except (TypeError, ValueError):
            continue
        if last <= 0 or qv < 100_000:                # کتاب کم‌عمق، گینر واقعی نیست
            continue
        raw.append({"symbol": s, "pcp": pcp, "last": last, "vol": qv})
    if not raw:
        return []
    vals = sorted(abs(x["pcp"]) for x in raw)
    frac = len(raw) >= 20 and vals[int(len(vals) * 0.9)] <= 0.5
    out = []
    for x in raw:
        chg = x["pcp"] * 100 if frac else x["pcp"]
        if abs(chg) > 300:                           # لیستِ امروز/دادهٔ بی‌معنا
            continue
        out.append({"symbol": x["symbol"], "change_pct": round(chg, 1),
                    "last": x["last"], "venue": "توبیت"})
    return out


def _toobit_gainers():
    """تاپ گینرز توبیت — خواست حمید: بیتیونیکس و توبیت هر دو زیر نظر باشند."""
    r = sources._json(TOOBIT_TICKERS)
    rows = r if isinstance(r, list) else (r.get("data") or r.get("result") or [])
    if rows:
        print("کلیدهای تیکر توبیت:", sorted((rows[0] or {}).keys()))
    return _parse_toobit(rows)


def gainers(top=6, min_pct=5.0):
    """(نام منبع، لیست گینرها) — بیتیونیکس + توبیت با هم؛ حمید هر دو را
    می‌خواهد زیر نظر داشته باشد تا ارزی از دست نرود."""
    merged, names = {}, []
    try:
        rows = sources._rows(sources._json(BITUNIX_TICKERS))
        g = _parse_bitunix(rows)
        if rows:
            print("کلیدهای تیکر بیتیونیکس:", sorted((rows[0] or {}).keys()))
        moved = [x for x in g if abs(x["change_pct"]) >= 0.5]
        # اگر هیچ‌کس «حرکت» ندارد، داده تغییرِ واقعی ندارد — ادعای بیتیونیکس
        # نمی‌کنیم و صادقانه به منبع بعدی می‌رویم (درس اجرای دوم: همه +0.0٪).
        if len(g) >= 20 and len(moved) >= 5:
            for x in g:
                x["venue"] = "بیتیونیکس"
                merged[x["symbol"]] = x
            names.append("بیتیونیکس")
            print("بیتیونیکس، ۵ تغییر بزرگ ۲۴س: " +
                  ", ".join(f"{x['symbol']} {x['change_pct']:+}%"
                            for x in sorted(g, key=lambda x: -x["change_pct"])[:5]))
        else:
            print(f"تیکر بیتیونیکس تغییرِ قابل‌استفاده ندارد ({len(g)} جفت، {len(moved)} متحرک)")
    except Exception as e:                           # noqa: BLE001 - صرافی بعدی
        print(f"بیتیونیکس جواب نداد: {type(e).__name__}")
    try:
        tb = _toobit_gainers()
        moved_t = [x for x in tb if abs(x["change_pct"]) >= 0.5]
        if len(tb) >= 20 and len(moved_t) >= 5:
            for x in tb:
                # هر دو صرافی داشتندش → تغییرِ بزرگ‌تر می‌ماند (زودتر دیدن مهم است)
                if x["symbol"] not in merged or x["change_pct"] > merged[x["symbol"]]["change_pct"]:
                    merged[x["symbol"]] = x
            names.append("توبیت")
            print("توبیت، ۵ تغییر بزرگ ۲۴س: " +
                  ", ".join(f"{x['symbol']} {x['change_pct']:+}%"
                            for x in sorted(tb, key=lambda x: -x["change_pct"])[:5]))
        else:
            print(f"تیکر توبیت تغییرِ قابل‌استفاده ندارد ({len(tb)} جفت)")
    except Exception as e:                           # noqa: BLE001
        print(f"توبیت جواب نداد: {type(e).__name__}")
    if merged:
        allg = sorted(merged.values(), key=lambda x: -x["change_pct"])
        return " + ".join(names), [x for x in allg if x["change_pct"] >= min_pct][:top]
    r = sources._json("https://api.mexc.com/api/v3/ticker/24hr")
    out = []
    for t in r:
        s = t.get("symbol", "")
        if not s.endswith("USDT"):
            continue
        try:
            last, op = float(t.get("lastPrice") or 0), float(t.get("openPrice") or 0)
            vol = float(t.get("quoteVolume") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or op <= 0 or vol < 100_000:    # کتاب کم‌عمق، گینر واقعی نیست
            continue
        out.append({"symbol": s, "change_pct": round((last / op - 1) * 100, 1),
                    "last": last, "vol": vol})
    out.sort(key=lambda x: -x["change_pct"])
    return "MEXC (جایگزین — بیتیونیکس در دسترس نبود)", \
        [x for x in out if x["change_pct"] >= min_pct][:top]


# ── تازگی رهبر ─────────────────────────────────────────────────────────────

def _load_seen():
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return {}


def freshness(gs, now_ms=None, seen=None):
    """کدام گینر رویدادِ تازه است و کدام کهنه — با دفتر ماندگار.

    قاعده: از اولین باری که یک نماد بالای STALE_PCT دیده می‌شود ساعت شروع
    به کار می‌کند. اگر بعد از STALE_AFTER_H هنوز آن‌جاست، کهنه است و دیگر
    ماشه نمی‌شود. به‌محض این‌که زیر آستانه برگردد پرونده‌اش بسته می‌شود، پس
    پامپ بعدیِ همان ارز دوباره تازه حساب می‌شود.

    خالص نگه داشته شده (now_ms/seen تزریق‌شدنی) تا بدون شبکه و بدون
    صبرکردنِ دو روزه آزمون شود. برگشتی: (gs_annotated, seen_updated)."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    seen = dict(_load_seen() if seen is None else seen)
    out = []
    live = set()
    for g in gs:
        s, pct = g["symbol"], g.get("change_pct") or 0
        g = dict(g)
        if pct >= STALE_PCT:
            live.add(s)
            first = (seen.get(s) or {}).get("first_ms")
            if first is None:
                first = now
            seen[s] = {"first_ms": first, "last_ms": now, "last_pct": pct}
            age_h = (now - first) / 3600e3
            g["top_age_h"] = round(age_h, 1)
            g["stale"] = age_h >= STALE_AFTER_H
            if g["stale"]:
                g["stale_note"] = (f"{round(age_h / 24, 1)} روز است بالای "
                                   f"{STALE_PCT:.0f}٪ در صدر جدول مانده — "
                                   "خبر کهنه، ماشهٔ تازه نیست")
        else:
            seen.pop(s, None)                        # برگشت زیر آستانه = پروندهٔ بسته
            g["stale"] = False
            g["sweet"] = SWEET_LO <= pct < SWEET_HI
        out.append(g)
    # نمادی که دیگر در جدول نیست هم پرونده‌اش بسته می‌شود، وگرنه دفتر
    # بی‌نهایت رشد می‌کند و یک پامپِ ماه پیش تا ابد «کهنه» می‌ماند.
    for s in [k for k in seen if k not in live]:
        seen.pop(s, None)
    return out, seen


def triggers_of(gs, ign=None, deep_n=4):
    """ماشه‌ها به ترتیب اولویت حمید: حرکت سریع ۵–۱۰٪ اول، بعد بقیه؛ کهنه‌ها
    هرگز. اگر همه کهنه بودند فهرست خالی برمی‌گردد و رادار صادقانه می‌گوید
    امروز رویداد تازه‌ای نبود — بهتر از گزارش تکراری."""
    ign = ign or []
    fresh = [g for g in gs if not g.get("stale")]
    sweet = [g for g in fresh if SWEET_LO <= (g.get("change_pct") or 0) < SWEET_HI]
    rest = [g for g in fresh if g not in sweet]
    ordered = sweet + rest
    have = {g["symbol"] for g in ordered[:deep_n]}
    return ordered[:deep_n] + [x for x in ign if x["symbol"] not in have][:3]


# ── ابزار تحلیل ────────────────────────────────────────────────────────────

def _corr(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5


def best_match(cd1h, eps, window=48):
    """شبیه‌ترین «قبل از پامپ» تاریخی به چارت الان، و اینکه بعد از آن پامپ چه شد."""
    if len(cd1h) < window + 2 or not eps:
        return None
    now = [c["c"] for c in cd1h[-window:]]
    best = None
    for e in eps:
        i = e["i"]
        if i - 4 - window < 0:
            continue
        seg = [c["c"] for c in cd1h[i - 4 - window:i - 4]]
        c = _corr(now, seg)
        nxt = cd1h[min(i + 24, len(cd1h) - 1)]["c"] / cd1h[i]["c"] - 1
        cand = {"pump_t": e["t"], "corr_pct": round(c * 100),
                "then_24h_pct": round(nxt * 100, 1)}
        if best is None or cand["corr_pct"] > best["corr_pct"]:
            best = cand
    return best


def role_of(rel, gate=8.0):
    """سردسته یا دنباله‌رو؟ leaders = ارزهایی که قبلش حرکت کرده‌اند،
    followers = ارزهایی که بعدش. نقش از مقایسهٔ بزرگ‌ترینِ این دو درمی‌آید."""
    leaders = sorted([{"symbol": s, **v} for s, v in rel.items()
                      if v["pre_24h_pct"] >= gate and v["n"] >= 2],
                     key=lambda x: -x["pre_24h_pct"])
    followers = sorted([{"symbol": s, **v} for s, v in rel.items()
                        if v["post_24h_pct"] >= gate * 0.75 and v["n"] >= 2],
                       key=lambda x: -x["post_24h_pct"])
    biggest_pre = leaders[0]["pre_24h_pct"] if leaders else 0
    biggest_post = followers[0]["post_24h_pct"] if followers else 0
    role = "دنباله‌رو" if leaders and biggest_pre > biggest_post else "سردسته"
    return role, leaders[:5], followers[:5]


class Kcache:
    """هر نماد یک بار از شبکه؛ تحلیل خوشه‌ای بدون این، صدها فچ تکراری می‌شود.
    اگر قبلاً با n کوچک‌تر گرفته شده و حالا بلندتر لازم است، دوباره می‌گیرد."""

    def __init__(self):
        self.d = {}
        self.n = {}

    def get(self, sym, tf, n):
        k = (sym, tf)
        if k not in self.d or (self.n.get(k, 0) < n and len(self.d[k]) >= self.n.get(k, 0)):
            if k in self.d and self.n.get(k, 0) >= n:
                return self.d[k]
            try:
                self.d[k] = cds(sym, tf, n)
            except Exception:                        # noqa: BLE001 - نماد بی‌داده
                self.d[k] = []
            self.n[k] = n
        return self.d[k]


def early_movers(kc, uni, gate=4.0):
    """شعله‌گیری در ۳۰ دقیقهٔ اخیر — برای اینکه زودتر از تیکر ۲۴ساعته بفهمیم.
    دو کندل ۱۵ دقیقهٔ آخر بالای آستانه + حجم دو کندل آخر بیش از ۳ برابر
    میانگین. این همان «زودتر رسیدن» است که حمید خواست: منتظر نمی‌مانیم ارز
    در جدول گینرهای روز بنشیند."""
    out = []
    for s in uni:
        c = kc.get(s, "15m", 40)
        if len(c) < 32:
            continue
        r30 = (c[-1]["c"] / c[-3]["c"] - 1) * 100
        # ماشهٔ صریح حمید: «کندل ۵ تا ۱۵ دقیقه بالای ۵٪» — یک کندل ۱۵د به
        # تنهایی ≥۵٪ هم شعله است، حتی بدون شرط حجم (حرکت ۵٪/۱۵د خودش خبر است)
        r15 = (c[-1]["c"] / c[-2]["c"] - 1) * 100
        vols = [x["v"] for x in c[-32:-2]]
        m = sum(vols) / len(vols) if vols else 0
        vol_ok = m > 0 and (c[-1]["v"] + c[-2]["v"]) > 3 * 2 * m
        if (r30 >= gate and vol_ok) or r15 >= 5.0:
            out.append({"symbol": s, "change_pct": round(max(r30, r15), 1),
                        "chg_15m": round(r15, 1),
                        "last": c[-1]["c"], "vol": c[-1]["v"], "ignition": True})
    out.sort(key=lambda x: -x["change_pct"])
    return out


def related_cached(sym, eps, cd1h, universe, kc, window=24):
    out = {}
    for other in universe:
        if other == sym:
            continue
        oc = kc.get(other, "1h", len(cd1h) + 10)
        if not oc:
            continue
        idx = {c["t"]: k for k, c in enumerate(oc)}
        pre, post = [], []
        for e in eps:
            k = idx.get(cd1h[e["i"]]["t"])
            if k is None or k < window or k + window >= len(oc):
                continue
            pre.append(oc[k]["c"] / oc[k - window]["c"] - 1)
            post.append(oc[k + window]["c"] / oc[k]["c"] - 1)
        if pre:
            out[other] = {"n": len(pre),
                          "pre_24h_pct": round(sum(pre) / len(pre) * 100, 1),
                          "post_24h_pct": round(sum(post) / len(post) * 100, 1)}
    return out


def follower_lags(leader_eps, fol_eps, within_h=48):
    """فاصلهٔ تاریخی پامپ سردسته تا پامپ دنباله‌رو — کلیدی که حمید گفت:
    این فاصله می‌گوید چقدر وقت برای سیگنال هست، و اگر از پنجرهٔ تاریخی
    بگذرد و نپرد، طبق سابقهٔ خودش دیگر احتمالاً نمی‌پرد."""
    lags = []
    for le in leader_eps or []:
        after = [(fe["t"] - le["t"]) / 3600e3 for fe in fol_eps or []
                 if 0 < (fe["t"] - le["t"]) / 3600e3 <= within_h]
        if after:
            lags.append(min(after))
    if not lags:
        return None
    lags.sort()
    return {"n": len(lags), "med_h": round(lags[len(lags) // 2], 1),
            "max_h": round(max(lags), 1)}


def react_similarity(kc, sym, fol_eps, leader_eps, window=24):
    """معاینهٔ خود حمید: چارت الانِ دنباله‌رو در برابر چارتش درست قبل از
    واکنش‌های قبلی‌اش به همین سردسته. شباهت بالا = دارد همان رفتار را تکرار
    می‌کند؛ شباهت پایین = این دفعه فرق دارد و باید گفته شود."""
    c1h = kc.get(sym, "1h", 1000)
    if len(c1h) < window + 2:
        return None
    idx = {c["t"]: k for k, c in enumerate(c1h)}
    lead_ts = [e["t"] for e in leader_eps or []]
    reacts = [e for e in fol_eps or []
              if any(0 < (e["t"] - lt) / 3600e3 <= 48 for lt in lead_ts)]
    now = [c["c"] for c in c1h[-window:]]
    best = None
    for e in reacts:
        k = idx.get(e["t"])
        if k is None or k - window < 0:
            continue
        cc = round(_corr(now, [c["c"] for c in c1h[k - window:k]]) * 100)
        if best is None or cc > best["corr_pct"]:
            best = {"corr_pct": cc, "react_t": e["t"], "n_reacts": len(reacts)}
    return best


def btc_move_cause(kc, gate=1.5):
    """علت‌یابی فوری حرکت بزرگ بیت‌کوین — قانون حمید: ریخت یا پرید، همان
    لحظه اعلام شود «به این دلایل تکنیکال یا به دلیل این خبر».

    خبری: تیترهای داغ دسته‌بندی‌شدهٔ شکار خبر. تکنیکال: جاروی نقدینگی
    (شکستن خوشهٔ کف/سقف برابر در ۱۵د)، فاندینگ انباشته (جمعیت کدام سمت
    شلوغ بود)، RSI. هر عامل با عدد؛ اگر علت خبری پیدا نشد، صادقانه گفته
    می‌شود — حدس جای اندازه نمی‌نشیند."""
    c1h = kc.get("BTCUSDT", "1h", 60)
    if len(c1h) < 30:
        return None
    chg = (c1h[-1]["c"] / c1h[-2]["c"] - 1) * 100
    if abs(chg) < gate:
        return None
    up = chg > 0
    tech = []
    try:
        from hamid import liquidity
        from hamid.analyze_pump import rsi
        c15 = kc.get("BTCUSDT", "15m", 260)
        # استخرها روی کندل‌های قبل از حرکت — بعد از جارو، خوشهٔ جاروشده دیگر
        # «زیر قیمت» نیست و از نقشهٔ لحظهٔ حال حذف می‌شود؛ سطح باید همان‌طور
        # دیده شود که قبل از حرکت روی چارت بود
        p = liquidity.pools(c15[:-4])
        recent_lo = min(k["l"] for k in c15[-4:])
        recent_hi = max(k["h"] for k in c15[-4:])
        if not up:
            swept = [g for g in p["below"] if g["price"] > recent_lo]
            if swept:
                tech.append(f"جاروی نقدینگی زیر کف برابر {swept[0]['price']:.10g} "
                            f"({swept[0]['touches']} برخورد) — استاپ لانگ‌ها فعال شد")
        else:
            swept = [g for g in p["above"] if g["price"] < recent_hi]
            if swept:
                tech.append(f"شکستن سقف برابر {swept[0]['price']:.10g} "
                            f"({swept[0]['touches']} برخورد) — استاپ شورت‌ها سوخت")
        r15 = rsi(c15)
        if r15 is not None and (r15 <= 25 or r15 >= 75):
            tech.append(f"RSI ۱۵د {r15:.0f} — حرکت هیجانی")
    except Exception:                                # noqa: BLE001
        pass
    try:
        it = json.loads((ROOT / "brain" / "intel" / "latest.json").read_text())
        fb = ((it.get("funding") or {}).get("BTC"))
        if fb is not None and abs(fb) >= 0.005:
            side = "لانگ‌ها" if fb > 0 else "شورت‌ها"
            tech.append(f"فاندینگ BTC {fb:+.3f}٪ — {side} شلوغ بودند"
                        + ("؛ ریزش همان‌ها را لیکویید می‌کند" if fb > 0 and not up
                           else ""))
    except Exception:                                # noqa: BLE001
        pass
    news = None
    try:
        nj = json.loads((ROOT / "signals" / "news.json").read_text())
        hot = [x.get("title") for x in (nj.get("classified") or [])
               if x.get("cat") != "عمومی"]
        news = hot[0] if hot else None
    except Exception:                                # noqa: BLE001
        pass
    return {"dir": "up" if up else "down", "btc_1h_pct": round(chg, 2),
            "news": news, "tech": tech}


def move_cause_fa(mc):
    L = [f"بیت‌کوین در یک ساعت {mc['btc_1h_pct']:+}٪ "
         + ("پرید." if mc["dir"] == "up" else "ریخت.")]
    L.append(f"علت خبری: {mc['news']}" if mc["news"]
             else "علت خبری در شکار فعلی پیدا نشد — دلایل تکنیکال:")
    L += [f"· {t}" for t in mc["tech"]]
    if not mc["tech"] and not mc["news"]:
        L.append("عامل تکنیکال بارزی هم در سنجه‌های ما ثبت نشد — حرکت بی‌امضا؛ حدس نمی‌زنیم")
    return "\n".join(L)


def crash_watch(kc, uni, trigger_pct=-2.0):
    """آینهٔ ریزش — مثال خود حمید: «بیت‌کوین ریخت؟ سریع علتش را پیدا کن و
    بفرست؛ بعد ببین در گذشته بعد از ریزش‌هایش چه ارزهایی ریخته‌اند و همان‌ها
    را با الان مقایسه کن و بگو حواست به این‌ها باشد.»"""
    btc = kc.get("BTCUSDT", "1h", 1000)
    if len(btc) < 50:
        return None
    r1 = (btc[-1]["c"] / btc[-2]["c"] - 1) * 100
    if r1 > trigger_pct:
        return None
    crash_ts = [btc[i]["t"] for i in range(1, len(btc) - 1)
                if (btc[i]["c"] / btc[i - 1]["c"] - 1) * 100 <= trigger_pct]
    followers = []
    for sym in uni[:25]:
        if sym == "BTCUSDT":
            continue
        c = kc.get(sym, "1h", 1000)
        if len(c) < 50:
            continue
        idx = {x["t"]: k for k, x in enumerate(c)}
        drops = tot = 0
        for t in crash_ts:
            k = idx.get(t)
            if k is None or k + 1 >= len(c):
                continue
            tot += 1
            if (c[k + 1]["c"] / c[k]["c"] - 1) * 100 <= -3:
                drops += 1
        if tot >= 3 and drops / tot >= 0.5:
            followers.append({"symbol": sym, "n": tot,
                              "hit_pct": round(100 * drops / tot),
                              "chg_now": round((c[-1]["c"] / c[-2]["c"] - 1) * 100, 1)})
    followers.sort(key=lambda f: -f["hit_pct"])
    why = None
    try:
        nj = json.loads((ROOT / "signals" / "news.json").read_text())
        hot = [x.get("title") for x in (nj.get("classified") or [])
               if x.get("cat") != "عمومی"]
        why = hot[0] if hot else None
    except Exception:                                # noqa: BLE001
        pass
    return {"btc_1h": round(r1, 2), "why": why, "followers": followers[:6],
            "n_crashes": len(crash_ts)}


HIST = ROOT / "brain" / "pump-history.json"


def _teh_date(ms):
    """تاریخ و ساعت تهران (UTC+3:30) — خوانا برای حمید، نه فقط timestamp."""
    t = time.gmtime(ms / 1000 + 3.5 * 3600)
    return time.strftime("%m-%d %H:%M", t)


def update_history(blocks):
    """دفتر ماندگار تاریخچهٔ پامپ‌ها — قرار حمید: «تاریخچهٔ ارزهای پامپ‌شده
    را در بیاور».

    کندل در دسترس فقط ~۴۱ روز است و هر روز یک روز از تهش می‌ریزد؛ این دفتر
    هر رخداد را یک بار ثبت می‌کند و نگه می‌دارد، پس با گذر زمان از پنجرهٔ
    کندل عمیق‌تر می‌شود. برای هر پامپِ سردسته، واکنش دنباله‌روها (که در همین
    اجرا تحلیل شده‌اند) با فاصلهٔ ساعتی و اندازه ثبت می‌شود."""
    try:
        led = json.loads(HIST.read_text())
    except Exception:                                # noqa: BLE001
        led = {"symbols": {}}
    syms = led.setdefault("symbols", {})
    bmap = {b["symbol"]: b for b in blocks}
    fresh = []                                        # (sym, event) های تازه‌ثبت‌شده
    for b in blocks:
        if not b.get("pumps"):
            continue
        rec = syms.setdefault(b["symbol"], {"events": []})
        known = {e["t"] for e in rec["events"]}
        fols = [f["symbol"] for f in (b.get("followers") or []) if f["symbol"] in bmap]
        for e in b["pumps"]:
            reacts = []
            for fs in fols:
                for fe in bmap[fs].get("pumps") or []:
                    lag = (fe["t"] - e["t"]) / 3600e3
                    if 0 < lag <= 48:
                        reacts.append({"symbol": fs, "lag_h": round(lag, 1),
                                       "ret_pct": fe["ret_4h_pct"]})
                        break
            if e["t"] in known:
                # رخداد قدیمی: فقط واکنش‌های تازه‌فهمیده اضافه شود
                old = next(x for x in rec["events"] if x["t"] == e["t"])
                have = {r["symbol"] for r in old.get("reactions", [])}
                old.setdefault("reactions", []).extend(
                    r for r in reacts if r["symbol"] not in have)
                continue
            ev = {"t": e["t"], "date": _teh_date(e["t"]),
                  "ret_4h_pct": e["ret_4h_pct"],
                  "vol_z": e.get("vol_z"),
                  "reactions": reacts}
            rec["events"].append(ev)
            fresh.append((b["symbol"], ev))
        # دستور صریح حمید: «پاک نشود» — هیچ سقفی، هیچ حذفی؛ فقط مرتب‌سازی
        rec["events"] = sorted(rec["events"], key=lambda x: -x["t"])
        rec["updated"] = int(time.time() * 1000)
        # خلاصهٔ خوانا روی خود بلوک — پنل و تلگرام همین را نشان می‌دهند
        b["history"] = [
            {"date": ev["date"], "ret_4h_pct": ev["ret_4h_pct"],
             "reactions": ev.get("reactions") or []}
            for ev in rec["events"][:3]]
    led["updated"] = int(time.time() * 1000)
    HIST.parent.mkdir(exist_ok=True)
    HIST.write_text(json.dumps(led, ensure_ascii=False, indent=1))
    return sum(len(r["events"]) for r in syms.values()), fresh


def entry_point(c15):
    """همان قاعدهٔ تحلیل‌گر پامپ: تازه‌ترین اردر بلاک خرید مصرف‌نشده ≤۶۰ کندل."""
    if len(c15) < 60:
        return None
    obs = [b for b in orderblock.find(c15, "bullish")
           if not b.consumed and len(c15) - 1 - b.i < 60]
    if not obs:
        return None
    b = sorted(obs, key=lambda x: -x.i)[0]
    a15 = atr(c15) or 0
    return {"entry": round(b.high, 10), "sl": round(b.low - 0.3 * a15, 10)}


def analyze_one(sym, kc, universe, with_related=True):
    c1h = kc.get(sym, "1h", 1000)
    if len(c1h) < 80:
        return None
    c15 = kc.get(sym, "15m", 400)
    eps = pumps(c1h)
    rel = related_cached(sym, eps, c1h, universe, kc) if (with_related and eps) else {}
    role, leaders, followers = role_of(rel) if rel else ("نامشخص", [], [])
    ch1 = channel(c1h)
    c30 = (c15[-1]["c"] / c15[-3]["c"] - 1) * 100 if len(c15) >= 3 else None
    c60 = (c15[-1]["c"] / c15[-5]["c"] - 1) * 100 if len(c15) >= 5 else None
    c24 = (c1h[-1]["c"] / c1h[-25]["c"] - 1) * 100 if len(c1h) >= 25 else None
    block = {
        "symbol": sym, "price": c1h[-1]["c"],
        "change_30m_pct": round(c30, 1) if c30 is not None else None,
        "change_60m_pct": round(c60, 1) if c60 is not None else None,
        "change_24h_pct": round(c24, 1) if c24 is not None else None,
        "pumps": eps,
        "pump_note": (f"{len(eps)} پامپ در {len(c1h)//24} روز؛ بزرگ‌ترین "
                      f"+{max((e['ret_4h_pct'] for e in eps), default=0)}٪"
                      if eps else "در تاریخچهٔ در دسترس، پامپی با این آستانه ندارد"),
        "role": role, "leaders": leaders, "followers": followers,
        "match": best_match(c1h, eps),
        "now": {"trend_4h": None, "trend_1h": trend(c1h),
                "rsi_1h": rsi(c1h), "rsi_15m": rsi(c15) if c15 else None,
                "channel_pos_1h": round(ch1.position, 2) if ch1 else None},
        "alarm": entry_point(c15) if c15 else None,
    }
    from hamid.cycle import resample
    c4h = resample(c1h, 4)
    block["now"]["trend_4h"] = trend(c4h)
    return block


# ── پیشنهاد ────────────────────────────────────────────────────────────────

def recommend(blocks, hot=None):
    """امتیازِ هر ارزِ دارای نقطهٔ ورود، با دلیلِ نوشته‌شده برای تک‌تک امتیازها —
    پیشنهادی که دلیلش را نگوید قابل حذف‌کردنِ هوش مصنوعی ضعیف نیست.

    قانون حمید، سخت و بی‌استثنا: ارزی که خودش پامپ خورده (۱۰٪+ در ۳۰ دقیقه
    یا ۱۰٪+ در ۲۴ ساعت) دیگر «سیگنال پامپ» نیست — دیر است. کار ما گرفتن
    عضوهای هنوز-نپریدهٔ خوشه است از روی گذشتهٔ اعضای پریده، نه توضیح دادن
    پامپی که تمام شده."""
    hot = hot or set()
    scored = []
    for b in blocks:
        al = b.get("alarm")
        if not al or not al.get("entry"):
            continue
        c30, c24 = b.get("change_30m_pct"), b.get("change_24h_pct")
        c60 = b.get("change_60m_pct")
        # آستانه‌ها از ۱۰٪ به «هنوز نپریده» سفت شدند. شکایت حمید (۱۴ اوت):
        # «لیست ارزایی که دادی در گذشته پامپ شده بودند نگاه کردم همشون توی
        # پامپ بودن.» ارزی که ۸٪ رفته از نظر عدد زیر ۱۰٪ بود ولی از نظر او
        # در حال پامپ — و حق با او بود. پیشنهاد یعنی «هنوز نرفته»، نه
        # «کمتر از ۱۰ درصد رفته».
        moved = []
        if c60 is not None and c60 >= QUIET_60M:
            moved.append(f"+{c60}٪ در ۱س")
        if c30 is not None and c30 >= QUIET_30M:
            moved.append(f"+{c30}٪ در ۳۰د")
        if c24 is not None and c24 >= QUIET_24H:
            moved.append(f"+{c24}٪ در ۲۴س")
        if moved:
            b["skipped"] = ("هنوز-نپریده نیست (" + "، ".join(moved) +
                            ") — پیشنهاد پامپ فقط برای ارزی است که حرکتش را نکرده")
            continue
        # داور بیرونی: قول spec («فقط دنباله‌رو با ۲+ سابقه») در کد نبود —
        # حالا شرط سخت است. راه دوم اثبات رابطه، خواست بعدی حمید است:
        # لگ-کورولیشنِ سری بازده‌ها در گذشته (r≥۰.۲ با تأخیر مثبت).
        strong_leaders = [l for l in (b.get("leaders") or []) if (l.get("n") or 0) >= 2]
        lc_leaders = b.get("lag_corr_leaders") or []
        ev_leaders = b.get("event_leaders") or []     # مطالعهٔ رویدادی — مدل حمید
        event_ok = b.get("role") == "دنباله‌رو" and strong_leaders
        if not event_ok and not lc_leaders and not ev_leaders:
            b["skipped"] = ("رابطهٔ اثبات‌شده ندارد (نه ۲+ سابقهٔ رخدادی، نه "
                            "لگ-کورولیشن، نه k/N مطالعهٔ رویدادی) — پیشنهاد نمی‌شود")
            continue
        s, why = 0, []
        # قوی‌ترین مدرک: k از N پامپ واقعی تاریخچه — «ارز با احتمال پامپ»
        for el in ev_leaders[:2]:
            s += 3
            why.append(el["reason"])
        for lc in lc_leaders[:2]:
            s += 2 if lc.get("both_tf") else 1
            why.append(lc["reason"])
        if b["symbol"].replace("USDT", "") and b.get("leaders") and \
                any(l["symbol"] in hot for l in b["leaders"]):
            s += 2
            hl = next(l["symbol"] for l in b["leaders"] if l["symbol"] in hot)
            why.append(f"سردسته‌اش ({hl}) همین حالا در حال پریدن است و این هنوز نپریده")
        if b["role"] == "دنباله‌رو" and b.get("leaders"):
            s += 2
            why.append(f"دنباله‌روی خوشه است — سردسته‌اش ({b['leaders'][0]['symbol']}) "
                       f"قبل از پامپ‌هایش به‌طور میانگین {b['leaders'][0]['pre_24h_pct']:+}٪ حرکت کرده")
        if len(b.get("pumps") or []) >= 3:
            s += 2
            why.append(f"تکرارکنندهٔ پامپ است ({len(b['pumps'])} بار در تاریخچه)")
        m = b.get("match")
        if m and m["corr_pct"] >= 70:
            if m["then_24h_pct"] > 0:
                s += 2
            why.append(f"چارت الان {m['corr_pct']}٪ شبیه قبل از پامپ قبلی است "
                       f"(آن بار ۲۴ ساعت بعدش {m['then_24h_pct']:+}٪ شد)")
        r1 = b["now"].get("rsi_1h")
        if r1 is not None:
            if r1 < 65:
                s += 1
                why.append(f"RSI یک‌ساعته {r1} — هنوز اشباع نشده")
            elif r1 >= 75:
                s -= 2
                why.append(f"RSI یک‌ساعته {r1} — اشباع خرید؛ دنبالش دویدن همان‌جایی است که استاپ می‌خورد")
        dist = abs(b["price"] - al["entry"]) / al["entry"] * 100
        if dist <= 3:
            s += 2
            why.append(f"قیمت فقط {dist:.1f}٪ با نقطهٔ ورود فاصله دارد")
        elif dist > 15:
            s -= 1
            why.append(f"نقطهٔ ورود {dist:.1f}٪ دورتر است — فقط با صبر و آلارم")
        risk = abs(al["entry"] - al["sl"]) / al["entry"] * 100
        scored.append({"symbol": b["symbol"], "score": s, "reasons": why,
                       "entry": al["entry"], "sl": al["sl"],
                       "dist_pct": round(dist, 1), "risk_pct": round(risk, 1),
                       "price": b["price"]})
    scored.sort(key=lambda x: -x["score"])
    return scored


# ── ثبت آلارم و تلگرام ─────────────────────────────────────────────────────

def merge_alarms(picks):
    """آلارم پیشنهادها در اتاق رادار — idempotent: برای هر نماد فقط یک آلارم
    pump-radar نگه داشته می‌شود تا اجرای هر نیم‌ساعت، لیست را پر نکند."""
    if not picks:
        return
    import brain
    st = brain.room_load("radar", {}) or {}
    pick_syms = {p["symbol"] for p in picks}
    al, keep_fired = [], set()
    for a in (st.get("alarms") or []):
        if a.get("strategy") == "pump-radar" and a.get("sym") in pick_syms:
            # بازبینی کد: آلارم فعال‌شده/باطل‌شده نباید هر نیم‌ساعت دوباره
            # مسلح شود — سیگنال و معاملهٔ کاغذی تکراری می‌ساخت. فقط ARMED
            # قدیمی با نسخهٔ تازه جایگزین می‌شود.
            if a.get("stage") in ("TRIGGERED", "DEAD"):
                al.append(a)
                keep_fired.add(a["sym"])
            continue
        al.append(a)
    for p in reversed(picks):
        if p["symbol"] in keep_fired:
            continue
        al.insert(0, {"sym": p["symbol"], "tf": "15m", "dir": "LONG",
                      "strategy": "pump-radar", "strategyName": "پامپ رادار خوشه‌ای",
                      "price": p["entry"], "now": p["price"],
                      "distancePct": p["dist_pct"],
                      "why": "؛ ".join(p["reasons"][:2]),
                      "expires_at": p.get("expires_at"),
                      "stage": "ARMED"})
    brain.room_save("radar", {**st, "alarms": al[:80]})


def _load_sent():
    try:
        d = json.loads(SENT.read_text())
        now = time.time() * 1000
        return {k: v for k, v in d.items() if now - v < SENT_TTL_MS}
    except Exception:                                # noqa: BLE001
        return {}


def tg_message(source, picks, blocks):
    import telegram as tg
    L = [f"🏷 <b>{tg.PANEL_NAME}</b>",
         "🚀 <b>گزینه‌های پامپ — رادار خوشه‌ای</b>",
         f"<i>منبع تاپ گینرز: {source}</i>", ""]
    bmap = {b["symbol"]: b for b in blocks}

    # ترکیب اجباری گزارش (دستور حمید): یک رهبرِ **پامپ‌شده** + کاندیداهایی
    # که **هنوز پامپ نشده‌اند**. بدون نام‌بردن رهبر، گزارش می‌شود فهرستی از
    # چند ارز بی‌ربط؛ با نام‌بردنش، خواننده می‌بیند رابطه از کجا آمده.
    lead = [b for b in blocks if b.get("layer") == 1]
    lead.sort(key=lambda b: -(b.get("change_24h_pct") or 0))
    if lead:
        h = lead[0]
        mv = [f"+{h[k]}٪ در {lab}" for k, lab in
              (("change_30m_pct", "۳۰د"), ("change_60m_pct", "۱س"),
               ("change_24h_pct", "۲۴س")) if h.get(k)]
        L.append(f"⚡️ <b>رهبر (پامپ‌شده): {h['symbol']}</b>"
                 + (f" — {'، '.join(mv)}" if mv else ""))
        es0 = h.get("event_study") or {}
        if es0.get("pumps_n"):
            L.append(f"<i>تاریخچه‌اش خوانده شد: {es0['pumps_n']} پامپ از "
                     f"{es0.get('from_date') or '؟'}</i>")
        if len(lead) > 1:
            L.append("<i>رهبرهای دیگر همین اجرا: "
                     + "، ".join(b["symbol"] for b in lead[1:4]) + "</i>")
        L.append("")
    if picks:
        L.append("<b>کاندیداها — هیچ‌کدام هنوز پامپ نشده‌اند:</b>")
    for rank, p in enumerate(picks, 1):
        head = "انتخاب اول" if rank == 1 else "جایگزین"
        L.append(f"<b>{head}: {p['symbol']}</b>  (امتیاز {p['score']})")
        L += [f"• {w}" for w in p["reasons"]]
        # تاریخچهٔ درآورده‌شده — قرار حمید: سابقهٔ سردسته، با تاریخ و واکنش‌ها
        b = bmap.get(p["symbol"]) or {}
        leader = (b.get("leaders") or [{}])[0].get("symbol") or b.get("via")
        lh = (bmap.get(leader) or {}).get("history") if leader else None
        if lh:
            L.append(f"📜 سابقهٔ {leader}:")
            for ev in lh[:2]:
                rx = "، ".join(f"{r['symbol'].replace('USDT','')} +{r['ret_pct']}٪ "
                               f"({r['lag_h']}س بعد)" for r in ev["reactions"][:2])
                L.append(f"  {ev['date']} پامپ +{ev['ret_4h_pct']}٪"
                         + (f" → {rx}" if rx else " → واکنشی ثبت نشد"))
        # لگ-کورولیشن کل تاریخچه (قرار حمید، ۱۳ اوت — و شکایت ۱۴ اوت که از
        # گزارش افتاده بود): رابطهٔ آماری با تأخیر، جدا از سابقهٔ رخدادی
        lcl = b.get("lag_corr_leaders") or []
        if lcl:
            L.append("📊 لگ-کورولیشن تاریخی: " + " · ".join(
                f"دنبال {l['symbol'].replace('USDT','')} با r={l['best']['r']:+.2f} "
                f"در تأخیر {l['best']['lag_h']}س"
                + (" (هر دو تایم‌فریم)" if l.get("both_tf") else "")
                for l in lcl[:2]))
        lcf = b.get("lag_corr_followers") or []
        if lcf:
            L.append("📊 دنباله‌روهای آماری‌اش: " + "، ".join(
                f"{f['symbol'].replace('USDT','')} (r={f['best']['r']:+.2f}@{f['best']['lag_h']}س)"
                for f in lcf[:3]))
        evf = b.get("event_followers") or []
        es = b.get("event_study") or {}
        if evf:
            L.append(f"🧾 مطالعهٔ رویدادی ({es.get('pumps_n', '؟')} پامپ تاریخی): " +
                     "، ".join(f"{f['symbol'].replace('USDT','')} "
                               f"{f['k_after']}از{f['N']} ({round(f['prob']*100)}٪)"
                               for f in evf[:3]))
        L.append(f"ورود <code>{p['entry']:.10g}</code> · استاپ <code>{p['sl']:.10g}</code>"
                 f" · ریسک {p['risk_pct']}٪ · فاصله {p['dist_pct']}٪")
        L.append("")
    others = [b["symbol"] for b in blocks
              if b["symbol"] not in {p["symbol"] for p in picks}][:6]
    if others:
        L.append("زیر نظر: " + "، ".join(others))
    L.append(f"🕐 تحلیل و ارسال <code>{tg.tehran()}</code> — به وقت ایران")
    L.append("<i>آلارم روی نقطهٔ ورود ثبت شد — با رسیدن قیمت، بازبینی و سیگنال. "
             "نمونهٔ پامپ کم است؛ این مشاهده است، نه قانون.</i>")
    return "\n".join(L)


def _pick_chart(kc, p):
    """چارت ۵ دقیقه با واترمارک برای انتخاب اول — قانون حمید: سیگنال بی‌چارت نرود."""
    try:
        from tg_batch import chart as _c
        cd = kc.get(p["symbol"], "5m", 120)
        if len(cd) < 20:
            return None
        # خطوط روند از تایم بالا — دستور حمید (۱۶ اوت): «خطوط باید در
        # تایم‌فریم‌های بالاتر کشیده شود و معتبر باشد.» خط از پنجرهٔ ۵د
        # (۱۰ ساعت نویز) قانونِ «۴س/۱س، حداقل ۳ برخورد» را نقض می‌کرد.
        # trendline() خودش بی‌اعتبار را None می‌کند — خط تزئینی کشیده نمی‌شود.
        htf = []
        try:
            from hamid import structure as _st
            for lbl, tf, n, col in (("4H", "4h", 200, "#e91e63"),
                                    ("1H", "1h", 240, "#ab47bc")):
                hcd = kc.get(p["symbol"], tf, n)
                if len(hcd) >= 60:
                    tl = _st.trendline(hcd, lookback=min(len(hcd), 200),
                                       min_touches=3)
                    if tl:
                        htf.append((lbl, tl, hcd, col))
        except Exception:                            # noqa: BLE001
            pass
        return _c(p["symbol"], cd, p.get("entry"), p.get("sl"), None, None,
                  "LONG", htf=htf)
    except Exception as e:                           # noqa: BLE001 - چارت اختیاری، سیگنال نه
        print(f"چارت پیک: {type(e).__name__}")
        return None


def send_telegram(source, picks, blocks, kc=None):
    import telegram as tg
    token, chat = tg.creds()
    if not token:
        print("تلگرام: توکن نیست — چیزی فرستاده نشد (پیام در پنل ثبت است)")
        return False
    sent = _load_sent()
    key = "|".join(f"{p['symbol']}@{p['entry']:.6g}" for p in picks)
    if key in sent:
        print("تلگرام: همین نتیجه قبلاً رفته — تکرار نمی‌کنیم")
        return False
    msg = tg_message(source, picks, blocks)
    buf = _pick_chart(kc, picks[0]) if (kc and picks) else None
    try:
        if buf and len(msg) <= 1024:
            # سقف کپشن تلگرام ۱۰۲۴ است — پیام کوتاه با خود عکس می‌رود
            tg._post(token, "sendPhoto",
                     {"chat_id": chat, "caption": msg, "parse_mode": "HTML"},
                     {"photo": (f"{picks[0]['symbol']}.png", buf.read())})
        else:
            tg._post(token, "sendMessage",
                     {"chat_id": chat, "text": msg,
                      "parse_mode": "HTML", "disable_web_page_preview": "true"})
            if buf:
                tg._post(token, "sendPhoto",
                         {"chat_id": chat, "parse_mode": "HTML",
                          "caption": (f"📈 چارت ۵ دقیقهٔ <b>{picks[0]['symbol']}</b> — "
                                      f"انتخاب اول رادار")},
                         {"photo": (f"{picks[0]['symbol']}.png", buf.read())})
    except Exception as e:                           # noqa: BLE001
        print(f"تلگرام نفرستاد: {tg.scrub(e)}")
        return False
    sent[key] = time.time() * 1000
    SENT.parent.mkdir(exist_ok=True)
    SENT.write_text(json.dumps(sent, indent=1))
    for p in picks:
        tg._log_final({"sym": p["symbol"], "dir": "LONG", "tf": "15m",
                       "entry": p["entry"], "sl": p["sl"], "tp1": None,
                       "strategyName": "پامپ رادار خوشه‌ای"})
    print(f"تلگرام: گزینه‌های پامپ ({len(picks)} انتخاب) فرستاده شد")
    return True


# ── بازنشانی بعد از git reset (ورک‌فلو) ────────────────────────────────────

def reapply(backup_dir):
    """ورک‌فلو قبل از هر تلاشِ پوش، شاخه را به origin/main برمی‌گرداند تا با
    نوشته‌های همزمانِ چرخه تصادم نکند — همان تصادمی که یک بار نتیجهٔ TUT را
    انداخت. این تابع خروجی‌های ما را روی وضعیت تازه دوباره می‌نشاند:
    فایل‌های خودمان کپی، لاگ تلگرام اجتماع دو نسخه، آلارم‌ها merge."""
    bk = Path(backup_dir)
    for name in ("pump-radar.json", "bubbles.json"):
        src = bk / name
        if src.exists():
            OUT.parent.mkdir(exist_ok=True)
            shutil.copy(src, OUT.parent / name)
    if (bk / "pump-radar-sent.json").exists():
        SENT.parent.mkdir(exist_ok=True)
        shutil.copy(bk / "pump-radar-sent.json", SENT)
    # دفتر تاریخچهٔ پامپ — اجتماع رخدادها، تا reset چیزی از تاریخ نکشد
    hist_bk = bk / "pump-history.json"
    if hist_bk.exists():
        try:
            ours = json.loads(hist_bk.read_text()).get("symbols", {})
            theirs = (json.loads(HIST.read_text()).get("symbols", {})
                      if HIST.exists() else {})
            for sym, rec in ours.items():
                trec = theirs.setdefault(sym, {"events": []})
                have = {e["t"] for e in trec["events"]}
                # «پاک نشود» — اجتماع کامل، بدون سقف
                trec["events"] = sorted(
                    trec["events"] + [e for e in rec["events"] if e["t"] not in have],
                    key=lambda x: -x["t"])
                trec["updated"] = max(trec.get("updated", 0), rec.get("updated", 0))
            HIST.parent.mkdir(exist_ok=True)
            HIST.write_text(json.dumps({"symbols": theirs,
                                        "updated": int(time.time() * 1000)},
                                       ensure_ascii=False, indent=1))
        except Exception as e:                       # noqa: BLE001
            print(f"بازنشانی تاریخچهٔ پامپ: {type(e).__name__}")
    # دفتر انتظار + ضدتکرار ضعف — کلاس خطای ۱۷ اوت: این دو در لیست
    # بازنشانی نبودند؛ reset --hard هر اجرا قبرستان و دفتر روز را می‌کشت،
    # ورودی‌های منقضی برمی‌گشتند و همان درس ×۲۶ بار ثبت می‌شد.
    try:
        from hamid import pump_watchlist as _pw
        wl_bk = bk / "pump-watchlist.json"
        ours_wl = json.loads(wl_bk.read_text()) if wl_bk.exists() else {}
        theirs_wl = _pw._load()
        _pw._save(_pw.merge_state(ours_wl, theirs_wl))
    except Exception as e:                           # noqa: BLE001
        print(f"اجتماع دفتر انتظار نشد: {type(e).__name__}")
    try:
        wk_bk = bk / "pump-weakness-seen.json"
        wk = ROOT / "brain" / "pump-weakness-seen.json"
        a = json.loads(wk_bk.read_text()) if wk_bk.exists() else {}
        b = json.loads(wk.read_text()) if wk.exists() else {}
        b.update({k: max(v, b.get(k, 0)) for k, v in a.items()})
        wk.write_text(json.dumps(dict(list(b.items())[-60:]),
                                 ensure_ascii=False, indent=1))
    except Exception as e:                           # noqa: BLE001
        print(f"اجتماع ضدتکرار ضعف نشد: {type(e).__name__}")
    # درس‌های حافظه هم باید از reset جان به در ببرند — یافتهٔ بازبینی معماری:
    # reset --hard هر بار درس‌های همین اجرا را می‌کشت و رادار هیچ‌وقت
    # چیزی «یاد نمی‌گرفت» با اینکه می‌نوشت.
    les_bk = bk / "lessons.json"
    les = ROOT / "brain" / "memory" / "lessons.json"
    if les_bk.exists():
        try:
            ours = json.loads(les_bk.read_text()).get("lessons", [])
            theirs = json.loads(les.read_text()).get("lessons", []) if les.exists() else []
            seen, union = set(), []
            for e in sorted(ours + theirs, key=lambda x: -(x.get("at") or 0)):
                # کلید با روز، نه timestamp — متنِ یکسان در همان روز
                # با مهر تازه، درسِ جدید نیست (ریشهٔ ×۲۶ تکرار).
                _day = int((e.get("at") or 0) / 86_400_000)
                k = (_day, e.get("sym"), e.get("text"))
                if k not in seen:
                    seen.add(k)
                    union.append(e)
            les.parent.mkdir(parents=True, exist_ok=True)
            les.write_text(json.dumps({"lessons": union[:300],
                                       "updated": int(time.time() * 1000)},
                                      ensure_ascii=False, indent=1))
        except Exception as e:                       # noqa: BLE001
            print(f"اجتماع درس‌ها نشد: {type(e).__name__}")
    # (mergeِ ۱۷ اوت: هر دو خط تولید مستقل برای دفتر انتظار رفع نوشتند.
    # نسخهٔ کپیِ «مالِ ما» حذف شد چون merge_state بالا — union با قبرستانِ
    # حذف‌ها — همان مشکل را قوی‌تر حل می‌کند: حذف حتی اگر پشتیبان هم گم
    # شود، با tombstone زنده می‌ماند. دو رفع روی یک فایل، دومی اولی را
    # بازنویسی می‌کرد.)
    tglog_bk = bk / "telegram-log.json"
    tglog = ROOT / "signals" / "telegram-log.json"
    if tglog_bk.exists():
        try:
            ours = json.loads(tglog_bk.read_text()).get("sent", [])
            theirs = json.loads(tglog.read_text()).get("sent", []) if tglog.exists() else []
            seen, union = set(), []
            for e in sorted(ours + theirs, key=lambda x: -(x.get("at") or 0)):
                k = (e.get("at"), e.get("sym"))
                if k not in seen:
                    seen.add(k)
                    union.append(e)
            tglog.write_text(json.dumps({"generated": int(time.time() * 1000),
                                         "sent": union[:40]}, ensure_ascii=False, indent=1))
        except Exception as e:                       # noqa: BLE001
            print(f"اجتماع لاگ تلگرام نشد: {type(e).__name__}")
    try:
        picks = (json.loads(OUT.read_text()).get("recommendation") or [])[:2]
        merge_alarms(picks)
    except Exception as e:                           # noqa: BLE001
        print(f"ثبت آلارم رادار نشد: {type(e).__name__}")


# ── اجرای کامل ─────────────────────────────────────────────────────────────

def run(top=6, min_pct=5.0, deep_n=4, no_telegram=False):
    t0 = time.time()
    source, gs = gainers(top=top, min_pct=min_pct)
    print(f"تاپ گینرز از {source}: " +
          (", ".join(f"{g['symbol']} {g['change_pct']:+}%" for g in gs) or "هیچ"))

    try:
        uni = [s["symbol"] for s in
               sorted(sources.tickers(), key=lambda x: -float(x["quoteVolume"] or 0))
               if s["symbol"].endswith("USDT")][:30]
    except Exception:                                # noqa: BLE001
        uni = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    kc = Kcache()

    # دفتر انتظار — اول از همه: ورودی‌های اجراهای قبل را پایش کن و اگر
    # حجم خورد همان لحظه سیگنال کن. این حلقه مستقل از ماشهٔ امروز است؛
    # رهبرِ کهنه‌شده دیگر ماشه نیست ولی پنجرهٔ دنباله‌روهایش باز است.
    watch_ignited, watch_notes = [], []
    try:
        from hamid import pump_watchlist
        watch_ignited, watch_notes = pump_watchlist.sweep(kc)
        if watch_ignited:
            pump_watchlist.send_ignitions(watch_ignited, kc)
        for wn in watch_notes:
            print(f"  دفتر انتظار: {wn}")
            try:
                from hamid import memory as _m
                _m.remember("درس", wn.split(" ")[0], "دفتر انتظار: " + wn)
            except Exception:                        # noqa: BLE001
                pass
    except Exception as e:                           # noqa: BLE001
        print(f"دفتر انتظار: {type(e).__name__}: {e}")

    # شعله‌گیری ۳۰ دقیقه‌ای — زودتر از جدول گینرهای روز می‌فهمیم
    ign = early_movers(kc, uni)
    if ign:
        print("شعله‌ور در ۳۰ دقیقهٔ اخیر: " +
              ", ".join(f"{x['symbol']} {x['change_pct']:+}%" for x in ign[:5]))
    # تازگی رهبر — «دو روز بالای ۱۰٪ = خبر کهنه». پرونده‌ها ذخیره می‌شوند تا
    # سن واقعی هر رهبر بین اجراها بماند؛ بدون این دفتر، هر اجرا همه‌چیز را
    # «تازه» می‌بیند و همان گزارش تکراری ساخته می‌شود.
    gs, _seen = freshness(gs)
    stale = [g for g in gs if g.get("stale")]
    if stale:
        print("رهبرهای کهنه (ماشه نمی‌شوند): " +
              "، ".join(f"{g['symbol']} {g['change_pct']:+}٪ / {g['top_age_h']}س"
                        for g in stale))
    try:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(_seen, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except Exception as e:                           # noqa: BLE001
        print(f"دفتر تازگی رهبر: {type(e).__name__}: {e}")

    triggers = triggers_of(gs, ign, deep_n=deep_n)
    if not triggers:
        print("هیچ رویداد پامپِ تازه‌ای نیست — گینرهای فعلی همان‌های دیروزند")
    sweet = [t for t in triggers if t.get("sweet")]
    if sweet:
        print(f"حرکت سریع ۵–۱۰٪ (اولویت حمید): " +
              "، ".join(f"{g['symbol']} {g['change_pct']:+}٪" for g in sweet))
    hot = {t["symbol"] for t in triggers}

    blocks, seen = [], set()

    def add(sym, layer, via=None, with_related=True):
        if sym in seen:
            return None
        seen.add(sym)
        b = analyze_one(sym, kc, uni, with_related=with_related)
        if b:
            b["layer"] = layer
            if via:
                b["via"] = via
            blocks.append(b)
            print(f"  لایه {layer} · {sym}: نقش {b['role']} · {b['pump_note']}")
        return b

    for g in triggers:
        b = add(g["symbol"], 1)
        if not b:
            continue
        if g.get("ignition"):
            b["ignition"] = True
        # لایهٔ دوم: دنباله‌روهای این گینر — و لایهٔ سوم: دنباله‌روهای آن‌ها
        for f in (b.get("followers") or [])[:3]:
            b2 = add(f["symbol"], 2, via=g["symbol"])
            if not b2:
                continue
            for f3 in (b2.get("followers") or [])[:2]:
                add(f3["symbol"], 3, via=f["symbol"], with_related=False)
        # لگ-کورولیشن — خواست حمید: همبستگیِ با-تأخیرِ سری بازده‌ها در
        # گذشته، در دو تایم‌فریم؛ دنباله‌روهای آماری هم تحلیل و نامزد می‌شوند
        try:
            from hamid import lagcorr
            lcf = lagcorr.followers_of(kc, g["symbol"], uni)
            if lcf:
                b["lag_corr_followers"] = lcf
                print(f"  لگ-کورولیشن {g['symbol']}: " +
                      ", ".join(f"{x['symbol']} r={x['best']['r']:+.2f}"
                                f"@{x['best']['lag_h']}س" for x in lcf[:3]))
            for f in lcf[:4]:
                b2 = add(f["symbol"], 2, via=g["symbol"])
                if b2 is None:
                    b2 = next((x for x in blocks if x["symbol"] == f["symbol"]), None)
                if b2 is not None:
                    b2.setdefault("lag_corr_leaders", []).append(
                        {"symbol": g["symbol"], "both_tf": f["both_tf"],
                         "best": f["best"],
                         "reason": lagcorr.reason_fa(g["symbol"], f)})
        except Exception as e:                       # noqa: BLE001 - آمار، رادار را نمی‌کشد
            print(f"  لگ-کورولیشن {g['symbol']}: {type(e).__name__}")
        # مطالعهٔ رویدادی کامل — مدل دقیق حمید (۱۴ اوت): تاریخچهٔ لیدر از
        # روز لانچ، هر پامپ ±۲۴س، شمارش k از N برای هر کاندیدا؛ ازقاعده‌گذشته
        # (k≥۳ و ≥۳۰٪) کاندیدای «ارز با احتمال پامپ» می‌شود.
        try:
            from hamid import pump_study
            es = pump_study.run_for_leader(g["symbol"], kc, uni)
            if es:
                b["event_study"] = {
                    "pumps_n": es["pumps_n"],
                    "coverage_from": es["coverage_from"],
                    # تاریخِ خواندنی برای کپشن — timestamp خام روی پیام
                    # تلگرام هیچ چیزی به حمید نمی‌گوید
                    "from_date": (_teh_date(es["coverage_from"])
                                  if es.get("coverage_from") else None)}
                for sym2, row in es["followers"].items():
                    if not row["qualified"]:
                        continue
                    b.setdefault("event_followers", []).append(
                        {"symbol": sym2, **row})
                    b2 = add(sym2, 2, via=g["symbol"])
                    if b2 is None:
                        b2 = next((x for x in blocks if x["symbol"] == sym2), None)
                    if b2 is not None:
                        b2.setdefault("event_leaders", []).append(
                            {"symbol": g["symbol"], **row,
                             "reason": pump_study.reason_fa(g["symbol"], sym2, row)})
        except Exception as e:                       # noqa: BLE001
            print(f"  مطالعهٔ رویدادی {g['symbol']}: {type(e).__name__}")

    # دفتر ماندگار تاریخچهٔ پامپ‌ها — هر رخداد یک بار ثبت و برای همیشه نگه
    # داشته می‌شود («پاک نشود»)؛ خلاصهٔ خوانا هم روی بلوک می‌نشیند
    past_reports = []
    try:
        n_h, fresh_evs = update_history(blocks)
        print(f"دفتر تاریخچهٔ پامپ: {n_h} رخداد ثبت‌شده تا امروز"
              + (f" ({len(fresh_evs)} تازه)" if fresh_evs else ""))
        # وظیفهٔ ثابت (دستور حمید): گذشتهٔ هر ارزِ تازه‌پامپ‌شده چک و به خود
        # ایجنت گزارش شود — اتاق یادگیری + حافظه + گزارش JSON، نه فقط تلگرام.
        bmap_h = {b["symbol"]: b for b in blocks}
        for sym, ev in fresh_evs:
            b = bmap_h.get(sym) or {}
            hist = b.get("history") or []
            n_all = len((json.loads(HIST.read_text())["symbols"].get(sym) or {})
                        .get("events", [])) if HIST.exists() else len(hist)
            fols = [f["symbol"] for f in (b.get("followers") or [])
                    if (f.get("n") or 0) >= 2][:3]
            m = b.get("match")
            rpt = (f"پامپ تازهٔ {sym} ({ev['date']}، +{ev['ret_4h_pct']}٪): "
                   f"در گذشته {n_all} پامپ ثبت‌شده"
                   + (f"؛ شبیه‌ترین پامپ قبلی {m['corr_pct']}٪ همخوان و بعدش "
                      f"{m['then_24h_pct']:+}٪ رفت" if m else "")
                   + (f"؛ دنباله‌روهای تاریخی‌اش: {'، '.join(fols)}" if fols
                      else "؛ دنباله‌روی تاریخی معناداری ندارد"))
            past_reports.append({"symbol": sym, "event": ev, "report": rpt})
            try:
                import brain
                brain.room_log("learning", rpt, "pump-past")
            except Exception:                        # noqa: BLE001
                pass
            try:
                from hamid import memory as _mem
                _mem.remember("تحلیل", sym, rpt, {"ret": ev["ret_4h_pct"]})
            except Exception:                        # noqa: BLE001
                pass
            print(f"  📜 {rpt}")
    except Exception as e:                           # noqa: BLE001
        print(f"دفتر تاریخچه: {type(e).__name__}: {e}")

    # قانون ترکیب، ساختاری نه اتفاقی: رهبرِ همین اجرا هرگز کاندیدا نیست.
    # دروازهٔ «هنوز-نپریده» در recommend این را عملاً می‌گیرد، ولی اتکا به
    # یک آستانهٔ عددی برای یک قانونِ قطعی درست نیست — رهبر با نام حذف می‌شود.
    picks = [p for p in recommend(blocks, hot=hot) if p["symbol"] not in hot][:3]
    picks = [p for p in picks if p["score"] >= 2]

    # پنجرهٔ زمانی تاریخی — هستهٔ قانون جدید حمید: دنباله‌رو فقط تا وقتی
    # پیشنهاد است که طبق فاصله‌های تاریخی خودش هنوز «وقت پریدن» دارد.
    bmap = {b["symbol"]: b for b in blocks}
    now_ms = int(time.time() * 1000)
    timed = []
    for p in picks:
        b = bmap.get(p["symbol"]) or {}
        leader = (b.get("leaders") or [{}])[0].get("symbol") or b.get("via")
        lb = bmap.get(leader) if leader else None
        # پنجرهٔ لگ-کورولیشنی: وقتی رابطه از سری بازده‌هاست نه رخداد،
        # مهلت هم از همان تأخیر آماری می‌آید — دو برابر lag، کف ۳ ساعت
        lc = (b.get("lag_corr_leaders") or [None])[0]
        if not (lb and lb.get("pumps")) and lc:
            w_h = max(2 * lc["best"]["lag_h"], 3.0)
            p["expires_at"] = int(now_ms + w_h * 3600e3)
            p["lag"] = {"leader": lc["symbol"], "med_h": lc["best"]["lag_h"],
                        "window_h": round(w_h, 1), "left_h": round(w_h, 1),
                        "n": lc["best"]["n"], "kind": "lag-corr"}
            p["reasons"].append(f"پنجرهٔ آماری: ~{w_h:.1f}س از الان "
                                f"(دو برابر تأخیر لگ-کورولیشن)")
        if lb and lb.get("pumps"):
            lg = follower_lags(lb["pumps"], b.get("pumps"))
            last_lead_pump = max(e["t"] for e in lb["pumps"])
            since_h = (now_ms - last_lead_pump) / 3600e3
            if lg:
                window_h = max(lg["max_h"], 2 * lg["med_h"])
                left_h = round(window_h - since_h, 1)
                if left_h <= 0:
                    p["expired_reason"] = (f"طبق {lg['n']} سابقه، {p['symbol']} معمولاً "
                                           f"{lg['med_h']}س بعد از {leader} می‌پرد؛ "
                                           f"{since_h:.1f}س گذشته — پنجره بسته است، پیشنهاد نمی‌شود")
                    continue
                p["lag"] = {**lg, "leader": leader, "since_h": round(since_h, 1),
                            "window_h": round(window_h, 1), "left_h": left_h}
                p["expires_at"] = int(last_lead_pump + window_h * 3600e3)
                p["reasons"].insert(0, (f"طبق {lg['n']} سابقه معمولاً ~{lg['med_h']}س بعد از "
                                        f"{leader} می‌پرد — {left_h}س از پنجره باقی است"))
                # معاینهٔ چارت — قانون حمید: چارتِ الانِ دنباله‌رو را با چارتش
                # درست قبل از واکنش‌های قبلی به همین سردسته مقایسه کن؛ شباهت
                # بالا یعنی همان الگو دارد تکرار می‌شود، شباهت پایین گفتنی است.
                try:
                    sim = react_similarity(kc, p["symbol"], b.get("pumps"), lb["pumps"])
                except Exception:                    # noqa: BLE001
                    sim = None
                if sim:
                    p["react_sim"] = sim
                    if sim["corr_pct"] >= 60:
                        p["reasons"].insert(1, (f"چارت الان {sim['corr_pct']}٪ شبیه قبلِ "
                                                f"{sim['n_reacts']} واکنش قبلی‌اش به {leader} است"))
                    elif sim["corr_pct"] <= 20:
                        p["reasons"].append((f"هشدار معاینه: چارت الان فقط {sim['corr_pct']}٪ "
                                             f"شبیه قبلِ واکنش‌های قبلی‌اش است — الگو فرق دارد"))
        # نقشهٔ لیکوییدیشن — خوشهٔ بالای قیمت یعنی سوخت حرکت خرید
        try:
            from hamid import liqmap
            lm = liqmap.build(kc.get(p["symbol"], "1h", 1000))
            if lm:
                p["liq_map"] = {"magnet": lm["magnet"], "above": lm["above"][:2],
                                "below": lm["below"][:2]}
                ln = liqmap.note(lm, "LONG")
                if ln:
                    p["reasons"].append(ln)
        except Exception:                            # noqa: BLE001
            pass
        timed.append(p)
    expired_picks = [p for p in picks if p.get("expired_reason")]
    picks = timed[:2]

    # ثبت در دفتر انتظار — کاندیدای رابطه‌دارِ هنوز-ساکت گمشدنی نیست؛
    # اجراهای بعدی حجمش را پایش می‌کنند و لحظهٔ شروع حرکت سیگنال می‌شود.
    try:
        from hamid import pump_watchlist
        _, wl_added = pump_watchlist.add_candidates(blocks, timed)
        if wl_added:
            print("  دفتر انتظار: ثبت " + "، ".join(wl_added))
    except Exception as e:                           # noqa: BLE001
        print(f"دفتر انتظار (ثبت): {type(e).__name__}: {e}")

    skipped = [{"symbol": b["symbol"], "why": b["skipped"]}
               for b in blocks if b.get("skipped")]
    verdict = None
    if (gs or ign) and not picks:
        wl_n = 0
        try:
            from hamid import pump_watchlist
            wl_n = len([k for k in pump_watchlist._load() if k != "_graveyard"])
        except Exception:                            # noqa: BLE001
            pass
        verdict = ("خوشه قبل از رسیدن ما دویده — همهٔ اعضا ۱۰٪+ رفته‌اند یا نقطهٔ "
                   "ورود ندارند. سیگنالِ دیر صادر نمی‌کنیم"
                   + (f"؛ {wl_n} دنباله‌روی هنوز-ساکت در دفتر انتظار زیر پایش "
                      "حجم است — لحظهٔ شروع حرکت سیگنال می‌شود." if wl_n
                      else " و این یک ضعف ثبت‌شده است، نه یک فرصت."))
        print(verdict)

    # ذخیره در حافظه — قانون حمید: هر تحلیل، نتیجه و ضعفش را ثبت کند تا
    # تحلیل بعد از آن استفاده کند، نه اینکه هر بار از صفر شروع شود.
    try:
        from hamid import memory as mem
        if verdict:
            # ضدتکرار: همین ضعف برای همین رهبر امروز قبلاً ثبت شده؟ ۶۳ کپی
            # از یک جمله در حافظه یادگیری نیست، نویز است.
            _wk = ROOT / "brain" / "pump-weakness-seen.json"
            _key = (gs[0]["symbol"] if gs else "-") + time.strftime("|%Y-%m-%d")
            try:
                _wd = json.loads(_wk.read_text()) if _wk.exists() else {}
            except Exception:                        # noqa: BLE001
                _wd = {}
            if _key not in _wd:
                mem.remember("ضعف", gs[0]["symbol"] if gs else "-",
                             "پامپ رادار دیر رسید: " + verdict[:120])
                _wd[_key] = int(time.time() * 1000)
                _wd = dict(list(_wd.items())[-60:])
                _wk.write_text(json.dumps(_wd, ensure_ascii=False, indent=1))
        for p in picks:
            mem.remember("تحلیل", p["symbol"],
                         f"رادار {p['symbol']} را پیشنهاد کرد (امتیاز {p['score']}): "
                         + (p["reasons"][0] if p["reasons"] else ""),
                         {"entry": p["entry"], "score": p["score"]})
    except Exception as e:                           # noqa: BLE001 - حافظه تحلیل را نمی‌کشد
        print(f"ثبت حافظه: {type(e).__name__}")

    # آینهٔ ریزش — قانون حمید: بیت‌کوین که ریخت، سریع علت را پیدا کن، ارزهایی
    # که طبق سابقه بعد از ریزش‌های مشابه ریخته‌اند را با الان مقایسه کن و
    # هشدار بده: «آقای حمید حواست به این‌ها باشد».
    try:
        cw = crash_watch(kc, uni)
    except Exception as e:                           # noqa: BLE001
        print(f"آینهٔ ریزش: {type(e).__name__}")
        cw = None
    if cw:
        print(f"⚠️ ریزش BTC {cw['btc_1h']}٪ در یک ساعت — "
              f"{len(cw['followers'])} دنباله‌روی تاریخی ریزش پیدا شد")
    # علت‌یابی حرکت BTC — دو طرفه (قانون حمید: ریخت یا پرید، فوری علت اعلام شود)
    try:
        mc = btc_move_cause(kc)
    except Exception as e:                           # noqa: BLE001
        print(f"علت‌یابی BTC: {type(e).__name__}")
        mc = None
    if mc:
        print("🧭 " + move_cause_fa(mc).replace("\n", " | "))

    report = {
        "generated": int(time.time() * 1000),
        "source": source,
        "crash": cw,
        "btc_move": mc,
        "gainers": gs,
        "ignitions": ign[:6],
        "universe_n": len(uni),
        "coins": blocks,
        "recommendation": picks,
        "past_reports": past_reports,
        "window_closed": [{"symbol": p["symbol"], "why": p["expired_reason"]}
                          for p in expired_picks],
        "already_pumped": skipped,
        "verdict": verdict,
        "note": ("قانون: ارزِ ۱۰٪+ پریده سیگنال نیست — فقط عضو نپریدهٔ خوشه. "
                 "رخدادهای پامپ کم‌اند؛ روابط خوشه‌ای مشاهده‌اند، نه قانون. "
                 "پیشنهاد یعنی آلارم و بازبینی در لحظهٔ رسیدن قیمت — نه ورود کور."),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    # دفتر نمرهٔ پیشنهادها (داور: precision پیشنهاد هیچ‌جا نمره نمی‌شد) —
    # هر pick با قیمت لحظه ثبت می‌شود تا اسکریپت نمره‌دهی بعداً بسنجد چند
    # درصدشان واقعاً در پنجره پریدند.
    try:
        with (ROOT / "brain" / "pump-picks.jsonl").open("a") as f:
            for p in picks:
                f.write(json.dumps({"t": report["generated"], "sym": p["symbol"],
                                    "entry": p["entry"], "price": p["price"],
                                    "score": p["score"],
                                    "expires_at": p.get("expires_at")},
                                   ensure_ascii=False) + "\n")
    except Exception as e:                           # noqa: BLE001
        print(f"دفتر پیشنهادها: {type(e).__name__}")
    print(f"خروجی: {OUT.relative_to(ROOT)} · {len(blocks)} ارز در ۳ لایه")

    try:
        merge_alarms(picks)
    except Exception as e:                           # noqa: BLE001
        print(f"ثبت آلارم رادار نشد: {type(e).__name__}")

    # حباب‌ها — شخصیت صفر تا صد متحرک‌ها، سوار بر همین دادهٔ کش‌شده (۱۵ دقیقه)
    try:
        from hamid import bubbles
        moving = sorted({g["symbol"] for g in gs} | {x["symbol"] for x in ign}
                        | set(uni[:20]) | {b["symbol"] for b in blocks})
        n_b = bubbles.build(kc, moving, blocks)
        print(f"حباب‌ها: {n_b} پروفایل شخصیت ساخته شد")
    except Exception as e:                           # noqa: BLE001 - حباب رادار را نمی‌کشد
        print(f"حباب‌ها: {type(e).__name__}: {e}")

    # هشدار ریزش — فوری، جدا از پیشنهادهای پامپ؛ ضدتکرار با سطل ۲ساعته تا
    # در ریزش ادامه‌دار هر ۱۵ دقیقه پیام تکراری نرود.
    if cw and not no_telegram:
        try:
            import telegram as _tg
            tok, chat = _tg.creds()
            sent = _load_sent()
            key = f"crash|{int(time.time() // 7200)}"
            if tok and key not in sent:
                if mc and mc["dir"] == "down":
                    why = move_cause_fa(mc)
                else:
                    why = (f"علت احتمالی: {cw['why']}" if cw.get("why") else
                           "علت هنوز در خبرها پیدا نشد — شکار خبر ادامه دارد")
                rows = "\n".join(
                    f"· <b>{f['symbol'].replace('USDT','')}</b> — در {f['hit_pct']}٪ از "
                    f"{f['n']} ریزش مشابه BTC ریخته (الان {f['chg_now']:+}٪)"
                    for f in cw["followers"]) or "دنباله‌روی تاریخی معناداری پیدا نشد"
                text = (f"🏷 <b>{_tg.PANEL_NAME}</b>\n"
                        f"🔻 <b>هشدار ریزش بیت‌کوین</b>\n\n"
                        f"BTC در یک ساعت <b>{cw['btc_1h']}٪</b> ریخت "
                        f"(از {cw['n_crashes']} ریزش مشابه در تاریخچه).\n"
                        f"{why}\n\n"
                        f"طبق سابقه، این‌ها بعد از ریزش‌های مشابه ریخته‌اند —\n"
                        f"<b>آقای حمید حواست به این‌ها باشد:</b>\n{rows}\n\n"
                        f"🕐 <code>{_tg.tehran()}</code> به وقت ایران")
                bbuf = None
                try:
                    from tg_batch import chart as _c
                    b5 = kc.get("BTCUSDT", "5m", 120)
                    if len(b5) >= 20:
                        bbuf = _c("BTCUSDT", b5, None, None, None, None, "DUMP")
                except Exception:                    # noqa: BLE001
                    bbuf = None
                if bbuf and len(text) <= 1024:
                    _tg._post(tok, "sendPhoto",
                              {"chat_id": chat, "parse_mode": "HTML", "caption": text},
                              {"photo": ("BTCUSDT.png", bbuf.read())})
                else:
                    _tg._post(tok, "sendMessage",
                              {"chat_id": chat, "parse_mode": "HTML", "text": text})
                    if bbuf:
                        _tg._post(tok, "sendPhoto",
                                  {"chat_id": chat,
                                   "caption": "📉 چارت ۵ دقیقهٔ BTCUSDT — لحظهٔ ریزش"},
                                  {"photo": ("BTCUSDT.png", bbuf.read())})
                sent[key] = time.time() * 1000
                SENT.parent.mkdir(exist_ok=True)
                SENT.write_text(json.dumps(sent, indent=1))
                print("تلگرام: هشدار ریزش فرستاده شد")
        except Exception as e:                       # noqa: BLE001
            print(f"هشدار ریزش تلگرام: {type(e).__name__}")

    # پرش BTC — علت‌یابی همان لحظه به تلگرام (ریزش داخل هشدار ریزش می‌رود)
    if mc and mc["dir"] == "up" and not no_telegram:
        try:
            import telegram as _tg
            tok, chat = _tg.creds()
            sent = _load_sent()
            key = f"btcup|{int(time.time() // 7200)}"
            if tok and key not in sent:
                _tg._post(tok, "sendMessage",
                          {"chat_id": chat, "parse_mode": "HTML",
                           "text": (f"🏷 <b>{_tg.PANEL_NAME}</b>\n"
                                    f"🚀 <b>پرش بیت‌کوین — علت‌یابی فوری</b>\n\n"
                                    f"{move_cause_fa(mc)}\n\n"
                                    f"🕐 <code>{_tg.tehran()}</code> به وقت ایران")})
                sent[key] = time.time() * 1000
                SENT.parent.mkdir(exist_ok=True)
                SENT.write_text(json.dumps(sent, indent=1))
                print("تلگرام: علت‌یابی پرش BTC فرستاده شد")
        except Exception as e:                       # noqa: BLE001
            print(f"علت‌یابی پرش BTC: {type(e).__name__}")

    if picks and not no_telegram:
        send_telegram(source, picks, blocks, kc=kc)
    elif not picks:
        print("هیچ گزینه‌ای به آستانهٔ امتیاز نرسید — نفرستادن بهتر از پیشنهاد ضعیف است")
        # دستور صریح حمید (۱۷ اوت، بعد از دیدن پیام «دیر رسیدیم» در
        # تلگرام): «۱۰۰ بار گفتم این سیستم را پاک کن.» گزارشِ دیر رسیدن
        # دیگر هرگز به تلگرام نمی‌رود — سیستم جایگزین، دفتر انتظار است:
        # پیشنهاد = رهبرِ پامپ‌شده + دنباله‌روهای هنوز-ساکتِ تاریخچه‌محور،
        # و سیگنال فقط در لحظهٔ حجم خوردن (🧠). حکم late فقط در لاگ/پنل
        # می‌ماند (برای ممیزی)، نه در تلگرام حمید.
        print(f"تمام شد در {time.time() - t0:.0f} ثانیه")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--min-pct", type=float, default=5.0)
    ap.add_argument("--deep", type=int, default=4)
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--reapply", metavar="DIR",
                    help="فقط بازنشانی خروجی‌های بکاپ‌شده روی درخت تازه")
    a = ap.parse_args()
    if a.reapply:
        reapply(a.reapply)
        return
    run(top=a.top, min_pct=a.min_pct, deep_n=a.deep, no_telegram=a.no_telegram)


if __name__ == "__main__":
    main()
