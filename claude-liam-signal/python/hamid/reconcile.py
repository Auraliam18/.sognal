"""Reconciliation — پیش‌نیاز ۶ از آستانهٔ پول واقعی (CLAUDE.md).

درس VERIFIED کتابخانه (bot-ops-risk): پوزیشن‌های واقعی صرافی دوره‌ای با
دفترهای خودمان تطبیق داده می‌شوند؛ «بی‌خبری = رفتار امن، نه فرضِ فیل».

طراحی: منطقِ تطبیق قطعی و تست‌شده این‌جاست؛ آداپتور صرافی تزریق می‌شود.
تا وقتی کلید API بیت‌یونیکس ثبت نشده، آداپتور واقعی وجود ندارد و این
ماژول در حالت INACTIVE گزارش می‌دهد — هیچ فرضی دربارهٔ پوزیشن‌ها نمی‌کند.

قواعد تطبیق (هر ناهمخوانی = کیل‌سوییچ RECONCILE):
  MISSING_LOCAL   صرافی پوزیشنی دارد که دفتر ما ندارد — جدی‌ترین حالت
  MISSING_REMOTE  دفتر ما پوزیشن باز دارد که صرافی ندارد (فیلِ فرضی؟)
  SIZE_MISMATCH   اندازه‌ها بیش از تلورانس فرق دارند (فیل جزئی؟)
  UNKNOWN         آداپتور جواب نداد — بی‌خبری؛ سفارش تازه ممنوع
"""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "reconcile.json"
SIZE_TOL_PCT = 2.0                    # فیل جزئی زیر این تلورانس فقط هشدار


def compare(local_positions, remote_positions):
    """دو فهرست پوزیشن {symbol, qty, side} → فهرست ناهمخوانی‌ها."""
    issues = []
    loc = {(p["symbol"], p.get("side", "LONG")): p for p in local_positions or []}
    rem = {(p["symbol"], p.get("side", "LONG")): p for p in remote_positions or []}
    for k, rp in rem.items():
        if k not in loc:
            issues.append(dict(kind="MISSING_LOCAL", symbol=k[0], side=k[1],
                               remote_qty=rp.get("qty"),
                               msg=f"صرافی {k[0]} {k[1]} دارد که در دفتر ما نیست"))
    for k, lp in loc.items():
        if k not in rem:
            issues.append(dict(kind="MISSING_REMOTE", symbol=k[0], side=k[1],
                               local_qty=lp.get("qty"),
                               msg=f"دفتر ما {k[0]} {k[1]} باز دارد که صرافی ندارد"))
            continue
        rq, lq = rem[k].get("qty") or 0, lp.get("qty") or 0
        if lq and abs(rq - lq) / lq * 100 > SIZE_TOL_PCT:
            issues.append(dict(kind="SIZE_MISMATCH", symbol=k[0], side=k[1],
                               local_qty=lq, remote_qty=rq,
                               msg=f"{k[0]}: دفتر {lq} ولی صرافی {rq} "
                                   f"(>{SIZE_TOL_PCT}٪) — فیل جزئی محتمل"))
    return issues


def run(adapter=None, local_positions=None, now_ms=None):
    """adapter.positions() → فهرست پوزیشن صرافی. بدون آداپتور = INACTIVE."""
    now_ms = now_ms or int(time.time() * 1000)
    rep = dict(generated=now_ms, status="INACTIVE", issues=[],
               note="آداپتور صرافی ثبت نشده — reconciliation تا اتصال "
                    "کلید API بیت‌یونیکس غیرفعال است؛ هیچ فرضی نمی‌شود")
    if adapter is not None:
        try:
            remote = adapter.positions()
            issues = compare(local_positions or [], remote)
            rep.update(status="MISMATCH" if issues else "OK", issues=issues,
                       note=f"{len(remote)} پوزیشن صرافی با "
                            f"{len(local_positions or [])} دفترِ ما تطبیق شد")
            if issues:
                from hamid import killswitch
                killswitch.trip("RECONCILE: " + issues[0]["msg"], now_ms)
        except Exception as e:                       # noqa: BLE001
            rep.update(status="UNKNOWN",
                       note=f"آداپتور جواب نداد ({type(e).__name__}) — "
                            "بی‌خبری = رفتار امن؛ سفارش تازه ممنوع")
            from hamid import killswitch
            killswitch.trip("RECONCILE: بی‌خبری از پوزیشن‌های صرافی", now_ms)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep
