"""پرونده‌های معامله — brain/cases، بند ۲۲ منشور LIAM.

هر ستاپ بستهٔ سیگنال‌گرید یک فایل JSON یکتا می‌شود:
cases/YYYY-MM/<SYM>-<closed_ms>.json — فایل یکتا یعنی دو ورک‌فلوی
هم‌زمان هرگز روی یک فایل نمی‌نویسند (ایمنی همزمانی، بند ۳۴). پرونده
append-only است: نه ویرایش، نه حذف — باخت پنهان نمی‌شود.

فیلد غایب نوشته نمی‌شود؛ جعل UNKNOWN با عدد، ممنوع.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
CASES = ROOT / "brain" / "cases"

_FIELDS = ("sym", "dir", "entry", "sl", "tp1", "tp2", "opened", "filled",
           "closed", "outcome", "R", "R_net", "fee_r", "mfe_r", "mae_r",
           "held_h", "late_fill")


def enrich_recent_losses():
    """بعد از هر نوبت ثبت پرونده — باختِ بی‌علت باقی نماند (دستور ۱۷ اوت)."""
    try:
        from hamid import loss_autopsy
        loss_autopsy.run(window_h=6, write_memory=True)
    except Exception:                                # noqa: BLE001
        pass


def write_case(t, autopsy=None, regime=None):
    """یک معاملهٔ بسته → یک پروندهٔ یکتا. برگشتی: مسیر یا None."""
    try:
        closed = int(t.get("closed") or time.time() * 1000)
        month = time.strftime("%Y-%m", time.gmtime(closed / 1000))
        d = CASES / month
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{t['sym']}-{closed}.json"
        if path.exists():                            # append-only، بازنویسی ممنوع
            return None
        case = {k: t[k] for k in _FIELDS if t.get(k) is not None}
        why = t.get("why")
        if isinstance(why, dict):
            case["setup_type"] = why.get("stage")
            case["ctx"] = {k: v for k, v in why.items() if v is not None}
        if autopsy:
            case["autopsy"] = autopsy
        if regime:
            case["regime"] = regime
        path.write_text(json.dumps(case, ensure_ascii=False, indent=1))
        try:
            return str(path.relative_to(ROOT))
        except ValueError:                           # مسیر تست خارج از ریپو
            return str(path)
    except Exception as e:                           # noqa: BLE001 - پرونده، تسویه را نمی‌کشد
        print(f"پرونده نوشته نشد ({t.get('sym')}): {type(e).__name__}")
        return None


def write_cases(trades, autopsies=None, regime=None):
    autopsies = autopsies or {}
    n = 0
    for t in trades:
        if write_case(t, autopsy=autopsies.get(t.get("sym", "") + t.get("dir", "")),
                      regime=regime):
            n += 1
    if n:
        print(f"دفتر پرونده‌ها: {n} case ثبت شد")
    return n
    enrich_recent_losses()   # باختِ بی‌علت باقی نماند (۱۷ اوت)
