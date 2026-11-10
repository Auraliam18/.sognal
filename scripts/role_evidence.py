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
    watch_messages = set()
    trade_messages = Counter()
    for raw in items(rows):
        row = mapping(raw)
        kind, mid, sid = (row.get(k) for k in ("kind", "tg_msg_id", "signal_id"))
        if kind not in ("watch_alert", "trade_signal"):
            groups["legacy_unverified"] += 1
            continue
        if type(mid) is not int or mid < 1 or not finite(row.get("at")) or row["at"] <= 0:
            groups["invalid"] += 1
            continue
        if kind == "watch_alert":
            watch_messages.add(mid)
            groups["watch_rows"] += 1
        elif isinstance(sid, str) and re.fullmatch(r"S-[0-9a-f]{20}", sid) and sid not in trades:
            trades[sid] = row["at"]
            trade_messages[mid] += 1
        else:
            groups["invalid"] += 1
    # Pump radar can include multiple watched symbols in one Telegram post.
    conflicts = sum(n-1 for n in trade_messages.values()) + len(watch_messages.intersection(trade_messages))
    return {"watch_receipts": len(watch_messages), "watch_rows": groups["watch_rows"], "trade_receipts": len(trades),
            "last_trade_at": max(trades.values(), default=None), "legacy_unverified": groups["legacy_unverified"],
            "invalid": groups["invalid"], "reused_receipts": conflicts}


def observation_time(sample):
    raw = str(mapping(sample).get("at", ""))
    if raw.isascii() and raw.isdecimal() and len(raw) == 13:
        return int(raw)
    return None


def derivative_observation(key, world, intel, cycle_at):
    # The heartbeat and full scan may publish out of order. Use the exchange
    # timestamp, never the Git commit time, to compare compatible observations.
    options = []
    for source, record in (("signals/hamid-latest.json", world), ("brain/intel/latest.json", mapping(intel))):
        sample = mapping(record.get(key))
        ts = observation_time(sample)
        if ts and finite(cycle_at) and -300000 <= cycle_at - ts <= 3600000:
            options.append((ts, source, sample))
    if options:
        return max(options, key=lambda item:item[0])
    return None, None, {}


def resolve_strategy_references(root, routes):
    """Match the named section and its content, never promote a documentary reference."""
    import hashlib
    expected = {"s1":"S1","s2":"S2","liam_s":"Liam S Checklist"}
    path = "AuraLiam369_Trading_Agent_Master_Spec_FA_v2.1.md"
    try:
        doc = (root/path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        doc = ""
    for key, title in expected.items():
        rule = mapping(mapping(routes).get(key))
        ref = mapping(rule.get("reference"))
        mark = "## " + title + "\n"
        parts = ("\n"+doc).split("\n"+mark)
        body = parts[1].split("\n## ",1)[0].strip() if len(parts)==2 else ""
        verified = bool(body and ref.get("path")==path and ref.get("heading")==title and
                        hashlib.sha256(body.encode()).hexdigest()==ref.get("section_sha256"))
        rule["reference_verified"] = verified
        if verified:
            rule["documented_rules"] = [line.lstrip("- ").strip() for line in body.splitlines() if line.strip()]


def inspect(role, raw, *, lessons, reconciliation, risk, portfolio, routes=None, cycle=None, intel=None):
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
        oi_at, oi_source, oi = derivative_observation("open_interest", world, intel, data.get("generated"))
        book_at, book_source, depth = derivative_observation("order_book", world, intel, data.get("generated"))
        stats["sources"] = {"open_interest":oi_source, "order_book":book_source}
        stats.update(funding=mapping(world.get("funding")), btc_oi=oi.get("btc_oi"), oi_at=oi.get("at"),
                     liquidity_maps=sum(bool(mapping(x).get("liq_map")) for x in items(data.get("setups"))))
        need(all(finite(stats["funding"].get(k)) for k in ("BTC","ETH","SOL")), "فاندینگ")
        need(finite(oi.get("btc_oi")) and oi["btc_oi"] > 0, "موقعیت باز BTC")
        observed = [ts for ts in (oi_at, book_at) if ts is not None]
        if observed:
            source_clock = (min(observed), 3600)
        # Candle-derived attraction zones do not establish the order book or observed liquidations.
        stats["btc_depth"] = depth
        need(depth.get("instrument") == "BTC-USDT-SWAP" and finite(depth.get("imbalance"))
             and abs(depth["imbalance"]) <= 1 and finite(depth.get("at"))
             and finite(data.get("generated")) and -300000 <= data["generated"] - depth["at"] <= 3600000,
             "نمونهٔ زمان‌دار عمق سفارش بیت‌کوین")
        liq_at, origin, liq = derivative_observation("liquidations", world, intel, data.get("generated"))
        events = [x for x in items(liq.get("events")) if isinstance(x,dict) and isinstance(x.get("symbol"),str)
                  and x["symbol"].endswith("_USDT") and finite(x.get("fill_price")) and x["fill_price"] > 0
                  and finite(x.get("order_contracts")) and x["order_contracts"] != 0 and finite(x.get("at"))
                  and finite(liq_at) and liq_at-3600000 <= x["at"] <= liq_at]
        stats.update(liquidation_source=liq.get("source"), liquidation_symbols=sorted({x["symbol"] for x in events}),
                     liquidation_samples=len(events), last_liquidation_at=liq_at)
        stats["sources"]["liquidations"] = origin
        need(bool(events) and max(x["at"] for x in events) == liq_at and liq.get("source") == "Gate futures/usdt/liq_orders",
             "دادهٔ مستقل لیکوییدیشن نمادها")
        if liq_at and observed:
            source_clock = (min(*observed,liq_at),3600)
    elif role == "E11":
        observed = mapping(data.get("per_strategy"))
        stats["published_routes"] = sorted(observed)
        need(all(all(count(mapping(v).get(k)) for k in ("signals","armed","watching")) for v in observed.values())
             and bool(observed), "شمارش مسیرهای اسکن")
        declared = mapping(routes)
        contract = ("s1","s2","liam_s","ibs_pullback_plus","one_idm_wick_15")
        stats["registry"] = {k:{f:mapping(declared.get(k)).get(f) for f in ("strategy_id","version","status","reference","reference_verified","documented_rules","missing_requirements")}
                             for k in contract}
        for key, rule in stats["registry"].items():
            if key in ("s1","s2","liam_s"):
                need(rule["reference_verified"] is True, f"تطبیق متن مرجع {key}")
            need(rule["strategy_id"] and rule["version"] and rule["status"] in ("LIVE_SIGNAL","EXPERIMENT_ONLY"),
                 f"تعریف اجرایی نسخه‌دار {key}")
        primary = mapping(cycle)
        stats["paper_inducement"] = len(items(primary.get("inducement")))
        stats["primary_candidates"] = len(items(primary.get("setups")))
        need(isinstance(primary.get("inducement"),list) and isinstance(primary.get("setups"),list),
             "خروجی مسیر اصلی و آزمایشی پولبک")
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
        # Only a decision from this cycle and this same ledger can attest sizing.
        decision = mapping(data.get("portfolio_risk_decision"))
        stats["decision"] = decision
        need(isinstance(decision.get("approved"), bool) and decision.get("cycle_at") == data.get("generated")
             and finite(decision.get("observed_at")) and finite(data.get("generated"))
             and 0 <= decision["observed_at"] - data["generated"] <= 3600000
             and decision.get("open_positions") == portfolio.get("open_positions") and decision.get("equity_usd") == balance
             and finite(exposure) and finite(decision.get("open_exposure_usd")) and abs(decision["open_exposure_usd"]-exposure)<0.00001,
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
        stats.update({k:r.get(k) for k in (*keys,"market_attempts","missing_symbols")})
        need(all(count(r.get(k)) for k in keys) and r["open_before"] == r["exact_closed_matches"]+r["remaining_before_mark"]
             and (r["remaining_before_mark"] == 0 or ((r["market_reads"] > 0 or (r.get("awaiting_first_bar") or 0) > 0) and r["market_reads"] == r.get("market_attempts") and r.get("missing_symbols") == [])), "تطبیق دفتر باز با معاملات بسته و قیمت‌خوانی")
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
        if stats["last_trade_at"] is not None:
            source_clock = (stats["last_trade_at"], 3600)
        need(stats["trade_receipts"] > 0, "رسید تلگرام متصل به شناسهٔ سیگنال معاملاتی")
        need(stats["invalid"] == 0 and stats["reused_receipts"] == 0, "رسید ناسازگار یا تکراری")
    return stats, missing, source_clock

