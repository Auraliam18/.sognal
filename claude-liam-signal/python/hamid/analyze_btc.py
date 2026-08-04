#!/usr/bin/env python3
"""تحلیل کامل بیت‌کوین با روش خود حمید — همان ترتیبی که خودش کار می‌کند.

    ۱. ۴ ساعته: سقف/کف معتبر + روند
    ۲. ۱ ساعته: کانال + جایگاه قیمت + اردر بلاک و FVG
    ۳. ۱۵ دقیقه: روند + ستاپ
    و قبل از همه: دامیننس تتر و بیت، ترس و طمع، فاندینگ، تقویم، اخبار

خروجی JSON کامل در brain/analysis-btc.json تا از هر جا خواندنی باشد.

    python3 -m hamid.analyze_btc
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                                # noqa: E402
from hamid import intel                                       # noqa: E402
from hamid.cycle import resample                              # noqa: E402
from hamid.stack import read                                  # noqa: E402
from hamid.structure import atr, channel, levels, reentry, trend  # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "brain" / "analysis-btc.json"


def candles(sym, tf, n):
    rows = sources.klines(sym, tf, n)
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def main():
    out = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

    # کندل‌ها: ۱ ساعته (که ۴ ساعته از آن ساخته می‌شود) و ۱۵ دقیقه
    c1h = candles("BTCUSDT", "1h", 1000)
    c15 = candles("BTCUSDT", "15m", 800)
    c4h = resample(c1h, 4)
    price = c15[-1]["c"]
    out["price"] = price
    out["source"] = sources.used()["klines"]

    # ── ۴ ساعته: روند و سطوح معتبر ──────────────────────────────────────────
    t4 = trend(c4h)
    lv4 = levels(c4h)
    a4 = atr(c4h)
    out["h4"] = {
        "trend": t4,
        "atr": round(a4, 1),
        "levels": [{"price": round(l.price, 1), "kind": l.kind,
                    "touches": l.touches, "reactions": l.reactions,
                    "flipped": l.flipped,
                    "dist_pct": round((l.price / price - 1) * 100, 2)}
                   for l in lv4],
    }

    # ── ۱ ساعته: کانال، جایگاه، اردر بلاک ──────────────────────────────────
    ch = channel(c1h)
    re1 = reentry(c1h, ch) if ch else None
    t1 = trend(c1h)
    lv1 = levels(c1h)
    out["h1"] = {
        "trend": t1,
        "channel": None if not ch else {
            "position": round(ch.position, 3),
            "slope": ch.slope,
            "width_pct": round(ch.width / price * 100, 2),
            "mid": round(ch.mid(len(c1h) - 1), 1),
            "upper_now": round(ch.at(len(c1h) - 1)[0], 1),
            "lower_now": round(ch.at(len(c1h) - 1)[1], 1),
            "reentry": re1,
        },
        "levels": [{"price": round(l.price, 1), "kind": l.kind,
                    "reactions": l.reactions,
                    "dist_pct": round((l.price / price - 1) * 100, 2)}
                   for l in lv1],
    }

    # اردر بلاک‌ها و FVG از خوانش کامل استک
    r = read("BTCUSDT", c4h, c1h, c15)
    out["blocks"] = r.blocks
    out["fvgs"] = r.fvgs
    out["m15_trend"] = r.trend_15m
    out["setup"] = r.setup
    out["notes"] = r.notes

    # ── دامیننس، ترس، فاندینگ، تقویم، اخبار ────────────────────────────────
    world = intel.gather(quiet=True)
    out["world"] = {k: world.get(k) for k in
                    ("verdict", "fear_greed", "dominance", "funding",
                     "open_interest", "calendar", "news", "trending")}

    # ── حرکت اخیر، برای زمینه ───────────────────────────────────────────────
    def chg(cd, bars):
        if len(cd) <= bars:
            return None
        return round((cd[-1]["c"] / cd[-1 - bars]["c"] - 1) * 100, 2)
    out["change"] = {"24h": chg(c1h, 24), "7d": chg(c1h, 168),
                     "30d": chg(c4h, 180) if len(c4h) > 180 else chg(c1h, len(c1h) - 2)}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
