#!/usr/bin/env python3
"""حل‌کنندهٔ تعارض rebase برای خروجی‌های جستجوی پارامتر.

دو شب متوالی (۱۵–۱۶ اوت) ۴.۵ ساعت اندازه‌گیری در قدم push سوخت:
شب اول پوش به برنچ واگرا، شب دوم تعارض add/add روی search-cache.json
وقتی اجرای کرونِ صف‌شده با اجرای دستی هم‌پوشان شد. کش قابل‌ادغام است —
نتایج هر دو طرف union می‌شوند (قانون وضعیت مشترک: اجتماع برای دفترها).

استفاده در ورک‌فلو، فقط وقتی rebase تعارض داد:
    python3 tests/search-merge.py && git add claude-liam-signal/cycles \
        && GIT_EDITOR=true git rebase --continue
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYCLES = "claude-liam-signal/cycles"


def _stage(stage, path):
    r = subprocess.run(["git", "show", f":{stage}:{path}"],
                       capture_output=True, text=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


def main():
    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                       capture_output=True, text=True, cwd=ROOT)
    conflicted = [x for x in r.stdout.split() if x.startswith(CYCLES)]
    if not conflicted:
        print("تعارضی در cycles نیست")
        return 0
    for path in conflicted:
        if path.endswith("search-cache.json"):
            ours, theirs = _stage(2, path), _stage(3, path)
            merged = None
            for side in (ours, theirs):
                try:
                    d = json.loads(side)
                except Exception:                    # noqa: BLE001
                    continue
                if merged is None:
                    merged = d
                    continue
                # فقط کش هم‌هویت (همان موتور/شبیه‌ساز/تقسیم بازار) ادغام
                # می‌شود؛ غیر از آن، بزرگ‌تر می‌ماند — اختلاط دو سنجش ممنوع.
                if (d.get("engine") == merged.get("engine")
                        and d.get("fit") == merged.get("fit")
                        and d.get("test") == merged.get("test")):
                    merged["results"].update(d.get("results") or {})
                elif len(d.get("results") or {}) > len(merged.get("results") or {}):
                    merged = d
            if merged is None:
                print(f"هیچ طرف {path} JSON سالم نبود", file=sys.stderr)
                return 1
            (ROOT / path).write_text(json.dumps(merged))
            print(f"union {path}: {len(merged['results'])} نتیجه")
        else:
            # گزارش‌ها (md/json روزانه) بازتولیدشدنی‌اند — نسخهٔ همین اجرا
            ours = _stage(2, path)
            if ours is not None:
                (ROOT / path).write_text(ours)
                print(f"ours {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
