"""خودآزمایی کالبدشکافی باخت — python3 -m hamid.test_loss_autopsy"""
import json, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import loss_autopsy as la


def case(**kw):
    base = dict(sym="XUSDT", dir="LONG", outcome="stop", closed=int(time.time()*1000),
                fee_r=0.05, mfe_r=0.1, mae_r=-1.0, held_h=2.0, setup_type="alarm", why={})
    base.update(kw); return base


def run():
    assert la.classify(case(fee_r=0.4))[0][0] == "fee_trap"
    assert la.classify(case(mfe_r=1.1))[0][0] == "gave_back"
    assert la.classify(case(mfe_r=0.05, held_h=1))[0][0] == "instant_reversal"
    assert la.classify(case(why={"trend_4h": "down"}))[0][0] == "counter_trend" or \
           any(k == "counter_trend" for k, _ in la.classify(case(why={"trend_4h": "down"})))
    assert any(k == "setup_weak" for k, _ in la.classify(case(mfe_r=0.5, held_h=9)))
    print("۱ ✅ طبقه‌بندی: پنج کلاس درست تشخیص داده شد")

    tmp = Path(tempfile.mkdtemp()); (tmp / "2026-08").mkdir()
    la.CASES, la.OUT = tmp, tmp / "loss-analysis.json"
    (tmp / "2026-08" / "a.json").write_text(json.dumps(case(fee_r=0.5)))
    (tmp / "2026-08" / "b.json").write_text(json.dumps(
        case(autopsy="ربطی به حرکت BTC نداشت — کلیشه", mfe_r=1.0)))
    rep = la.run(write_memory=False)
    assert rep["stops"] == 2 and rep["enriched_now"] == 2
    d = json.loads((tmp / "2026-08" / "b.json").read_text())
    assert d["autopsy_v1"].startswith("ربطی") and "gave_back" in d["autopsy_causes"]
    print("۲ ✅ غنی‌سازی: بی‌علت و کلیشه‌ای هر دو علت‌دار شدند (v1 حفظ شد)")
    print("\nهمهٔ آزمون‌های کالبدشکافی گذشت")


if __name__ == "__main__":
    run()
