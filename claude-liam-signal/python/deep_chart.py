#!/usr/bin/env python3
"""چارت تحلیل عمیق تک‌نماد — دستور حمید (۱۴ اوت): «همه چیز در چارت نشان داده شود».

فرق با chart.py: آن یکی چارت *یک ستاپ* است — کندل، اردر بلاک، ورود/استاپ/
تارگت. این یکی چارت *یک تحلیل کامل* است و باید هر چیزی که انجین‌ها پیدا
کرده‌اند را نشان دهد، در دو قاب:

  قاب بالا (۱۵د یا ۵د): ستاپ و اجرا
    · کندل‌ها + حجم زیرشان
    · اردر بلاک‌های ob_intel با رنگِ گرید (A سبز/آبی پررنگ، B کم‌رنگ‌تر)
      و برچسبِ وضعیت (FRESH/MITIGATED/BREAKER…)
    · FVG فعال
    · استخرهای نقدینگی (سقف/کف برابر) به‌صورت خطوط نقطه‌چین با شمارش لمس
    · آهن‌ربای لیکویید
    · سطوح معتبر ۱۵د + کانال
    · ورود/استاپ/تارگت + مسیر سناریو

  قاب پایین (۱س): میدان نبرد
    · کندل ۱س
    · سطوح معتبر ۱س و ۴س (۴س ضخیم‌تر — اولویت تایم بالا)
    · کانال ۱س
    · اردر بلاک‌های ۱س/۴س
    · جای قیمت فعلی

قانون خط: هیچ خط تزئینی کشیده نمی‌شود. هر خط از یک انجین می‌آید و برچسبش
می‌گوید از کجا. اگر انجینی چیزی پیدا نکرد، آن لایه غایب است — نه ساختگی.

برچسب‌ها لاتین‌اند چون matplotlib شکل‌دهی فارسی ندارد و متن فارسی
حروف‌جدا و برعکس در می‌آید؛ توضیح فارسی در کپشن زیر عکس می‌رود.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BG = "#0b1017"
GRID = "#1b2532"
DIM = "#7f8ea3"
UP = "#2ecc71"
DOWN = "#e74c3c"
ENTRY = "#f0a92e"
TP = "#2ecc71"
SL = "#e74c3c"
LIQ = "#e6b800"          # استخر نقدینگی
FVG = "#9b59b6"          # گپ ارزش منصفانه
CH = "#5d8ecb"           # کانال
L4 = "#ff8c42"           # سطح ۴ ساعته — پررنگ‌تر، چون تایم بالا اولویت دارد
L1 = "#8fa8c8"           # سطح ۱ ساعته

# رنگ باکس بر اساس گرید مدرکی ob_intel — گرید بالاتر، پررنگ‌تر
GRADE_COLOR = {"A": "#3d8bfd", "B": "#4a90d9", "C": "#5a7fa8", "D": "#5f6b7a"}
GRADE_ALPHA = {"A": 0.26, "B": 0.18, "C": 0.11, "D": 0.07}


def _fmt(v):
    a = abs(v)
    if a >= 1000:
        return f"{v:,.1f}"
    if a >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if a >= 0.001:
        return f"{v:.6f}".rstrip("0").rstrip(".")
    return f"{v:.8f}".rstrip("0").rstrip(".")


def _watermark(ax):
    ax.text(0.5, 0.5, "@Trade_Osuli", transform=ax.transAxes,
            fontsize=30, color=DIM, alpha=0.11, ha="center", va="center",
            rotation=15, fontweight="bold", zorder=0)


def _candles(ax, cd, width=0.62):
    for i, c in enumerate(cd):
        up = c["c"] >= c["o"]
        col = UP if up else DOWN
        ax.plot([i, i], [c["l"], c["h"]], color=col, linewidth=0.8,
                solid_capstyle="round", zorder=2)
        lo, hi = (c["o"], c["c"]) if up else (c["c"], c["o"])
        ax.add_patch(Rectangle((i - width / 2, lo), width, max(hi - lo, 1e-12),
                               facecolor=col, edgecolor=col, linewidth=0.6, zorder=3))


def _boxes(ax, boxes, n, lo_px, hi_px, tf_tag="", cap=4, x0=0.5, max_h=0.22):
    """اردر بلاک‌ها با رنگِ گرید و برچسب وضعیت.

    سه صافی که چارت را خوانا نگه می‌دارد:
      · بیرون قاب → کشیده نمی‌شود
      · بلندتر از `max_h` کلِ قاب → کشیده نمی‌شود. باکسی که یک‌چهارم تصویر
        را می‌گیرد نه قابل معامله است نه چیزی نشان می‌دهد؛ فقط کندل را
        پنهان می‌کند.
      · برچسب‌ها پلکانی جابه‌جا می‌شوند تا روی هم نیفتند
    """
    drawn = 0
    span = max(hi_px - lo_px, 1e-12)
    for b in boxes or []:
        if b.get("grade") in (None, "REJECT"):
            continue
        blo, bhi = b.get("low"), b.get("high")
        if blo is None or bhi is None:
            continue
        if bhi < lo_px or blo > hi_px:            # بیرون قاب
            continue
        if (bhi - blo) / span > max_h:            # آن‌قدر بلند که چیزی نمی‌گوید
            continue
        g = b.get("grade", "D")
        col = GRADE_COLOR.get(g, "#5f6b7a")
        ax.add_patch(Rectangle((-0.5, blo), n, max(bhi - blo, 1e-12),
                               facecolor=col, alpha=GRADE_ALPHA.get(g, 0.08),
                               edgecolor=col, linewidth=1.2,
                               linestyle="-" if g in ("A", "B") else "--", zorder=1))
        state = (b.get("state") or "").replace("_", " ")[:14]
        tag = f"OB{tf_tag} {g}"
        if state:
            tag += f"·{state}"
        if b.get("hunts"):
            tag += f"·{b['hunts']}H"
        ax.text(n * (x0 + drawn * 0.17) % max(n * 0.75, 1), bhi, tag, color=col,
                fontsize=6.8, va="bottom", ha="left", zorder=6,
                family="monospace", alpha=0.95)
        drawn += 1
        if drawn >= cap:
            break


def _levels(ax, lvls, n, color, prefix, lo_px, hi_px, lw=0.9, cap=5):
    for l in (lvls or [])[:cap]:
        p = l.get("price")
        if p is None or p < lo_px or p > hi_px:
            continue
        style = "-" if l.get("flipped") else ":"
        ax.plot([-0.5, n - 0.5], [p, p], color=color, linewidth=lw,
                linestyle=style, alpha=0.8, zorder=2)
        mark = "R" if l.get("kind") == "high" else "S"
        lab = f"{prefix}{mark}{l.get('reactions', '')}"
        if l.get("flipped"):
            lab += "*"                            # ستاره = نقش عوض کرده
        ax.text(-0.5, p, lab, color=color, fontsize=7.0, va="bottom",
                ha="left", family="monospace", zorder=5)


def _channel(ax, ch, n, color=CH):
    """کانال با مقدار «الان» — دو سر خط از upper_now/lower_now بازسازی می‌شود."""
    if not ch:
        return
    up_now, lo_now = ch.get("upper_now"), ch.get("lower_now")
    if up_now is None or lo_now is None:
        return
    for y in (up_now, lo_now):
        ax.plot([-0.5, n - 0.5], [y, y], color=color, linewidth=1.0,
                alpha=0.55, linestyle="-.", zorder=2)
    mid = ch.get("mid_now")
    if mid is not None:
        ax.plot([-0.5, n - 0.5], [mid, mid], color=color, linewidth=0.8,
                alpha=0.35, linestyle=":", zorder=2)
    ax.text(n - 0.5, up_now, f"CH {ch.get('slope','')}", color=color,
            fontsize=7.0, va="bottom", ha="right", family="monospace", zorder=5)


def _liquidity(ax, liq, n, lo_px, hi_px):
    """استخرهای نقدینگی — سقف/کف برابر که استاپ پشتشان جمع است."""
    if not liq:
        return
    for side, col in (("above", LIQ), ("below", LIQ)):
        for g in (liq.get(side) or [])[:3]:
            p = g.get("price")
            if p is None or p < lo_px or p > hi_px:
                continue
            ax.plot([-0.5, n - 0.5], [p, p], color=col, linewidth=1.0,
                    linestyle=(0, (6, 3)), alpha=0.7, zorder=2)
            ax.text(n * 0.55, p, f"LIQ {g.get('touches','')}x", color=col,
                    fontsize=6.8, va="bottom", ha="left", family="monospace",
                    zorder=5, alpha=0.9)


def _fvgs(ax, fvgs, n, lo_px, hi_px):
    for f in (fvgs or [])[:3]:
        flo, fhi = f.get("low"), f.get("high")
        if flo is None or fhi is None or fhi < lo_px or flo > hi_px:
            continue
        ax.add_patch(Rectangle((-0.5, flo), n, max(fhi - flo, 1e-12),
                               facecolor=FVG, alpha=0.10, edgecolor=FVG,
                               linewidth=0.8, linestyle=":", zorder=1))
        ax.text(n * 0.30, fhi, "FVG", color=FVG, fontsize=6.8, va="bottom",
                ha="left", family="monospace", zorder=5, alpha=0.9)


def render(deep, cds, path, bars_lo=120, bars_hi=140):
    """deep: خروجی hamid.deep.analyze · cds: {'c1h','c15','c5',...}"""
    sym = deep.get("symbol", "")
    price = deep.get("price")
    setup = deep.get("setup") or {}
    struct = deep.get("structure") or {}
    obs = deep.get("order_blocks") or {}

    c_lo = (cds.get("c15") or [])[-bars_lo:]     # قاب بالا: ستاپ
    c_hi = (cds.get("c1h") or [])[-bars_hi:]     # قاب پایین: میدان نبرد
    if len(c_lo) < 10 or len(c_hi) < 10:
        raise ValueError("کندل کافی برای رسم نیست")

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(13.5, 10.4), dpi=110,
        gridspec_kw={"height_ratios": [1.35, 1.0], "hspace": 0.17})
    fig.patch.set_facecolor(BG)

    # ══ قاب بالا — ۱۵ دقیقه: ستاپ و اجرا ══════════════════════════════════
    ax.set_facecolor(BG)
    _watermark(ax)
    n = len(c_lo)
    _candles(ax, c_lo)

    lo_px = min(c["l"] for c in c_lo)
    hi_px = max(c["h"] for c in c_lo)
    for y in (setup.get("entry"), setup.get("sl"), setup.get("tp1"), setup.get("tp2")):
        if y is not None:
            lo_px, hi_px = min(lo_px, y), max(hi_px, y)
    span = hi_px - lo_px
    lo_v, hi_v = lo_px - span * 0.10, hi_px + span * 0.10

    _boxes(ax, obs.get("15m"), n, lo_v, hi_v, tf_tag="15m")
    _fvgs(ax, (deep.get("hamid_read") or {}).get("fvgs"), n, lo_v, hi_v)
    _liquidity(ax, deep.get("liquidity"), n, lo_v, hi_v)
    _levels(ax, (struct.get("m15") or {}).get("levels"), n, L1, "", lo_v, hi_v)
    _channel(ax, (struct.get("m15") or {}).get("channel"), n)

    def level(y, color, label, style="-", lw=1.3):
        if y is None:
            return
        ax.plot([-0.5, n - 0.5], [y, y], color=color, linewidth=lw,
                linestyle=style, alpha=0.95, zorder=4)
        ax.text(n + 0.8, y, f"{label} {_fmt(y)}", color=color, fontsize=8.2,
                va="center", ha="left", zorder=6, family="monospace")

    level(setup.get("entry"), ENTRY, "ENTRY")
    level(setup.get("sl"), SL, "SL")
    level(setup.get("tp1"), TP, "TP1", style="--")
    level(setup.get("tp2"), TP, "TP2", style=":", lw=1.0)

    # مسیر سناریو
    if setup.get("tp1"):
        px, py = [n - 1], [c_lo[-1]["c"]]
        for t in (setup.get("tp1"), setup.get("tp2")):
            if t:
                px.append(px[-1] + 5)
                py.append(t)
        ax.plot(px, py, color="#ab47bc", linewidth=1.5, linestyle="--",
                marker=">", markersize=5, alpha=0.9, zorder=5)

    # آهن‌ربای لیکویید
    lm = deep.get("liq_map") or {}
    if lm.get("magnet"):
        ax.text(0.5, 0.965, f"LIQ MAGNET: {lm['magnet']}", transform=ax.transAxes,
                color=LIQ, fontsize=8.0, ha="center", va="top",
                family="monospace", alpha=0.9, zorder=7)

    ax.set_ylim(lo_v, hi_v)
    ax.set_xlim(-1, n * 1.22)

    direction = setup.get("dir")
    col_dir = UP if direction == "LONG" else DOWN if direction == "SHORT" else DIM
    head = f"{sym}   15m   " + (direction or "NO SETUP")
    ax.text(0, 1.075, head, transform=ax.transAxes, color=col_dir,
            fontsize=13.5, fontweight="bold", va="bottom", ha="left",
            family="monospace")

    bits = [f"{_fmt(price)}" if price else "",
            f"4H {(struct.get('h4') or {}).get('trend','?')}",
            f"1H {(struct.get('h1') or {}).get('trend','?')}",
            f"15m {(struct.get('m15') or {}).get('trend','?')}"]
    if setup.get("rr"):
        bits.append(f"R:R {setup['rr']}")
    if deep.get("engines_ok") is not None:
        bits.append(f"engines {deep['engines_ok']}/9")
    ax.text(0, 1.012, "   ·   ".join(b for b in bits if b),
            transform=ax.transAxes, color=DIM, fontsize=8.4, va="bottom",
            ha="left", family="monospace")

    ax.grid(color=GRID, linewidth=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(colors=DIM, labelsize=8)
    ax.set_xticks([])
    for lbl in ax.get_yticklabels():
        lbl.set_family("monospace")

    # ══ قاب پایین — ۱ ساعته: میدان نبرد ═══════════════════════════════════
    ax2.set_facecolor(BG)
    n2 = len(c_hi)
    _candles(ax2, c_hi, width=0.58)
    lo2 = min(c["l"] for c in c_hi)
    hi2 = max(c["h"] for c in c_hi)
    span2 = hi2 - lo2
    lo2v, hi2v = lo2 - span2 * 0.06, hi2 + span2 * 0.06

    # ۴س اول و کم‌شمار — تایم بالا مهم‌تر است ولی باکسش هم بزرگ‌تر، پس
    # سقف سخت‌گیرانه‌تری می‌گیرد تا میدان نبرد زیر باکس دفن نشود.
    _boxes(ax2, obs.get("4h"), n2, lo2v, hi2v, tf_tag="4h", cap=2, x0=0.05, max_h=0.18)
    _boxes(ax2, obs.get("1h"), n2, lo2v, hi2v, tf_tag="1h", cap=3, x0=0.42, max_h=0.14)
    # ۴س ضخیم‌تر — تایم بالا بر پایین اولویت دارد
    _levels(ax2, (struct.get("h4") or {}).get("levels"), n2, L4, "4H·", lo2v, hi2v, lw=1.4, cap=6)
    _levels(ax2, (struct.get("h1") or {}).get("levels"), n2, L1, "1H·", lo2v, hi2v, lw=0.9, cap=5)
    _channel(ax2, (struct.get("h1") or {}).get("channel"), n2)

    if price is not None:
        ax2.plot([-0.5, n2 - 0.5], [price, price], color=ENTRY, linewidth=1.0,
                 linestyle="-", alpha=0.55, zorder=4)
        ax2.text(n2 + 0.5, price, f"NOW {_fmt(price)}", color=ENTRY,
                 fontsize=8.0, va="center", ha="left", family="monospace", zorder=6)

    ax2.set_ylim(lo2v, hi2v)
    ax2.set_xlim(-1, n2 * 1.22)
    ax2.text(0, 1.020, f"1H   battlefield   ·   4H {(struct.get('h4') or {}).get('trend','?')}"
                       f"   ·   {(struct.get('h1') or {}).get('bars','?')} bars",
             transform=ax2.transAxes, color=DIM, fontsize=8.4, va="bottom",
             ha="left", family="monospace")
    ax2.grid(color=GRID, linewidth=0.6, alpha=0.5)
    ax2.set_axisbelow(True)
    for sp in ax2.spines.values():
        sp.set_color(GRID)
    ax2.tick_params(colors=DIM, labelsize=8)
    ax2.set_xticks([])
    for lbl in ax2.get_yticklabels():
        lbl.set_family("monospace")

    ax2.text(1.0, -0.05, "Hamid Signal Agent · deep single-symbol",
             transform=ax2.transAxes, color=DIM, fontsize=7.5, ha="right",
             va="top", family="monospace")

    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return path
