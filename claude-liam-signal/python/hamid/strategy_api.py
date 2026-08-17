"""درگاه استراتژی برای داشبورد بیت‌یونیکس — «کد استراتژی به پایتون».

استراتژی از قبل پایتون است؛ این فایل نسخهٔ موازی نمی‌سازد (قانون: قابلیتِ
موجود گسترش می‌یابد، بازنویسی نمی‌شود) — فقط یک درِ ورودی تمیز است:

  from hamid.strategy_api import analyze_symbol, full_cycle, gates

نقشهٔ کد اصلی:
  hamid/cycle.py        روش کامل حمید (سلسله‌مراتب ۴س→۱س→۱۵د→۵د + دروازه‌ها)
  hamid/deep.py         تحلیل عمیق تک‌ارز — همان که analyze() این‌جا صدا می‌زند
  hamid/structure.py    سوینگ/روند/کانال/S-R/خط روند (canon شش‌کتابی)
  hamid/orderblock*.py  چرخهٔ کامل OB
  hamid/trend_gate.py   وتوی روند ۴س/۱س + قواعد خلاف روند
  hamid/fees.py         دروازهٔ RR خالص از کارمزد (Bitunix VIP0)
  hamid/sizing.py       سقف‌های سخت سایز (۵٪/۱۵x قفل)
  hamid/killswitch.py   پنج ماشه — داشبورد موظف است پیش از هر سفارش guard()
  hamid/execution_gate  زنجیرهٔ نهایی → signals/exec-outbox.json
"""


def analyze_symbol(sym, quiet=True):
    """تحلیل کامل تک‌ارز با موتور اصلی (deep). خروجی: dict ستاپ/سطوح/دلایل."""
    from hamid import deep
    return deep.analyze(sym, quiet=quiet)


def full_cycle(symbols, on_ready=None):
    """چرخهٔ کامل روش حمید روی فهرست ارزها؛ on_ready(sym, read) برای
    ارسال لحظه‌ای (قانون: سیگنال منتظر پایان چرخه نمی‌ماند)."""
    from hamid import cycle
    return cycle.run_active(symbols, on_ready=on_ready)


def gates(signal, equity_usd=None):
    """زنجیرهٔ پیش از اجرا روی یک سیگنال آماده: کیل‌سوییچ → کارمزد → سایز.
    equity_usd واقعی بدهید تا سایز نهایی (نه پیشنهاد 10k) برگردد."""
    from hamid import execution_gate, sizing
    r = execution_gate.evaluate(signal)
    if r["ok"] and equity_usd:
        r["intent"]["sizing_real"] = sizing.position(
            equity_usd, signal["entry"], signal["sl"], leverage=5)
    return r
