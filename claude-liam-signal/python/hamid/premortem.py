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
    px = c15[-1]["c"]

    # ۱) استاپ در برابر نویز ۱۵ دقیقه — درس استاپ ZAMA
    atr = _atr_pct(c15)
    stop_pct = abs(s["entry"] - s["sl"]) / s["entry"] * 100 if s.get("sl") else None
    if atr and stop_pct is not None:
        if stop_pct < 1.2 * atr:
            con.append(f"استاپ {stop_pct:.2f}٪ داخل نویز ۱۵د است (ATR {atr:.2f}٪) — ویک می‌خورد")
        else:
            pro.append(f"استاپ {stop_pct:.2f}٪ بیرون نویز ۱۵د (ATR {atr:.2f}٪)")

    # ۲) روند ۱۵ دقیقه
    t15 = trend(c15)
    if t15 in ("up", "down"):
        if (t15 == "up") == (d == "LONG"):
            pro.append(f"روند ۱۵د هم‌جهت ({t15})")
        else:
            con.append(f"روند ۱۵د خلاف جهت ({t15})")

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
            pro.append(hn)
        elif ha < 0:
            con.append(hn)
    except Exception:                                # noqa: BLE001
        pass

    # ۷) دامیننس تتر — ریسک‌گریزی بازار خلاف لانگ است
    try:
        dom = json.loads(DOM.read_text())
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

    issue = len(pro) > len(con)
    note = (f"⚖️ بازجویی ۱۵د: {len(pro)} دلیل تارگت / {len(con)} دلیل استاپ — "
            + ("صادر شد" if issue else "صادر نشد"))
    return {"pro": pro, "con": con, "issue": issue, "note": note, "price": px}
