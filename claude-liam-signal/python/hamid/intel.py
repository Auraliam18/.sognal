#!/usr/bin/env python3
"""اطلاعات جهانی، هر چرخه، داخل اتاق‌ها.

حمید پرسید: «مگه قرار نبود ایجنت به تمام اطلاعات جهانی دسترسی داشته باشد و هر
لحظه اطلاعاتش اپدیت شود و بهترین دیتاها را به اتاقها اضافه کنید؟»

درست پرسیده. تا حالا چرخه فقط کندل می‌خواند. دامیننس و شاخص ترس فقط گاهی، و
تقویم اقتصادی فقط در روزهای آرام. سه API هم وصل بودند ولی هیچ‌کجا صدا زده
نمی‌شدند. این ماژول آن شکاف را پر می‌کند.

اصل کار: **اول رایگان، بعد پولی.** هر چیزی که یک اندپوینت رایگان می‌تواند
جواب دهد، از سهمیهٔ ماهانه خرج نمی‌کند. سریع‌ترین راه تمام کردن سهمیهٔ یک ماه
در یک روز، پرسیدن سؤالی از Tavily است که CoinGecko مجانی جوابش را می‌داد.

چیزی که این ماژول عمداً نمی‌کند: تظاهر به داشتن داده‌ای که ندارد. تحلیل هولدر
زنجیره‌ای، دفتر سفارش عمیق، و جریان پول نهنگ‌ها با این کلیدها در دسترس نیست، و
اسم دیگری روی گردش معاملاتی گذاشتن بدتر از نداشتنش است.

    python3 -m hamid.intel            # یک بار جمع‌آوری
    python3 -m hamid.intel --deep     # با جستجوی وب (سهمیه خرج می‌کند)
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import brain                                                  # noqa: E402
from hamid import research                                    # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "brain" / "intel"
UA = {"User-Agent": "Mozilla/5.0 (compatible; hamid-signal-intel)"}
TIMEOUT = 15


def _json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _text(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf8", "replace")


# ── منابع رایگان ───────────────────────────────────────────────────────────

def fear_greed():
    d = research.fear_greed()
    return {"value": d["value"], "label": d["label"],
            "note": "زیر ۳۰ ترس، بالای ۷۰ طمع"}


def dominance():
    g = research.global_market()
    return {"btc": g["btc_dominance"], "eth": g["eth_dominance"],
            "usdt": g["usdt_dominance"], "mcap_change_24h": g["mcap_change_24h"]}


def funding():
    """فاندینگ چند ارز اصلی — می‌گوید جمعیت کدام سمت سنگین است.

    این نزدیک‌ترین چیزی است که به «بقیهٔ تریدرها چه می‌کنند» داریم و قابل
    اندازه‌گیری هم هست، برخلاف خواندن تحلیل دیگران در تریدینگ‌ویو.
    """
    out = {}
    for sym in ("BTC", "ETH", "SOL"):
        try:
            j = _json(f"https://www.okx.com/api/v5/public/funding-rate"
                      f"?instId={sym}-USDT-SWAP")
            out[sym] = round(float(j["data"][0]["fundingRate"]) * 100, 5)
        except Exception:                            # noqa: BLE001 - یکی نبود، بقیه هستند
            continue
    if not out:
        # هیچ ارزی جواب نداد. برگرداندن دیکشنری خالی یعنی این منبع «موفق»
        # شمرده می‌شود و در گزارش به‌عنوان دادهٔ موجود می‌آید، در حالی که هیچ
        # چیزی ندارد — همان‌جور خرابی ساکتی که این پروژه بارها ازش ضربه خورده.
        raise RuntimeError("هیچ نرخ فاندینگی نیامد")
    avg = sum(out.values()) / len(out)
    out["verdict"] = ("لانگ‌ها پول می‌دهند — جمعیت سمت خرید سنگین است"
                      if avg > 0.005 else
                      "شورت‌ها پول می‌دهند — جمعیت سمت فروش سنگین است"
                      if avg < -0.005 else "فاندینگ خنثی")
    return out


def open_interest():
    """تغییر پوزیشن باز بیت‌کوین — پول تازه می‌آید یا بسته می‌شود."""
    j = _json("https://www.okx.com/api/v5/public/open-interest"
              "?instType=SWAP&instId=BTC-USDT-SWAP")
    d = j["data"][0]
    return {"btc_oi": float(d.get("oiCcy") or 0), "at": d.get("ts")}


def _tv_calendar():
    """تقویم رویدادهای تریدینگ‌ویو — پشتیبان تقویم اصلی (خواستهٔ حمید: سرچ
    مداوم در تریدینگ‌ویو و ایونت‌ها). فقط رویدادهای اهمیت بالا."""
    now = datetime.now(timezone.utc)
    frm = now.strftime("%Y-%m-%dT00:00:00.000Z")
    to = (now + timedelta(days=3)).strftime("%Y-%m-%dT00:00:00.000Z")
    j = _json("https://economic-calendar.tradingview.com/events"
              f"?from={frm}&to={to}&minImportance=1")
    rows = j.get("result") if isinstance(j, dict) else j
    return [{"title": e.get("title"), "country": e.get("country"),
             "date": e.get("date"), "impact": "High"}
            for e in (rows or []) if e.get("title")]


def calendar():
    """تقویم اقتصادی — در روزهای آرام مهم‌ترین چیزی است که بازار را تکان می‌دهد.
    منبع اصلی faireconomy؛ اگر نداد، تقویم تریدینگ‌ویو جایگزین می‌شود."""
    try:
        j = _json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
        high = [e for e in j if (e.get("impact") or "").lower() == "high"]
    except Exception:                                # noqa: BLE001 - پشتیبان TV
        high = _tv_calendar()
    now = datetime.now(timezone.utc)
    soon = []
    for e in high:
        try:
            d = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        except Exception:                            # noqa: BLE001
            continue
        hrs = (d - now).total_seconds() / 3600
        if -2 <= hrs <= 48:
            soon.append({"title": e.get("title"), "country": e.get("country"),
                         "in_hours": round(hrs, 1)})
    soon.sort(key=lambda x: x["in_hours"])
    return {"high_this_week": len(high), "next_48h": soon[:8]}


NEWS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
]

# واژه‌هایی که تجربه نشان داده قیمت را تکان می‌دهند. فهرست عمداً کوتاه است:
# فهرست بلند همه‌چیز را مهم نشان می‌دهد و آن وقت هیچ‌چیز مهم نیست.
HOT = ("hack", "exploit", "sec ", "lawsuit", "etf", "halving", "unlock",
       "delist", "listing", "fed", "rate cut", "cpi", "liquidat")


def news():
    items = []
    def one(pair):
        name, url = pair
        try:
            raw = _text(url)
        except Exception:                            # noqa: BLE001
            return []
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw)[1:14]
        return [{"source": name, "title": t.strip()} for t in titles if t.strip()]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in pool.map(one, NEWS_FEEDS):
            items += r
    # تریدینگ‌ویو هم — خواستهٔ حمید. JSON عمومی؛ اگر شکل عوض شد بی‌صدا رد
    # می‌شود و RSSها سر جایشان هستند.
    try:
        j = _json("https://news-headlines.tradingview.com/v2/headlines"
                  "?category=crypto&lang=en")
        rows = j.get("items") if isinstance(j, dict) else j
        for it in (rows or [])[:12]:
            t = it.get("title") or it.get("headline")
            if t:
                items.append({"source": "TradingView", "title": str(t).strip()})
    except Exception:                                # noqa: BLE001
        pass
    hot = [i for i in items if any(k in i["title"].lower() for k in HOT)]
    return {"count": len(items), "hot": hot[:8], "headlines": items[:12]}


def trending():
    """آنچه مردم همین الان جستجو می‌کنند — پیش‌درآمد پامپ، نه تأییدش."""
    j = _json("https://api.coingecko.com/api/v3/search/trending")
    return [{"symbol": c["item"]["symbol"].upper(), "name": c["item"]["name"],
             "rank": c["item"].get("market_cap_rank")}
            for c in (j.get("coins") or [])[:10]]


# ── منبع پولی، فقط وقتی رایگان جواب نمی‌دهد ────────────────────────────────

def deep_search(topics):
    """جستجوی وب برای چیزهایی که کندل و RSS نمی‌گویند.

    فقط با --deep، و از سهمیه‌ای که research.py نگه می‌دارد. اگر سهمیهٔ امروز
    تمام باشد، صریح رد می‌کند و چرخه بدون آن ادامه می‌دهد.
    """
    out = []
    for q in topics:
        try:
            r = research.search(q, max_results=3)
            out.append({"query": q, "answer": r.get("answer"),
                        "sources": [x["url"] for x in r["results"]]})
        except research.Refused as e:
            out.append({"query": q, "refused": str(e)})
            break                                    # سهمیه تمام است، بقیه هم رد می‌شوند
        except Exception as e:                       # noqa: BLE001
            out.append({"query": q, "error": type(e).__name__})
    return out


# ── جمع‌آوری ───────────────────────────────────────────────────────────────

SOURCES = [
    ("fear_greed", fear_greed, "market"),
    ("dominance", dominance, "market"),
    ("funding", funding, "trade"),
    ("open_interest", open_interest, "trade"),
    ("calendar", calendar, "intel"),
    ("news", news, "intel"),
    ("trending", trending, "radar"),
]


def gather(deep=False, quiet=False):
    t0 = time.time()
    data, failed = {}, []

    def one(item):
        name, fn, _room = item
        try:
            return name, fn(), None
        except Exception as e:                       # noqa: BLE001 - یک منبع خراب کل جمع‌آوری نیست
            return name, None, f"{type(e).__name__}"

    with ThreadPoolExecutor(max_workers=7) as pool:
        for name, val, err in pool.map(one, SOURCES):
            if err:
                failed.append(f"{name}: {err}")
            else:
                data[name] = val

    # هر منبع به اتاق خودش می‌رود، نه همه در یک جا. اتاقی که همه‌چیز را
    # می‌گیرد، عملاً هیچ‌چیز را نمی‌گیرد.
    for name, _fn, room in SOURCES:
        if name in data:
            brain.room_log(room, f"{name}: {json.dumps(data[name], ensure_ascii=False)[:200]}",
                           "intel")

    if deep:
        topics = ["crypto market outlook today", "bitcoin news last 24 hours"]
        tr = data.get("trending") or []
        if tr:
            topics.append(f"{tr[0]['symbol']} crypto news")
        data["deep"] = deep_search(topics)
        brain.room_log("intel", f"جستجوی عمیق: {len(data['deep'])} موضوع", "intel")

    verdict = _verdict(data)
    data["verdict"] = verdict
    data["gathered"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data["failed"] = failed

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    brain.append(OUT / "history.jsonl",
                 {"t": int(time.time() * 1000), "verdict": verdict,
                  "fear": (data.get("fear_greed") or {}).get("value"),
                  "usdt_dom": (data.get("dominance") or {}).get("usdt"),
                  "hot_news": len((data.get("news") or {}).get("hot") or [])})
    brain.event("intel", verdict=verdict, sources=len(data) - 3, failed=len(failed))

    if not quiet:
        print(f"\nاطلاعات جهانی — {len(data)-3} منبع در {time.time()-t0:.1f} ثانیه")
        print("═" * 66)
        for k in ("fear_greed", "dominance", "funding", "open_interest"):
            if k in data:
                print(f"  {k:<15} {json.dumps(data[k], ensure_ascii=False)[:120]}")
        cal = data.get("calendar") or {}
        if cal.get("next_48h"):
            print(f"  {'تقویم':<15} {len(cal['next_48h'])} رویداد مهم تا ۴۸ ساعت آینده:")
            for e in cal["next_48h"][:3]:
                print(f"{'':<18}· {e['title']} ({e['country']}) — {e['in_hours']} ساعت دیگر")
        nw = data.get("news") or {}
        if nw.get("hot"):
            print(f"  {'خبر داغ':<15} {len(nw['hot'])} تیتر:")
            for h in nw["hot"][:3]:
                print(f"{'':<18}· {h['title'][:80]}")
        if failed:
            print(f"  {'نیامد':<15} {', '.join(failed)}")
        print("═" * 66)
        print(f"  {verdict}")
    return data


def _verdict(d):
    """یک جمله که بگوید امروز چه‌جور روزی است — از روی همان چیزی که جمع شد.

    عمداً محافظه‌کار: وقتی سیگنال‌ها با هم نمی‌خوانند، می‌گوید نمی‌خوانند، نه
    اینکه یکی را انتخاب کند.
    """
    bits = []
    fg = (d.get("fear_greed") or {}).get("value")
    dom = d.get("dominance") or {}
    cal = (d.get("calendar") or {}).get("next_48h") or []
    hot = (d.get("news") or {}).get("hot") or []

    if fg is not None:
        if fg < 25:
            bits.append("ترس شدید")
        elif fg > 75:
            bits.append("طمع شدید")
    if dom.get("usdt", 0) > 8.5:
        bits.append("دامیننس تتر بالا — پول کنار گود است")
    if dom.get("mcap_change_24h", 0) < -3:
        bits.append("بازار ۲۴ ساعته قرمز")
    elif dom.get("mcap_change_24h", 0) > 3:
        bits.append("بازار ۲۴ ساعته سبز")
    imminent = [e for e in cal if 0 <= e["in_hours"] <= 6]
    if imminent:
        bits.append(f"{len(imminent)} خبر اقتصادی مهم تا ۶ ساعت آینده — "
                    "نوسان غیرعادی محتمل است")
    if hot:
        bits.append(f"{len(hot)} تیتر حساس در اخبار")
    return " · ".join(bits) if bits else "هیچ سیگنال غیرعادی‌ای در داده‌های جهانی نیست"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", action="store_true", help="جستجوی وب هم بکن")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    gather(deep=a.deep, quiet=a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
