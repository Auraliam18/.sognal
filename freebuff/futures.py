#!/usr/bin/env python3
"""لایهٔ دادهٔ فیوچرز — پنل فری‌باف ۱.

پنل فعلی روی کندل اسپات تحلیل می‌کند و سیگنال فیوچرز می‌دهد؛ این ماژول
همان شکاف را برای پنل فری‌باف ۱ می‌بندد: کندل فیوچرز (usdt-perp)،
Open Interest، فاندینگ و نسبت لانگ/شورت، از پنج صرافی با ترتیب جایگزینی
— همان الگوی sources.py، اما برای فیوچرز و مخصوص پنل فری‌باف ۱.

ترتیب صرافی‌ها از آزمایش شبکه‌ای آمده، نه ترجیح: بایننس و بای‌بیت از
شبکه‌های محدود (و رانرهای US گاهی) رد می‌شوند؛ OKX/Bitget/Gate پاسخ‌گوترند
و جلوتر می‌نشینند. هیچ چیز به ترتیب وابسته نیست — اولین پاسخِ سالم برنده است.

قواعد قرضی از کد قبلی:
  · پاسخ ناقص یا برعکس = رد، نه «همین‌جا استفاده کنیم» (sane).
  · صرافیِ برنده روی خروجی نوشته می‌شود، برند حدس زده نمی‌شود.
  · صرافیِ ردشده بلافاصله دوباره پرسیده نمی‌شود (stand-down).

شکل خروجی در «شکل Binance» است تا مصرف‌کننده یکی باشد:

    klines(sym, tf, limit) -> [[open_ms, o, h, l, c, v, close_ms], ...] قدیم→جدید

    python3 freebuff/futures.py          # خودآزمایی شبکه‌ای
"""
import json
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; freebuff1/1.0)"}
TIMEOUT = 12

# stand-down — همان درس sources.py: صرافیِ ردشده تا ۵ دقیقه دوباره پرسیده
# نشود، وگرنه یک صرافیِ محدودشده کل چرخهٔ ۵ دقیقه‌ای را می‌بلعد.
_STOOD_DOWN = {}
_FAILS = {}
STAND_DOWN_SECONDS = 300
FAILS_BEFORE_STAND_DOWN = 3

_TF = {"5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}
_TF_BITGET = {"5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}


def _available(vid):
    return time.time() >= _STOOD_DOWN.get(vid, 0)


def _note_failure(vid):
    _FAILS[vid] = _FAILS.get(vid, 0) + 1
    if _FAILS[vid] >= FAILS_BEFORE_STAND_DOWN:
        _STOOD_DOWN[vid] = time.time() + STAND_DOWN_SECONDS
        _FAILS[vid] = 0


def _note_success(vid):
    _FAILS[vid] = 0
    _STOOD_DOWN.pop(vid, None)


def _json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _k(t, o, h, l, c, v):
    return [int(t), float(o), float(h), float(l), float(c), float(v), int(t)]


VENUES = []


def venue(vid, label, url):
    """ثبت صرافی. `url` درخواست را می‌سازد؛ تابعِ تزئین‌شده پاسخ را به
    شکل Binance برمی‌گرداند، قدیم→جدید — جدا نگه‌داشته‌شده تا
    test_futures.py بدون شبکه، ترتیب فیلدها را با پاسخِ ضبط‌شده بسنجد."""
    def deco(fn):
        VENUES.append({"id": vid, "label": label, "url": url, "parse": fn})
        return fn
    return deco


def _okx_inst(sym):
    return sym.replace("USDT", "") + "-USDT-SWAP"


@venue("okx", "OKX",
       lambda s, tf, n: f"https://www.okx.com/api/v5/market/candles?instId={_okx_inst(s)}"
                        f"&bar={_TF[tf]}&limit={min(n, 300)}")
def _k_okx(r):
    # data: [ts,o,h,l,c,volCcy,vol] رشته، جدید→قدیم
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in reversed(r["data"])]


@venue("btg", "Bitget",
       lambda s, tf, n: f"https://api.bitget.com/api/v2/mix/market/candles?symbol={s}"
                        f"&productType=USDT-FUTURES&granularity={_TF_BITGET[tf]}&limit={min(n, 1000)}")
def _k_bitget(r):
    # data: [ts,o,h,l,c,baseVol,quoteVol] رشته، قدیم→جدید
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in r["data"]]


@venue("gate", "Gate.io",
       lambda s, tf, n: f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks"
                        f"?contract={s.replace('USDT','_USDT')}&interval={_TF[tf]}&limit={min(n, 1000)}")
def _k_gate(r):
    # [{t(s),o,h,l,c,v,sum},...] جدید→جدید، رشته
    return [_k(int(x["t"]) * 1000, x["o"], x["h"], x["l"], x["c"], x["v"])
            for x in reversed(r)]


@venue("binf", "Binance Futures",
       lambda s, tf, n: f"https://fapi.binance.com/fapi/v1/klines?symbol={s}"
                        f"&interval={_TF[tf]}&limit={n}")
def _k_binance(r):
    # شکل مرجع: قدیم→جدید — بعضی شبکه‌ها ۴۵۱ می‌دهند، به همین دلیل آخر است
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in r]


@venue("byb", "Bybit",
       lambda s, tf, n: f"https://api.bybit.com/v5/market/kline?category=linear"
                        f"&symbol={s}&interval={ {'5m':'5','15m':'15','1h':'60','4h':'240','1d':'D'}[tf] }&limit={min(n, 1000)}")
def _k_bybit(r):
    # result.list: [start_ms,o,h,l,c,vol,turnover] جدید→قدیم
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in reversed(r["result"]["list"])]


def sane(rows, want):
    """همان گارد پنل: پاسخ خوب‌شکل می‌تواند بی‌فایده باشد — برعکس، کوتاه،
    یا با دو فیلد جابه‌جا. هر کدام یک بار برای کسی اتفاق افتاده."""
    if not rows or len(rows) < min(want, 10):
        return False
    if len(rows) < want * 0.9:
        return False
    if rows[0][0] >= rows[-1][0]:
        return False
    for k in rows:
        o, h, l, c = k[1], k[2], k[3], k[4]
        if not all(x == x for x in (o, h, l, c)):
            return False
        if h < l or min(o, h, l, c) <= 0:
            return False
        if h < max(o, c) or l > min(o, c):
            return False
    return True


_used = {"klines": None, "oi": None, "funding": None, "longshort": None}


def used():
    """کدام صرافی واقعاً جواب داد — روی خروجی می‌نشیند، حدس نمی‌شود."""
    return dict(_used)


def klines(sym, tf, limit):
    """کندل فیوچرز از اولین صرافی که سریِ کاملِ سالم بدهد."""
    errs = []
    order = [v for v in VENUES if _available(v["id"])] or VENUES
    for v in order:
        try:
            rows = v["parse"](_json(v["url"](sym, tf, limit)))[-limit:]
        except Exception as e:                       # noqa: BLE001
            errs.append(f"{v['id']}: {type(e).__name__}")
            _note_failure(v["id"])
            continue
        if not sane(rows, limit):
            errs.append(f"{v['id']}: {len(rows)} rows, rejected")
            _note_failure(v["id"])
            continue
        _note_success(v["id"])
        _used["klines"] = v["id"]
        return rows
    raise RuntimeError(f"{sym} {tf} futures: no venue — {'; '.join(errs[:6])}")


def oi_history(sym="BTCUSDT", period="5m", limit=48):
    """تاریخچهٔ OI بایننس — رشد/کاهش پوزیشن باز، مادهٔ خام تشخیص پامپ واقعی."""
    try:
        j = _json(f"https://fapi.binance.com/futures/data/openInterestHist"
                  f"?symbol={sym}&period={period}&limit={limit}")
        _used["oi"] = "binf"
        return [{"t": int(x["timestamp"]), "oi": float(x["sumOpenInterest"]),
                 "oi_usd": float(x["sumOpenInterestValue"])}
                for x in j]
    except Exception as e:                           # noqa: BLE001
        raise RuntimeError(f"oi_hist: binf {type(e).__name__}") from e


def oi_snapshot_okx():
    """سطح لحظه‌ای OI از OKX — جایگزینِ تاریخچهٔ بایننس وقتی بایننس رد می‌شود."""
    out = []
    for sym in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"):
        try:
            j = _json(f"https://www.okx.com/api/v5/public/open-interest"
                      f"?instType=SWAP&instId={sym}")
            d = j["data"][0]
            out.append({"symbol": sym, "oi": float(d.get("oiCcy") or 0),
                        "oi_usd": float(d.get("oiUsd") or 0),
                        "at": int(d.get("ts") or 0)})
        except Exception:                            # noqa: BLE001
            continue
    if not out:
        raise RuntimeError("oi_snapshot: no venue")
    _used["oi"] = "okx"
    return out


def funding(limit=60):
    """فاندینگ جفت‌های فیوچرز OKX — صعودی مرتب‌شده بر قدرت انحراف."""
    rows = []
    # OKX: funding-rate فهرستی — اول جفت‌های اصلی، بعد هرچه بتوانیم
    for sym in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP",
                "XRP-USDT-SWAP", "DOGE-USDT-SWAP"):
        try:
            j = _json(f"https://www.okx.com/api/v5/public/funding-rate"
                      f"?instId={sym}")
            d = j["data"][0]
            rows.append({"symbol": sym.replace("-USDT-SWAP", "USDT"),
                         "rate": round(float(d["fundingRate"]) * 100, 5),
                         "mark": float(d.get("markPx") or 0),
                         "at": int(d.get("fundingTime") or 0)})
        except Exception:                            # noqa: BLE001
            continue
    if not rows:
        raise RuntimeError("funding: no venue")
    _used["funding"] = "okx"
    return sorted(rows, key=lambda r: -abs(r["rate"]))[:limit]


def longshort(limit=40):
    """نسبت لانگ/شورت حساب‌های عمومی بایننس — جمعیت کدام سمت سنگین است."""
    out = []
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"):
        try:
            j = _json(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
                      f"?symbol={sym}&period=5m&limit=1")
            if j:
                x = j[-1]
                out.append({"symbol": sym,
                            "ratio": round(float(x["longShortRatio"]), 3),
                            "long_pct": round(float(x["longAccount"]) * 100, 1)})
        except Exception:                            # noqa: BLE001
            continue
    if not out:
        raise RuntimeError("longshort: no venue")
    _used["longshort"] = "binf"
    return out[:limit]


# ── تحلیل‌های کوتاه روی همان داده ──────────────────────────────────────────

def oi_pulse(hist, window=12):
    """ضربان OI: رشد پوزیشن باز در پنجرهٔ اخیر — پول تازه یا بسته‌شدن.

    ورودی خروجی oi_history است؛ خروجی قابل‌چاپ برای پنل. بذردار نیست:
    آستانه‌ها درصدی‌اند و دادهٔ ورودی همان چیزی است که صرافی داد."""
    if not hist or len(hist) < window + 1:
        return {"verdict": "سری OI کوتاه است", "chg_pct": None}
    now, then = hist[-1]["oi"], hist[-1 - window]["oi"]
    if then <= 0:
        return {"verdict": "سری OI ناسالم", "chg_pct": None}
    chg = (now - then) / then * 100
    verdict = ("پوزیشن باز دارد رشد می‌کند — پول تازه وارد است"
               if chg > 1.0 else
               "پوزیشن باز در حال بسته‌شدن است — پول خارج می‌شود"
               if chg < -1.0 else "OI خنثی")
    return {"verdict": verdict, "chg_pct": round(chg, 2)}


def funding_verdict(rows):
    """حکم فاندینگ از فهرست نرخ‌ها — بدون هیچ حدسی."""
    if not rows:
        return {"verdict": "دادهٔ فاندینگ نیامد", "avg": None, "extremes": []}
    core = [r["rate"] for r in rows if r["symbol"] in
            ("BTCUSDT", "ETHUSDT", "SOLUSDT")]
    avg = sum(core) / len(core) if core else sum(r["rate"] for r in rows) / len(rows)
    verdict = ("فاندینگ مثبت — لانگ‌ها پول می‌دهند، جمعیت سمت خرید سنگین است"
               if avg > 0.005 else
               "فاندینگ منفی — شورت‌ها پول می‌دهند، جمعیت سمت فروش سنگین است"
               if avg < -0.005 else "فاندینگ خنثی")
    extremes = [r for r in rows if abs(r["rate"]) > 0.05][:6]
    return {"verdict": verdict, "avg": round(avg, 4), "extremes": extremes}


def longshort_verdict(rows):
    if not rows:
        return "نسبت لانگ/شورت نیامد"
    hot = [r for r in rows if r["ratio"] >= 2.0]
    if hot:
        names = ", ".join(r["symbol"].replace("USDT", "") for r in hot)
        return f"جمعیت لانگ سنگین: {names} — سوخت لیکویید برای شورت‌ها"
    if all(r["ratio"] < 1.0 for r in rows):
        return "جمعیت سمت شورت سنگین‌تر است — سوخت لیکویید برای لانگ‌ها"
    return "نسبت لانگ/شورت متعادل"


if __name__ == "__main__":
    t0 = time.time()
    kl = klines("BTCUSDT", "15m", 200)
    print(f"klines: {len(kl)} candles from {used()['klines']}, last close {kl[-1][4]}")
    try:
        h = oi_history("BTCUSDT")
        print(f"OI history: {len(h)} points — {oi_pulse(h)}")
    except Exception as e:                           # noqa: BLE001
        s = oi_snapshot_okx()
        print(f"OI snapshot (OKX, بایننس رد شد: {type(e).__name__}): {len(s)} نماد")
    f = funding()
    v = funding_verdict(f)
    print(f"funding: {len(f)} symbols — {v['verdict']} (avg {v['avg']})")
    try:
        ls = longshort()
        print(f"longshort: {longshort_verdict(ls)}")
    except Exception as e:                           # noqa: BLE001
        print(f"longshort: در دسترس نیست ({type(e).__name__})")
    print(f"venues used: {used()} in {time.time() - t0:.1f}s")
