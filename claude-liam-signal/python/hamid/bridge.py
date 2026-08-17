"""پل کنترل‌شده از میز تمرین به مسیر سیگنال (گزینهٔ ۲ — دستور حمید ۱۶ اوت).

## مسئله‌ای که این فایل حل می‌کند

اندازه‌گیری ۱۶ اوت جواب صریحی داد: **تأثیر میز تمرین روی سیگنال‌های ارسالی
صفر است، و این عمدی بود.** دفتر تمرین از هر دو کانال تصمیم بیرون گذاشته
شده (`experience_index` و `reasons` هر دو stage="practice" را رد می‌کنند)،
چون دروازه‌اش شل‌تر از دروازهٔ واقعی است و قاضیِ منصفی برای سیگنال واقعی
نیست. نتیجه: ۱۷۰۰ معاملهٔ تمرین انباشته شد و هیچ‌کدام هرگز روی هیچ
تصمیمی اثر نگذاشت.

حمید گزینهٔ ۲ را انتخاب کرد: «یافتهٔ تمرین فقط وقتی به مسیر سیگنال برسد
که روی دفتر **سیگنال واقعی** هم تکرار شده باشد.»

## چرا این کار آماری درست است (و صرفاً شل‌کردن آستانه نیست)

طرحِ استاندارد کشف/تکرار، دقیقاً همین است:

  **کشف** روی یک نمونه، با تصحیح کامل چندآزمونی. دفتر تمرین بزرگ است
  (~۱۷۰۰ معامله) پس بونفرونی روی همهٔ شرط‌های واجدشرایط اعمال می‌شود و
  عبور از آن سخت است.

  **تکرار** روی نمونهٔ **مستقل** (دفتر سیگنال واقعی)، با یک آزمون
  یک‌طرفه در جهتی که از قبل ثبت شده. این‌جا دیگر ماهی‌گیری نیست: جهت
  پیش‌ثبت شده، فقط یک آزمون انجام می‌شود، پس جریمهٔ چندآزمونی دوباره
  لازم نیست — هزینه‌اش یک بار در مرحلهٔ کشف پرداخت شده.

تفاوتش با «آستانه را شل کن» این است که یک شرط باید **دو بار، روی دو
نمونهٔ مستقل، با یک علامت** زنده بماند. شرطی که فقط روی تمرین زنده است
هرگز رد نمی‌شود؛ فقط ثبت می‌شود که کاندید بود و تکرار نشد.

## اندازهٔ اثری که اعمال می‌شود

عدد `diff` که به رتبه‌بندی می‌رود، از **دفتر سیگنال واقعی** برداشته
می‌شود نه از تمرین. تمرین حق دارد بگوید «این‌جا را نگاه کن»؛ حق ندارد
بگوید «به این اندازه مهم است».

## تعارض حذف نمی‌شود (قانون ۰۳)

اگر تمرین بگوید مثبت و سیگنال واقعی بگوید منفی، وضعیت `disagree` ثبت
می‌شود و می‌ماند — نه پاک می‌شود، نه به نفع هیچ‌کدام گرد می‌شود.

## چه چیزی اعمال **نمی‌شود**

هیچ قانون استراتژی، هیچ دروازه، هیچ آستانهٔ ورود. تنها اثرِ عملی، همان
`learn_score` رتبه‌بندی است که از قبل هم از `reasons.json` تغذیه می‌شد —
و هر ورودی پل با برچسب `via="bridge"` می‌آید تا در گزارش چرخه از
تأییدشدهٔ مستقیم قابل تفکیک باشد. قانون ۱۲ سر جایش است.

اجرا:
    python3 -m hamid.bridge            # ارزیابی و نوشتن bridge.json
    python3 -m hamid.bridge --stages   # کارنامهٔ میز تمرین به تفکیک پلهٔ دروازه
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import paper                                       # noqa: E402

OUT = paper.BOOK / "bridge.json"

# مرحله‌های دفتر تمرین: فقط بازپخش میز تمرین. دفترهای آزمایشی دیگر
# (پولبک اول، ایندوسمنت، v2) نمونهٔ کشف نیستند — آن‌ها آزمایش‌های جدا با
# سؤال خودشان‌اند و قاطی‌کردنشان با تمرین یعنی سه سؤال در یک کاسه.
PRACTICE_STAGES = ("practice",)

MIN_SIDE = 8            # کف نمونهٔ هر طرف در هر دو دفتر (هم‌سطح با paper)
MIN_DAYS = 3            # کف روزهای متمایز در نمونهٔ تکرار — بلوک روزانه
                        # بدون این، بوت‌استرپ روی یک روزِ هم‌حرکت i.i.d
                        # فرض می‌شود و بازهٔ دروغینِ باریک می‌سازد.
MIN_WIDTH = 1e-9        # بازهٔ صفرعرض = شاهد قلابی. اگر همهٔ Rهای یک طرف
                        # یک عدد باشند، هر بازنمونه‌گیری همان میانگین را
                        # می‌دهد و بازه به یک نقطه جمع می‌شود؛ آن نقطه اگر
                        # اتفاقاً غیرصفر باشد، «از صفر رد شد» به نظر می‌رسد
                        # در حالی که هیچ تغییرپذیری‌ای سنجیده نشده. این تلهٔ
                        # واقعی است نه فرضی: ۱۱۲ از ۱۱۹ معامله دقیقاً روی
                        # عدد نردبان تریل بسته بودند و همین بازهٔ [۰.۱۵،
                        # ۰.۱۵] را ساخته بود.


def _day(t):
    return int((t.get("closed") or 0) // 86_400_000)


def _books():
    """دو نمونهٔ مستقل: (تمرین، سیگنال واقعی).

    «مستقل» این‌جا معنای دقیقی دارد: میز تمرین بازپخش تاریخی است و هرگز
    سیگنالی به تلگرام نفرستاده، پس هیچ معامله‌ای در هر دو دفتر نیست.
    """
    prac, sig = [], []
    for t in paper._read(paper.CLOSED):
        if t.get("R") is None or t.get("outcome") == "expired":
            continue
        st = (t.get("why") or {}).get("stage") or ""
        if st in PRACTICE_STAGES:
            prac.append(t)
        elif st not in ("first", "inducement", "vetoed", "v2"):
            sig.append(t)
    return prac, sig


def _eligible(trades, fn):
    na = sum(1 for t in trades if fn(t.get("why") or {}))
    return na >= MIN_SIDE and (len(trades) - na) >= MIN_SIDE


def _arm(trades, fn):
    ta = [t for t in trades if fn(t.get("why") or {})]
    tb = [t for t in trades if not fn(t.get("why") or {})]
    return (([t["R"] for t in ta], [_day(t) for t in ta]),
            ([t["R"] for t in tb], [_day(t) for t in tb]))


def discover(practice, alpha=0.05):
    """کشف روی دفتر تمرین، با بونفرونی کامل روی شرط‌های واجدشرایط.

    خروجی: dict نام‌شرط → یافته، فقط برای آن‌هایی که بازهٔ **تصحیح‌شده**
    از صفر رد شده. جهت (`sign`) همین‌جا پیش‌ثبت می‌شود؛ مرحلهٔ تکرار حق
    ندارد جهت را عوض کند.
    """
    k = max(1, sum(1 for _n, fn in paper.CONDITIONS
                   if _eligible(practice, fn)))
    adj = alpha / k
    found = {}
    for name, fn in paper.CONDITIONS:
        if not _eligible(practice, fn):
            continue
        (a, da), (b, db) = _arm(practice, fn)
        ci = paper._boot_diff(a, b, alpha=adj, days_a=da, days_b=db)
        if not ci or ci[1] - ci[0] < MIN_WIDTH:      # بازهٔ صفرعرض — شاهد نیست
            continue
        if not (ci[0] > 0 or ci[1] < 0):
            continue
        diff = statistics.fmean(a) - statistics.fmean(b)
        found[name] = {"condition": name, "sign": 1 if diff > 0 else -1,
                       "n_with": len(a), "n_without": len(b),
                       "diff": round(diff, 4), "interval": ci,
                       "alpha": round(adj, 5), "tests": k}
    return found


def replicate(signal, name, fn, sign, alpha=0.05):
    """آزمون تکرار روی دفتر سیگنال واقعی — یک‌طرفه، در جهت پیش‌ثبت‌شده.

    بازهٔ دوطرفهٔ ۲α گرفته می‌شود و فقط کرانهٔ سمتِ جهت بررسی می‌شود؛ این
    دقیقاً معادل آزمون یک‌طرفه در سطح α است، و چون جهت از قبل ثبت شده
    ماهی‌گیری نیست.
    """
    if not _eligible(signal, fn):
        return {"status": "insufficient", "why": "نمونهٔ کم در دفتر سیگنال"}
    (a, da), (b, db) = _arm(signal, fn)
    days = len(set(da) | set(db))
    if days < MIN_DAYS:
        return {"status": "insufficient",
                "why": f"فقط {days} روز متمایز — کف {MIN_DAYS} است"}
    ci = paper._boot_diff(a, b, alpha=alpha * 2, days_a=da, days_b=db)
    if not ci:
        return {"status": "insufficient", "why": "بازه ساخته نشد"}
    if ci[1] - ci[0] < MIN_WIDTH:
        return {"status": "insufficient",
                "why": "بازهٔ صفرعرض — Rها ثابت‌اند و تغییرپذیری سنجیده نشد",
                "n_with": len(a), "n_without": len(b), "days": days,
                "interval": ci}
    diff = statistics.fmean(a) - statistics.fmean(b)
    passed = (ci[0] > 0) if sign > 0 else (ci[1] < 0)
    opposite = (ci[1] < 0) if sign > 0 else (ci[0] > 0)
    return {"status": "replicated" if passed else
                      "disagree" if opposite else "not_replicated",
            "n_with": len(a), "n_without": len(b), "days": days,
            "diff": round(diff, 4), "interval": ci}


def evaluate(alpha=0.05, verbose=True, write=True):
    """کشف روی تمرین + تکرار روی سیگنال → bridge.json."""
    prac, sig = _books()
    fns = dict(paper.CONDITIONS)
    rows, promoted = [], []

    if verbose:
        print(f"\nپل تمرین→سیگنال · تمرین {len(prac)} معامله · "
              f"سیگنال واقعی {len(sig)} معامله")

    if len(prac) < 20 or len(sig) < 20:
        if verbose:
            print("یکی از دو دفتر برای کشف/تکرار کوچک است — پل ساکت می‌ماند.")
    else:
        found = discover(prac, alpha=alpha)
        if verbose:
            print(f"کشف روی تمرین: {len(found)} شرط از بونفرونی رد شد\n")
            print(f"{'شرط':<30}{'تمرین':>10}{'سیگنال':>10}   وضعیت")
            print("─" * 78)
        for name, f in sorted(found.items(), key=lambda kv: -abs(kv[1]["diff"])):
            rep = replicate(sig, name, fns[name], f["sign"], alpha=alpha)
            row = {**f, "replication": rep, "status": rep["status"]}
            rows.append(row)
            if verbose:
                sd = rep.get("diff")
                print(f"{name:<30}{f['diff']:>+10.3f}"
                      f"{(f'{sd:+.3f}' if sd is not None else '—'):>10}   "
                      + {"replicated": "✓ تکرار شد — وارد مسیر سیگنال",
                         "not_replicated": "— تکرار نشد (کاندید می‌ماند)",
                         "disagree": "⚠ تعارض: دو دفتر خلاف هم",
                         "insufficient": f"— {rep.get('why', '')}"}[rep["status"]])
            if rep["status"] == "replicated":
                # اندازهٔ اثر از دفتر **سیگنال واقعی**، نه از تمرین.
                promoted.append({"condition": name,
                                 "n_with": rep["n_with"],
                                 "n_without": rep["n_without"],
                                 "diff": rep["diff"],
                                 "interval": rep["interval"],
                                 "days": rep["days"],
                                 "practice_diff": f["diff"],
                                 "via": "bridge"})
        if verbose:
            print("─" * 78)
            if promoted:
                print(f"{len(promoted)} یافته دو بار زنده ماند و به رتبه‌بندی "
                      "می‌رود (با برچسب bridge).")
            else:
                print("هیچ یافتهٔ تمرینی روی دفتر واقعی تکرار نشد — "
                      "پس هیچ‌چیز به مسیر سیگنال نمی‌رود. این جواب درست است، "
                      "نه شکست.")

    doc = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "book": str(paper.CLOSED),
        "n_practice": len(prac), "n_signal": len(sig),
        "candidates": rows,
        "promoted": promoted,
        "stages": stage_report(prac, verbose=False),
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return doc


def promoted():
    """آن‌چه چرخه اجازه دارد اعمال کند — با امضای دفتر، مثل reasons.json."""
    try:
        j = json.loads(OUT.read_text())
    except Exception:                                # noqa: BLE001 - نبودش حالت معتبر است
        return []
    if j.get("book") != str(paper.CLOSED):
        return []
    return j.get("promoted") or []


# ── گزینهٔ ۳: کارنامهٔ میز تمرین به تفکیک پلهٔ دروازه ───────────────────────
#
# دروازه‌های تمرین پله‌پله به دروازهٔ واقعی نزدیک می‌شوند (trainer.gate_stage).
# هر معاملهٔ تمرین با بالاترین پله‌ای که از آن رد شده برچسب می‌خورد، پس یک
# بازپخش، دادهٔ **همهٔ** پله‌ها را هم‌زمان می‌سازد: نه تقسیم نمونه، نه از
# دست رفتن معامله. این‌جا جواب می‌دهیم «سخت‌ترکردن دروازه واقعاً کمک کرد؟»

def stage_report(practice=None, verbose=True):
    if practice is None:
        practice, _ = _books()
    tagged = [t for t in practice
              if (t.get("why") or {}).get("gate_stage") is not None]
    if not tagged:
        if verbose:
            print("هیچ معاملهٔ تمرینی برچسب پلهٔ دروازه ندارد — "
                  "بعد از اولین اجرای trainer با نسخهٔ جدید پر می‌شود.")
        return {"n_tagged": 0}
    top = max((t["why"]["gate_stage"] for t in tagged), default=0)
    out = {"n_tagged": len(tagged), "levels": []}
    if verbose:
        print(f"\n{len(tagged)} معاملهٔ تمرینِ برچسب‌خورده")
        print(f"{'پله':<8}{'n':>8}{'میانگین R':>12}{'برد٪':>8}   "
              "بازهٔ تفاوت با پایین‌ترها")
        print("─" * 72)
    for k in range(0, top + 1):
        a = [t for t in tagged if t["why"]["gate_stage"] >= k]
        b = [t for t in tagged if t["why"]["gate_stage"] < k]
        row = {"stage": k, "n": len(a),
               "mean_r": round(statistics.fmean([t["R"] for t in a]), 4) if a else None,
               "win_pct": round(100 * sum(1 for t in a if t["R"] > 0) / len(a), 1)
               if a else None}
        ci = None
        if k and len(a) >= MIN_SIDE and len(b) >= MIN_SIDE:
            ci = paper._boot_diff([t["R"] for t in a], [t["R"] for t in b],
                                  alpha=0.05,
                                  days_a=[_day(t) for t in a],
                                  days_b=[_day(t) for t in b])
            row["vs_lower"] = ci
            row["helps"] = bool(ci and ci[0] > 0)
        out["levels"].append(row)
        if verbose:
            print(f"{k:<8}{row['n']:>8}"
                  f"{(row['mean_r'] if row['mean_r'] is not None else 0):>+12.4f}"
                  f"{(row['win_pct'] or 0):>8.1f}   "
                  + (f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"
                     + ("  ✓ کمک می‌کند" if ci[0] > 0 else
                        "  ✗ بدتر می‌کند" if ci[1] < 0 else "  — از صفر رد نشد")
                     if ci else "—"))
    if verbose:
        print("─" * 72)
        print("«پله ۳» یعنی همان چیزی که دروازهٔ سیگنال واقعی می‌خواهد. تا وقتی "
              "بازه از صفر رد نشده، پلهٔ کف تمرین بالا نمی‌رود — قانون ثابت.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", action="store_true",
                    help="فقط کارنامهٔ پله‌های دروازهٔ تمرین")
    a = ap.parse_args()
    if a.stages:
        stage_report()
        return 0
    evaluate()
    stage_report()
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
