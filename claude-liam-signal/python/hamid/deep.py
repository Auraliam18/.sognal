"""تحلیل عمیق تک‌نماد — دستور حمید (۱۴ اوت).

«در تحلیل تک نماد هم باید تمام انجین‌ها و ایجنت‌ها همان مدل پایشی که روی
اسکن ۳۰ ثانیه‌ای انجام می‌دهند را با دقت بیشتر روی تحلیل تک‌نماد انجام دهند
و دیتاهای زنده بدهند و همه چیز در چارت نشان داده شود.»

تفاوت با اسکن: اسکن برای پوشش صدها ارز، عمق را قربانی می‌کند —
۳۰۰ کندل ۱س/۱۵د و فقط بخشی از انجین‌ها روی ستاپ‌های زنده. اینجا یک نماد
است، پس عمق کامل می‌شود:

  ۴س ۳۰۰ کندل (از ۱س ساخته می‌شود) · ۱س ۱۲۰۰ · ۱۵د ۸۰۰ · ۵د ۶۰۰

و **تمام** انجین‌ها اجرا می‌شوند، نه فقط آن‌هایی که ستاپ دارند:

  ساختار (روند/سطوح/کانال هر سه تایم) · اردر بلاک روش حمید ·
  ob_intel (ماشین ۱۱وضعیتی + بریکر + گرید مدرکی) روی ۴س/۱س/۱۵د ·
  نقدینگی (سقف/کف برابر) · نقشهٔ لیکویید · الگوهای کلاسیک ·
  ایندوسمنت · لید-لگ BTC→نماد · دامیننس ساختاری · فاندینگ/OI/ترس‌وطمع ·
  حافظه و آمار تاریخی همان نماد · بازجویی premortem

قانون صداقت پابرجاست: هیچ عددی ساخته نمی‌شود. انجینی که داده‌اش نبود
`null` با علت برمی‌گرداند، نه حدس. منبع هر سری کندل ثبت می‌شود.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                                # noqa: E402
from hamid.cycle import resample                              # noqa: E402
from hamid.stack import read                                  # noqa: E402
from hamid.structure import atr, channel, levels, reentry, trend  # noqa: E402

ROOT = HERE.parent.parent.parent
OUT_DIR = ROOT / "signals"

# عمق‌ها — بیشتر از اسکن، طبق قانون «۴س و ۱س حداقل ۲۰۰ کندل»
LIMIT_1H = 1200        # ۴س از این ساخته می‌شود → ۳۰۰ کندل ۴س
LIMIT_15M = 800
LIMIT_5M = 600


def candles(sym, tf, n):
    """کندل زنده. خطا بالا می‌رود — تحلیل روی دادهٔ ناقص ممنوع است."""
    rows = sources.klines(sym, tf, n)
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def _try(label, fn, box):
    """انجین را اجرا کن؛ اگر نشد، علتش را صادقانه ثبت کن — نه حدس."""
    try:
        return fn()
    except Exception as e:                           # noqa: BLE001 - یک انجین نباید بقیه را بکشد
        box[label] = f"{type(e).__name__}: {e}"
        return None


def _lv(l, price):
    return {"price": round(l.price, 8), "kind": l.kind, "touches": l.touches,
            "reactions": l.reactions, "flipped": l.flipped,
            "dist_pct": round((l.price / price - 1) * 100, 2)}


def _tf_map(cd, tf, price):
    """نقشهٔ ساختاری یک تایم‌فریم: روند، سطوح معتبر، کانال، ATR."""
    if len(cd) < 30:
        return {"bars": len(cd), "note": "کندل کافی نیست"}
    ch = channel(cd) if len(cd) >= 40 else None
    out = {
        "bars": len(cd),
        "trend": trend(cd),
        "atr": round(atr(cd), 8),
        "atr_pct": round(atr(cd) / price * 100, 2) if price else None,
        "levels": [_lv(l, price) for l in levels(cd)],
        "channel": None,
    }
    if ch:
        out["channel"] = {
            "position": round(ch.position, 3),
            "slope": ch.slope,
            "width_pct": round(ch.width / price * 100, 2) if price else None,
            "upper_now": round(ch.at(len(cd) - 1)[0], 8),
            "lower_now": round(ch.at(len(cd) - 1)[1], 8),
            "mid_now": round(ch.mid(len(cd) - 1), 8),
            "reentry": reentry(cd, ch),
        }
    return out


def analyze(sym, quiet=False):
    """کل استک روی یک نماد، با عمق کامل. دادهٔ زنده، بدون حدس."""
    sym = sym.upper().strip()
    if not sym.endswith("USDT"):
        sym = sym + "USDT"

    started = datetime.now(timezone.utc)
    errors = {}
    out = {
        "symbol": sym,
        "at": started.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "at_ms": int(started.timestamp() * 1000),
        "depth": {"h1_bars": LIMIT_1H, "m15_bars": LIMIT_15M, "m5_bars": LIMIT_5M},
    }

    # ── دادهٔ زنده ─────────────────────────────────────────────────────────
    c1h = candles(sym, "1h", LIMIT_1H)
    c15 = candles(sym, "15m", LIMIT_15M)
    c5 = _try("m5", lambda: candles(sym, "5m", LIMIT_5M), errors) or []
    c4h = resample(c1h, 4)
    price = c15[-1]["c"]
    out["price"] = price
    out["source"] = sources.used().get("klines")
    out["candle_age_min"] = round(
        (started.timestamp() * 1000 - c5[-1]["t"]) / 60000, 1) if c5 else None

    # ── همان موتور اسکن، با عمق بیشتر ──────────────────────────────────────
    # عمداً همان read() است که چرخهٔ ۳۰ثانیه‌ای می‌زند: «همان مدل پایشی».
    r = read(sym, c4h, c1h, c15)
    out["hamid_read"] = {
        "trend_4h": r.trend_4h, "trend_1h": r.trend_1h, "trend_15m": r.trend_15m,
        "position_1h": r.position_1h, "channel_note": r.channel_note,
        "levels_4h": r.levels_4h, "levels_1h": r.levels_1h,
        "blocks": r.blocks, "fvgs": r.fvgs, "notes": r.notes,
    }
    setup = r.setup
    out["setup"] = setup

    # ── ساختار کامل هر تایم‌فریم ───────────────────────────────────────────
    out["structure"] = {
        "h4": _tf_map(c4h, "4h", price),
        "h1": _tf_map(c1h, "1h", price),
        "m15": _tf_map(c15, "15m", price),
        "m5": _tf_map(c5, "5m", price) if c5 else {"note": "۵د در دسترس نبود"},
    }

    # ── هوش اردر بلاک: ماشین ۱۱وضعیتی روی هر سه تایم ───────────────────────
    def ob_all():
        from hamid import ob_intel
        res = {}
        for tf, cd in (("4h", c4h), ("1h", c1h), ("15m", c15)):
            if len(cd) < 60:
                continue
            boxes = ob_intel.analyze(cd, tf)
            res[tf] = [{
                "low": b["low"], "high": b["high"], "mid": b["mid"],
                "move": b["move"], "state": b["state"], "grade": b["grade"],
                "score": b.get("score"), "why": b.get("why"),
                "evidence": b.get("evidence"), "groups": b.get("groups"),
                "touches": b["touches"], "reactions": b["reactions"],
                "hunts": b["hunts"], "fresh": b["fresh"], "broken": b["broken"],
                "age": b["age"], "dist_atr": b["dist_atr"],
                "inside_now": b["inside_now"],
                "dist_pct": round((b["mid"] / price - 1) * 100, 2) if price else None,
            } for b in boxes]
        return res
    out["order_blocks"] = _try("ob_intel", ob_all, errors)

    # ── اردر بلاک روش حمید (شمارش واکنش/هانت) ──────────────────────────────
    def ob_hamid():
        from hamid import orderblocks
        res = {}
        for tf, cd in (("1h", c1h), ("15m", c15)):
            b_in, b_near = orderblocks.near(cd, tf=tf)
            res[tf] = {"inside": b_in, "near": b_near}
        return res
    out["ob_hamid"] = _try("orderblocks", ob_hamid, errors)

    # ── نقدینگی: سقف/کف برابر و استخر استاپ ────────────────────────────────
    direction = (setup or {}).get("dir")
    out["liquidity"] = _try("liquidity", lambda: __import__(
        "hamid.liquidity", fromlist=["read"]).read(c15, direction), errors)

    # ── نقشهٔ لیکویید اهرمی ────────────────────────────────────────────────
    def liq_map():
        from hamid import liqmap
        lm = liqmap.build(c1h)
        if not lm:
            return None
        return {"magnet": lm["magnet"], "above": lm["above"][:3],
                "below": lm["below"][:3], "note": liqmap.note(lm, direction)}
    out["liq_map"] = _try("liqmap", liq_map, errors)

    # ── الگوهای کلاسیک ─────────────────────────────────────────────────────
    def pats():
        from hamid import patterns
        found = patterns.detect(c15)
        return {"m15": found,
                "aligned": patterns.align(found, direction) if direction else None}
    out["patterns"] = _try("patterns", pats, errors)

    # ── ایندوسمنت / ONE-IDM (آزمایشی) ──────────────────────────────────────
    def ind():
        from hamid import inducement
        f = inducement.find(c15)
        if not f:
            return None
        return {k: getattr(f, k) for k in f.__dataclass_fields__} \
            if hasattr(f, "__dataclass_fields__") else f
    out["inducement"] = _try("inducement", ind, errors)

    # ── لید-لگ: واکنش این نماد به بیت‌کوین ─────────────────────────────────
    def leadlag():
        from hamid import lagcorr
        btc1h = candles("BTCUSDT", "1h", 400)
        mr = lagcorr.market_reaction(btc1h, c1h)
        return {"reaction": mr, "fa": lagcorr.reaction_fa(sym, mr) if mr else None}
    out["lead_lag"] = _try("lagcorr", leadlag, errors)

    # ── دامیننس ساختاری (دروازهٔ USDT.D) ───────────────────────────────────
    def dom():
        from hamid import dominance
        p = ROOT / "brain" / "dominance-series.json"
        pts = json.loads(p.read_text()).get("points", []) if p.exists() else []
        if not pts:
            return {"note": "سری دامیننس هنوز ذخیره نشده — INSUFFICIENT"}
        return dominance.structural(pts)
    out["dominance"] = _try("dominance", dom, errors)

    # ── مشتقات و بستر: فاندینگ، OI، ترس‌وطمع ───────────────────────────────
    def market_intel():
        from hamid import intel
        g = intel.gather(deep=False, quiet=True)
        base = sym[:-4]
        return {
            "fear_greed": g.get("fear_greed"),
            "dominance_level": g.get("dominance"),
            "funding_symbol": (g.get("funding") or {}).get(sym)
            or (g.get("funding") or {}).get(base),
            "oi_symbol": (g.get("open_interest") or {}).get(sym)
            or (g.get("open_interest") or {}).get(base),
        }
    out["intel"] = _try("intel", market_intel, errors)

    # ── حافظه و آمار تاریخی همین نماد ──────────────────────────────────────
    def mem():
        from hamid import memory
        res = {"lessons": memory.lessons(sym=sym, limit=6)}
        if direction:
            res["history"] = memory.history(sym, direction)
            res["consult"] = memory.consult(sym, direction,
                                            (setup or {}).get("strategy", "second"))
        return res
    out["memory"] = _try("memory", mem, errors)

    # ── بازجویی پیش از صدور (فقط اگر ستاپ هست) ─────────────────────────────
    if setup:
        def pm():
            from hamid import premortem
            return premortem.review(setup, c15)
        out["premortem"] = _try("premortem", pm, errors)
    else:
        out["premortem"] = None

    out["errors"] = errors
    out["engines_ok"] = sum(1 for k in ("order_blocks", "ob_hamid", "liquidity",
                                        "liq_map", "patterns", "lead_lag",
                                        "dominance", "intel", "memory")
                            if out.get(k) is not None)
    out["took_sec"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)

    if not quiet:
        print(f"{sym} @ {price} — {out['engines_ok']}/9 انجین، "
              f"{out['took_sec']}s، منبع {out['source']}")
        if errors:
            for k, v in errors.items():
                print(f"  ⚠ {k}: {v}")

    return out, {"c4h": c4h, "c1h": c1h, "c15": c15, "c5": c5}


def save(out):
    """خروجی برای پنل. فایل یکتای هر نماد — بدون تصادم با چرخه."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"deep-{out['symbol']}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    o, _ = analyze(sym)
    print("→", save(o))
