#!/usr/bin/env python3
"""آیا یادگیری، دلیلِ الکی را رد می‌کند؟

This is the test that matters for what Hamid asked: «بر اساس دلایل درست یاد
بگیری». Recording trades is easy. The failure mode is attribution — with twelve
conditions and forty trades, some will look predictive by pure chance, and a
loop that acts on those degrades every cycle while appearing to learn.

So the check is adversarial: feed it trades whose outcomes are *independent* of
every recorded condition, and require it to find nothing. Then feed it a real
relationship and require it to find that.

    python3 -m hamid.test_paper
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import paper                                       # noqa: E402
import brain                                                  # noqa: E402

# هیچ ردپای تستی در brain واقعی نمی‌نشیند — درس تکراری ۱۲ اوت: reasons()
# الگوی «تأییدشده»ی ساختگی را با save_pattern و room_log در مخزن می‌نوشت.
brain.save_pattern = lambda *a, **k: None
brain.room_log = lambda *a, **k: None

R = []


def check(name, ok, detail=""):
    R.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<52} {detail}")


def fake(n, seed, rule=None):
    """Trades with random conditions. `rule(why) -> bool` makes the outcome
    depend on a condition; without it outcomes are pure noise."""
    random.seed(seed)
    out = []
    for _ in range(n):
        why = {
            "dir": random.choice(["LONG", "SHORT"]),
            "trend_4h": random.choice(["up", "down"]),
            "impulse": random.uniform(4, 15),
            "returns": random.randint(1, 5),
            "reactions": random.randint(2, 9),
            "flipped": random.random() < 0.4,
            "stop_pct": random.uniform(0.5, 8),
            "fear": random.randint(10, 80),
            "funding": random.uniform(-0.01, 0.01),
            "usdt_dom": random.uniform(6, 10),
        }
        if rule is None:
            R_ = 1.5 if random.random() < 0.42 else -1.0
        else:
            p = 0.75 if rule(why) else 0.20
            R_ = 1.5 if random.random() < p else -1.0
        out.append({"R": R_, "why": why})
    return out


def with_book(trades, fn):
    """Run against a throwaway book so the real one is never touched."""
    import tempfile
    d = Path(tempfile.mkdtemp())
    old = paper.CLOSED, paper.OPEN, paper.EQUITY, paper.BOOK
    # BOOK هم منحرف می‌شود. نسخهٔ قبلی فقط سه فایل اول را عوض می‌کرد و
    # reasons() که در BOOK می‌نویسد، «قوانین تأییدشده»ی ساختگیِ تست را در
    # brain واقعی نوشت — و چرخهٔ واقعی همان‌ها را در رتبه‌بندی اعمال کرد.
    # دقیقاً همان مسموم شدنی که کل این معماری برای جلوگیری از آن ساخته شده،
    # این بار از در پشتیِ خود تست.
    paper.CLOSED, paper.OPEN, paper.EQUITY, paper.BOOK = \
        d / "c.jsonl", d / "o.jsonl", d / "e.json", d
    for t in trades:
        paper._append(paper.CLOSED, t)
    try:
        return fn()
    finally:
        paper.CLOSED, paper.OPEN, paper.EQUITY, paper.BOOK = old


def t_noise_finds_nothing():
    """۶۰ معامله با نتیجهٔ کاملاً تصادفی — نباید هیچ دلیلی پیدا کند."""
    worst = 0
    for seed in range(6):
        found = with_book(fake(60, seed), lambda: paper.reasons(verbose=False))
        worst = max(worst, len(found))
    check("روی دادهٔ کاملاً تصادفی هیچ دلیلی اعلام نمی‌کند", worst == 0,
          f"بیشترین دلیل کاذب در ۶ اجرا: {worst}")


def t_small_sample_refuses():
    found = with_book(fake(12, 1), lambda: paper.reasons(verbose=False))
    check("با نمونهٔ کم اصلاً نتیجه‌گیری نمی‌کند", found == [],
          "۱۲ معامله → هیچ")


def t_real_effect_is_found():
    """رابطهٔ واقعی و قوی باید پیدا شود، وگرنه فیلتر بیش از حد سخت است."""
    rule = lambda w: w["impulse"] >= 10
    found = with_book(fake(200, 7, rule), lambda: paper.reasons(verbose=False))
    hit = any("ضربهٔ بلاک ≥ ۱۰" in f["condition"] for f in found)
    check("رابطهٔ واقعی و قوی را پیدا می‌کند", hit,
          f"{len(found)} دلیل: {', '.join(f['condition'] for f in found) or '—'}")


def t_expired_not_scored():
    """سفارشی که پر نشده معامله نیست و نباید در موجودی اثر بگذارد."""
    import tempfile, json
    d = Path(tempfile.mkdtemp())
    old = paper.CLOSED, paper.EQUITY
    paper.CLOSED, paper.EQUITY = d / "c.jsonl", d / "e.json"
    try:
        paper._append(paper.CLOSED, {"R": None, "outcome": "expired", "why": {}})
        paper._append(paper.CLOSED, {"R": 1.5, "outcome": "target", "why": {}})
        eq = paper._equity()
        check("سفارش پر نشده در موجودی شمرده نمی‌شود", eq["trades"] == 1,
              f"{eq['trades']} معامله، موجودی ${eq['balance']}")
    finally:
        paper.CLOSED, paper.EQUITY = old


def t_stables_rejected():
    """کشف ۱۲ اوت: USD1/USDE با استاپ ذره‌ای R نجومی قلابی ساختند (+58R).
    استیبل و رپد از گلوگاه open_from وارد هیچ دفتری نمی‌شوند."""
    import tempfile
    d = Path(tempfile.mkdtemp())
    old = paper.OPEN
    paper.OPEN = d / "o.jsonl"
    try:
        # استاپ ۲٪ — قرارداد ۱۷ اوت: دفتر سیگنال‌گرید ورودِ استاپ‌تنگ
        # (کارمزد ≥0.25R) نمی‌گیرد؛ فیکسچر قدیمی 0.1٪ بود و رد می‌شد.
        sig = {"dir": "LONG", "entry": 1.0, "sl": 0.98, "tp1": 1.04,
               "waiting": False}
        n = paper.open_from([dict(sig, symbol="USD1USDT"),
                             dict(sig, symbol="USDEUSDT"),
                             dict(sig, symbol="WBTCUSDT"),
                             dict(sig, symbol="SOLUSDT")], {})
        opened = [json.loads(l)["sym"] for l in paper.OPEN.read_text().splitlines()]
        check("استیبل/رپد رد شد و ارز واقعی باز شد",
              n == 1 and opened == ["SOLUSDT"], f"opened={opened}")
    finally:
        paper.OPEN = old


def t_viability_gate():
    """قرارداد ۱۷ اوت: کالبدشکافی ۲۵۵ استاپ نشان داد نصفشان تلهٔ کارمزد
    بودند. دفتر سیگنال‌گرید ورودِ استاپ‌تنگ نمی‌گیرد؛ دفتر آزمایش می‌گیرد."""
    import tempfile
    d = Path(tempfile.mkdtemp())
    old = paper.OPEN
    paper.OPEN = d / "o.jsonl"
    try:
        tight = {"dir": "LONG", "entry": 1.0, "sl": 0.999, "tp1": 1.002,
                 "waiting": False, "symbol": "SOLUSDT"}
        n = paper.open_from([tight], {})
        check("سیگنال‌گرید با استاپ 0.1٪ رد شد", n == 0, f"n={n}")
        exp = dict(tight, stage_tag="vetoed")
        n = paper.open_from([exp], {})
        check("دفتر آزمایش (vetoed) همان ورود را گرفت", n == 1, f"n={n}")
    finally:
        paper.OPEN = old


def t_no_candle_expiry():
    """عیب‌یابی ۱۳ اوت: نماد بی‌کندل (دیلیست‌شده) تا ابد در دفتر باز می‌ماند —
    ۲۷ اردر با عمر ۸۴ ساعت پیدا شد. حالا بعد از مهلت بسته می‌شود."""
    import tempfile, time as _t
    d = Path(tempfile.mkdtemp())
    old = (paper.CLOSED, paper.OPEN, paper.EQUITY, paper._candles_since)
    paper.CLOSED, paper.OPEN, paper.EQUITY = d / "c.jsonl", d / "o.jsonl", d / "e.json"
    paper._candles_since = lambda sym, since: []
    now = _t.time() * 1000
    try:
        paper._append(paper.OPEN, {"sym": "DEADUSDT", "dir": "LONG", "entry": 1.0,
                                   "sl": 0.99, "tp1": 1.02, "tp2": None,
                                   "opened": int(now - 90 * 3600e3), "filled": None,
                                   "why": {"stage": "alarm"}})
        paper._append(paper.OPEN, {"sym": "FRESHUSDT", "dir": "LONG", "entry": 1.0,
                                   "sl": 0.99, "tp1": 1.02, "tp2": None,
                                   "opened": int(now - 2 * 3600e3), "filled": None,
                                   "why": {"stage": "alarm"}})
        still, closed = paper.mark()
        cl = paper._read(paper.CLOSED)
        check("اردر بی‌کندلِ گذشته از مهلت منقضی شد، تازه‌اش نه",
              closed == 1 and still == 1 and cl[0]["sym"] == "DEADUSDT"
              and cl[0]["outcome"] == "expired" and cl[0]["R"] is None,
              f"closed={closed} still={still}")
    finally:
        paper.CLOSED, paper.OPEN, paper.EQUITY, paper._candles_since = old


def t_trailing_stop():
    """قانون تریل حمید (درس EURI): ⅓ مسیر تارگت → استاپ در سودِ کارمزددار؛
    ⅔ → استاپ در ⅓؛ برگشتِ کامل دیگر ضرر نمی‌سازد."""
    import tempfile, time as _t
    d = Path(tempfile.mkdtemp())
    old = (paper.CLOSED, paper.OPEN, paper.EQUITY, paper._candles_since)
    paper.CLOSED, paper.OPEN, paper.EQUITY = d / "c.jsonl", d / "o.jsonl", d / "e.json"
    now = int(_t.time() * 1000)
    H5 = 300_000

    def bar(i, h, l):
        return {"t": now - (40 - i) * H5, "o": (h + l) / 2, "h": h, "l": l,
                "c": (h + l) / 2, "v": 1.0}

    # سناریوی EURI: ورود ۱۰۰، استاپ ۹۹، تارگت ۱۰۳؛ قیمت تا ۱۰۱.۲ (>⅓=۱۰۱)
    # می‌رود و بعد تا ۹۸ برمی‌گردد → باید تریل در سود ببندد، نه استاپ کامل
    euri = [bar(0, 100.2, 99.8), bar(1, 101.2, 100.0), bar(2, 100.4, 99.6),
            bar(3, 99.8, 98.0)]
    # سناریوی ⅔: تا ۱۰۲.۱ می‌رود (>⅔=۱۰۲) بعد کامل برمی‌گردد → استاپ در ⅓=۱۰۱
    deep = [bar(0, 100.2, 99.8), bar(1, 102.1, 100.0), bar(2, 101.5, 100.8),
            bar(3, 99.5, 98.0)]
    series = {"EURIUSDT": euri, "DEEPUSDT": deep}
    paper._candles_since = lambda sym, since: series[sym]
    try:
        for sym in series:
            paper._append(paper.OPEN, {"sym": sym, "dir": "LONG", "entry": 100.0,
                                       "sl": 99.0, "tp1": 103.0, "tp2": None,
                                       "opened": now - 40 * H5,
                                       "filled": now - 40 * H5, "why": {"stage": "second"}})
        paper.mark()
        closed = paper._read(paper.CLOSED)
        e = next(t for t in closed if t["sym"] == "EURIUSDT")
        check("EURI: تریل در سودِ کارمزددار بست، نه استاپ کامل",
              e["outcome"] == "trail" and 0 < e["R"] < 0.3,
              f"outcome={e['outcome']} R={e['R']}")
        dp = next(t for t in closed if t["sym"] == "DEEPUSDT")
        check("⅔ مسیر → استاپ در ⅓ مسیر (R≈+۱)",
              dp["outcome"] == "trail" and 0.9 <= dp["R"] <= 1.1,
              f"outcome={dp['outcome']} R={dp['R']}")
    finally:
        paper.CLOSED, paper.OPEN, paper.EQUITY, paper._candles_since = old


def main():
    print("\nیادگیری از دلیل درست — تست خصمانه\n")
    t_small_sample_refuses()
    t_noise_finds_nothing()
    t_real_effect_is_found()
    t_expired_not_scored()
    t_stables_rejected()
    t_viability_gate()
    t_no_candle_expiry()
    t_trailing_stop()
    bad = [(n, d) for ok, n, d in R if not ok]
    print(f"\n{'=' * 74}")
    print(f"{len(R)-len(bad)} از {len(R)} تست قبول")
    for n, d in bad:
        print(f"  · {n} — {d}")
    print("=" * 74)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
