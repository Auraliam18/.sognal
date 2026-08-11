"""بازسنجی حافظه (Memory Curator) — دستور حمید، ۱۲ اوت:

    «با تغییر انجین‌ها، یادگیری‌های قبلی ارزها از بین نروند؛ مجدد توسط
    انجین‌های جدید پایش شوند — تأییدشده در یادگیری بماند، تأییدنشده و
    ردشده پاک شود.»

روزی یک بار، هر درسِ حافظهٔ فعال (lessons.json) در برابر شواهد
اندازه‌گیری‌شدهٔ انجین‌های *جدید* سنجیده می‌شود:

· شاهد اصلی: brain/history-stats.json — هر شب انجین فعلی روی کندل واقعی
  همهٔ ارزها را ریپلی می‌کند (۴هزار+ ترید)؛ این «پایش مجدد با انجین جدید»
  به معنای واقعی است چون فایل هر شب از صفر با کد امروز ساخته می‌شود.
· شاهد دوم: Universe روزانه — ارزی که دیگر در ۲۰۰تای قابل‌معامله نیست.

حکم هر درس:
  fact       — نتیجهٔ واقعی معامله/ضرر واقعی: فاکت است، هرگز بازسنجی/پاک نمی‌شود
  confirmed  — پیکرهٔ ریپلی ارز (n≥۳۰) CI روشن دارد: می‌ماند
  pending    — شاهد هنوز کافی نیست: می‌ماند تا شاهد برسد (پاک کردن بی‌شاهد،
               خودش حدس است)
  retired    — ارز از Universe خارج و درس کهنه (>۳۰ روز)، یا pendingِ
               بالای ۶۰ روز که هیچ شاهدی برایش نیامده: از حافظهٔ فعال
               حذف و به retired.jsonl منتقل می‌شود (append-only، برای
               حسابرسی — «پاک از حافظهٔ کاری»، نه جعلِ تاریخ)

مستثنی‌های صریح (دستورهای قبلی خود حمید): brain/pump-history.json و
brain/cases/ فاکت‌اند و هرگز پاک نمی‌شوند. انجین‌ها هم دست نمی‌خورند —
این یک ناظر جداست.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
RETIRED = ROOT / "brain" / "memory" / "retired.jsonl"
MARK = ROOT / "brain" / "memory" / ".revalidated"

FACT_KINDS = ("نتیجه", "ضرر واقعی")


def _corpus(hist, sym):
    """بزرگ‌ترین پیکرهٔ ریپلی این ارز (هر دو جهت) از history-stats."""
    best = None
    for d in ("LONG", "SHORT"):
        s = (hist.get("stats") or {}).get(f"{sym}|{d}")
        if s and (best is None or s["n"] > best["n"]):
            best = s
    return best


def judge(lesson, hist, uni_syms, now_ms):
    """حکم یک درس — خالص و تست‌پذیر. برگشتی: status."""
    if lesson.get("kind") in FACT_KINDS:
        return "fact"
    sym = lesson.get("sym")
    age_d = (now_ms - (lesson.get("at") or now_ms)) / 86400e3
    if not sym or sym == "-":
        return "retired" if age_d > 60 else "pending"
    c = _corpus(hist, sym)
    if c and c["n"] >= 30:
        ci = c.get("ci")
        if ci and (ci[0] > 0 or ci[1] < 0):
            return "confirmed"
        return "pending"
    if uni_syms and sym not in uni_syms and age_d > 30:
        return "retired"
    if age_d > 60:
        return "retired"                              # دو ماه بی‌شاهد = تأییدنشده
    return "pending"


def run(force=False):
    """بازسنجی روزانه — ایمن برای فراخوانی مکرر (نشان روز)."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if not force and MARK.exists() and MARK.read_text().strip() == today:
        return None
    from hamid import memory
    j = memory._load()
    try:
        hist = json.loads(memory.HISTORY.read_text())
    except Exception:                                # noqa: BLE001
        hist = {}
    uni_syms = set()
    try:
        from hamid import universe
        latest = sorted(universe.UNI_DIR.glob("*.json"))
        if latest:
            uni_syms = {m["symbol"] for m in
                        json.loads(latest[-1].read_text()).get("members", [])}
    except Exception:                                # noqa: BLE001
        uni_syms = set()
    now = time.time() * 1000
    kept, retired = [], []
    counts = {"fact": 0, "confirmed": 0, "pending": 0, "retired": 0}
    for l in j.get("lessons", []):
        st = judge(l, hist, uni_syms, now)
        counts[st] += 1
        if st == "retired":
            retired.append({**l, "retired_at": int(now),
                            "why_retired": "بازسنجی انجین جدید: شاهد تأیید نیامد"})
        else:
            kept.append({**l, "status": st})
    if retired:
        RETIRED.parent.mkdir(parents=True, exist_ok=True)
        with RETIRED.open("a") as f:
            for r in retired:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    j["lessons"] = kept
    j["revalidated"] = {"date": today, **counts}
    memory.LESSONS.parent.mkdir(parents=True, exist_ok=True)
    memory.LESSONS.write_text(json.dumps(j, ensure_ascii=False, indent=1))
    MARK.write_text(today)
    print(f"بازسنجی حافظه: {counts['fact']} فاکت · {counts['confirmed']} تأیید · "
          f"{counts['pending']} در انتظار شاهد · {counts['retired']} بازنشسته")
    return counts
