#!/usr/bin/env python3
"""چهار ساعته → یک ساعته → پانزده دقیقه، به همان ترتیبی که حمید کار می‌کند.

    ۱. ۴ ساعته  → سقف/کف بکش، ادامه بده، معتبرها را نگه دار
    ۲. ۱ ساعته  → همان کار + کانال
    ۳. ۴ ساعته  → مقاومت/حمایت + تعیین روند
    ۴. ۱ ساعته  → اردر بلاک + FVG مصرف‌نشده
    ۵. ۱۵ دقیقه → سقف/کف + روند + انتظار پولبک دوم
    ۶. لیمیت روی اردر بلاک، استاپ کمی بالاتر از هانت نقدینگی

And before any of it: «بیت‌کوین را اول از همه تحلیل می‌کنم، چون پرچم این مارکت
است» — plus USDT dominance and BTC dominance, which say whether there is money
coming in at all and whether it is going to Bitcoin or to the alts.

What this module does *not* do is decide. It produces the read. Whether a read
becomes a signal is the engine's business, and whether that signal was any good
is the backtest's — the whole point of writing the method down is that it can
now be argued with by measurement.
"""
from dataclasses import dataclass, asdict

from hamid import orderblock as ob_mod
from hamid.structure import Channel, atr, channel, levels, reentry, trend


@dataclass
class Read:
    symbol: str
    trend_4h: str
    trend_1h: str
    trend_15m: str
    position_1h: float or None       # where in the 1H channel price sits
    channel_note: str
    levels_4h: list
    levels_1h: list
    blocks: list
    fvgs: list
    setup: dict or None
    notes: list


def _lv(l):
    return {"price": round(l.price, 8), "kind": l.kind, "touches": l.touches,
            "reactions": l.reactions, "flipped": l.flipped}


def _ob(o):
    return {"low": round(o.low, 8), "high": round(o.high, 8), "dir": o.dir,
            "returns": o.returns, "impulse": round(o.impulse, 2),
            "valid": o.valid, "second": o.second_pullback}


def read(symbol, c4h, c1h, c15m):
    """The whole stack for one symbol. Any timeframe may be short; the read
    then says less rather than guessing more."""
    notes = []

    # ۱ و ۳ — چهار ساعته
    t4 = trend(c4h) if len(c4h) >= 30 else "range"
    lv4 = levels(c4h) if len(c4h) >= 30 else []

    # ۲ — یک ساعته: کانال
    ch = channel(c1h) if len(c1h) >= 40 else None
    t1 = trend(c1h) if len(c1h) >= 30 else "range"
    lv1 = levels(c1h) if len(c1h) >= 30 else []

    pos = round(ch.position, 3) if ch else None
    cnote = "کانالی تشکیل نشده"
    if ch:
        where = ("نزدیک سقف کانال" if ch.position > 0.75 else
                 "نزدیک کف کانال" if ch.position < 0.25 else "میانهٔ کانال")
        cnote = f"{where} (شیب {ch.slope})"
    re = reentry(c1h, ch) if ch else None
    if re:
        cnote += " — از کانال خارج شد و برگشت و تثبیت داد"
        notes.append("قانون کانال فعال است: تارگت اول میدلاین، بعد سمت مقابل")

    # ۴ — یک ساعته: اردر بلاک و FVG
    # «بعد از مشخص شدن روند» — the 4H direction decides which side we want.
    want = "bearish" if t4 == "down" else "bullish" if t4 == "up" else None
    blocks = []
    for d in (["bearish", "bullish"] if want is None else [want]):
        blocks += ob_mod.find(c1h, d)
    blocks = [b for b in blocks if b.valid]
    blocks.sort(key=lambda b: (-b.returns, -b.impulse))
    fvgs = ob_mod.fvg(c1h)

    # ۵ — پانزده دقیقه
    t15 = trend(c15m) if len(c15m) >= 30 else "range"

    setup = _setup(symbol, c15m, blocks, lv4 + lv1, t4, t1, t15, ch, re, notes)

    return Read(symbol=symbol, trend_4h=t4, trend_1h=t1, trend_15m=t15,
                position_1h=pos, channel_note=cnote,
                levels_4h=[_lv(l) for l in lv4[:8]],
                levels_1h=[_lv(l) for l in lv1[:8]],
                blocks=[_ob(b) for b in blocks[:6]],
                fvgs=fvgs[:6], setup=setup, notes=notes)


def _near_level(price, lvls, tol):
    for l in lvls:
        if abs(price - l.price) <= tol:
            return l
    return None


def _setup(symbol, c15m, blocks, lvls, t4, t1, t15, ch, re, notes):
    """«اگر روی سقف یا کفی اردر بلاک باشد، می‌دانیم آنجا می‌شود لیمیت گذاشت»

    The entry Hamid describes needs three things to line up, and it refuses
    rather than settles when they do not:

      · a block that price has already returned to once (تقریباً معتبر)
      · that block sitting on a level that has proven itself (سقف یا کف معتبر)
      · the 4H direction agreeing with the side of the trade

    The stop is «کمی بالاتر» — above the liquidity that gets hunted just beyond
    the block, not on its edge, because the edge is exactly where the stop hunt
    is aimed.
    """
    if not c15m or not blocks:
        return None
    # «بعد از مشخص شدن روند ارز می‌آیم توی تایم یک ساعته» — the 4H direction is
    # a precondition of the method, not a filter applied afterwards. Without it
    # there is nothing for the 1H channel position to be relative to.
    #
    # This was caught by a test rather than by reading: on a flat series with no
    # structure at all the stack still produced a setup, because "range" fell
    # through both of the direction checks below instead of stopping here.
    if t4 == "range":
        notes.append("روند ۴ ساعته مشخص نیست — طبق روش، ستاپی گرفته نمی‌شود")
        return None
    price = c15m[-1]["c"]
    a15 = atr(c15m) or price * 0.003

    for b in blocks:
        if not b.second_pullback and b.returns < 1:
            continue
        direction = "SHORT" if b.dir == "bearish" else "LONG"
        if t4 == "down" and direction != "SHORT":
            continue
        if t4 == "up" and direction != "LONG":
            continue
        lvl = _near_level(b.mid, lvls, max(a15 * 2, b.mid * 0.002))
        if lvl is None:
            continue                     # a block not sitting on a level is not his setup

        entry = b.mid
        # «هانت نقدینگی بالای اردر بلاک … استاپ را کمی بالاتر تنظیم می‌کنم»
        hunt = a15 * 0.8
        sl = (b.high + hunt) if direction == "SHORT" else (b.low - hunt)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp1 = entry - risk * 1.5 if direction == "SHORT" else entry + risk * 1.5
        tp2 = entry - risk * 2.5 if direction == "SHORT" else entry + risk * 2.5
        if ch and re:
            i = len(c15m) - 1
            notes.append("تارگت کانالی هم فعال است")

        return {
            "dir": direction,
            "entry": round(entry, 8),
            "sl": round(sl, 8),
            "tp1": round(tp1, 8),
            "tp2": round(tp2, 8),
            "rr": round(abs(tp1 - entry) / risk, 2),
            "block": _ob(b),
            "on_level": _lv(lvl),
            "stage": "پولبک دوم" if b.second_pullback else "پولبک اول",
            "waiting": not b.second_pullback,
            "why": (f"روند ۴ساعته {t4}؛ اردر بلاک روی سطحی با "
                    f"{lvl.reactions} واکنش؛ استاپ بالای هانت نقدینگی"),
        }
    return None


def market_first(btc, usdt_d, btc_d):
    """«بیت‌کوین را اول از همه … دامیننس تتر … دامیننس بیت»

    Three reads that come before any coin. USDT dominance rising means money
    leaving the market; BTC dominance rising means what money there is going to
    Bitcoin rather than the alts. Neither is a signal on its own — they decide
    whether the day is one for taking alt longs at all.
    """
    out = {}
    for name, cd in (("BTC", btc), ("USDT.D", usdt_d), ("BTC.D", btc_d)):
        if not cd or len(cd) < 40:
            out[name] = {"trend": "unknown", "note": "کندل کافی نیست"}
            continue
        ch = channel(cd)
        out[name] = {
            "trend": trend(cd),
            "position": round(ch.position, 3) if ch else None,
            "slope": ch.slope if ch else None,
            "reentry": bool(reentry(cd, ch)) if ch else False,
        }

    verdict = "نامشخص"
    u, b = out.get("USDT.D", {}), out.get("BTC", {})
    if u.get("trend") == "up":
        verdict = "دامیننس تتر صعودی — پول از بازار بیرون می‌رود، لانگ آلت محتاطانه"
    elif u.get("trend") == "down" and b.get("trend") == "up":
        verdict = "دامیننس تتر نزولی و بیت صعودی — شرایط برای لانگ مساعد است"
    elif b.get("trend") == "down":
        verdict = "بیت‌کوین نزولی — پرچم بازار پایین است، شورت اولویت دارد"
    out["verdict"] = verdict
    return out
