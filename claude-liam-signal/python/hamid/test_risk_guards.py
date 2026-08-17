"""خودآزمایی سه محافظ پول واقعی — python3 -m hamid.test_risk_guards"""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import killswitch as ks, sizing, reconcile   # noqa: E402


def run():
    tmp = Path(tempfile.mkdtemp())
    ks.STATE = tmp / "killswitch.json"
    ks.CFG = tmp / "risk.json"
    reconcile.OUT = tmp / "reconcile.json"
    now = int(time.time() * 1000)

    # ── کیل‌سوییچ ──
    assert ks.guard() is True
    ok = True
    for r in (-1, -1, -1, -1, -1):
        ok = ks.record_result(r, now)
    assert ok is False and ks.guard() is False
    assert "سقف ضرر" in ks._load()["tripped"]["reason"]
    print("۱ ✅ LOSS: ۵ باخت ۱R پیاپی → trip، guard رد می‌کند")

    ks.reset("hamid-test")
    assert ks.guard() is True
    for i in range(7):
        ok = ks.record_order(now + i * 1000)
    assert ok is False and "نرخ غیرعادی" in ks._load()["tripped"]["reason"]
    print("۲ ✅ RATE: ۷ سفارش در دقیقه → trip (لوپ نرم‌افزاری)")

    ks.reset("hamid-test")
    assert ks.check_deviation(100.0, 100.5) is True
    assert ks.check_deviation(100.0, 102.0) is False
    print("۳ ✅ DEVIATION: ۰.۵٪ قبول · ۲٪ trip")

    ks.reset("hamid-test")
    assert ks.check_deadman(now - 60_000, now) is True
    assert ks.check_deadman(now - 300_000, now) is False
    print("۴ ✅ DEADMAN: سکوت ۶۰s قبول · ۳۰۰s trip")

    try:
        ks.reset("")
        raise AssertionError("ریست بی‌نام نباید قبول شود")
    except ValueError:
        print("۵ ✅ ریست فقط با نام (تأیید انسانی)")
    ks.reset("hamid-test")

    # ── سایز ──
    # استاپ ۵٪: notional = ۱۰۰$/۰.۰۵ = ۲۰۰۰$ = دقیقاً سقف اکسپوژر — بدون برش
    p = sizing.position(10_000, entry=100.0, sl=95.0, leverage=10)
    assert p["ok"] and abs(p["risk_usd"] - 100.0) < 1 and abs(p["notional_usd"] - 2_000) < 1
    print(f"۶ ✅ سایز پایه: ریسک ۱٪=۱۰۰$ · استاپ ۵٪ → notional {p['notional_usd']}$")

    # استاپ تنگ ۱٪ → notional اسمی ۱۰هزار$ ولی سقف اکسپوژر ۲۰٪ می‌بُرد به ۲۰۰۰$
    p = sizing.position(10_000, entry=100.0, sl=99.0, leverage=10)
    assert p["ok"] and abs(p["notional_usd"] - 2_000) < 1 and "اکسپوژر" in p["reason"]
    print("۶ب ✅ استاپ تنگ: سقف اکسپوژر بر ریسک٪ حاکم شد (۱۰k→۲k با دلیل)")

    p = sizing.position(10_000, entry=100.0, sl=99.0, leverage=20)
    assert not p["ok"] and "اهرم" in p["reason"]
    print("۷ ✅ اهرم ۲۰x > سقف ۱۵x قانون حمید → رد")

    p = sizing.position(10_000, entry=100.0, sl=99.0, leverage=10,
                        open_exposure_usd=1900.0)
    assert p["ok"] and p["notional_usd"] <= 100.01
    p2 = sizing.position(10_000, entry=100.0, sl=99.0, leverage=10,
                         open_exposure_usd=2000.0)
    assert not p2["ok"] and "اکسپوژر" in p2["reason"]
    print("۸ ✅ سقف اکسپوژر ۲۰٪: نزدیک سقف بریده، پر رد")

    # سایز معکوس نوسان (زیر سقف اکسپوژر): استاپ ۲برابر → notional نصف
    calm = sizing.position(10_000, entry=100.0, sl=95.0, leverage=5, risk_pct=0.5)
    wild = sizing.position(10_000, entry=100.0, sl=90.0, leverage=5, risk_pct=0.5)
    assert abs(wild["notional_usd"] - calm["notional_usd"] / 2) < 1
    print(f"۹ ✅ نوسان‌معکوس: آرام {calm['notional_usd']}$ · وحشی {wild['notional_usd']}$")

    # config نمی‌تواند سقف مطلق را بشکند
    ks.CFG.write_text(json.dumps({"sizing": {"risk_pct_per_trade": 50,
                                             "max_leverage": 100}}))
    sizing.CFG = ks.CFG
    p = sizing.position(10_000, entry=100.0, sl=99.0, leverage=16)
    assert not p["ok"]
    p = sizing.position(10_000, entry=100.0, sl=99.0, leverage=15)
    assert p["risk_usd"] <= 500.01
    print("۱۰ ✅ ادیت خراب config سقف مطلق ۵٪/۱۵x را نمی‌شکند")

    # ── reconciliation ──
    class FakeX:
        def __init__(self, pos): self.pos = pos
        def positions(self): return self.pos

    ks.reset("hamid-test")
    rep = reconcile.run(FakeX([{"symbol": "BTCUSDT", "qty": 1.0, "side": "LONG"}]),
                        [{"symbol": "BTCUSDT", "qty": 1.0, "side": "LONG"}])
    assert rep["status"] == "OK" and ks.guard() is True
    rep = reconcile.run(FakeX([{"symbol": "ETHUSDT", "qty": 2.0, "side": "LONG"}]),
                        [])
    assert rep["status"] == "MISMATCH" and ks.guard() is False
    assert rep["issues"][0]["kind"] == "MISSING_LOCAL"
    print("۱۱ ✅ تطبیق: همخوان OK · پوزیشن ناشناختهٔ صرافی → کیل‌سوییچ")

    ks.reset("hamid-test")

    class DeadX:
        def positions(self): raise TimeoutError

    rep = reconcile.run(DeadX(), [])
    assert rep["status"] == "UNKNOWN" and ks.guard() is False
    print("۱۲ ✅ بی‌خبری از صرافی → رفتار امن: trip، نه فرضِ فیل")

    rep = reconcile.run(None, [])
    assert rep["status"] == "INACTIVE"
    print("۱۳ ✅ بدون آداپتور (قبل از کلید API): INACTIVE، بدون فرض")

    print("\nهمهٔ ۱۳ آزمون محافظ‌های پول واقعی گذشت")


if __name__ == "__main__":
    run()
