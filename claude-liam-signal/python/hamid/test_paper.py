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
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import paper                                       # noqa: E402

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


def main():
    print("\nیادگیری از دلیل درست — تست خصمانه\n")
    t_small_sample_refuses()
    t_noise_finds_nothing()
    t_real_effect_is_found()
    t_expired_not_scored()
    bad = [(n, d) for ok, n, d in R if not ok]
    print(f"\n{'=' * 74}")
    print(f"{len(R)-len(bad)} از {len(R)} تست قبول")
    for n, d in bad:
        print(f"  · {n} — {d}")
    print("=" * 74)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
