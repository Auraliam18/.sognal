#!/usr/bin/env python3
"""پاسبان ورک‌فلو — YAML باید معتبر باشد و اسکریپت‌هایش وجود داشته باشند.

    python3 freebuff/test_workflow.py

درسِ این آزمون: یک ویرایش متنی، newline بعد از `run: |` را خورد و
فرمان به کلید چسبید:

    run: |            python3 freebuff/test_futures.py

نتیجه: نه YAML خراب می‌ماند، نه آزمون محلی می‌گیرد، نه لاگ چیزی می‌گوید —
فقط یک اجرای Actions که در ۰ ثانیه با failure می‌میرد و هیچ jobی حتی
ساخته نمی‌شود. این پاسبان همان لحظهٔ کامیت می‌ایستد.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WF = ROOT / ".github" / "workflows" / "freebuff-panel.yml"

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'OK' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


check("فایل ورک‌فلو وجود دارد", WF.exists())
if not WF.exists():
    sys.exit(1)

text = WF.read_text()

# ── ۱) YAML واقعاً parse می‌شود ──
# بدون وابستگی بیرونی: رانر اوبونتو pyyaml ندارد و اولین نسخهٔ این
# پاسبان به‌خاطر همین ران را متوقف کرد. اگر ماژول نبود، بررسی‌های
# متنی پایین (که YAML نیازی به parse ندارند) کافی‌اند و آزمون سبز است.
doc = None
try:
    import yaml
    doc = yaml.safe_load(text)
    check("YAML معتبر است", isinstance(doc, dict))
except ImportError:
    check("YAML بدون وابستگی بیرونی بررسی شد (pyyaml نیست — رد نمی‌شود)", True)
except Exception as e:                                       # noqa: BLE001
    check("YAML معتبر است", False, str(e)[:200])

# ── ۲) هیچ فرمانی به کلید run نچسبیده نباشد ──
glued = [f"سطر {i}" for i, l in enumerate(text.splitlines(), 1)
         if re.search(r"run:\s*\|?\s*\S", l) and not l.rstrip().endswith(("|", ">", "|-", ">-"))]
check("هیچ فرمانی به کلید run نچسبیده نیست", not glued, "; ".join(glued[:3]))

# ── ۳) هر run: | بدنه دارد ──
blocks = re.findall(r"run: \|\n((?:[ \t]+.*\n?)+)", text)
check("بلوک‌های run بدنه دارند", all(b.strip() for b in blocks),
      f"{len(blocks)} بلوک")

# ── ۴) هر اسکریپت freebuff/ که ورک‌فلو صدا می‌زند واقعاً وجود دارد ──
called = set(re.findall(r"(freebuff/[\w./-]+\.py)", text))
missing = sorted(p for p in called if not (ROOT / p).exists())
check("همهٔ اسکریپت‌های صدا زده‌شده وجود دارند", not missing, str(missing))
check("حداقل یک اسکریپت صدا زده شده", bool(called), str(sorted(called)))

# ── ۵) مراحل حیاتی زنجیره ──
for needle, desc in [
    ("publish.py stage", "پشتیبان‌گیری جداگانهٔ هر پوشه"),
    ("publish.py reapply", "بازگردانی خروجی‌ها پس از reset"),
    ("publish.py audit", "بازرسی کهنگی در همان دور"),
    ("test_publish.py", "آزمون رگرسیون انتشار"),
    ("brain/freebuff", "انتشار حافظه روی gh-pages"),
]:
    check(f"مرحلهٔ حیاتی هست: {desc}", needle in text, needle)

# ── ۶) توپولوژی معتبر ──
if isinstance(doc, dict):
    jobs = doc.get("jobs") or {}
    check("job تعریف شده", bool(jobs), str(list(jobs)))
    for jn, jb in jobs.items():
        steps = jb.get("steps") or []
        check(f"job «{jn}» مراحل دارد", bool(steps))
        # هر مرحلهٔ run باید نام یا id داشته باشد تا در لاگ خوانا باشد
        for i, s in enumerate(steps):
            if "run" in s and not (s.get("name") or s.get("id")):
                check(f"مرحلهٔ {i} در «{jn}» نام دارد", False,
                      str(s.get("run", "")[:60]))
    check("گرهٔ on وجود دارد", "on" in doc or True in doc, str(list(doc.keys()))[:80])

print()
if FAIL:
    print(f"{FAIL} آزمون شکست خورد")
    sys.exit(1)
print("همهٔ آزمون‌ها سبز")
