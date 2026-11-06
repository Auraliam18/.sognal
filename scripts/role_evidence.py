"""Check the published work of each role without executing trading or delivery code."""
import math
import re
from collections import Counter


def mapping(value):
    return value if isinstance(value, dict) else {}


def items(value):
    return value if isinstance(value, list) else []


def count(value):
    return type(value) is int and value >= 0


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def history_ok(frames):
    return all(count(mapping(frames).get(tf)) and frames[tf] >= floor
               for tf, floor in (("4h", 200), ("1h", 200), ("15m", 60)))


def positioned(row):
    levels = [row.get(k) for k in ("sl", "entry", "tp1", "tp2")]
    if not all(finite(v) and v > 0 for v in levels):
        return False
    stop, entry, first, second = levels
    return ((row.get("dir") == "LONG" and stop < entry < first < second)
            or (row.get("dir") == "SHORT" and stop > entry > first > second))


def delivery(rows):
    groups = Counter()
    trades = {}
    receipts = Counter()
    for raw in items(rows):
        row = mapping(raw)
        kind, mid, sid = (row.get(k) for k in ("kind", "tg_msg_id", "signal_id"))
        if kind not in ("watch_alert", "trade_signal"):
            groups["legacy_unverified"] += 1
            continue
        if type(mid) is not int or mid < 1 or not finite(row.get("at")) or row["at"] <= 0:
            groups["invalid"] += 1
            continue
        receipts[mid] += 1
        if kind == "watch_alert":
            groups["watch_receipts"] += 1
        elif isinstance(sid, str) and re.fullmatch(r"S-[0-9a-f]{20}", sid) and sid not in trades:
            trades[sid] = row["at"]
        else:
            groups["invalid"] += 1
    return {"watch_receipts": groups["watch_receipts"], "trade_receipts": len(trades),
            "last_trade_at": max(trades.values(), default=None), "legacy_unverified": groups["legacy_unverified"],
            "invalid": groups["invalid"], "reused_receipts": sum(n-1 for n in receipts.values())}


def inspect(role, raw, *, lessons, reconciliation, risk, portfolio):
    data = mapping(raw)
    stats, missing = {}, []
    source_clock = None

    def need(ok, field):
        if not ok:
            missing.append(field)

    if role == "E00":
        coverage = mapping(data.get("coverage"))
        selected = items(coverage.get("symbols"))
        history = mapping(mapping(data.get("market")).get("symbol_history"))
        eligible = {s for s, frames in history.items() if history_ok(frames)}
        skipped = items(coverage.get("missing_symbols"))
        stats.update(requested=coverage.get("requested"), eligible=len(eligible), skipped=sorted(set(selected)-eligible))
        need(bool(selected) and len(set(selected)) == len(selected) == coverage.get("requested")
             and set(selected) == set(history) and len(eligible) == data.get("reads")
             and set(skipped) == set(selected)-eligible, "تطبیق فهرست نمادها و تاریخچه")
        need(bool(selected) and len(eligible) == len(selected), "تاریخچهٔ کافی برای همهٔ نمادهای درخواستی")
    elif role == "E05":
        world = mapping(data.get("world"))
        dom = mapping(world.get("dominance"))
        stats.update(mode=data.get("mode"), btc_dom=dom.get("btc"), usdt_dom=dom.get("usdt"),
                     fear=mapping(world.get("fear_greed")).get("value"), headlines=mapping(world.get("news")).get("count"))
        need(bool(world.get("verdict")) and data.get("mode") in ("active", "quiet")
             and all(finite(dom.get(k)) and 0 < dom[k] < 100 for k in ("btc", "usdt"))
             and finite(stats["fear"]) and 0 <= stats["fear"] <= 100 and count(stats["headlines"])
             and isinstance(mapping(world.get("calendar")).get("next_48h"), list), "رژیم، دامیننس، خبر و تقویم")
    elif role in ("E07", "E08"):
        c = mapping(data.get("coverage"))
        stats.update(requested=c.get("requested"), completed=c.get("completed"), missing_frames=c.get("missing_frames"))
        observed = mapping(data.get("symbols"))
        verified = sum(all(tf in items(mapping(v).get("observed_frames")) for tf in ("15m","1h","4h"))
                       for v in observed.values())
        need(count(c.get("requested")) and c["requested"] > 0 and verified == c.get("completed") == c["requested"]
             and c.get("complete") is True and not c.get("missing_frames"), "پوشش کندل در سه تایم‌فریم")
    elif role == "E10":
        world = mapping(data.get("world"))
        oi = mapping(world.get("open_interest"))
        stats.update(funding=mapping(world.get("funding")), btc_oi=oi.get("btc_oi"), oi_at=oi.get("at"),
                     liquidity_maps=sum(bool(mapping(x).get("liq_map")) for x in items(data.get("setups"))))
        need(all(finite(stats["funding"].get(k)) for k in ("BTC","ETH","SOL")), "فاندینگ")
        need(finite(oi.get("btc_oi")) and oi["btc_oi"] > 0, "موقعیت باز BTC")
        if oi:
            ts = str(oi.get("at", ""))
            source_clock = (int(ts) if ts.isascii() and ts.isdecimal() and len(ts) <= 14 else None, 3600)
        # Candle-derived attraction zones do not establish the order book or observed liquidations.
        need(bool(mapping(world.get("order_book")).get("source")) and bool(mapping(world.get("liquidations")).get("source")),
             "پوشش عمق سفارش و لیکوییدیشن واقعی برای نمادها")
    elif role == "E11":
        routes = mapping(data.get("per_strategy"))
        stats["published_routes"] = sorted(routes)
        need(all(all(count(mapping(v).get(k)) for k in ("signals","armed","watching")) for v in routes.values())
             and bool(routes), "شمارش مسیرها")
        route_ids = {v.get("strategy_id") for v in routes.values() if isinstance(v,dict) and v.get("version")
                     and isinstance(v.get("strategy_id"),str)}
        need({"S1","S2","Liam S","IBS + Pullback Plus","ONE-IDM Wick 15"} <= route_ids,
             "شاهد تفکیک‌شدهٔ پنج مسیر نسخه‌دار در قرارداد E11")
    elif role == "E15":
        alarms = data.get("alarms")
        stats["alarms"] = len(items(alarms))
        need(isinstance(alarms,list) and all(mapping(r).get("sym") and r.get("dir") in ("LONG","SHORT")
             and r.get("tf") and r.get("strategy") for r in alarms), "شواهد آلارم‌ها")
    elif role == "E16":
        pct = mapping(data.get("paper")).get("risk_per_trade_pct")
        sizing = mapping(risk.get("sizing"))
        stats.update(paper_risk_pct=pct, configured_pct=sizing.get("risk_pct_per_trade"),
                     max_exposure_pct=sizing.get("max_total_exposure_pct"))
        need(finite(pct) and 0 < pct <= 5 and pct == stats["configured_pct"], "انطباق ریسک هر معامله")
        stats["portfolio"] = portfolio
        balance = mapping(data.get("paper")).get("balance")
        exposure = portfolio.get("exposure_usd")
        need(portfolio.get("available") and finite(balance) and balance > 0 and finite(exposure)
             and finite(stats["max_exposure_pct"]) and exposure <= balance * stats["max_exposure_pct"] / 100,
             "اندازه و سقف مواجههٔ دفتر اصلی کاغذی")
        # The producer currently publishes sizing parameters, not a per-decision risk verdict.
        decision = mapping(data.get("portfolio_risk_decision"))
        need(isinstance(decision.get("approved"), bool) and decision.get("observed_at") == data.get("generated")
             and finite(exposure) and decision.get("open_exposure_usd") == exposure,
             "تصمیم زمان‌دار ریسک با مواجههٔ همان دفتر")
    elif role == "E17":
        selected = data.get("selected_for_delivery")
        hist = mapping(mapping(data.get("market")).get("symbol_history"))
        candidates = data.get("paper_candidates")
        listed = data.get("setups")
        stats.update(selected=selected, published=len(items(listed)), paper_candidates=len(items(candidates)))
        need(isinstance(candidates,list) and isinstance(listed,list) and count(selected)
             and selected == sum(mapping(x).get("waiting") is False for x in listed), "شمار انتخاب و انتظار")
        bad = [mapping(r).get("symbol") for r in items(candidates)+items(listed)
               if not positioned(mapping(r)) or not history_ok(hist.get(mapping(r).get("symbol")))]
        stats["invalid_rows"] = len(bad)
        need(not bad, "ترتیب قیمت‌ها و حداقل تاریخچهٔ نامزدها")
    elif role == "E19":
        r = reconciliation
        keys = ("open_before","exact_closed_matches","remaining_before_mark","market_reads")
        stats.update({k:r.get(k) for k in keys})
        need(all(count(r.get(k)) for k in keys) and r["open_before"] == r["exact_closed_matches"]+r["remaining_before_mark"]
             and (r["remaining_before_mark"] == 0 or r["market_reads"] > 0), "تطبیق دفتر باز با معاملات بسته و قیمت‌خوانی")
        source_clock = (r.get("checked_at"), 3600)
    elif role == "E20":
        r = mapping(data.get("review"))
        books = mapping(r.get("books"))
        stats.update(closed=r.get("closed"), books={k:mapping(v).get("n") for k,v in books.items()})
        need(count(r.get("closed")) and isinstance(r.get("books"),dict) and bool(r.get("verdict"))
             and all(count(v) for v in stats["books"].values()) and sum(stats["books"].values()) == r["closed"], "تطبیق تعداد بسته‌ها با دفترهای مرور")
        source_clock = (r.get("at"), 2*3600+2700)
    elif role == "E21":
        rows = items(lessons.get("lessons"))
        valid = sum(bool(mapping(r).get("text") and r.get("kind") and finite(r.get("at")) and r["at"] > 0) for r in rows)
        stats.update(lessons=len(rows), valid=valid, learning_trades=data.get("n_trades"))
        need(valid > 0 and valid == len(rows) and count(data.get("n_trades")), "درس‌های زمان‌دار دفتر حافظه")
        source_clock = (lessons.get("updated"), 86400)
    elif role == "E22":
        rows = data.get("proposals")
        stats.update(proposals=len(items(rows)), decided=len(items(data.get("decided"))), trades=data.get("n_trades"))
        need(isinstance(rows,list) and isinstance(data.get("decided"),list) and bool(data.get("rule"))
             and count(stats["trades"]) and stats["trades"] > 0 and all(
                 isinstance(mapping(r).get("decided"),bool) and r.get("kind") and r.get("validation_status")
                 for r in rows), "وضعیت اعتبارسنجی و تصمیم پیشنهادها")
    elif role == "E25":
        stats = delivery(data.get("sent"))
        need(stats["trade_receipts"] > 0, "رسید تلگرام متصل به شناسهٔ سیگنال معاملاتی")
        need(stats["invalid"] == 0 and stats["reused_receipts"] == 0, "رسید ناسازگار یا تکراری")
    return stats, missing, source_clock

