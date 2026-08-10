"""حباب‌ها — شخصیت‌شناسی صفر تا صد ارزهای متحرک، هر ۱۵ دقیقه.

تشبیه خود حمید: «مثل این می‌ماند که صفر تا صد شخصیت یک نفر را بدانی —
آن‌وقت می‌فهمی موقع جنگ چه واکنشی دارد، و وقتی دوستش ماشین جدید می‌خرد
چه می‌کند.» برای یک ارز یعنی:

  · **موقع جنگ** = ساعت‌هایی که بیت‌کوین می‌ریزد (۱٪- در یک ساعت): این ارز
    به‌طور تاریخی چند برابر BTC می‌ریزد؟ (بتای سقوط، از کندل واقعی)
  · **ماشینِ دوست** = وقتی سردستهٔ خوشه‌اش می‌پرد: معمولاً چند ساعت بعد و
    چند بار در تاریخچه دنبالش رفته؟
  · مزاج عمومی: بتای کل به BTC، تعداد و اندازهٔ پامپ‌های قبلی، RSI و روند
    الان، آهن‌ربای نقدینگی، جهش حجم.

هر عدد از کندل واقعی همان صرافی‌هاست و روی دادهٔ کش‌شدهٔ رادار سوار
می‌شود — فچ اضافه تقریباً صفر. نمونهٔ کم صادقانه «؟» می‌شود، نه ادعا.
خروجی: signals/bubbles.json — پنل تب «حباب‌ها» همین را می‌کشد.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "bubbles.json"


def _rets(cd):
    return [(cd[i]["c"] / cd[i - 1]["c"] - 1) for i in range(1, len(cd))]


def beta_to_btc(coin_1h, btc_1h, look=300):
    """بتای ساعتی به بیت‌کوین + «بتای جنگ» (فقط ساعت‌های افتِ ≥۱٪ BTC)."""
    bt = {c["t"]: c for c in btc_1h}
    pairs = []
    for i in range(1, len(coin_1h)):
        b = bt.get(coin_1h[i]["t"])
        b0 = bt.get(coin_1h[i - 1]["t"])
        if b and b0 and b0["c"]:
            pairs.append((coin_1h[i]["c"] / coin_1h[i - 1]["c"] - 1,
                          b["c"] / b0["c"] - 1))
    pairs = pairs[-look:]
    if len(pairs) < 50:
        return None, None, 0
    xs = [p[1] for p in pairs]
    ys = [p[0] for p in pairs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    beta = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx, 2) if vx else None
    war = [(y, x) for y, x in pairs if x <= -0.01]
    war_beta = (round(sum(y for y, x in war) / sum(x for y, x in war), 2)
                if len(war) >= 5 else None)
    return beta, war_beta, len(war)


def character(p):
    """خلاصهٔ شخصیت به فارسی — از عدد، نه از تخیل."""
    bits = []
    wb = p.get("war_beta")
    if wb is not None:
        if wb >= 1.5:
            bits.append(f"در جنگ ترسو: با افت BTC حدود {wb}× می‌ریزد")
        elif wb <= 0.6:
            bits.append(f"در جنگ خونسرد: با افت BTC فقط {wb}× تکان می‌خورد")
        else:
            bits.append(f"در جنگ همراه BTC ({wb}×)")
    lg = p.get("lag")
    if lg:
        bits.append(f"وقتی {lg['leader']} می‌پرد، طبق {lg['n']} سابقه ~{lg['med_h']}س بعد دنبالش می‌رود")
    elif p.get("role") == "سردسته":
        bits.append("خودش سردسته است — دنبال کسی نمی‌دود")
    n_p = p.get("pumps_n") or 0
    if n_p >= 3:
        bits.append(f"تکرارکنندهٔ پامپ ({n_p} بار، بزرگ‌ترین +{p.get('pumps_max')}٪)")
    elif n_p == 0:
        bits.append("در تاریخچهٔ در دسترس پامپ بزرگی نداشته")
    if p.get("liq_magnet") == "above":
        bits.append("نقدینگی بالای سرش جمع است (آهن‌ربای بالا)")
    elif p.get("liq_magnet") == "below":
        bits.append("نقدینگی زیر پایش جمع است")
    return "؛ ".join(bits) or "شخصیت هنوز خوانا نیست — دادهٔ کافی نداریم"


def build(kc, universe, blocks, top=25):
    """پروفایل صفر تا صد برای متحرک‌ترین‌های الان (سبک کریپتو بابلز)."""
    from hamid.analyze_pump import pumps, rsi
    from hamid.structure import trend
    from hamid import liquidity
    from hamid.pump_radar import follower_lags

    btc = kc.get("BTCUSDT", "1h", 1000)
    bmap = {b["symbol"]: b for b in blocks}
    rows = []
    for sym in universe:
        c1h = kc.get(sym, "1h", 1000)
        if len(c1h) < 80:
            continue
        chg24 = round((c1h[-1]["c"] / c1h[-25]["c"] - 1) * 100, 1) if len(c1h) >= 25 else None
        chg1 = round((c1h[-1]["c"] / c1h[-2]["c"] - 1) * 100, 2)
        vols = [c["v"] for c in c1h[-101:-1]]
        m = sum(vols) / len(vols) if vols else 0
        sd = (sum((v - m) ** 2 for v in vols) / len(vols)) ** 0.5 if vols else 0
        volz = round((c1h[-1]["v"] - m) / sd, 1) if sd else None
        eps = pumps(c1h)
        beta, war_beta, war_n = beta_to_btc(c1h, btc)
        b = bmap.get(sym) or {}
        lag = None
        leader = (b.get("leaders") or [{}])[0].get("symbol") if b else None
        if leader and leader in bmap and bmap[leader].get("pumps"):
            lag = follower_lags(bmap[leader]["pumps"], eps)
            if lag:
                lag["leader"] = leader
        c15 = kc.get(sym, "15m", 240)
        try:
            liq = liquidity.read(c15) if len(c15) >= 30 else {}
        except Exception:                            # noqa: BLE001
            liq = {}
        p = {"symbol": sym, "price": c1h[-1]["c"],
             "chg_24h": chg24, "chg_1h": chg1, "vol_z": volz,
             "beta": beta, "war_beta": war_beta, "war_n": war_n,
             "pumps_n": len(eps),
             "pumps_max": max((e["ret_4h_pct"] for e in eps), default=None),
             "role": b.get("role"), "leader": leader, "lag": lag,
             "rsi_1h": rsi(c1h), "trend_1h": trend(c1h),
             "liq_magnet": liq.get("magnet")}
        p["character"] = character(p)
        rows.append(p)
    rows.sort(key=lambda p: -abs(p.get("chg_24h") or 0))
    rows = rows[:top]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": int(time.time() * 1000),
        "coins": rows,
        "note": ("شخصیت‌ها از کندل واقعی‌اند؛ بتای جنگ زیر ۵ رخداد و فاصلهٔ "
                 "دنباله‌روی زیر ۲ سابقه اصلاً ادعا نمی‌شود."),
    }, ensure_ascii=False, indent=1))
    return len(rows)
