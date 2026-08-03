#!/usr/bin/env python3
"""تست روش حمید روی کندل‌هایی که جوابشان از قبل معلوم است.

Every check here builds a series where the correct answer is known by
construction, so a wrong answer is unambiguous. That matters more than usual on
this module: the outputs are levels and boxes, which look plausible whatever
they are. A level engine that is subtly wrong does not crash — it just draws
lines somewhere else and keeps going.

    python3 -m hamid.selfcheck
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import orderblock as ob
from hamid.stack import read
from hamid.structure import channel, levels, reentry, swings, trend

R = []


def check(name, ok, detail=""):
    R.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<48} {detail}")
    return ok


def bar(t, o, h, l, c, v=100.0):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def series(prices, spread=0.4):
    """A candle per price, with sane wicks around it.

    The wick length varies slightly per bar on purpose. A fixed spread makes a
    reversal bar and the bar after it share an identical high — both are
    max(open, close) + spread of the same number — and a swing detector then
    sees a two-bar plateau where the data meant a peak. Real candles do produce
    equal highs (that is what a double top is), so the detector handles them by
    taking the last of the plateau; but a fixture should not manufacture one on
    every single turn, or it tests the tie-break instead of the rule.
    """
    out = []
    for i, p in enumerate(prices):
        o = prices[i - 1] if i else p
        w = spread * (1 + (i % 5) * 0.17)
        hi = max(o, p) + w
        lo = min(o, p) - spread * (1 + ((i + 2) % 5) * 0.17)
        out.append(bar(1_700_000_000_000 + i * 900_000, o, hi, lo, p))
    return out


# ── سقف و کف ────────────────────────────────────────────────────────────────
def t_swings():
    cd = series([10, 11, 12, 13, 12, 11, 10, 11, 12, 13, 14, 13, 12])
    sw = swings(cd)
    highs = [s for s in sw if s.kind == "high"]
    lows = [s for s in sw if s.kind == "low"]
    return check("قله و دره پیدا می‌شود", len(highs) >= 1 and len(lows) >= 1,
                 f"{len(highs)} قله، {len(lows)} دره")


def t_level_kept_and_dropped():
    """یک سطح که قیمت بارها به آن واکنش نشان داده باید بماند، و سطحی که فقط
    یک بار لمس شده باید پاک شود — دقیقاً همان کاری که حمید با دست می‌کند."""
    p = []
    # a ceiling at 100 that price is rejected from three separate times
    for _ in range(3):
        p += [90, 94, 98, 100, 97, 92, 88, 91, 95, 99, 100, 96, 90]
    # and one lonely spike to 120 that never matters again
    p += [92, 120, 92, 90, 88, 90, 92, 90, 88, 90, 92, 90, 88, 90]
    cd = series(p)
    lv = levels(cd, min_reactions=2)
    near100 = [l for l in lv if abs(l.price - 100) < 2]
    near120 = [l for l in lv if abs(l.price - 120) < 2]
    ok = bool(near100) and not near120
    d = f"سطح ۱۰۰ با {near100[0].reactions if near100 else 0} واکنش نگه داشته شد"
    d += "، سطح ۱۲۰ پاک شد" if not near120 else "، ولی ۱۲۰ هم مانده ✗"
    return check("سطح پرواکنش می‌ماند، سطح تک‌برخورد پاک می‌شود", ok, d)


def t_trend():
    up = series([10 + i * 0.5 + (1 if i % 4 == 0 else 0) for i in range(80)])
    dn = series([50 - i * 0.5 - (1 if i % 4 == 0 else 0) for i in range(80)])
    a, b = trend(up), trend(dn)
    return check("روند صعودی و نزولی درست خوانده می‌شود",
                 a == "up" and b == "down", f"صعودی→{a}، نزولی→{b}")


def t_range_admits_it():
    flat = series([100 + (2 if i % 2 else -2) for i in range(80)])
    t = trend(flat)
    return check("در بازار بی‌روند اعتراف می‌کند", t == "range", f"→ {t}")


# ── کانال ───────────────────────────────────────────────────────────────────
def t_channel_position():
    p = []
    for i in range(120):
        base = 100 + i * 0.3
        p.append(base + (4 if i % 8 < 4 else -4))
    cd = series(p)
    ch = channel(cd)
    ok = ch is not None and 0 <= ch.position <= 1
    return check("کانال کشیده می‌شود و جایگاه قیمت در آن معلوم است", ok,
                 f"جایگاه {round(ch.position, 2) if ch else '—'}، شیب {ch.slope if ch else '—'}")


def t_reentry_rule():
    """«از کانال بزند بیرون و برگردد و تثبیت بدهد» — باید تشخیص داده شود."""
    p = []
    for i in range(100):
        p.append(100 + (3 if i % 8 < 4 else -3))
    p += [118, 122, 119]                 # breaks out above
    p += [104, 101, 100, 99, 100]        # comes back in and settles
    cd = series(p)
    ch = channel(cd)
    re = reentry(cd, ch) if ch else None
    return check("خروج از کانال و تثبیت دوباره تشخیص داده می‌شود", re is not None,
                 f"{re['side']}, تارگت اول {round(re['target1'], 1)}" if re else "تشخیص نداد")


# ── اردر بلاک ───────────────────────────────────────────────────────────────
def t_body_beats_shadows():
    good = bar(0, 10, 10.6, 9.9, 10.5)       # body .5, wicks .1 + .1
    bad = bar(0, 10, 12.0, 8.0, 10.5)        # body .5, wicks 1.5 + 2.0
    return check("قانون «بدنه بزرگ‌تر از مجموع شدوها» درست پیاده شده",
                 ob.body_beats_shadows(good) and not ob.body_beats_shadows(bad),
                 "کندل بدنه‌دار قبول، کندل شدوبلند رد")


def t_orderblock_found_backwards():
    """کندل سبز بدنه‌دار، بعد ریزش — باید همان کندل سبز به‌عنوان بلاک برگردد."""
    # at least 30 bars: find() refuses shorter series, because a level engine
    # given twenty candles is guessing
    cd = series([50 + (0.3 if i % 2 else -0.3) for i in range(14)])
    cd.append(bar(0, 50, 52.3, 49.9, 52.0))          # decisive green
    for p in [50, 47, 44, 41, 38, 35, 33]:
        cd.append(bar(0, p + 2, p + 2.1, p - 0.2, p))
    for p in [35, 38, 41, 44, 47, 50, 51, 49, 46, 43, 45, 47, 44, 42]:
        cd.append(bar(0, p - 1, p + 0.4, p - 1.4, p))
    for i, c in enumerate(cd):
        c["t"] = 1_700_000_000_000 + i * 900_000
    blocks = ob.find(cd, "bullish")
    hit = [b for b in blocks if abs(b.high - 52.2) < 0.5]
    return check("اردر بلاک با برگشت به عقب پیدا می‌شود", bool(hit),
                 f"{len(blocks)} بلاک، برگشت به بلاک {hit[0].returns if hit else 0} بار")


def t_consumed_block_dropped():
    cd = series([50 + (0.3 if i % 2 else -0.3) for i in range(14)])
    cd.append(bar(0, 50, 52.3, 49.9, 52.0))
    for p in [50, 47, 44, 41, 38, 35, 33]:
        cd.append(bar(0, p + 2, p + 2.1, p - 0.2, p))
    for p in [36, 40, 45, 50, 55, 60, 65, 70, 74, 78]:   # blows clean through it
        cd.append(bar(0, p - 2, p + 0.3, p - 2.3, p))
    for i, c in enumerate(cd):
        c["t"] = 1_700_000_000_000 + i * 900_000
    blocks = [b for b in ob.find(cd, "bullish") if b.valid]
    return check("بلاکی که قیمت از آن رد شده دیگر معتبر نیست", not blocks,
                 f"{len(blocks)} بلاک معتبر مانده")


def t_fvg_unfilled_only():
    cd = series([10] * 5)
    cd.append(bar(0, 10, 10.2, 9.9, 10.1))
    cd.append(bar(0, 10.1, 14.0, 10.1, 13.8))        # the gap bar
    cd.append(bar(0, 13.8, 14.2, 12.0, 13.0))        # low 12 > prev high 10.2
    for p in [13, 13.4, 13.1, 13.6]:
        cd.append(bar(0, p, p + 0.3, p - 0.3, p))
    for i, c in enumerate(cd):
        c["t"] = 1_700_000_000_000 + i * 900_000
    gaps = ob.fvg(cd)
    return check("FVG مصرف‌نشده گزارش می‌شود", len(gaps) >= 1,
                 f"{len(gaps)} گپ باز")


# ── کل استک ─────────────────────────────────────────────────────────────────
def t_stack_runs_and_refuses():
    """روی داده‌ای که هیچ ستاپی ندارد، باید ستاپ ندهد — نه اینکه چیزی بسازد."""
    flat = series([100 + (0.5 if i % 2 else -0.5) for i in range(200)])
    r = read("TESTUSDT", flat, flat, flat)
    return check("روی بازار بی‌ساختار ستاپ نمی‌سازد", r.setup is None,
                 f"روند ۴ساعته {r.trend_4h}، ستاپ {'ندارد' if not r.setup else 'دارد ✗'}")


def t_stack_produces_a_read():
    p = []
    for i in range(300):
        p.append(200 - i * 0.3 + (5 if i % 10 < 5 else -5))
    cd = series(p)
    r = read("TESTUSDT", cd, cd, cd)
    ok = r.trend_4h in ("up", "down", "range") and isinstance(r.levels_4h, list)
    return check("استک سه‌تایم‌فریمی یک خوانش کامل می‌دهد", ok,
                 f"روند {r.trend_4h}، {len(r.levels_4h)} سطح، {len(r.blocks)} بلاک")


def t_setup_stop_is_beyond_the_block():
    """استاپ باید بالاتر از لبهٔ بلاک باشد، نه روی آن — «که شکار نشوم»."""
    p = []
    for i in range(200):
        p.append(200 - i * 0.4 + (6 if i % 12 < 6 else -6))
    cd = series(p)
    r = read("TESTUSDT", cd, cd, cd)
    if not r.setup:
        return check("استاپ بیرون از بلاک گذاشته می‌شود", True,
                     "ستاپی تشکیل نشد (قابل قبول)")
    s = r.setup
    beyond = (s["sl"] > s["block"]["high"]) if s["dir"] == "SHORT" \
        else (s["sl"] < s["block"]["low"])
    return check("استاپ بیرون از بلاک گذاشته می‌شود", beyond,
                 f"{s['dir']} استاپ {s['sl']} در برابر لبهٔ {s['block']['high'] if s['dir']=='SHORT' else s['block']['low']}")


def main():
    print("\nروش حمید — تست روی داده‌ای که جوابش معلوم است\n")
    print("سقف و کف")
    t_swings(); t_level_kept_and_dropped(); t_trend(); t_range_admits_it()
    print("\nکانال")
    t_channel_position(); t_reentry_rule()
    print("\nاردر بلاک")
    t_body_beats_shadows(); t_orderblock_found_backwards()
    t_consumed_block_dropped(); t_fvg_unfilled_only()
    print("\nاستک کامل")
    t_stack_runs_and_refuses(); t_stack_produces_a_read()
    t_setup_stop_is_beyond_the_block()

    bad = [(n, d) for ok, n, d in R if not ok]
    print(f"\n{'=' * 70}")
    print(f"{len(R) - len(bad)} از {len(R)} تست قبول")
    for n, d in bad:
        print(f"  · {n} — {d}")
    print("=" * 70)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
