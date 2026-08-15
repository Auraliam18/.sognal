#!/usr/bin/env python3
"""حل تعارضِ فایل‌های تولیدشدهٔ brain/ با معنای درستِ هرکدام.

چرا لازم شد: ورک‌فلوهای ابری (چرخه، رادار، میز تمرین) هم‌زمان با کار
دستی به همین مسیرها می‌نویسند، و هر merge روی این فایل‌ها تعارض می‌دهد.
دو راه‌حلِ رایج هر دو غلط‌اند:

  · `--ours` → درس‌ها و معامله‌های سمت دیگر پاک می‌شوند. دستور صریح
    حمید: «هیچ‌وقت نباید اطلاعات از پنل پاک شود.»
  · `--theirs` → همان خسارت، در جهت عکس.

پس هر فایل با **معنای خودش** حل می‌شود:

  closed.jsonl      append-only → اجتماع خطوط یکتا، مرتب بر زمان بسته‌شدن
  lessons.json      فهرست درس → اجتماع بر (زمان، نوع، نماد، متن)، سقفِ خودش
  learning/index.json  مشتق‌شده → **بازساخته** می‌شود، نه merge؛ ادغام دو
                    شمارنده عدد بی‌معنا می‌سازد که شبیه عدد درست است.

استفاده:  python3 scripts/resolve_brain_conflicts.py
خروج ۰ یعنی همه حل شد؛ هر مسیر ناشناخته دست‌نخورده و گزارش می‌شود.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _stage(stage, path):
    r = subprocess.run(["git", "show", f":{stage}:{path}"],
                       capture_output=True, text=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


def unresolved():
    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                       capture_output=True, text=True, cwd=ROOT)
    return [p for p in r.stdout.split("\n") if p.strip()]


def merge_jsonl(path):
    """اجتماع خطوط یکتا. خط تکراری یک معامله نیست، همان معامله است."""
    rows, seen = [], set()
    for st in (2, 3):
        for line in (_stage(st, path) or "").splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            try:
                rows.append((json.loads(line).get("closed") or 0, line))
            except Exception:                        # noqa: BLE001 - خط خراب رد
                continue
    rows.sort(key=lambda x: x[0])
    (ROOT / path).write_text("\n".join(l for _, l in rows) + "\n", encoding="utf-8")
    return f"{len(rows)} ردیف یکتا"


def merge_lessons(path):
    o, t = _stage(2, path), _stage(3, path)
    o, t = json.loads(o), json.loads(t)
    seen, out = set(), []
    for L in (o.get("lessons") or [], t.get("lessons") or []):
        for e in L:
            k = (e.get("at"), e.get("kind"), e.get("sym"), (e.get("text") or "")[:120])
            if k in seen:
                continue
            seen.add(k)
            out.append(e)
    out.sort(key=lambda e: e.get("at") or 0)
    # سقف را از خودِ فایل بردار، نه از یک عدد ثابت اینجا — اگر memory.py
    # سقفش را عوض کند، این اسکریپت نباید با آن اختلاف پیدا کند.
    cap = max(len(o.get("lessons") or []), len(t.get("lessons") or [])) or len(out)
    (ROOT / path).write_text(
        json.dumps({"lessons": out[-cap:],
                    "updated": max(o.get("updated") or 0, t.get("updated") or 0)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return f"اجتماع {len(out)} درس → {min(len(out), cap)} نگه داشته شد"


def rebuild_index(path):
    sys.path.insert(0, str(ROOT / "claude-liam-signal" / "python"))
    import brain                                     # noqa: PLC0415
    j = brain.build_index()
    return (f"بازساخته شد: {len(j.get('by_symbol') or {})} نماد"
            if isinstance(j, dict) else "بازساخته شد")


HANDLERS = {
    "brain/paper/closed.jsonl": merge_jsonl,
    "brain/memory/lessons.json": merge_lessons,
    "brain/learning/index.json": rebuild_index,
}


def main():
    files = unresolved()
    if not files:
        print("تعارضی نیست")
        return 0
    left = []
    for p in files:
        fn = HANDLERS.get(p)
        if fn is None:
            left.append(p)
            continue
        try:
            print(f"✓ {p}: {fn(p)}")
        except Exception as e:                       # noqa: BLE001
            print(f"✗ {p}: {type(e).__name__}: {e}")
            left.append(p)
            continue
        subprocess.run(["git", "add", "--", p], cwd=ROOT, check=False)
    if left:
        print(f"\n⚠ دستی بماند ({len(left)}): {left}")
        return 1
    # هرگز فایلی با مارکر تعارض ثبت نشود — یک بار index.json با مارکر
    # کامیت شد و یادگیری ساعت‌ها بی‌صدا خاموش ماند.
    g = subprocess.run(["git", "grep", "-lE", "^(<<<<<<< |>>>>>>> )", "--", "brain"],
                       capture_output=True, text=True, cwd=ROOT)
    if g.stdout.strip():
        print(f"✗ مارکر تعارض باقی مانده: {g.stdout.split()}")
        return 1
    print("همهٔ تعارض‌های brain حل شد")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
