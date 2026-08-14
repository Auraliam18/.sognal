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
    """کلید if تکراری داخل یک گام، حتی اگر YAML آن را بپذیرد."""
    bad, cur = [], None
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith(("- name:", "- uses:", "- if:")):
            cur = {"ifs": 1 if s.startswith("- if:") else 0}
        elif cur is not None and s.startswith("if:"):
            cur["ifs"] += 1
            if cur["ifs"] > 1:
                bad.append(i)
    return bad


print("── سلامت ورک‌فلوها ──")

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
