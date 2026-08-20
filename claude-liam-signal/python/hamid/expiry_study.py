"""مطالعهٔ انقضا — چرا نیمی از ستاپ‌های دفتر اول هرگز پر نمی‌شوند؟

اندازه‌گیری ۲۰ اوت روی ۲۴ ساعت: دفتر پولبک اول ۱۷۹ پرشده در برابر ۱۷۵
منقضی. هر منقضی یعنی تحلیلِ انجام‌شده‌ای که هیچ‌وقت معامله نشد. دو حکم
ممکن است و هر دو باید با عدد بیایند، نه با سلیقه:

  الف) ورودها بیش از حد دورند → پنجرهٔ پر شدن یا فاصلهٔ ورود باید عوض شود
  ب) دوری ورود همان چیزی است که کیفیت می‌سازد (ورودِ نزدیک = ورودِ وسط
     حرکت) → دست زدن به آن، لبه را می‌کشد

این ماژول رابطهٔ «فاصلهٔ ورود در لحظهٔ صدور» با «نرخ پر شدن» و
«میانگین R پس از پر شدن» را به تفکیک سطل می‌سنجد. ستون dist_pct از
امروز در paper.open_from ثبت می‌شود؛ تا نمونه به حد نصاب نرسد، خروجی
صادقانه «نتیجه‌گیری ممنوع» می‌گوید. هیچ رفتاری این‌جا عوض نمی‌شود —
فقط عدد تولید می‌شود (قانون ۱۲).

خروجی: brain/backtests/expiry-study.json
اجرا:   python3 -m hamid.expiry_study
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import paper                              # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "brain" / "backtests" / "expiry-study.json"

BUCKETS = ((0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 99.0))
MIN_N = 25


def boot(vals, n=3000, alpha=0.05):
    if len(vals) < MIN_N:
        return None
    k = len(vals)
    m = sorted(sum(random.choice(vals) for _ in range(k)) / k for _ in range(n))
    lo, hi = m[int(n * alpha / 2)], m[int(n * (1 - alpha / 2))]
    return None if hi - lo < 1e-9 else (round(lo, 3), round(hi, 3))


def study(rows=None):
    rows = paper._read(paper.CLOSED) if rows is None else rows
    # فقط ردیف‌هایی که ستون فاصله را دارند — ردیف قدیمی بی‌ستون، شاهد نیست
    pool = [t for t in rows
            if ((t.get("why") or {}).get("dist_pct")) is not None]
    per = []
    for lo, hi in BUCKETS:
        b = [t for t in pool if lo <= t["why"]["dist_pct"] < hi]
        filled = [t for t in b if t.get("outcome") != "expired"
                  and t.get("R") is not None]
        rs = [t["R"] for t in filled]
        per.append({
            "bucket": f"{lo}–{hi if hi < 99 else '∞'}٪",
            "n": len(b),
            "fill_rate_pct": round(100 * len(filled) / len(b), 1) if b else None,
            "n_filled": len(filled),
            "ev_r": round(statistics.fmean(rs), 3) if rs else None,
            "ci": (lambda c: list(c) if c else None)(boot(rs)),
        })
    enough = all(p["n"] >= MIN_N for p in per[:3])
    rep = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "rows_with_dist": len(pool), "rows_total": len(rows),
           "buckets": per,
           "verdict": ("نمونه هنوز کم است — نتیجه‌گیری ممنوع؛ ستون از "
                       "۲۰ اوت ثبت می‌شود و هر روز پر می‌شود"
                       if not enough else
                       "نمونه رسید — حکم فقط اگر CI سطل‌ها از هم جدا شود")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep


def main():
    rep = study()
    print(f"مطالعهٔ انقضا — {rep['rows_with_dist']} ردیفِ دارای فاصله "
          f"از {rep['rows_total']}")
    for p in rep["buckets"]:
        print(f"  {p['bucket']:<10} n={p['n']:>5}  پر شد "
              f"{p['fill_rate_pct'] if p['fill_rate_pct'] is not None else '—'}٪  "
              f"E={p['ev_r'] if p['ev_r'] is not None else '—'}R  CI={p['ci']}")
    print(f"  {rep['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
