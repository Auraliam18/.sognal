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


def merge_frontier(path):
    """پرونده‌های «مرز پیشروی»: {نماد: زمان}. بزرگ‌ترین برنده است.

    این فایل‌ها فقط جلو می‌روند — می‌گویند تا کجای تاریخ هر ارز بازپخش شده.
    گرفتنِ max نه چیزی را از دست می‌دهد و نه تکراری می‌سازد؛ گرفتنِ min
    باعث می‌شد همان بازه دوباره ترید شود و نمونهٔ متورمِ تکراری بسازد.

    ۱۵ اوت: نبودِ همین handler کل job را قرمز کرد و ~۳۸ معاملهٔ تازه را
    از بین برد. «دستی بماند» برای آدم درست است؛ داخل ورک‌فلو آدمی نیست."""
    a, b = json.loads(_stage(2, path) or "{}"), json.loads(_stage(3, path) or "{}")
    out = dict(a)
    for k, v in b.items():
        cur = out.get(k)
        try:
            out[k] = max(cur, v) if cur is not None else v
        except TypeError:                             # نوع ناسازگار → تازه‌تر
            out[k] = v
    (ROOT / path).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return f"{len(out)} نماد، مرز جلوتر برنده"


def merge_key_list(path):
    """فهرست کلیدهای ضدتکرار (مثل brain/telegram-sent.json): اجتماع.

    این عکس‌فوری **نیست** — دفترِ «چه چیزی قبلاً فرستاده شده» است. اگر
    کلیدی از یک طرف بیفتد، همان سیگنال دوباره به تلگرام می‌رود و قانون
    ضدتکرار حمید نقض می‌شود. پس اجتماع، با همان سقف ۵۰۰تایی که خودِ
    tg_batch نگه می‌دارد و تازه‌ترین‌ها را می‌ماند."""
    a = json.loads(_stage(2, path) or "[]")
    b = json.loads(_stage(3, path) or "[]")
    seen, out = set(), []
    for k in list(a) + list(b):
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    out = out[-500:]
    (ROOT / path).write_text(json.dumps(out, ensure_ascii=False),
                             encoding="utf-8")
    return f"{len(out)} کلید ضدتکرار (اجتماع)"


def take_ours(path):
    """برای عکس‌فوری‌های تولیدشده: نسخهٔ همین اجرا تازه‌تر است و برنده.

    این فقط برای signals/ درست است — آن‌جا فایل یک **عکس کاملِ لحظه** است،
    نه دفتر انباشته. اگر همین منطق روی brain/ اعمال شود، دفتر معاملهٔ اجرای
    دیگر پاک می‌شود؛ دقیقاً همان اتفاقی که ۱۵ اوت افتاد و ۳۹۰ ردیف برد."""
    subprocess.run(["git", "checkout", "--ours", "--", path], cwd=ROOT, check=False)
    return "عکس‌فوری تازهٔ همین اجرا"


EXACT = {
    "brain/memory/lessons.json": merge_lessons,
    "brain/learning/index.json": rebuild_index,
}

# ── دفترِ انباشته در برابر عکس‌فوریِ مشتق‌شده ─────────────────────────────
#
# این تمایز، تمام ماجرای ۱۵ اوت است و باید دقیق بماند:
#
#   · **دفتر انباشته** (closed.jsonl، lessons) تاریخِ منحصربه‌فرد دارد. هر
#     طرف می‌تواند ردیف‌هایی داشته باشد که طرف دیگر ندارد، پس `--ours`
#     یعنی نابودیِ آن‌ها. این‌ها **اجتماع** می‌شوند.
#
#   · **عکس‌فوری مشتق‌شده** (سلامت، ترازو، دلایل، سری دامیننس) تاریخِ
#     منحصربه‌فرد **ندارد** — تابعی از همان دفترهاست و اجرای بعدی از نو
#     می‌سازدش. این‌جا تازه‌ترین محاسبه برنده است و چیزی از دست نمی‌رود.
#
# فهرست صریح است، نه قاعدهٔ فراگیر: قاعدهٔ فراگیرِ «هر json زیر brain مالِ
# ماست» همان چیزی است که ۳۹۰ ردیف را برد. هر فایل تازه باید آگاهانه
# این‌جا اضافه شود، وگرنه آزمونِ ساختاری صدایش را درمی‌آورد.
DERIVED_SNAPSHOTS = {
    "brain/analysis-btc.json",
    "brain/dominance-series.json",
    "brain/health.json",
    "brain/history-stats.json",
    "brain/medic.json",
    "brain/paper/equity.json",       # از closed.jsonl ساخته می‌شود
    "brain/paper/reasons.json",      # خروجی ماشین بونفرونی، از همان دفتر
    "brain/paper/bridge.json",       # پل تمرین→سیگنال، هر اجرا از closed.jsonl
                                     # از نو ساخته می‌شود — تاریخِ انباشته ندارد
    "brain/sources-probe.json",      # نتیجهٔ کاوش منابع، هر اجرا از نو
}


def handler_for(path):
    """کدام معنا برای کدام مسیر — ترتیب مهم است."""
    if path in EXACT:
        return EXACT[path]
    if path == "brain/telegram-sent.json":
        return merge_key_list                         # دفتر ضدتکرار، نه عکس‌فوری
    if path in DERIVED_SNAPSHOTS:
        return take_ours                              # مشتق‌شده، تاریخ ندارد
    if path.startswith("brain/") and path.endswith(".jsonl"):
        return merge_jsonl                            # هر دفتر append-only
    if path.startswith("brain/") and path.endswith("-state.json"):
        return merge_frontier                         # مرز پیشروی هر انجین
    if path.startswith("brain/research/") and path.endswith("last-seen.json"):
        return merge_frontier                         # {url: وضعیت} — کلیدها جمع
    if path.startswith("signals/"):
        return take_ours
    # آرشیو بک‌تست — ۱۷ اوت: heartbeat و hamid-backtest هر دو این پوشه را
    # commit می‌کنند ولی resolver برایش handler نداشت؛ اولین تصادم واقعی
    # None گرفت، exit 1 شد و **کل استپ ضربان** را کشت (سه شکست Heartbeat
    # و یک Publish to main در همان صبح). فایل‌های تاریخ‌دار
    # (backtest-<date>.json) دو محتوای متفاوت با یک نام نمی‌گیرند مگر دو
    # رانر هم‌زمان — آن‌جا هم هر دو از یک ورودی ساخته شده‌اند و تازه‌تر
    # کافی است؛ latest.json هم عکس‌فوریِ بازتولیدشدنی است.
    if path.startswith("claude-liam-signal/backtests/") and path.endswith(".json"):
        return take_ours
    if path.startswith("claude-liam-signal/backtests/") and path.endswith(".jsonl"):
        return merge_jsonl                            # اگر روزی دفتر شد، اجتماع
    # ── واپسین پناه برای هر json تولیدشدهٔ ناشناخته زیر brain/ ──────────────
    #
    # قبلاً این‌جا None برمی‌گشت یعنی «دستی بماند». برای یک آدم درست است؛
    # داخل ورک‌فلوی بی‌ناظر یعنی exit 1، merge --abort، و کارِ آن اجرا نابود.
    # دو بار همین اتفاق افتاد: یک‌بار با fill-state، یک‌بار با fill-status.
    #
    # این پناه امنِ ماجرای ۱۵ اوت را تکرار نمی‌کند، چون هر نوعِ خطرناکی
    # قبلاً handler صریح دارد و بالاتر گرفته می‌شود: دفتر jsonl (اجتماع)،
    # درس‌ها (اجتماع)، کلیدهای ضدتکرار (اجتماع)، مرز پیشروی (max). چیزی که
    # به این‌جا می‌رسد یک عکس‌فوری مشتق‌شده است و اجرای بعد از نو می‌سازدش.
    #
    # بلند اعلام می‌شود تا اگر روزی یک **دفتر انباشتهٔ تازه** از این‌جا رد
    # شد، در لاگ دیده شود و handler صریحش نوشته شود.
    if path.startswith("brain/") and path.endswith(".json"):
        print(f"⚠ handler صریح ندارد، عکس‌فوری فرض شد: {path} — "
              "اگر این فایل تاریخِ انباشته دارد، handler برایش بنویس")
        return take_ours
    return None                                       # بیرون از brain/ = دستی


def main():
    files = unresolved()
    if not files:
        print("تعارضی نیست")
        return 0
    left = []
    for p in files:
        fn = handler_for(p)
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
    g = subprocess.run(["git", "grep", "-lE", "^(<<<<<<< |>>>>>>> )",
                        "--", "brain", "signals"],
                       capture_output=True, text=True, cwd=ROOT)
    if g.stdout.strip():
        print(f"✗ مارکر تعارض باقی مانده: {g.stdout.split()}")
        return 1
    print("همهٔ تعارض‌ها با معنای خودشان حل شد")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
