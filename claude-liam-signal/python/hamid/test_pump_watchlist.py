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

    # قبرستان: ارز منقضی تا ۲۴س دوباره ثبت نمی‌شود — پایان ۱۶ کپی از یک درس
    pw.add_candidates([], old, now_ms=now)
    assert "BBBUSDT" not in pw._load() or "BBBUSDT" in (pw._load().get("_graveyard") or {}), \
        "ارز منقضی نباید دوباره ثبت شود"
    ig, notes2 = pw.sweep(FakeK(mk15(), mk1h()), now_ms=now + 1000)
    assert not any("BBBUSDT" in x for x in notes2), "درس تکراری برای همان انقضا ممنوع"
    print("۷ ✅ قبرستان: ثبت مجدد و درس تکراری بلاک شد")

    # merge_state: قبرستانِ ما بعد از reset ورک‌فلو زنده می‌ماند و ورودیِ
    # قبرستانی از نسخهٔ main برنمی‌گردد (کلاس ×۲۶ درس تکراری، ۱۷ اوت)
    ours = {"_graveyard": {"XUSDT": 100}, "NEWUSDT": {"added_at": 5}}
    theirs = {"XUSDT": {"added_at": 1}, "OLDUSDT": {"added_at": 2}}
    m = pw.merge_state(ours, theirs)
    assert "XUSDT" not in [k for k in m if k != "_graveyard"], m
    assert m["_graveyard"]["XUSDT"] == 100 and "NEWUSDT" in m and "OLDUSDT" in m
    print("۸ ✅ merge_state: قبرستان از reset جان به در می‌برد، منقضی برنمی‌گردد")

    # پیام «دیر رسیدیم» هرگز به تلگرام نمی‌رود (دستور ۱۷ اوت — ۱۰۰ بار)
    import inspect
    from hamid import pump_radar as pr
    src = inspect.getsource(pr)
    seg = src[src.index('elif not picks:'):src.index('تمام شد در')]
    assert '_tg._post' not in seg, "مسیر تلگرامِ حکم late برگشته!"
    print("۹ ✅ حکم «دیر رسیدیم» هیچ مسیری به تلگرام ندارد")

    print("\nهمهٔ ۹ آزمون گذشت — دفتر انتظار درست کار می‌کند")


if __name__ == "__main__":
    run()
