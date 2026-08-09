#!/usr/bin/env python3
"""تحلیل پامپ یک ارز، همان‌طور که حمید خواست — BICO نمونهٔ اول است.

    python3 -m hamid.analyze_pump --symbol BICOUSDT

۱. پامپ‌های گذشتهٔ همین ارز را در تاریخچهٔ در دسترس پیدا می‌کند (بازده ۴ساعته
   بالای آستانه + جهش حجم).
۲. برای هر پامپ، بازهٔ یک روز قبل تا یک روز بعد را روی ارزهای پرحجم بازار
   می‌سنجد: کدام‌ها قبلش پامپ بودند (محرک احتمالی) و کدام‌ها بعدش (دنباله‌رو).
۳. حجم و RSI در لحظهٔ شروع هر پامپ.
۴. علت خبری از جستجوی وب (سهمیه‌دار).
۵. وضعیت الان: کانال ۴ساعته و ۱ساعته، و نقطهٔ ورود ۱۵ دقیقه به سبک
   «IBS پولبک» — پولبک به ناحیهٔ تقاضای همین حرکت — به‌عنوان آلارم ثبت
   می‌شود تا با رسیدن قیمت، بازبینی و سیگنال شود.

خروجی: brain/analysis-<sym>.json + signals/pump-analysis.json (برای پنل).
هر عدد از کندل واقعی است؛ جایی که داده کوتاه است، صریح نوشته می‌شود.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                                # noqa: E402
from hamid.structure import atr, channel, trend               # noqa: E402
from hamid import orderblock                                  # noqa: E402

ROOT = HERE.parent.parent.parent


def cds(sym, tf, n):
    rows = sources.klines(sym, tf, n)
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def rsi(cd, n=14):
    if len(cd) < n + 1:
        return None
    gains = losses = 0.0
    for a, b in zip(cd[-n - 1:-1], cd[-n:]):
        d = b["c"] - a["c"]
        gains += max(d, 0)
        losses += max(-d, 0)
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100 - 100 / (1 + rs), 1)


def rsi_at(cd, i, n=14):
    return rsi(cd[: i + 1], n)


def pumps(cd1h, ret_gate=0.12, vol_z=2.5):
    """شروع پامپ: بازدهٔ ۴ کندل یک‌ساعته بالای آستانه + حجم غیرعادی. پامپ‌های
    نزدیک‌به‌هم یکی حساب می‌شوند."""
    eps = []
    for i in range(30, len(cd1h) - 1):
        r4 = cd1h[i]["c"] / cd1h[i - 4]["c"] - 1
        base = [c["v"] for c in cd1h[max(0, i - 30):i]]
        m = sum(base) / len(base)
        sd = (sum((v - m) ** 2 for v in base) / len(base)) ** 0.5 or 1e-12
        if r4 >= ret_gate and (cd1h[i]["v"] - m) / sd >= vol_z:
            if eps and i - eps[-1]["i"] < 24:
                continue
            eps.append({"i": i, "t": cd1h[i]["t"], "ret_4h_pct": round(r4 * 100, 1),
                        "vol_z": round((cd1h[i]["v"] - m) / sd, 1),
                        "rsi": rsi_at(cd1h, i)})
    return eps


def related(sym, eps, cd1h, universe, window=24):
    """چه ارزهایی یک روز قبل/بعد از پامپ‌های این ارز حرکت کردند."""
    out = {}
    for other in universe:
        if other == sym:
            continue
        try:
            oc = cds(other, "1h", len(cd1h) + 10)
        except Exception:                            # noqa: BLE001
            continue
        idx = {c["t"]: k for k, c in enumerate(oc)}
        pre, post = [], []
        for e in eps:
            k = idx.get(cd1h[e["i"]]["t"])
            if k is None or k < window or k + window >= len(oc):
                continue
            pre.append(oc[k]["c"] / oc[k - window]["c"] - 1)
            post.append(oc[k + window]["c"] / oc[k]["c"] - 1)
        if pre:
            out[other] = {"n": len(pre),
                          "pre_24h_pct": round(sum(pre) / len(pre) * 100, 1),
                          "post_24h_pct": round(sum(post) / len(post) * 100, 1)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BICOUSDT")
    ap.add_argument("--universe", type=int, default=40)
    a = ap.parse_args()
    sym = a.symbol.upper()
    t0 = time.time()

    c1h = cds(sym, "1h", 1000)
    c15 = cds(sym, "15m", 400)
    c4h_like = c1h  # کانال ۴ساعته از resample پایین ساخته می‌شود
    from hamid.cycle import resample
    c4h = resample(c1h, 4)
    print(f"{sym}: {len(c1h)} کندل ۱ساعته (~{len(c1h)//24} روز)، {len(c15)} کندل ۱۵دقیقه")

    eps = pumps(c1h)
    print(f"پامپ‌های یافته: {len(eps)}")
    for e in eps:
        print(f"  {time.strftime('%m-%d %H:%M', time.gmtime(e['t']/1000))} UTC "
              f"+{e['ret_4h_pct']}٪/4h · حجم z={e['vol_z']} · RSI={e['rsi']}")

    # جهان مقایسه: پرحجم‌ترین‌ها
    try:
        uni = [s["symbol"] for s in
               sorted(sources.tickers(), key=lambda x: -float(x["quoteVolume"] or 0))
               if s["symbol"].endswith("USDT")][:a.universe]
    except Exception:                                # noqa: BLE001
        uni = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    rel = related(sym, eps, c1h, uni) if eps else {}
    movers_pre = sorted(rel.items(), key=lambda kv: -kv[1]["pre_24h_pct"])[:8]
    movers_post = sorted(rel.items(), key=lambda kv: -kv[1]["post_24h_pct"])[:8]

    # علت خبری — سهمیه‌دار؛ شکستش تحلیل را نمی‌کشد
    news = []
    try:
        from hamid import research
        base = sym.replace("USDT", "")
        j = research.search(f"{base} crypto pump news reason", max_results=5)
        news = [{"title": r.get("title"), "url": r.get("url")}
                for r in (j.get("results") or [])][:5]
    except Exception as e:                           # noqa: BLE001
        news = [{"title": f"جستجوی خبر در دسترس نبود: {type(e).__name__}", "url": None}]

    # وضعیت الان + نقطهٔ ورود ۱۵دقیقه (پولبک به تقاضای همین حرکت)
    ch4 = channel(c4h)
    ch1 = channel(c1h)
    t4, t1 = trend(c4h), trend(c1h)
    entry = None
    obs = orderblock.find(c15, "bullish")
    fresh = [b for b in obs if not b.consumed and len(c15) - 1 - b.i < 60]
    if fresh:
        b = sorted(fresh, key=lambda x: -x.i)[0]
        a15 = atr(c15) or 0
        entry = {"entry": round(b.high, 10), "sl": round(b.low - 0.3 * a15, 10),
                 "tp1": round(c15[-1]["c"], 10),
                 "note": "پولبک به سقف ناحیهٔ تقاضای همین حرکت — با رسیدن قیمت، بازبینی و سیگنال"}

    now_px = c1h[-1]["c"]
    report = {
        "generated": int(time.time() * 1000),
        "symbol": sym, "price": now_px,
        "history_days": len(c1h) // 24,
        "pumps": eps,
        "movers_before": [{"symbol": k, **v} for k, v in movers_pre],
        "movers_after": [{"symbol": k, **v} for k, v in movers_post],
        "news": news,
        "now": {"trend_4h": t4, "trend_1h": t1,
                "channel_4h": str(ch4) if ch4 else None,
                "channel_1h": str(ch1) if ch1 else None,
                "rsi_1h": rsi(c1h), "rsi_15m": rsi(c15)},
        "alarm": entry,
        "note": ("نمونهٔ پامپ کم است — نتیجه دربارهٔ دنباله‌روها فقط مشاهده است، نه قانون"
                 if len(eps) < 4 else
                 "برای قانون شدن، همین اندازه‌گیری باید روی نمونهٔ بزرگ‌تر و ارزهای بیشتر تکرار شود"),
    }
    (ROOT / "brain").mkdir(exist_ok=True)
    (ROOT / "brain" / f"analysis-{sym.lower()}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1))
    (ROOT / "signals").mkdir(exist_ok=True)
    (ROOT / "signals" / "pump-analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1))

    # آلارم در اتاق رادار — پنل همین را نشان می‌دهد و چرخه پایشش می‌کند
    if entry:
        try:
            import brain
            st = brain.room_load("radar", {}) or {}
            al = st.get("alarms") or []
            al.insert(0, {"sym": sym, "tf": "15m", "dir": "LONG",
                          "strategy": "pump", "strategyName": "پامپ — پولبک",
                          "price": entry["entry"], "now": now_px,
                          "distancePct": round(abs(now_px - entry["entry"]) / entry["entry"] * 100, 2),
                          "why": entry["note"], "stage": "ARMED"})
            brain.room_save("radar", {**st, "alarms": al[:80]})
        except Exception as e:                       # noqa: BLE001
            print(f"ثبت آلارم رادار نشد: {type(e).__name__}")

    print(f"\nتمام شد در {time.time()-t0:.0f} ثانیه — brain/analysis-{sym.lower()}.json")


if __name__ == "__main__":
    main()
