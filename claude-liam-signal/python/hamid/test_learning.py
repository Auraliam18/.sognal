"""آزمون‌های حلقهٔ دانش — بدون شبکه، با فایل‌سیستم موقت.

چیزی که اثبات می‌شود (قوانین سند یادگیری دائمی حمید، ۱۴ اوت):
  ۱. رجیستری ۲۶ انجین سالم لود می‌شود و پایپ‌لاین ۹ پله دارد
  ۲. پرش از پله ممنوع است — BACKTESTED یک‌باره PRODUCTION نمی‌شود
  ۳. گذار بی‌مدرک از HYPOTHESIS به بعد رد می‌شود
  ۴. Tier 5 (X/کامیونیتی) بدون evidence راستی‌آزمایی جلو نمی‌رود
  ۵. REJECTED با علت ذخیره می‌شود (تا تکرار نشود) و از وضعیت پایانی گذار نیست
  ۶. فقط E21 ارتقا می‌دهد؛ هر کمبود مدرک با نامش رد می‌شود
  ۷. CI دربرگیرندهٔ صفر ارتقا نمی‌گیرد (قانون LIAM)
  ۸. SUPERSEDE حذف نمی‌کند — نسخهٔ قدیم می‌ماند
  ۹. مانیتور منبع: تغییر واقعی → DISCOVERED؛ بی‌تغییر → هیچ؛ خطا → backoff
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ok = 0
fail = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


def expect_raise(name, fn, contains=""):
    try:
        fn()
    except Exception as e:                        # noqa: BLE001
        check(name, contains in str(e))
        return
    check(name, False)


print("── حلقهٔ دانش (فاز ۱) ──")

# همهٔ نوشتن‌ها به مغز موقت — مغز واقعی دست نمی‌خورد
TMP = Path(tempfile.mkdtemp())
from research import claim_registry as cr                      # noqa: E402
from research import memory_promotion as mp                    # noqa: E402
from research import source_monitor as sm                      # noqa: E402
cr.RESEARCH = TMP / "research"
mp.CANONICAL = TMP / "memory" / "canonical" / "lessons.jsonl"
mp.PRIVATE = TMP / "memory" / "private"
sm.RESEARCH = TMP / "research"

# ── ۱. رجیستری ─────────────────────────────────────────────────────────────
reg = sm.load_registry()
check("رجیستری ۲۶ انجین دارد", len(reg["engines"]) == 26)
check("پایپ‌لاین ۹ پله است", len(reg["knowledge_pipeline"]) == 9)
check("live_execution=false در رجیستری", reg["live_execution"] is False)
check("نوشتن مستقیم در production خاموش است",
      reg["production_learning_direct_write"] is False)
ids = [e["id"] for e in reg["engines"]]
check("هر ۵ انجین فاز ۱ در رجیستری هستند", all(e in ids for e in sm.PHASE1))
# بند G سند (۱۴ اوت): داربست research/private برای هر ۲۶ انجین
_root = Path(__file__).resolve().parents[3]
check("داربست brain/research برای هر ۲۶ انجین هست",
      all((_root / "brain" / "research" / e).is_dir() for e in ids))
check("داربست brain/memory/private برای هر ۲۶ انجین هست",
      all((_root / "brain" / "memory" / "private" / e).is_dir() for e in ids))
check("هر انجین ۳ کتاب و ۲ منبع دارد",
      all(len(e["books"]) == 3 and e.get("primary_source") and e.get("secondary_source")
          for e in reg["engines"]))

# ── ۲. دفتر Claim: مسیر پله‌پله ────────────────────────────────────────────
c = cr.new_claim("E18", "walk-forward با purge بهتر از split ساده",
                 "https://vectorbt.dev/", 1)
check("claim تازه از DISCOVERED شروع می‌شود", c["status"] == "DISCOVERED")

expect_raise("پرش DISCOVERED→BACKTESTED رد می‌شود",
             lambda: cr.advance("E18", c, "BACKTESTED"), "پرش")

c = cr.advance("E18", c, "SOURCE_VERIFIED")
c = cr.advance("E18", c, "CLAIM_EXTRACTED")
expect_raise("HYPOTHESIS بدون evidence رد می‌شود",
             lambda: cr.advance("E18", c, "HYPOTHESIS"), "evidence")
c = cr.advance("E18", c, "HYPOTHESIS", evidence="exp:wf-001")
c = cr.advance("E18", c, "BACKTESTED", evidence="exp:wf-001-result")
check("مسیر قانونی تا BACKTESTED رسید", c["status"] == "BACKTESTED")
check("تاریخچهٔ گذارها کامل ثبت شد", len(c["history"]) == 5)

# ── ۳. Tier 5 بدون راستی‌آزمایی ────────────────────────────────────────────
x = cr.new_claim("E00", "توییتر می‌گوید فلان الگو جواب می‌دهد",
                 "https://x.com/someone/status/1", 5)
x = cr.advance("E00", x, "SOURCE_VERIFIED")
expect_raise("Tier 5 بدون evidence راستی‌آزمایی جلو نمی‌رود",
             lambda: cr.advance("E00", x, "CLAIM_EXTRACTED"), "Tier 5")
x = cr.advance("E00", x, "CLAIM_EXTRACTED", evidence="verify:official-docs-match")
check("Tier 5 با راستی‌آزمایی رسمی عبور کرد", x["status"] == "CLAIM_EXTRACTED")

# ── ۴. REJECTED ────────────────────────────────────────────────────────────
expect_raise("REJECTED بدون علت ثبت نمی‌شود",
             lambda: cr.advance("E00", x, "REJECTED"), "علت")
x = cr.advance("E00", x, "REJECTED", note="در بک‌تست ۹۰ روزه اثر صفر بود")
check("REJECTED در فایل جدا ذخیره شد",
      (TMP / "research" / "E00" / "rejected.jsonl").exists())
expect_raise("گذار از REJECTED ممنوع است",
             lambda: cr.advance("E00", x, "HYPOTHESIS", evidence="e"), "پایانی")
loaded = cr.load("E00")
check("load آخرین وضعیت را می‌دهد (REJECTED ماند)",
      loaded[x["claim_id"]]["status"] == "REJECTED")

# ── ۵. دروازهٔ E21 ─────────────────────────────────────────────────────────
good = {"claim": "استاپ زیر سوییپ ۱س", "source_url": "exp://paper",
        "experiment_id": "exp-7", "dataset_snapshot_id": "snap-7",
        "strategy_version": "ibs-2.1", "sample_size": 64,
        "confidence_interval": [0.05, 0.31], "status": "PAPER_VALIDATED",
        "regime": "trend", "conflicts": [], "expires_at": None,
        "engine_id": "E18", "scope": "strategy"}

expect_raise("غیر از E21 هیچ‌کس ارتقا نمی‌دهد",
             lambda: mp.promote(good, actor="E18"), "E21")

bad_ci = dict(good, confidence_interval=[-0.1, 0.4])
expect_raise("CI دربرگیرندهٔ صفر رد می‌شود",
             lambda: mp.promote(bad_ci, actor="E21"), "صفر")

bad_n = dict(good, sample_size=5)
expect_raise("نمونهٔ کم رد می‌شود", lambda: mp.promote(bad_n, actor="E21"),
             "sample_size")

bad_st = dict(good, status="BACKTESTED")
expect_raise("BACKTESTED هنوز حق ارتقا ندارد (کف: PAPER_VALIDATED)",
             lambda: mp.promote(bad_st, actor="E21"), "PAPER_VALIDATED")

row, sup = mp.promote(good, actor="E21")
check("درس با مدرک کامل ارتقا گرفت", row["promoted_by"] == "E21")
check("درسِ ارتقایافته در canonical نشست", len(mp.load_canonical()) == 1)

# ── ۶. SUPERSEDE حذف نمی‌کند ───────────────────────────────────────────────
newer = dict(good, claim="استاپ زیر سوییپ ۱س + بافر ATR",
             confidence_interval=[0.08, 0.35], supersedes=row["lesson_id"])
row2, sup2 = mp.promote(newer, actor="E21")
check("نسخهٔ جدید، قدیمی را SUPERSEDED کرد", sup2 == [row["lesson_id"]])
allc = mp.load_canonical()
check("نسخهٔ قدیم حذف نشد — با برچسب SUPERSEDED ماند",
      any(l["lesson_id"] == row["lesson_id"] and l.get("status") == "SUPERSEDED"
          for l in allc))

# ── ۷. حافظهٔ خصوصی ────────────────────────────────────────────────────────
mp.private_note("E23", "p95 چرخهٔ ضربان از ۴۰s به ۱۱۰s رفت — علت: rate-limit صرافی")
check("حافظهٔ خصوصی انجین نوشته شد",
      (TMP / "memory" / "private" / "E23" / "notes.jsonl").exists())

# ── ۸. مانیتور منبع با fetcher ساختگی ──────────────────────────────────────
calls = {"n": 0}
def fake_fetch(url, etag=None):
    calls["n"] += 1
    if "broken" in url:
        raise RuntimeError("connection refused")
    return (b"content-v1" if calls["n"] <= 1 else b"content-v2"), 'W/"abc"'

r1 = sm.check_source("E02", "https://example.com/docs", 1, fetch=fake_fetch)
check("اولین دیدن منبع → new (DISCOVERED ساخته شد)", r1 == "new")
claims_e02 = cr.load("E02")
check("claim منبع در دفتر E02 نشست",
      any("SOURCE_CHANGED" in c["claim"] for c in claims_e02.values()))

r2 = sm.check_source("E02", "https://example.com/docs", 1, fetch=fake_fetch)
check("تغییر hash → دوباره new", r2 == "new")

def same_fetch(url, etag=None):
    return b"content-v2", 'W/"abc"'
r3 = sm.check_source("E02", "https://example.com/docs", 1, fetch=same_fetch)
check("بدون تغییر → unchanged (LLM صدا نمی‌شود)", r3 == "unchanged")

rf = sm.check_source("E02", "https://example.com/broken", 1, fetch=fake_fetch)
check("خطای شبکه → failed بدون crash", rf == "failed")
st = json.loads((TMP / "research" / "E02" / "last-seen.json").read_text())
check("failure_count و next_retry ثبت شد",
      st["https://example.com/broken"]["failure_count"] == 1
      and st["https://example.com/broken"]["next_retry"] > 0)
rf2 = sm.check_source("E02", "https://example.com/broken", 1, fetch=fake_fetch)
check("قبل از next_retry دوباره تلاش نمی‌کند (backoff)", rf2 == "skipped")

# ── ۹. جدایی از تولید ──────────────────────────────────────────────────────
real_research = Path(__file__).resolve().parents[3] / "brain" / "research"
check("آزمون‌ها به مغز واقعی دست نزدند",
      not (real_research / "E02" / "last-seen.json").exists())

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون حلقهٔ دانش گذشت")
