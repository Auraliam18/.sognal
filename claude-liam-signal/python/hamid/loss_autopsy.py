"""کالبدشکافی قطعی باخت‌ها — دستور حمید (۱۷ اوت): «مشکل باخت‌ها را سریع
برطرف کن و به پنل یادگیری اضافه کن.»

ممیزی همان روز: از ۱۸۷ استاپ شب، ۱۰۳ بدون autopsy و ۸۴ با یک جملهٔ
کلیشه‌ای. علت‌یابیِ تک‌معامله باید از اعدادِ ثبت‌شدهٔ خود پرونده دربیاید
(rule 06: قطعی، نه حدس LLM) و به سه جا برسد: پروندهٔ معامله، حافظه
(یک درس در روز به ازای هر کلاس، نه تکرار)، و فید پنل یادگیری.

کلاس‌های علت — هر یک با شاهد عددی داخل متن:

  fee_trap        کارمزد ≥ ۰.۲۵R — استاپ تنگ؛ حتی ستاپ درست هم بعد از
                  کارمزد نمی‌ارزید (کشف −۱۲۶.۵R خالصِ همان شب)
  counter_trend   جهت معامله خلاف روند ثبت‌شدهٔ ۴س هنگام ورود
  instant_reversal ورود و سقوط: mfe کوچک، mae سریع کامل — تله/ورود دیر
  gave_back       تا ≥۰.۸R در سود بود و برگشت تا استاپ — مدیریت/تریل
  chop            رفت‌وبرگشت بی‌جهت: نه سود گرفت نه یک‌طرفه باخت
  setup_weak      هیچ‌کدام — ضعف خود ستاپ (برچسب باقی‌مانده، نه پیش‌فرض)
"""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
CASES = ROOT / "brain" / "cases"
OUT = ROOT / "signals" / "loss-analysis.json"
FEE_TRAP_R = 0.25
GENERIC = "ربطی به حرکت BTC نداشت"


def classify(c):
    """پروندهٔ بسته با outcome=stop → (کلاس، متنِ شاهددار)."""
    causes = []
    fee = float(c.get("fee_r") or 0)
    mfe = float(c.get("mfe_r") or 0)
    mae = float(c.get("mae_r") or 0)
    held = float(c.get("held_h") or 0)
    t4 = ((c.get("why") or {}).get("trend_4h")
          or (c.get("ctx") or {}).get("trend_4h"))
    d = c.get("dir")
    if fee >= FEE_TRAP_R:
        causes.append(("fee_trap",
                       f"کارمزد {fee:.2f}R از استاپ تنگ — بعد از کارمزد "
                       f"اصلاً قابل‌دفاع نبود"))
    if t4 and ((d == "LONG" and t4 == "down") or (d == "SHORT" and t4 == "up")):
        causes.append(("counter_trend",
                       f"{d} در حالی که روند ۴س هنگام ورود {t4} بود"))
    if mfe >= 0.8:
        causes.append(("gave_back",
                       f"تا {mfe:.1f}R در سود بود و تا استاپ برگشت — "
                       f"مدیریت/تریل، نه انتخاب ستاپ"))
    elif mfe < 0.2 and held <= 4:
        causes.append(("instant_reversal",
                       f"ورود و سقوط: بیشینه سود {mfe:.1f}R در {held:.1f}س — "
                       f"تله/ایندوسمنت یا ورود دیر"))
    elif mfe < 0.4 and abs(mae) < 1.0:
        causes.append(("chop",
                       f"رفت‌وبرگشت بی‌جهت (mfe {mfe:.1f}R، mae {mae:.1f}R) — "
                       f"بازار رنج، ستاپ جهت‌دار نگرفت"))
    if not causes:
        causes.append(("setup_weak",
                       f"شاهد ساختاری خاصی در اعداد نیست (mfe {mfe:.1f}R، "
                       f"نگه‌داشت {held:.1f}س) — ضعف خود ستاپ"))
    return causes


def run(window_h=24, now_ms=None, write_memory=True):
    """پرکردن autopsy پرونده‌های بی‌علت/کلیشه‌ای + فید پنل + درسِ روزانه."""
    now_ms = now_ms or int(time.time() * 1000)
    cutoff = now_ms - window_h * 3600e3
    by_cause, by_book, enriched, total = {}, {}, 0, 0
    worst = []
    for f in sorted(CASES.glob("*/*.json")):
        try:
            c = json.loads(f.read_text())
        except Exception:                            # noqa: BLE001
            continue
        if (c.get("closed") or 0) < cutoff or c.get("outcome") != "stop":
            continue
        total += 1
        book = c.get("setup_type") or "?"
        by_book[book] = by_book.get(book, 0) + 1
        a = c.get("autopsy")
        needs = (not a) or (isinstance(a, str) and a.startswith(GENERIC))
        causes = classify(c)
        if needs:
            c["autopsy"] = " · ".join(t for _, t in causes)
            c["autopsy_causes"] = [k for k, _ in causes]
            if a:
                c["autopsy_v1"] = a
            f.write_text(json.dumps(c, ensure_ascii=False, indent=1))
            enriched += 1
        for k, _ in causes:
            by_cause[k] = by_cause.get(k, 0) + 1
        if float(c.get("fee_r") or 0) >= FEE_TRAP_R or (c.get("mfe_r") or 0) >= 0.8:
            worst.append({"sym": c.get("sym"), "book": book,
                          "fee_r": c.get("fee_r"), "mfe_r": c.get("mfe_r"),
                          "causes": [k for k, _ in causes]})
    rep = {"generated": now_ms, "window_h": window_h,
           "stops": total, "enriched_now": enriched,
           "by_cause": dict(sorted(by_cause.items(), key=lambda x: -x[1])),
           "by_book": dict(sorted(by_book.items(), key=lambda x: -x[1])),
           "note": ("vetoed = گروه کنترل عمدی (اثبات درستی وتو)؛ "
                    "باخت آن دفتر شکست سیستم نیست"),
           "worst": worst[:12]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    if write_memory:
        try:
            from hamid import memory as mem
            day = time.strftime("%Y-%m-%d", time.gmtime(now_ms / 1000))
            for k, n in rep["by_cause"].items():
                if n >= 5 and k != "setup_weak":
                    mem.remember("درس", "-",
                                 f"[{day}] کلاس باخت {k}: ×{n} در {window_h}س — "
                                 + dict(classify_docs())[k])
        except Exception:                            # noqa: BLE001
            pass
    return rep


def classify_docs():
    return [("fee_trap", "استاپ تنگ، کارمزد R را می‌خورد — کف فاصلهٔ استاپ لازم"),
            ("counter_trend", "ورود خلاف روند ۴س — دروازهٔ روند حالا در گلوگاه است"),
            ("gave_back", "سود ≥۰.۸R برگشت تا استاپ — قانون تریل ⅓ سخت‌گیرانه‌تر اجرا شود"),
            ("instant_reversal", "ورود و سقوط فوری — تأیید لحظهٔ ورود (۵د) ضعیف بوده"),
            ("chop", "بازار رنج — فیلتر ADX/رژیم ورود را نگرفته"),
            ("setup_weak", "بدون الگوی عددی مشخص")]


if __name__ == "__main__":
    r = run()
    print(f"استاپ‌های {r['window_h']}س: {r['stops']} · غنی‌شده: {r['enriched_now']}")
    for k, n in r["by_cause"].items():
        print(f"  {k:16} ×{n}")
