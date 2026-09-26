#!/usr/bin/env python3
"""انتشار خروجی‌های فری‌باف ۱ — ضدتصادم، با مرز مسیر روشن.

چرا این فایل وجود دارد (درسِ اندازه‌گیری‌شده، نه حدس):

نسخهٔ قبلی ورک‌فلو بکاپ را این‌طور می‌گرفت:

    cp -r signals/freebuff "$BK/"
    cp -r brain/freebuff   "$BK/"      # ← روی همان نام «freebuff» می‌نشیند

هر دو پوشه چند فایل هم‌نام دارند (dominance.json، futures.json،
round-state.json). دستور دوم محتویات اولی را هم‌نام‌به‌هم‌نام بازنویسی
می‌کرد. نتیجه در main قابل مشاهده بود: brain/freebuff/dominance.json از
۲۱ سپتامبر کهنه مانده و هر دور، نوشتهٔ تازهٔ signals/ را می‌بلعید —
یعنی پنل ۵ روز نقشهٔ دامیننس را نشان می‌داد در حالی که لاگ هر ۵ دقیقه
عدد تازه می‌ساخت. بازتولیدشده در tests/test_publish.py.

اینجا هر پوشهٔ خروجی پشتیبانِ خودش را دارد، پس هیچ هم‌نامی یقهٔ هم
نمی‌گیرد؛ و علاوه بر آن، موقع بازگردانی هر فایل با mtime سنجیده می‌شود:
نسخهٔ کهنه هرگز نمی‌تواند جای نسخهٔ تازهٔ همان مسیر بنشیند.
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# هر خروجی دقیقاً یک خانه دارد. این تنها منبع حقیقتِ مسیرها است؛
# ورک‌فلو و پنل هر دو از همین می‌خوانند.
SIGNALS = ROOT / "signals" / "freebuff"     # گزارش‌های همین دور
MEMORY = ROOT / "brain" / "freebuff"        # حافظهٔ ایجنت‌ها + سری زمانی

# فایل‌هایی که فقط در brain/ خانه دارند و نباید در signals/ (خروجی
# همین دور) هم دوباره ساخته شوند. این فیلتر فقط روی درخت signals
# اعمال می‌شود — اعمالش روی brain باعث می‌شد سری زمانی هرگز کامیت
# نشود، چون تنها خانهٔ معتبرش همان‌جاست.
SIGNALS_ONLY_TREE_SKIP = {"dominance-series.json"}

STALE_AFTER_S = 30 * 60      # خروجی تازه‌تر از این، «زنده» حساب می‌شود


def stage(dst_dir):
    """پشتیبانِ اختصاصی یک پوشه — بدون برخورد نام."""
    st = Path(tempfile.mkdtemp(prefix="fb-stage-")) / dst_dir.name
    st.mkdir(parents=True, exist_ok=True)
    return st


def _restore(stage_dir, dst_dir, *, force, skip=()):
    """بازگردانی یک پوشه با محافظ تازگی. تعداد فایل بازگردانی‌شده برمی‌گردد."""
    if not stage_dir.is_dir():
        return 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in sorted(stage_dir.iterdir()):
        if not src.is_file():
            continue
        if src.name in skip:
            continue
        dst = dst_dir / src.name
        if dst.exists() and not force:
            # فایلِ موجود تازه‌تر از پشتیبان است → دست‌نخورده می‌ماند.
            # (در چرخهٔ معمولی این شاخه هیچ‌وقت رخ نمی‌دهد چون پشتیبان
            #  درست همین لحظه از همین درخت برداشته شده؛ محافظ برای
            #  اجرای هم‌زمان و برای آزمون است.)
            try:
                if dst.stat().st_mtime > src.stat().st_mtime + 1:
                    continue
            except OSError:
                continue
        shutil.copy2(src, dst)
        n += 1
    return n


STATE = Path("/tmp/fb-bk-state.json")      # پل بین فراخوانی stage و reapply


def snapshot_outputs(*, signals=SIGNALS, memory=MEMORY, state=None):
    """هر پوشهٔ خروجی را جدا جدا در یک ریشهٔ موقت پشتیبان می‌گیرد."""
    state = STATE if state is None else state
    root = Path(tempfile.mkdtemp(prefix="fb-bk-"))
    stages = {}
    for d in (signals, memory):
        st = stage(d)
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file():
                    shutil.copy2(f, st / f.name)
        stages[d] = st
    if state is not None:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(
            {"root": str(root),
             "stages": {str(k): str(v) for k, v in stages.items()}}, indent=1))
    return root, stages


def load_state(state=None):
    """خواندن پشتیبانِ ذخیره‌شده از فراخوانی قبلی (فراخوانی CLI).

    state=None یعنی «همین حالا» — نه مقدارِ بسته‌شدهٔ هنگام تعریف. بستن
    مقدار در امضا باعث می‌شد بازنویسی STATE در تست بی‌اثر بماند.
    """
    state = STATE if state is None else state
    j = json.loads(state.read_text())
    return Path(j["root"]), {Path(k): Path(v) for k, v in j["stages"].items()}


def reapply(root, stages, *, signals=SIGNALS, memory=MEMORY, force=False):
    """درخت reset شده را با خروجی‌های خودمان دوباره می‌نشاند."""
    out = {}
    for d in (signals, memory):
        skip = SIGNALS_ONLY_TREE_SKIP if d == signals else ()
        out[d] = _restore(stages[d], d, force=force, skip=skip)
    shutil.rmtree(root, ignore_errors=True)
    return out


def audit(*, signals=SIGNALS, memory=MEMORY, stale_after_s=STALE_AFTER_S):
    """بازرسی سلامت: کهنگی و فایل‌های تکراری‌کنندهٔ نشانهٔ همان باگ.

    خروجی: dict با کلید ok. اگر ok نبود، runner باید هشدار بدهد.
    """
    now = time.time()
    problems = []
    seen = {}

    def rel(p):
        """مسیر نسبی اگر داخل ریشه باشد، وگرنه خودِ مسیر — تا audit هرگز
        به‌خاطر مسیرِ بیرون از ریشه (مثل آزمون با پوشهٔ موقت) نیفتد."""
        try:
            return p.relative_to(ROOT)
        except ValueError:
            return p

    for d in (signals, memory):
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            # همان فایل در دو درخت = نشانهٔ مرز مسیر شکسته
            if f.name in seen and seen[f.name] != d:
                problems.append(f"تکراری بین درخت‌ها: {f.name}")
            seen[f.name] = d
            if f.suffix == ".json":
                try:
                    age = now - f.stat().st_mtime
                except OSError:
                    continue
                if age > stale_after_s:
                    problems.append(f"کهنه: {rel(f)} ({int(age // 60)} دقیقه)")
                try:
                    json.loads(f.read_text())
                except Exception as e:                       # noqa: BLE001
                    problems.append(f"JSON خراب: {rel(f)} — {e}")
    return {"ok": not problems, "problems": problems}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "stage":
        root, _ = snapshot_outputs()
        print(root)
        return 0
    if cmd == "reapply":
        try:
            root, stages = load_state(STATE)
        except Exception as e:                            # noqa: BLE001
            # نبودِ پشتیبان نباید ران را بیندازد — فقط هشدار می‌دهیم.
            print(f"reapply: پشتیبانی نبود ({e}) — خروجی‌های این دور از دست رفت")
            return 0
        counts = reapply(root, stages)
        print("reapply:", sum(counts.values()), "فایل نشانده شد")
        return 0
    if cmd == "audit":
        a = audit()
        if a["ok"]:
            print("انتشار: سالم — همهٔ خروجی‌ها تازه و خوانا")
            return 0
        print("انتشار: مشکل —")
        for p in a["problems"]:
            print("  •", p)
        return 1
    print("usage: publish.py [stage|reapply|audit]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
