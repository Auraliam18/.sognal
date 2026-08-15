"""خودآزمایی دفتر انتظار پامپ — سه رفتاری که ۶۳ بار «دیر رسید» را می‌بندند:
ساکت→ثبت‌شده می‌ماند، حجم+حرکت→شلیک، پرش بدون ما→درس و حذف (نه سیگنال دیر).
python3 -m hamid.test_pump_watchlist
"""
import json
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import pump_watchlist as pw               # noqa: E402


class FakeK:
    def __init__(self, c15, c1h):
        self.c15, self.c1h = c15, c1h

    def get(self, sym, tf, n):
        return (self.c15 if tf == "15m" else self.c1h)[-n:]


def mk15(n=40, price=1.0, vol=100.0):
    return [{"t": i, "o": price, "h": price, "l": price, "c": price, "v": vol}
            for i in range(n)]


def mk1h(n=26, price=1.0):
    return [{"t": i, "o": price, "h": price, "l": price, "c": price, "v": 100.0}
            for i in range(n)]


def run():
    tmp = Path(tempfile.mkdtemp())
    pw.WL = tmp / "wl.json"
    now = int(time.time() * 1000)

    # ثبت از picks
    picks = [{"symbol": "AAAUSDT", "expires_at": now + 8 * 3600 * 1000,
              "reasons": ["در 3 از 7 پامپ HFT هم‌پرید"], "entry": 1.0, "sl": 0.95,
              "lag": {"leader": "HFTUSDT"}}]
    wl, added = pw.add_candidates([], picks, now_ms=now)
    assert added == ["AAAUSDT"], added
    print("۱ ✅ ثبت pick در دفتر")

    # ساکت → می‌ماند، شلیک نمی‌شود
    kc = FakeK(mk15(), mk1h())
    ig, notes = pw.sweep(kc, now_ms=now + 60_000)
    assert not ig and not notes and "AAAUSDT" in pw._load()
    print("۲ ✅ ارز ساکت: بدون شلیک، در دفتر می‌ماند")

    # حجم ×۴ + حرکت +۳٪ → شلیک
    c15 = mk15()
    c15[-1] = {**c15[-1], "c": 1.03, "v": 400.0}
    ig, _ = pw.sweep(FakeK(c15, mk1h()), now_ms=now + 120_000)
    assert len(ig) == 1 and ig[0]["symbol"] == "AAAUSDT" and ig[0]["vol_x"] >= 3
    assert "AAAUSDT" not in pw._load()
    print(f"۳ ✅ شلیک: حجم ×{ig[0]['vol_x']} و {ig[0]['move_pct']:+}٪ → سیگنال، حذف از دفتر")

    # حرکت +۳٪ ولی بدون حجم → شلیک نمی‌شود (حرکت بی‌حجم تله است)
    pw.add_candidates([], picks, now_ms=now)
    c15b = mk15()
    c15b[-1] = {**c15b[-1], "c": 1.03, "v": 110.0}
    ig, _ = pw.sweep(FakeK(c15b, mk1h()), now_ms=now + 120_000)
    assert not ig and "AAAUSDT" in pw._load()
    print("۴ ✅ حرکت بی‌حجم: شلیک نمی‌شود")

    # پرش +۱۲٪ در ۲۴س بدون ما → درس و حذف، نه سیگنال دیر
    c1h = mk1h()
    for k in range(1, 6):
        c1h[-k] = {**c1h[-k], "c": 1.12}
    ig, notes = pw.sweep(FakeK(mk15(price=1.12), c1h), now_ms=now + 180_000)
    assert not ig and notes and "بدون ما پرید" in notes[0]
    assert "AAAUSDT" not in pw._load()
    print("۵ ✅ پریده بدون ما: درس ثبت، حذف، سیگنال دیر صادر نشد")

    # انقضای پنجره → حذف با درس
    old = [{"symbol": "BBBUSDT", "expires_at": now - 1000, "reasons": [],
            "entry": None, "sl": None}]
    pw.add_candidates([], old, now_ms=now - 2000)
    ig, notes = pw.sweep(FakeK(mk15(), mk1h()), now_ms=now)
    assert not ig and any("بسته شد" in x for x in notes)
    print("۶ ✅ انقضا: پنجره بست → حذف با درس")

    print("\nهمهٔ ۶ آزمون گذشت — دفتر انتظار درست کار می‌کند")


if __name__ == "__main__":
    run()
