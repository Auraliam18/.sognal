#!/usr/bin/env python3
"""آیا هر منبع بیرونی سالم است؟ — یک جدول، بدون حدس.

Hamid asked for every outside source the agent can draw on to be checked. The
list is deliberately wider than the exchanges: candles say what price did, and
the rest of this says why, or whether today is a day to be looking at all.

Each entry is asked a real question and judged on the answer, not on the status
code. An endpoint returning 200 with an empty list is down as far as this
pipeline is concerned, and several of them do exactly that when rate-limited.

It has to run somewhere with network. The development container reaches nothing
but GitHub, so this is a workflow step, and the result is written to
brain/health.json so the panel and the rooms can see it without re-asking.

    python3 -m hamid.health
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import research                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUT = ROOT / "brain" / "health.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; hamid-signal-health)"}
TIMEOUT = 20


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _json(url, headers=None):
    return json.loads(_get(url, headers))


# ── each check answers: is this usable right now? ──────────────────────────

def c_exchanges():
    """The ten venues behind the Python side, each asked for real candles."""
    from sources import VENUES, _json as vjson, sane
    ok, bad = [], []
    for v in VENUES:
        try:
            rows = v["parse"](vjson(v["url"]("BTCUSDT", "15m", 100)))[-100:]
            (ok if sane(rows, 100) else bad).append(v["id"])
        except Exception:                            # noqa: BLE001 - down is the answer
            bad.append(v["id"])
    return len(ok) >= 3, f"{len(ok)} از {len(VENUES)} سالم: {', '.join(ok[:6])}" + \
                         (f" | خراب: {', '.join(bad)}" if bad else "")


def c_coingecko():
    j = _json("https://api.coingecko.com/api/v3/global")["data"]
    btc = j["market_cap_percentage"].get("btc")
    return bool(btc), f"دامیننس بیت {round(btc, 2)}٪، تتر {round(j['market_cap_percentage'].get('usdt', 0), 3)}٪"


def c_coingecko_markets():
    rows = research.coingecko_movers(10)
    return len(rows) >= 5, f"{len(rows)} ارز با بیشترین تغییر ۲۴ ساعته"


def c_fear_greed():
    d = research.fear_greed()
    return True, f"{d['value']} — {d['label']}"


def c_coinmarketcap():
    """Needs a key Hamid has not supplied. Reported rather than skipped, so the
    gap is visible instead of being quietly worked around."""
    import os
    if not os.environ.get("CMC_API_KEY"):
        return None, "کلید ندارد — CoinMarketCap بدون کلید کار نمی‌کند (CoinGecko جایش را می‌گیرد)"
    j = _json("https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest",
              {"X-CMC_PRO_API_KEY": os.environ["CMC_API_KEY"]})
    return True, f"دامیننس بیت {j['data']['btc_dominance']:.2f}٪"


def c_calendar():
    """تقویم اقتصادی — the free ForexFactory weekly JSON.

    Hamid asked for this specifically for quiet days: when the tape is doing
    nothing, what moves it next is a number on a calendar.
    """
    j = _json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
    high = [e for e in j if (e.get("impact") or "").lower() == "high"]
    return len(j) > 0, f"{len(j)} رویداد این هفته، {len(high)} تای مهم"


def c_news():
    """Free RSS, no key. Enough to notice a headline the candles have not
    priced in yet."""
    raw = _get("https://www.coindesk.com/arc/outboundfeeds/rss/").decode("utf8", "replace")
    n = raw.count("<item>")
    return n > 0, f"{n} خبر در فید کوین‌دسک"


def c_funding():
    """Funding and open interest — what the crowd is positioned for.

    This is the measurable substitute for "what are other traders doing", which
    is the thing Hamid has asked about and which no TradingView connector here
    can answer.
    """
    j = _json("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
    rate = float(j["data"][0]["fundingRate"]) * 100
    side = "لانگ‌ها پول می‌دهند" if rate > 0 else "شورت‌ها پول می‌دهند"
    return True, f"فاندینگ بیت {rate:.4f}٪ — {side}"


def c_bitunix():
    """The venue Hamid actually has an account on."""
    j = _json("https://fapi.bitunix.com/api/v1/futures/market/kline"
              "?symbol=BTCUSDT&interval=15m&limit=10")
    rows = j.get("data") or []
    return len(rows) >= 5, f"{len(rows)} کندل فیوچرز"


def c_research_keys():
    b = research.budget_report()
    have = [x["provider"] for x in b if x["key"]]
    miss = [x["provider"] for x in b if not x["key"]]
    detail = ""
    if have:
        detail += "کلید دارد: " + ", ".join(have)
    if miss:
        detail += (" | " if detail else "") + "کلید ندارد: " + ", ".join(miss)
    return bool(have), detail or "هیچ کلیدی تنظیم نشده"


def c_tavily_live():
    try:
        r = research.search("bitcoin price analysis", max_results=2)
    except research.Refused as e:
        return None, str(e)
    return bool(r["results"]), f"{len(r['results'])} نتیجه برگشت"


def c_firecrawl_live():
    try:
        r = research.scrape("https://example.com")
    except research.Refused as e:
        return None, str(e)
    return bool(r["markdown"]), f"{len(r['markdown'])} کاراکتر خوانده شد"


def c_context7_live():
    try:
        r = research.docs("/pandas-dev/pandas", topic="dataframe", tokens=500)
    except research.Refused as e:
        return None, str(e)
    return bool(r["text"]), f"{len(r['text'])} کاراکتر مستندات"


CHECKS = [
    ("صرافی‌ها (کندل)", c_exchanges),
    ("بیت‌یونیکس فیوچرز", c_bitunix),
    ("کوین‌گکو — دامیننس", c_coingecko),
    ("کوین‌گکو — بیشترین تغییر", c_coingecko_markets),
    ("کوین‌مارکت‌کپ", c_coinmarketcap),
    ("شاخص ترس و طمع", c_fear_greed),
    ("تقویم اقتصادی", c_calendar),
    ("اخبار", c_news),
    ("فاندینگ / پوزیشن بازار", c_funding),
    ("کلیدهای تحقیق", c_research_keys),
    ("Tavily (تماس واقعی)", c_tavily_live),
    ("Firecrawl (تماس واقعی)", c_firecrawl_live),
    ("Context7 (تماس واقعی)", c_context7_live),
]


def main():
    print("\nسلامت منابع بیرونی\n" + "═" * 78)
    results, down = [], 0
    for name, fn in CHECKS:
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as e:                       # noqa: BLE001 - the failure is the result
            ok, detail = False, f"{type(e).__name__}: {str(e)[:90]}"
        ms = int((time.time() - t0) * 1000)
        mark = "✓" if ok else ("—" if ok is None else "✗")
        if ok is False:
            down += 1
        print(f"  {mark}  {name:<26} {ms:>5}ms  {detail}")
        results.append({"name": name, "ok": ok, "ms": ms, "detail": detail})

    print("═" * 78)
    print(f"{sum(1 for r in results if r['ok'] is True)} سالم، "
          f"{down} خراب، "
          f"{sum(1 for r in results if r['ok'] is None)} در انتظار کلید\n")

    print("سهمیهٔ ماهانه")
    for b in research.budget_report():
        print(f"  {b['provider']:<11} امروز {b['today_left']:>4} | ماه {b['month_left']:>5} از {b['monthly']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "results": results,
        "budget": research.budget_report(),
    }, ensure_ascii=False, indent=1))
    print(f"\nنوشته شد در brain/health.json")
    # A source being down is information, not a failed job. Only a total outage
    # of the candle venues stops the pipeline, and c_exchanges reports that.
    return 0


if __name__ == "__main__":
    sys.exit(main())
