"""آزمون سلامت ورک‌فلوها — درس ۱۴ اوت: live-scan روزها بی‌صدا مرده بود.

عیب واقعی: یک گام دو کلید `if` داشت. پایتون YAML را می‌خواند (آخری برنده)
و همهٔ بررسی‌های ما سبز می‌شد، ولی **گیت‌هاب کل فایل را رد می‌کرد** —
run با صفر job، وضعیت failure، و در API به‌جای «Live scan» مسیر فایل
نشان داده می‌شد. یعنی اسکن زنده اصلاً اجرا نمی‌شد و فقط ایمیل
«Run failed» می‌آمد.

این آزمون همان چیزی را می‌سنجد که گیت‌هاب سخت‌گیرانه می‌سنجد:
  ۱. هیچ کلید تکراری در هیچ سطحی (چیزی که SafeLoader بی‌صدا می‌بلعد)
  ۲. name/on/jobs موجود باشد
  ۳. هر گام حداکثر یک if داشته باشد و هر job حداقل یک گام
  ۴. هر uses نسخهٔ پین‌شده داشته باشد
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WF = ROOT / ".github" / "workflows"

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


class StrictLoader(yaml.SafeLoader):
    """مثل گیت‌هاب: کلید تکراری خطاست، نه «آخری برنده»."""


def _no_dup(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise ValueError(f"کلید تکراری: {key!r}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dup)


def _raw_dup_if(text):
    """Inspect step mappings, keeping duplicate keys and their source lines.

    A job-level if or a shell-script line is not part of the previous step.
    compose preserves mapping pairs instead of silently keeping the last key.
    """
    def child(node, key):
        if isinstance(node, yaml.MappingNode):
            return next((v for k, v in node.value if k.value == key), None)
        return None

    bad = []
    jobs = child(yaml.compose(text, Loader=yaml.BaseLoader), "jobs")
    if not isinstance(jobs, yaml.MappingNode):
        return bad
    for _, job in jobs.value:
        steps = child(job, "steps")
        if not isinstance(steps, yaml.SequenceNode):
            continue
        for step in steps.value:
            if not isinstance(step, yaml.MappingNode):
                continue
            keys = [k for k, _ in step.value if k.value == "if"]
            bad.extend(k.start_mark.line + 1 for k in keys[1:])
    return bad


print("── سلامت ورک‌فلوها ──")

check("شرط job بعدی به گام قبلی نسبت داده نمی‌شود", not _raw_dup_if("""
jobs:
  first:
    steps:
      - run: echo one
        if: always()
  second:
    if: github.event_name == 'workflow_dispatch'
    steps:
      - run: echo two
"""))
check("شرط تکراری واقعی داخل گام شناسایی می‌شود", bool(_raw_dup_if("""
jobs:
  one:
    steps:
      - run: echo test
        if: success()
        if: always()
""")))
check("متن اسکریپت کلید شرط YAML نیست", not _raw_dup_if("""
jobs:
  one:
    steps:
      - if: always()
        run: |
          if: script text
"""))

files = sorted(WF.glob("*.yml")) + sorted(WF.glob("*.yaml"))
check(f"ورک‌فلو پیدا شد ({len(files)})", len(files) > 0)

dup, missing, many_if, unpinned, empty = [], [], [], [], []
for f in files:
    text = f.read_text(encoding="utf-8")
    try:
        j = yaml.load(text, StrictLoader)
    except Exception as e:                            # noqa: BLE001
        dup.append(f"{f.name}: {e}")
        continue
    if not j or "name" not in j or "jobs" not in j or not (True in j or "on" in j):
        missing.append(f.name)
        continue
    for ln in _raw_dup_if(text):
        many_if.append(f"{f.name}:{ln}")
    for jid, job in (j.get("jobs") or {}).items():
        steps = job.get("steps") or []
        if not steps:
            empty.append(f"{f.name}:{jid}")
        for s in steps:
            u = s.get("uses")
            if u and "@" not in str(u):
                unpinned.append(f"{f.name}: {u}")

check("هیچ کلید تکراری در هیچ ورک‌فلو (همان چیزی که گیت‌هاب رد می‌کند)", not dup)
for d in dup:
    print(f"      ↳ {d}")
check("همهٔ ورک‌فلوها name/on/jobs دارند", not missing)
if missing:
    print(f"      ↳ {missing}")
check("هیچ گامی دو if ندارد", not many_if)
if many_if:
    print(f"      ↳ {many_if}")
check("هر job حداقل یک گام دارد", not empty)
if empty:
    print(f"      ↳ {empty}")
check("همهٔ uses نسخهٔ پین‌شده دارند", not unpinned)
if unpinned:
    print(f"      ↳ {unpinned}")

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون سلامت ورک‌فلو گذشت ({len(files)} فایل)")
