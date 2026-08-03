#!/usr/bin/env python3
"""سه API بیرونی، با سهمیه‌بندی ماهانه که تمام نشود.

Hamid supplied keys for Tavily, Firecrawl and Context7 and asked for the free
tiers to be divided so they last the whole month. The interesting part of that
request is not the HTTP; it is the budget. A free tier spent in the first three
days is worse than no tier at all, because the pipeline will have been built
assuming it is there.

So every call goes through a ledger:

  · Each provider has a monthly allowance and a **daily** slice of it.
  · Unspent days roll forward, spent days do not roll back.
  · A call that would exceed today's slice is refused, and says how long until
    the next slice — it does not silently do nothing, and it does not borrow
    from tomorrow.
  · The ledger lives in brain/research/usage.json, so it survives the runner
    being torn down between jobs. A counter held in memory would reset on every
    scheduled run and enforce nothing at all.

**Keys are never stored in this repository.** They come from the environment:
TAVILY_API_KEY, FIRECRAWL_API_KEY, CONTEXT7_API_KEY. Anything committed to a
GitHub repository should be treated as public — these get scanned and abused
within hours — so they belong in repository Secrets and nowhere else. Without a
key the provider is skipped with a plain message rather than failing the run.
"""
import calendar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEDGER = ROOT / "brain" / "research" / "usage.json"

# Free-tier allowances, deliberately set a little under the published figures.
# A budget that exactly matches the limit hits the limit; the margin is what
# stops the last day of the month being the one that fails.
PROVIDERS = {
    "tavily": {
        "env": "TAVILY_API_KEY",
        "monthly": 900,           # free tier is 1000 credits
        "label": "Tavily — جستجوی وب",
    },
    "firecrawl": {
        "env": "FIRECRAWL_API_KEY",
        "monthly": 450,           # free tier is 500 credits
        "label": "Firecrawl — خواندن کامل صفحه",
    },
    "context7": {
        "env": "CONTEXT7_API_KEY",
        "monthly": 1500,          # generous but rate-limited; kept conservative
        "label": "Context7 — مستندات کتابخانه‌ها",
    },
}

UA = {"User-Agent": "hamid-signal-research"}
TIMEOUT = 30


# ── the ledger ─────────────────────────────────────────────────────────────

def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _days_in_month():
    now = datetime.now(timezone.utc)
    return calendar.monthrange(now.year, now.month)[1]


def _load():
    try:
        j = json.loads(LEDGER.read_text())
    except Exception:                                # noqa: BLE001 - a missing or torn ledger is a fresh one
        j = {}
    if j.get("month") != _month():
        j = {"month": _month(), "spent": {}, "daily": {}}
    j.setdefault("spent", {})
    j.setdefault("daily", {})
    return j


def _save(j):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(j, ensure_ascii=False, indent=1))


def allowance(provider):
    """Today's slice, including whatever earlier days did not spend.

    Rolling unused budget forward is the difference between a quota that is
    usable and one that is theoretical: most days need a handful of calls and
    one day needs fifty, and a flat daily cap makes that day impossible while
    leaving the month unspent.
    """
    cfg = PROVIDERS[provider]
    j = _load()
    now = datetime.now(timezone.utc)
    days = _days_in_month()
    per_day = cfg["monthly"] / days
    elapsed = now.day                                # today included
    earned = per_day * elapsed
    spent = j["spent"].get(provider, 0)
    return max(0, int(earned - spent)), int(cfg["monthly"] - spent)


def _charge(provider, n=1):
    j = _load()
    j["spent"][provider] = j["spent"].get(provider, 0) + n
    d = j["daily"].setdefault(_today(), {})
    d[provider] = d.get(provider, 0) + n
    _save(j)


def budget_report():
    """What is left, per provider — printed by the health check and the cycle."""
    out = []
    for pid, cfg in PROVIDERS.items():
        today, month = allowance(pid)
        has_key = bool(os.environ.get(cfg["env"]))
        out.append({
            "provider": pid, "label": cfg["label"], "key": has_key,
            "today_left": today, "month_left": month, "monthly": cfg["monthly"],
        })
    return out


# ── calls ──────────────────────────────────────────────────────────────────

class Refused(Exception):
    """Raised instead of spending budget that is not there, or a key that is
    not set. Callers are expected to carry on without the answer."""


def _key(provider):
    k = os.environ.get(PROVIDERS[provider]["env"])
    if not k:
        raise Refused(f"{provider}: کلید تنظیم نشده "
                      f"({PROVIDERS[provider]['env']} را به Secrets اضافه کن)")
    return k


def _spend_or_refuse(provider, cost):
    today, month = allowance(provider)
    if month < cost:
        raise Refused(f"{provider}: سهمیهٔ ماه تمام شده")
    if today < cost:
        raise Refused(f"{provider}: سهمیهٔ امروز تمام شده — فردا {int(PROVIDERS[provider]['monthly'] / _days_in_month())} تای دیگر آزاد می‌شود")


def _post(url, payload, headers, timeout=TIMEOUT):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={**UA, "Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def search(query, depth="basic", max_results=5):
    """Tavily. One credit basic, two advanced — so basic is the default.

    Used for the things candles cannot say: an exchange listing, a token
    unlock, whether a chain halted. Not for prices; prices come from the venues.
    """
    cost = 1 if depth == "basic" else 2
    _spend_or_refuse("tavily", cost)
    k = _key("tavily")
    j = _post("https://api.tavily.com/search",
              {"api_key": k, "query": query, "search_depth": depth,
               "max_results": max_results, "include_answer": True},
              {})
    _charge("tavily", cost)
    return {
        "answer": j.get("answer"),
        "results": [{"title": r.get("title"), "url": r.get("url"),
                     "content": (r.get("content") or "")[:600]}
                    for r in j.get("results", [])],
    }


def scrape(url, formats=("markdown",)):
    """Firecrawl. One credit a page. Reserved for pages worth reading in full —
    an economic calendar, a listing announcement — rather than for browsing."""
    _spend_or_refuse("firecrawl", 1)
    k = _key("firecrawl")
    j = _post("https://api.firecrawl.dev/v1/scrape",
              {"url": url, "formats": list(formats), "onlyMainContent": True},
              {"Authorization": f"Bearer {k}"})
    _charge("firecrawl", 1)
    data = j.get("data", j)
    return {"url": url, "markdown": (data.get("markdown") or "")[:20000],
            "title": (data.get("metadata") or {}).get("title")}


def docs(library, topic=None, tokens=4000):
    """Context7. Library documentation, for when the agent needs to use a tool
    correctly rather than guess at its API."""
    _spend_or_refuse("context7", 1)
    k = _key("context7")
    q = urllib.parse.urlencode({k2: v for k2, v in
                                (("topic", topic), ("tokens", tokens)) if v})
    url = f"https://context7.com/api/v1/{urllib.parse.quote(library)}?{q}"
    req = urllib.request.Request(url, headers={**UA, "Authorization": f"Bearer {k}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        text = r.read().decode("utf8", "replace")
    _charge("context7", 1)
    return {"library": library, "topic": topic, "text": text[:20000]}


# ── free sources, no budget needed ─────────────────────────────────────────
# These cost nothing and so are asked first. A paid call that a free endpoint
# could have answered is the fastest way to spend a month's quota in a day.

def fear_greed():
    req = urllib.request.Request("https://api.alternative.me/fng/?limit=2", headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        j = json.load(r)
    d = j["data"][0]
    return {"value": int(d["value"]), "label": d["value_classification"]}


def global_market():
    req = urllib.request.Request("https://api.coingecko.com/api/v3/global", headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        j = json.load(r)["data"]
    return {
        "btc_dominance": round(j["market_cap_percentage"].get("btc", 0), 2),
        "eth_dominance": round(j["market_cap_percentage"].get("eth", 0), 2),
        "usdt_dominance": round(j["market_cap_percentage"].get("usdt", 0), 3),
        "total_mcap_usd": j["total_market_cap"].get("usd"),
        "mcap_change_24h": round(j.get("market_cap_change_percentage_24h_usd", 0), 2),
    }


def coingecko_movers(n=25):
    """Biggest 24h movers among coins with real volume — the weekend shortlist."""
    url = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
           "&order=volume_desc&per_page=100&page=1&price_change_percentage=24h,7d")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        rows = json.load(r)
    out = []
    for c in rows:
        ch = c.get("price_change_percentage_24h") or 0
        vol = c.get("total_volume") or 0
        mc = c.get("market_cap") or 0
        if mc <= 0 or vol <= 0:
            continue
        out.append({
            "symbol": (c.get("symbol") or "").upper(),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "change_24h": round(ch, 2),
            "change_7d": round(c.get("price_change_percentage_7d_in_currency") or 0, 2),
            "volume": vol, "mcap": mc,
            # volume against market cap says whether anyone is actually trading
            # it, which is the difference between a mover and a print
            "turnover": round(vol / mc, 3),
        })
    out.sort(key=lambda x: -abs(x["change_24h"]))
    return out[:n]


if __name__ == "__main__":
    print("\nسهمیهٔ ماهانه\n" + "─" * 62)
    for b in budget_report():
        key = "کلید دارد" if b["key"] else "کلید ندارد ✗"
        print(f"  {b['provider']:<11} {key:<14} امروز {b['today_left']:>4} "
              f"| ماه {b['month_left']:>5} از {b['monthly']}")
    print()
    for name, fn in (("fear_greed", fear_greed), ("global", global_market)):
        try:
            print(f"  ✓ {name}: {fn()}")
        except Exception as e:                       # noqa: BLE001 - report and continue
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
