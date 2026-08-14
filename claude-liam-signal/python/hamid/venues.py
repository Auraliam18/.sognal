"""صرافی‌های هدف حمید — بیت‌یونیکس، XT.com، KCEX (دستور ۱۴ اوت).

«اولویت اصلی تو پایش ۱۰۰ تا ۲۰۰ ارز برتر مارکت هست... در بین بازار اولویتت
ارزهایی هست که در صرافی‌های بیت یونیکس، ایکس تی دات کام و KCEX هستند.»

چرا این ماژول جداست: رتبه‌بندی جهان اسکن با حجم انجام می‌شود (universe.py) و
باید همان بماند — نقدشوندگی همان چیزی است که ساختار را واقعی می‌کند. ولی
سیگنالی که حمید نمی‌تواند اجرا کند ارزشی ندارد. پس این ماژول رتبه را عوض
نمی‌کند، فقط **ترتیب** را عوض می‌کند: نمادِ قابل‌معامله جلو می‌افتد.

## چرا پارس این‌جا «شکل‌ناشناس» است و در sources.py نیست

sources.py با تأکید می‌گوید ایندکس اشتباهِ فیلد باز هم یک عدد است، فقط قیمت
نیست — پس آن‌جا شکل باید دقیقاً از پاسخ واقعی استخراج شود. این‌جا فرق دارد:
دنبال **نام نماد** می‌گردیم و نام نماد خودمعرف است. `BTCUSDT` یا `BTC_USDT`
یا `BTC-USDT` هر جای JSON که باشد همان است، و هیچ عدد یا رشتهٔ دیگری تصادفاً
شبیه آن نمی‌شود. برای همین این‌جا regex روی بدنهٔ خام امن است و در برابر
تغییر شکل API هم مقاوم — چیزی که برای کندل هرگز درست نبود.

## گاردها

- کمتر از MIN_SYMBOLS نماد = پاسخ را قبول نکن. یک صفحهٔ خطا هم ممکن است یکی
  دو نماد داشته باشد؛ فهرست واقعی صدها تاست. پاسخ مشکوک، «صرافی جواب نداد».
- کش با TTL؛ فهرست لیست‌شدن‌ها ساعتی عوض نمی‌شود و نباید هر چرخه گرفته شود.
- هیچ‌وقت اسکن را نمی‌کشد: صرافی نیامد → ترتیب دست‌نخورده می‌ماند و همین
  صادقانه گزارش می‌شود.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "brain" / "venues" / "listings.json"

UA = {"User-Agent": "Mozilla/5.0 (compatible; hamid-signal)"}
TIMEOUT = 12
TTL_H = 12                 # فهرست لیست‌شدن‌ها روزانه عوض می‌شود، نه ساعتی
MIN_SYMBOLS = 20           # کمتر از این = پاسخ معتبر نیست

# چند نقطهٔ پایانی برای هر صرافی: اولی که فهرست باورپذیر بدهد برنده است.
# هم اسپات هم فیوچرز، چون حمید روی هر دو معامله می‌کند و «قابل معامله بودن»
# یعنی حداقل روی یکی باشد.
ENDPOINTS = {
    "bitunix": [
        "https://fapi.bitunix.com/api/v1/futures/market/tickers",
        "https://fapi.bitunix.com/api/v1/futures/market/trading_pairs",
        "https://openapi.bitunix.com/api/v1/futures/market/tickers",
        "https://openapi.bitunix.com/api/spot/v1/market/tickers",
    ],
    "xt": [
        "https://sapi.xt.com/v4/public/ticker/24h",
        "https://sapi.xt.com/v4/public/symbol",
        "https://fapi.xt.com/future/market/v1/public/q/tickers",
        "https://fapi.xt.com/future/market/v1/public/symbol/list",
    ],
    "kcex": [
        "https://api.kcex.com/api/v1/exchange/market/ticker",
        "https://api.kcex.com/open/api/v2/market/ticker",
        "https://www.kcex.com/api/platform/spot/market/symbols",
        "https://api.kcex.com/api/v1/contract/ticker",
    ],
}

PRIORITY = tuple(ENDPOINTS)          # همان ترتیبی که حمید گفت

# BASE + جداکنندهٔ اختیاری + USDT، در مرز کلمه. `_PERP`/`:USDT` هم پوشش دارد.
_SYM = re.compile(r'"([A-Z0-9]{2,15})[-_/]?USDT(?:[-_](?:PERP|SWAP))?"')


def _fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def harvest(text):
    """هر نماد USDTـدارِ داخل بدنهٔ خام، نرمال‌شده به `XXXUSDT`.

    خالص و تست‌پذیر — بدون شبکه."""
    return {m.group(1) + "USDT" for m in _SYM.finditer(text or "")}


def _load_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return {}


def _save_cache(j):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(j, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    except Exception:                                # noqa: BLE001
        pass                                         # کش نشد؟ اسکن ادامه دارد


def listings(force=False, fetch=None):
    """{venue: {"symbols": [...], "at": ms, "url": str, "error": str}}.

    `fetch` برای تست تزریق می‌شود. کش TTLـدار؛ صرافیِ نیامده کشِ قبلی‌اش را
    نگه می‌دارد (فهرست کهنه از هیچ بهتر است — لیست‌شدن‌ها روزانه عوض می‌شوند)
    و دلیل نیامدنش هم ثبت می‌ماند."""
    get = fetch or _fetch
    cache = _load_cache()
    now = int(time.time() * 1000)
    out = {}
    for venue, urls in ENDPOINTS.items():
        old = cache.get(venue) or {}
        fresh = old.get("symbols") and (now - (old.get("at") or 0)) < TTL_H * 3600_000
        if fresh and not force:
            out[venue] = old
            continue
        got, err = None, None
        for u in urls:
            try:
                syms = harvest(get(u))
            except Exception as e:                   # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
                continue
            if len(syms) >= MIN_SYMBOLS:
                got = {"symbols": sorted(syms), "at": now, "url": u}
                break
            err = f"فقط {len(syms)} نماد از {u} — پاسخ معتبر نیست"
        if got:
            out[venue] = got
        elif old.get("symbols"):
            out[venue] = {**old, "error": err, "stale": True}
        else:
            out[venue] = {"symbols": [], "at": now, "error": err}
    _save_cache(out)
    return out


def index(ls=None):
    """{SYMBOL: [venue, ...]} — کدام نماد روی کدام صرافی هدف هست."""
    ls = ls if ls is not None else listings()
    idx = {}
    for venue in PRIORITY:
        for s in (ls.get(venue) or {}).get("symbols") or []:
            idx.setdefault(s, []).append(venue)
    return idx


def prioritize(symbols, idx=None, keep_all=True):
    """ترتیب را عوض می‌کند، نه عضویت را.

    نمادهای موجود روی صرافی‌های هدف جلو می‌آیند — با حفظ ترتیب حجمیِ درون هر
    گروه، چون رتبهٔ حجم همچنان بهترین معیار نقدشوندگی است. بقیه پشت سرشان
    می‌مانند (`keep_all=True`) تا تحقیق و لید-لگ کور نشود؛ فقط دیرتر دیده
    می‌شوند. اگر هیچ صرافی جواب نداده باشد، ورودی بی‌تغییر برمی‌گردد.

    برگشتی: (symbols_ordered, note) — note همان چیزی است که در گزارش می‌آید."""
    idx = idx if idx is not None else index()
    if not idx:
        return list(symbols), "صرافی‌های هدف جواب ندادند — ترتیب حجمی دست‌نخورده"
    on, off = [], []
    for s in symbols:
        (on if idx.get(s) else off).append(s)
    ordered = on + off if keep_all else on
    return ordered, (f"اولویت صرافی: {len(on)} از {len(symbols)} نماد روی "
                     f"{'/'.join(PRIORITY)} قابل معامله است — جلو افتادند")


def where(sym, idx=None):
    """رشتهٔ کوتاه برای کپشن سیگنال: «بیت‌یونیکس · XT» یا رشتهٔ خالی."""
    idx = idx if idx is not None else index()
    fa = {"bitunix": "بیت‌یونیکس", "xt": "XT", "kcex": "KCEX"}
    return " · ".join(fa[v] for v in (idx.get(sym) or []) if v in fa)


if __name__ == "__main__":
    ls = listings(force=True)
    for v, d in ls.items():
        n = len(d.get("symbols") or [])
        print(f"{v:9s} {n:5d} نماد  {d.get('url') or ''}  {d.get('error') or ''}")
    idx = index(ls)
    print(f"\nمجموع نمادهای یکتا روی صرافی‌های هدف: {len(idx)}")
    for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        print(f"  {s}: {where(s, idx) or '—'}")
