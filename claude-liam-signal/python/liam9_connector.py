"""لیام تریدر ۹ — کانکتور داشبورد. جدیدترین نسخهٔ پایتون، یک import:

    from liam9_connector import Liam9
    liam = Liam9()

    liam.pending_intents()      # قصدهای اجرای گذشته از همهٔ دروازه‌ها
    liam.guard()                # False = کیل‌سوییچ فعال؛ هیچ سفارشی نده
    liam.analyze("BTCUSDT")     # تحلیل کامل تک‌ارز با موتور اصلی
    liam.gates(sig, equity)     # زنجیرهٔ اجرا با سرمایهٔ واقعی → سایز نهایی
    liam.record_fill(expected, actual)   # بعد از هر فیل — انحراف = trip
    liam.record_result(r)       # بعد از بستن هر معامله (R) — سقف ضرر روز
    liam.reconcile(adapter, local)       # تطبیق دوره‌ای پوزیشن‌ها
    liam.pull_updates()         # دریافت آخرین کد/قوانین من از GitHub
    liam.version()              # نسخه + آخرین تغییرات

قرارداد سخت (CLAUDE.md): پیش از هر سفارش guard()؛ LIVE فقط با حکم حمید.
به‌روزرسانی دائمی: من هر بهبود را به main پوش می‌کنم؛ pull_updates()
همان را به داشبورد می‌آورد — بدون ری‌استارتِ دستیِ چیز دیگری.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent.parent


class Liam9:
    PANEL = "لیام تریدر ۹"

    # ── خواندن قصدها ──
    def pending_intents(self):
        p = ROOT / "signals" / "exec-outbox.json"
        try:
            box = json.loads(p.read_text())
        except Exception:                            # noqa: BLE001
            return []
        return [x for x in box if x.get("status") == "PENDING"]

    # ── ایمنی ──
    def guard(self):
        from hamid import killswitch
        return killswitch.guard()

    def killswitch_reset(self, who):
        from hamid import killswitch
        return killswitch.reset(who)

    def record_fill(self, expected, actual):
        from hamid import killswitch
        killswitch.record_order()
        return killswitch.check_deviation(expected, actual)

    def record_result(self, r):
        from hamid import killswitch
        return killswitch.record_result(r)

    def reconcile(self, adapter, local_positions):
        from hamid import reconcile
        return reconcile.run(adapter, local_positions)

    # ── استراتژی ──
    def analyze(self, sym):
        from hamid.strategy_api import analyze_symbol
        return analyze_symbol(sym)

    def gates(self, signal, equity_usd):
        from hamid.strategy_api import gates
        return gates(signal, equity_usd=equity_usd)

    # ── به‌روزرسانی و نسخه ──
    def pull_updates(self):
        r = subprocess.run(["git", "pull", "--rebase", "origin", "main"],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        return {"ok": r.returncode == 0,
                "log": (r.stdout + r.stderr).strip()[-400:]}

    def version(self):
        try:
            head = subprocess.run(["git", "log", "-1", "--format=%h %ci %s"],
                                  cwd=ROOT, capture_output=True, text=True,
                                  timeout=30).stdout.strip()
        except Exception:                            # noqa: BLE001
            head = "?"
        ch = ROOT / "CHANGELOG-LIAM9.md"
        latest = ""
        if ch.exists():
            lines = [l for l in ch.read_text().splitlines() if l.startswith("- ")]
            latest = lines[0] if lines else ""
        return {"panel": self.PANEL, "head": head, "latest_change": latest}
