"""بازجویی پیش از صدور — قانون حمید، کلمه به کلمه:

    «قبل از صدور سیگنال نهایی، در تایم ۱۵ دقیقه ببین چه چیزهایی می‌تواند
    استاپش کند؛ فقط وقتی دلایل تارگت خوردن بیشتر از دلایل استاپ خوردن بود
    صادرش کن.»

هر دلیل یک جملهٔ فارسی با عدد است، نه حس. دلایل استاپ (con) و دلایل تارگت
(pro) شمرده می‌شوند و حکم سخت است: صدور فقط با pro > con. سیگنالِ
ردشده گم نمی‌شود — در دفتر vetoed کاغذی دنبال می‌شود تا خود این دروازه
نمره بگیرد: اگر ردشده‌ها بیشترشان تارگت خوردند، دروازه اشتباه می‌کند و
باید شل شود. مثل همیشه، قضاوت نهایی با اندازه‌گیری است نه با من.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
DOM = ROOT / "signals" / "dominance.json"


def _atr_pct(c15, n=20):
    w = c15[-n:]
    if len(w) < 5:
        return None
    return sum((k["h"] - k["l"]) / k["c"] for k in w) / len(w) * 100


def review(s, c15):
    """s: سیگنال (sym/dir/entry/sl/tp1) · c15: کندل ۱۵ دقیقه (dict).

    خروجی: {"pro": [...], "con": [...], "issue": bool, "note": str}"""
    from hamid.structure import trend
    from hamid.analyze_pump import rsi
    from hamid import liquidity, liqmap, memory

    d = s["dir"]
    pro, con = [], []
    # وزن‌ها — دستور صریح حمید: «نتیجهٔ گذشته، هم‌مسیری با روند و ابزارهای
    # حجم بیشتر تأثیر بگذارند». این سه، وزن ۲ دارند؛ بقیه وزن ۱.
    w = {"pro": 0, "con": 0}

    def _add(side, text, weight=1):
        (pro if side == "pro" else con).append(text)
        w[side] += weight
    px = c15[-1]["c"]

    # ۱) استاپ در برابر نویز ۱۵ دقیقه — درس استاپ ZAMA + دستور حمید ۱۲ اوت:
    # «حاشیهٔ استاپ به شدت پایین بود؛ با یک نوسان کوچک استاپ می‌خورد.»
    # اندازه‌گیری همان روز: میانهٔ رسیدن به استاپ ۱۲ دقیقه بود. پس این دیگر
    # فقط یک دلیل شمرده‌شده نیست — پرچم noise_stop بالا می‌رود و گلوگاه
    # ارسال آن را وتوی سخت می‌کند، هرقدر هم دلیل تارگت باشد.
    noise_stop = False
    atr = _atr_pct(c15)
    stop_pct = abs(s["entry"] - s["sl"]) / s["entry"] * 100 if s.get("sl") else None
    if atr and stop_pct is not None:
        if stop_pct < 1.2 * atr:
            noise_stop = True
            _add("con", f"استاپ {stop_pct:.2f}٪ داخل نویز ۱۵د است (ATR {atr:.2f}٪) — ویک می‌خورد", 2)
        else:
            pro.append(f"استاپ {stop_pct:.2f}٪ بیرون نویز ۱۵د (ATR {atr:.2f}٪)")

    # ۲) روند ۱۵ دقیقه
    t15 = trend(c15)
    if t15 in ("up", "down"):
        if (t15 == "up") == (d == "LONG"):
            _add("pro", f"روند ۱۵د هم‌جهت ({t15})", 2)
        else:
            _add("con", f"روند ۱۵د خلاف جهت ({t15})", 2)

    # ۲.۵) انجین الگوهای کلاسیک (دستور حمید ۱۲ اوت): الگوهای شکل‌گرفته در
    # ۱۵د/۱س/۴س شرط تأثیرگذارند — هم‌جهتِ تازه دلیل تارگت، خلاف دلیل استاپ؛
    # توافق ≥۲ تایم‌فریم وزن ۲ (چند تایم‌فریم = اعتماد بیشتر). نام الگو به
    # پروندهٔ معامله می‌رود تا ماشین بونفرونیِ شبانه سهم واقعی هر الگو را
    # از نتیجه اندازه بگیرد — یادگیریِ هر شب از نو، همیشه به‌روز.
    patterns_out = None
    try:
        from hamid import patterns as _pat
        tfp = {"15m": _pat.detect(c15)}
        try:
            import sources as _srcp
            _p1h = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                    for k in _srcp.klines(s["sym"], "1h", 500)]
            if len(_p1h) >= 60:
                tfp["1h"] = _pat.detect(_p1h)
                from hamid.lagcorr import _to4h
                _p4h = _to4h(_p1h)
                if len(_p4h) >= 60:
                    tfp["4h"] = _pat.detect(_p4h)
        except Exception:                            # noqa: BLE001 - شبکه، انجین را نمی‌کشد
            pass
        notes, ag = [], {"with": [], "against": []}
        for _tf, ps in tfp.items():
            a, best = _pat.align(ps, d)
            if a:
                ag[a].append(_tf)
                notes.append(f"{best['fa']} در {_tf}"
                             + (" (تأییدشده)" if best["status"] == "confirmed" else ""))
        pat_align = None
        if ag["with"] and not ag["against"]:
            pat_align = "with"
            txt = "الگوی کلاسیک هم‌جهت: " + "، ".join(notes)
            if len(ag["with"]) >= 2:
                _add("pro", txt + " — دو تایم‌فریم موافق", 2)
            else:
                pro.append(txt)
        elif ag["against"] and not ag["with"]:
            pat_align = "against"
            txt = "الگوی کلاسیک خلاف جهت: " + "، ".join(notes)
            if len(ag["against"]) >= 2:
                _add("con", txt + " — دو تایم‌فریم مخالف", 2)
            else:
                con.append(txt)
        elif ag["with"] and ag["against"]:
            con.append("الگوهای تایم‌فریم‌ها متضادند: " + "، ".join(notes))
        patterns_out = {
            "by_tf": {t: [p["fa"] for p in ps] for t, ps in tfp.items() if ps},
            "align": pat_align, "note": "، ".join(notes) or None}
    except Exception:                                # noqa: BLE001
        pass

    # ۳) RSI ۱۵ دقیقه — ورود در اشباع، دعوت به استاپ است
    r15 = rsi(c15)
    if r15 is not None:
        if d == "LONG" and r15 >= 72:
            con.append(f"RSI ۱۵د اشباع خرید ({r15:.0f}) — ورود دیر")
        elif d == "SHORT" and r15 <= 28:
            con.append(f"RSI ۱۵د اشباع فروش ({r15:.0f}) — ورود دیر")
        elif 40 <= r15 <= 65:
            pro.append(f"RSI ۱۵د سالم ({r15:.0f})")

    # ۴) آهن‌ربای نقدینگی (سقف/کف‌های برابر)
    try:
        lq = liquidity.read(c15, d)
        if lq.get("side") == "with":
            pro.append("آهن‌ربای نقدینگی هم‌جهت")
        elif lq.get("side") == "against":
            con.append("آهن‌ربای نقدینگی خلاف جهت — استخر استاپ آن‌طرف است")
    except Exception:                                # noqa: BLE001
        pass

    # ۴.۷) انجین اردر بلاک (دستور حمید ۱۳ اوت): ورود روی OB معتبرِ هم‌جهت =
    # سوخت؛ ورود در دهان OB خلاف = دلیل استاپ. اعتبار یعنی واکنش‌های
    # شمرده‌شده و نشکسته (hamid/orderblocks — روش خود حمید + کنترل نویز).
    # ۱۵د از همین کندل‌ها؛ ۱س با فچ محافظت‌شده. نتیجه به دفتر هم می‌رود تا
    # ماشین بونفرونی شبانه سهم واقعی OB را از برد و باخت اندازه بگیرد.
    ob_ctx = None
    try:
        from hamid import orderblocks as _obm
        want = "up" if d == "LONG" else "down"
        found = []
        b_in, b_near = _obm.near(c15, tf="15m")
        if b_in or b_near:
            found.append((b_in or b_near, bool(b_in)))
        try:
            import sources as _srco
            _o1h = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4],
                     "v": k[5]} for k in _srco.klines(s["sym"], "1h", 320)]
            if len(_o1h) >= 60:
                b_in2, b_near2 = _obm.near(_o1h, tf="1h")
                if b_in2 or b_near2:
                    found.append((b_in2 or b_near2, bool(b_in2)))
        except Exception:                            # noqa: BLE001
            pass
        for b, inside in found:
            align = "with" if b["move"] == want else "against"
            note_ob = _obm.note_fa(b, "داخل" if inside else "نزدیک")
            if ob_ctx is None:
                ob_ctx = {"align": align, "tf": b["tf"],
                          "reactions": b["reactions"], "hunts": b["hunts"],
                          "fresh": b["fresh"], "note": note_ob}
            if align == "with":
                pro.append(f"{note_ob} — هم‌جهت، سوخت حرکت")
            else:
                con.append(f"{note_ob} — خلاف جهت، دیوار جلوی راه")
    except Exception:                                # noqa: BLE001
        pass

    # ۵) نقشهٔ لیکوییدیشن (تخمین از کندل)
    try:
        lm = liqmap.build(c15)
        if lm and lm["magnet"] in ("above", "below"):
            with_dir = (lm["magnet"] == "above") == (d == "LONG")
            (pro if with_dir else con).append(
                "خوشهٔ لیکویید " + ("هم‌جهت — سوخت حرکت" if with_dir
                                    else "خلاف جهت — قیمت آن‌طرف کشیده می‌شود"))
    except Exception:                                # noqa: BLE001
        pass

    # ۶) تمرین تاریخی — هزاران ریپلی روی کندل واقعی همین ارز/جهت
    try:
        hn, ha = memory.history(s["sym"], d)
        if ha > 0:
            _add("pro", hn, 2)
        elif ha < 0:
            _add("con", hn, 2)
    except Exception:                                # noqa: BLE001
        pass

    # ۶.۵) قانون‌های تأییدشدهٔ دفتر شبانه (کندل واقعی) — دستور حمید (۱۲ اوت):
    # «استراتژی‌ها را از چارت زنده و گذشتهٔ ارزها پیدا کن و به یادگیری اضافه
    # کن». کشف در backtest.py هر شب؛ عمل همین‌جا در گلوگاه صدور: فقط شرطی که
    # بازهٔ بوت‌استرپش از صفر رد شده و روی همین سیگنال قابل‌آزمایش است، با
    # علامتِ دلتای اندازه‌گیری‌شده و وزن ۲ (نتیجهٔ گذشته) در حکم می‌نشیند.
    # قانونی که تیپ دیگر پاداشش را قطع کند، در بازسنجی صبح بعد خودش می‌افتد.
    try:
        import scan as _scan
        s2 = dict(s)
        ob = s.get("ob") or {}
        if s2.get("inOB") is None and ob.get("low") is not None \
                and ob.get("high") is not None:
            s2["inOB"] = 1 if ob["low"] <= s["entry"] <= ob["high"] else 0
        for r in _scan.confirmed_rules().get(s.get("strategy"), []):
            test = _scan.RULE_TESTS.get(r["condition"])
            if not test:
                continue
            try:
                hit = bool(test(s2, None))
            except Exception:                        # noqa: BLE001
                continue
            if hit:
                _add("pro" if r["delta"] > 0 else "con",
                     f"قانون تأییدشدهٔ تاریخی «{r['condition']}» "
                     f"({r['delta']:+.2f}R، n={r['n']}، CI ردشده از صفر)", 2)
    except Exception:                                # noqa: BLE001
        pass

    # ۷) دامیننس تتر — فاز ۲: اول رژیم ساختاری (روند سوینگی خودِ سری USDT.D)،
    # با وزن ۲ طبق بند ۱۰ منشور («تعارض با فشار قوی USDT.D → امتیاز کم یا
    # رد»). تا وقتی سری به ۶۰ کندل ۱س نرسیده، رژیم INSUFFICIENT است و مثل
    # قبل به دلتای عددی ۱ساعته برمی‌گردیم (وزن ۱) — دروازهٔ صداقت داده.
    try:
        dom = json.loads(DOM.read_text())
        stc = dom.get("structure") or {}
        reg = stc.get("regime")
        if reg in ("BULLISH", "BEARISH"):
            with_dir = (reg == "BULLISH") == (d == "LONG")
            txt = f"رژیم ساختاری دامیننس {reg}"
            if stc.get("why"):
                txt += f" — {stc['why']}"
            _add("pro" if with_dir else "con", txt, 2)
        else:
            u1 = (dom.get("chg_1h") or {}).get("usdt")
            if u1 is not None and abs(u1) >= 0.15:
                risk_off = u1 > 0
                if risk_off == (d == "LONG"):
                    con.append(f"USDT.D در حال {'رشد' if risk_off else 'ریزش'} ({u1:+.2f}٪/۱س) — خلاف جهت")
                else:
                    pro.append(f"USDT.D {u1:+.2f}٪/۱س — هم‌جهت")
        ev = [m for m in (dom.get("macro") or []) if 0 <= (m.get("in_hours") or 99) <= 2]
        if ev:
            con.append(f"رویداد کلان تا ۲ ساعت دیگر ({ev[0]['title']}) — شلاق قیمت محتمل")
    except Exception:                                # noqa: BLE001
        pass

    # ۷.۵) ابزار حجم (دستور حمید — وزن ۲): جهش حجم کندل بستهٔ آخر ۱۵د
    # نسبت به ۲۰ کندل قبل؛ جهش هم‌جهت = سوخت، جهش خلاف = خطر.
    try:
        vols = [k["v"] for k in c15[-21:-1]]
        mv = sum(vols) / len(vols) if vols else 0
        sdv = (sum((v - mv) ** 2 for v in vols) / len(vols)) ** 0.5 if vols else 0
        vz = (c15[-1]["v"] - mv) / sdv if sdv else 0
        if vz >= 1.5:
            bull = c15[-1]["c"] >= c15[-1]["o"]
            if bull == (d == "LONG"):
                _add("pro", f"جهش حجم هم‌جهت (z={vz:.1f}) — مشارکت واقعی", 2)
            else:
                _add("con", f"جهش حجم خلاف جهت (z={vz:.1f})", 2)
    except Exception:                                # noqa: BLE001
        pass

    # ۸) واکنش-بازار (قانون حمید): وقتی حرکت بزرگی در BTC جریان دارد، اول
    # لگ-کورولیشنِ همین ارز با BTC و رفتارش در حرکت بزرگ قبلی بررسی شود —
    # بعد سیگنال. لانگ وسط ریزشی که این ارز تاریخاً دنبالش می‌ریزد، دلیل
    # استاپ است؛ هم‌جهتی، دلیل تارگت.
    try:
        import sources as _src
        from hamid import lagcorr
        _b1h = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                for k in _src.klines("BTCUSDT", "1h", 500)]
        _s1h = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                for k in _src.klines(s["sym"], "1h", 500)]
        mr = lagcorr.market_reaction(_b1h, _s1h)
        if mr and abs(mr["btc_1h_pct"]) >= 1.0 and mr["follow"]:
            line = lagcorr.reaction_fa(s["sym"], mr)
            btc_down = mr["btc_1h_pct"] < 0
            if btc_down == (d == "LONG"):
                con.append(line)
            else:
                pro.append(line)
    except Exception:                                # noqa: BLE001 - شبکه، دروازه را نمی‌کشد
        pass

    # ۹) فاصله تا تارگت در برابر مسیر رفته — تارگتِ دور با مومنتوم خرج‌شده
    if s.get("tp1"):
        tp_pct = abs(s["tp1"] - s["entry"]) / s["entry"] * 100
        if atr and tp_pct > 6 * atr:
            con.append(f"تارگت {tp_pct:.1f}٪ یعنی {tp_pct/atr:.0f} برابر ATR — راه خیلی دور")

    # حکم وزنی — دلایل ساده وزن ۱؛ گذشته/روند/حجم وزن ۲ (فقط وزنی‌ها در w
    # شمرده شده‌اند و همیشه با وزن ۲ اضافه می‌شوند). وزن هر سمت =
    # تعداد دلایل ساده + w همان سمت.
    n2p, n2c = w["pro"] // 2, w["con"] // 2
    pro_w = (len(pro) - n2p) + w["pro"]
    con_w = (len(con) - n2c) + w["con"]
    issue = pro_w > con_w
    note = (f"⚖️ بازجویی ۱۵د (وزنی): {pro_w} امتیاز تارگت / {con_w} امتیاز استاپ — "
            + ("صادر شد" if issue else "صادر نشد"))
    if noise_stop:
        issue = False                     # وتوی سخت — دستور حمید ۱۲ اوت
        note += " · ⛔ استاپ داخل نویز — وتوی سخت"
    return {"pro": pro, "con": con, "pro_w": pro_w, "con_w": con_w,
            "issue": issue, "note": note, "price": px, "patterns": patterns_out,
            "noise_stop": noise_stop, "ob_ctx": ob_ctx}
