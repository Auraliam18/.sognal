"""سقف سخت سایز — پیش‌نیاز ۴ از آستانهٔ پول واقعی (CLAUDE.md).

درس VERIFIED کتابخانه (bot-sizing-cap): «استراتژی حق تعیین سایز بی‌سقف
ندارد» — حتی استراتژی خوب با یک باگِ سایز حساب را نابود می‌کند.

قواعد (config/risk.json حاکم است، پیش‌فرض‌ها محافظه‌کار):
  ریسک بر ترید: ٪ ثابت از سرمایه (پیش‌فرض ۱٪، سقف مطلق ۵٪ — قانون حمید)
  اکسپوژر کل: سقف ٪ سرمایهٔ درگیر در همهٔ پوزیشن‌های باز
  اهرم: سقف ۱۵x (قانون حمید — بالاتر فقط با تأیید صریح او)
  سایز معکوس نوسان: ذاتیِ فرمول — سایز از فاصلهٔ استاپ می‌آید و استاپ از
  ATR؛ بازار وحشی → استاپ دور → سایز کوچک، خودکار.

خروجی همیشه دلیل نوشته دارد؛ ردشده = qty صفر با دلیل، نه استثنا.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
CFG = ROOT / "config" / "risk.json"

DEFAULTS = {
    "risk_pct_per_trade": 1.0,      # ٪ سرمایه که در استاپ می‌سوزد
    "risk_pct_hard_cap": 5.0,       # قانون حمید: ۱–۵٪ — بالاتر هرگز
    "max_total_exposure_pct": 20.0, # سقف ٪ سرمایهٔ درگیر همهٔ پوزیشن‌ها
    "max_leverage": 15,             # قانون حمید — بالاتر فقط با تأیید صریح
    "min_notional_usd": 10.0,       # زیر کف صرافی سفارش رد می‌شود
}


def _cfg():
    c = dict(DEFAULTS)
    try:
        c.update(json.loads(CFG.read_text()).get("sizing", {}))
    except Exception:                                # noqa: BLE001
        pass
    # سقف مطلق قابل‌عبور نیست حتی از config — دفاع در برابر ادیت اشتباه
    c["risk_pct_per_trade"] = min(c["risk_pct_per_trade"], c["risk_pct_hard_cap"])
    c["max_leverage"] = min(c["max_leverage"], DEFAULTS["max_leverage"])
    return c


def position(equity_usd, entry, sl, leverage=1,
             open_exposure_usd=0.0, risk_pct=None):
    """سایز پوزیشن با همهٔ سقف‌ها. خروجی: dict با qty، notional، دلیل."""
    c = _cfg()
    out = dict(qty=0.0, notional_usd=0.0, risk_usd=0.0, ok=False, reason="")
    if not equity_usd or equity_usd <= 0:
        out["reason"] = "سرمایه نامعتبر"
        return out
    if not entry or not sl or entry == sl:
        out["reason"] = "entry/sl نامعتبر — بدون استاپ سایز تعریف نمی‌شود"
        return out
    if leverage > c["max_leverage"]:
        out["reason"] = (f"اهرم {leverage}x > سقف {c['max_leverage']}x "
                         f"(قانون حمید) — رد")
        return out
    rp = min(risk_pct if risk_pct is not None else c["risk_pct_per_trade"],
             c["risk_pct_hard_cap"])
    risk_usd = equity_usd * rp / 100
    stop_frac = abs(entry - sl) / entry
    notional = risk_usd / stop_frac
    # سقف اکسپوژر کل — پوزیشن جدید نباید مجموع را از سقف بگذراند
    max_expo = equity_usd * c["max_total_exposure_pct"] / 100
    if open_exposure_usd + notional > max_expo:
        room = max_expo - open_exposure_usd
        if room <= 0:
            out["reason"] = (f"اکسپوژر کل پر است "
                             f"({open_exposure_usd:.0f}$/{max_expo:.0f}$) — رد")
            return out
        notional = room
        risk_usd = notional * stop_frac
        out["reason"] = f"سایز به سقف اکسپوژر بریده شد ({room:.0f}$)؛ "
    margin = notional / max(leverage, 1)
    if margin > equity_usd:
        out["reason"] += "مارجین لازم از سرمایه بیشتر است — رد"
        out["qty"] = 0.0
        return out
    if notional < c["min_notional_usd"]:
        out["reason"] += f"notional زیر کف {c['min_notional_usd']}$ — رد"
        return out
    out.update(qty=round(notional / entry, 8),
               notional_usd=round(notional, 2),
               risk_usd=round(risk_usd, 2),
               margin_usd=round(margin, 2), ok=True,
               reason=out["reason"] + (
                   f"ریسک {rp}٪ = {risk_usd:.2f}$ · استاپ {stop_frac*100:.2f}٪ "
                   f"→ notional {notional:.0f}$ · مارجین {margin:.0f}$ @ {leverage}x"))
    return out
