"""آزمون حل‌کنندهٔ تعارض — درس ۱۵ اوت: ۳۹۰ ردیف دفتر معامله پاک شد.

چه شد: چرخهٔ ساعت ۰۰:۰۹ مخزن را قبل از پوش چک‌اوت کرده بود، موقع انتشار
به تعارض خورد، و با `git checkout --ours` نسخهٔ **کهنهٔ خودش** را برنده
کرد. ۳۹۰ ردیف — که ۳۸۴تایشان تنها معامله‌های برچسب‌دار تایم‌فریم بودند —
از شاخه افتادند و جدول استراتژی×تایم‌فریم خالی شد.

این آزمون همان سناریو را بازمی‌سازد: دو طرف که هرکدام ردیف‌هایی دارند که
دیگری ندارد. شرط قبولی این است که **هیچ ردیفی از هیچ طرف** گم نشود.

مخزن موقت واقعی ساخته می‌شود (نه شبیه‌سازی گیت) چون چیزی که اشتباه شد
رفتار خودِ گیت در merge بود، نه منطق پایتون.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "resolve_brain_conflicts.py"

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


def git(*a, cwd, **kw):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True,
                          text=True, **kw)


print("── حل‌کنندهٔ تعارض فایل‌های تولیدشده ──")

tmp = Path(tempfile.mkdtemp(prefix="resolve-"))
git("init", "-q", "-b", "main", cwd=tmp)
git("config", "user.email", "t@t", cwd=tmp)
git("config", "user.name", "t", cwd=tmp)

# اسکریپت واقعی داخل مخزن آزمون، با همان مسیر نسبی
(tmp / "scripts").mkdir()
(tmp / "scripts" / "resolve_brain_conflicts.py").write_text(
    SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
for d in ("brain/paper", "brain/memory", "brain/learning", "signals"):
    (tmp / d).mkdir(parents=True, exist_ok=True)


def trade(i, tf=None):
    r = {"sym": f"S{i}USDT", "dir": "LONG", "R": 0.5, "outcome": "target",
         "closed": 1_700_000_000_000 + i * 1000, "why": {"stage": "practice"}}
    if tf:
        r["tf"] = tf
        r["why"]["tf"] = tf
    return json.dumps(r, ensure_ascii=False)


def lessons(items):
    return json.dumps({"lessons": items, "updated": 1}, ensure_ascii=False)


def les(i):
    return {"at": 1_700_000_000_000 + i, "kind": "درس", "sym": f"S{i}",
            "text": f"درس شمارهٔ {i}", "data": {}}


# پایهٔ مشترک
base = [trade(i) for i in range(5)]
(tmp / "brain/paper/closed.jsonl").write_text("\n".join(base) + "\n")
(tmp / "brain/memory/lessons.json").write_text(lessons([les(0), les(1)]))
(tmp / "brain/learning/index.json").write_text(json.dumps({"built": 1}))
(tmp / "signals/latest.json").write_text(json.dumps({"generated": 1}))
git("add", "-A", cwd=tmp)
git("commit", "-qm", "base", cwd=tmp)
git("branch", "other", cwd=tmp)

# ── شاخهٔ «دیگری»: همان چیزی که پوش شده بود (با برچسب تایم‌فریم) ─────────
git("checkout", "-q", "other", cwd=tmp)
theirs = base + [trade(100 + i, tf="15m") for i in range(4)]
(tmp / "brain/paper/closed.jsonl").write_text("\n".join(theirs) + "\n")
(tmp / "brain/memory/lessons.json").write_text(lessons([les(0), les(1), les(2)]))
(tmp / "signals/latest.json").write_text(json.dumps({"generated": 100}))
git("add", "-A", cwd=tmp)
git("commit", "-qm", "پوش با معامله‌های برچسب‌دار", cwd=tmp)

# ── شاخهٔ main: همان چیزی که رانرِ کهنه داشت ─────────────────────────────
git("checkout", "-q", "main", cwd=tmp)
ours = base + [trade(200 + i) for i in range(3)]
(tmp / "brain/paper/closed.jsonl").write_text("\n".join(ours) + "\n")
(tmp / "brain/memory/lessons.json").write_text(lessons([les(0), les(1), les(3)]))
(tmp / "signals/latest.json").write_text(json.dumps({"generated": 200}))
git("add", "-A", cwd=tmp)
git("commit", "-qm", "اجرای رانر", cwd=tmp)

m = git("merge", "--no-edit", "other", cwd=tmp)
check("سناریوی واقعی بازسازی شد (merge تعارض داد)", m.returncode != 0)
conf = git("diff", "--name-only", "--diff-filter=U", cwd=tmp).stdout.split()
check("هر سه فایل تعارض دارند (دفتر، درس، عکس‌فوری)",
      set(conf) >= {"brain/paper/closed.jsonl", "brain/memory/lessons.json",
                    "signals/latest.json"})

r = subprocess.run([sys.executable, "scripts/resolve_brain_conflicts.py"],
                   cwd=tmp, capture_output=True, text=True)
print("   " + "\n   ".join(r.stdout.strip().split("\n")[:6]))
check("اسکریپت با موفقیت تمام شد", r.returncode == 0)

got = [l for l in (tmp / "brain/paper/closed.jsonl").read_text().splitlines() if l]
check(f"هیچ ردیفی گم نشد — هر دو طرف ({len(got)} = ۵ پایه + ۳ ما + ۴ آن‌ها)",
      len(got) == 12)
check("ردیف‌های طرف مقابل ماندند (همان ۳۹۰ ردیفی که پاک شده بود)",
      all(any(f'"S{100 + i}USDT"' in l for l in got) for i in range(4)))
check("ردیف‌های خودمان هم ماندند",
      all(any(f'"S{200 + i}USDT"' in l for l in got) for i in range(3)))
check("معامله‌های برچسب‌دار تایم‌فریم زنده ماندند",
      sum(1 for l in got if '"tf"' in l) == 4)
times = [json.loads(l)["closed"] for l in got]
check("دفتر مرتب بر زمان بسته‌شدن است", times == sorted(times))
check("هیچ ردیف تکراری نیست", len(set(got)) == len(got))

ls = json.loads((tmp / "brain/memory/lessons.json").read_text())["lessons"]
got_at = {e["at"] for e in ls}
# اجتماع ۴ درس است ولی سقفِ فایل ۳ — پس قدیمی‌ترین می‌افتد. این **سیاست
# خودِ memory.py** است (پنجرهٔ چرخان ۳۰۰تایی)، نه از دست رفتن داده؛ رکورد
# ماندگار در closed.jsonl و brain/cases/ است. چیزی که واقعاً مهم است:
# هیچ درسی به‌خاطر «کدام طرف merge» حذف نشود.
check("درسِ منحصربه‌طرف مقابل زنده ماند (ضد همان اشتباه --ours)",
      les(2)["at"] in got_at)
check("درسِ منحصربه‌خودمان هم زنده ماند", les(3)["at"] in got_at)
check("سقف فایل رعایت شد و تازه‌ترین‌ها ماندند",
      len(ls) == 3 and got_at == {les(i)["at"] for i in (1, 2, 3)})

sig = json.loads((tmp / "signals/latest.json").read_text())
check("عکس‌فوری signals نسخهٔ تازهٔ همین اجرا را گرفت", sig["generated"] == 200)

check("چیزی حل‌نشده نماند",
      not git("diff", "--name-only", "--diff-filter=U", cwd=tmp).stdout.strip())
c = git("commit", "--no-edit", cwd=tmp)
check("کامیت merge بدون دخالت دستی انجام شد", c.returncode == 0)
check("هیچ مارکر تعارضی ثبت نشد",
      not git("grep", "-lE", "^(<<<<<<< |>>>>>>> )", "HEAD", cwd=tmp).stdout.strip())

# ── مسیر ناشناخته باید دستی بماند، نه اینکه حدس زده شود ─────────────────
import importlib.util                                  # noqa: E402

spec = importlib.util.spec_from_file_location("rbc", SCRIPT)
rbc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rbc)
check("دفتر jsonl تازه خودکار پوشش داده می‌شود",
      rbc.handler_for("brain/paper/open.jsonl") is rbc.merge_jsonl)
check("هر jsonl زیر brain (مثلاً learning) هم پوشش دارد",
      rbc.handler_for("brain/learning/experiences.jsonl") is rbc.merge_jsonl)
check("signals عکس‌فوری می‌گیرد نه اجتماع",
      rbc.handler_for("signals/pump-radar.json") is rbc.take_ours)
check("index.json بازساخته می‌شود نه merge",
      rbc.handler_for("brain/learning/index.json") is rbc.rebuild_index)
check("مسیر ناشناخته حدس زده نمی‌شود",
      rbc.handler_for("index.html") is None
      and rbc.handler_for("claude-liam-signal/python/x.py") is None)
# این شرط قبلاً برعکس بود: «brain/*.json ناشناخته باید دستی بماند». همان
# قانون بود که چرخه را ۱۲ بار قرمز کرد؛ داخل ورک‌فلو «دستی» یعنی مرگ job.
# حالا عکس‌فوری فرض می‌شود و بلند اعلام می‌شود — امن است چون هر نوع
# انباشته handler صریح دارد و بالاتر گرفته می‌شود.
check("brain/*.json ناشناخته job را نمی‌کشد (عکس‌فوری فرض می‌شود)",
      rbc.handler_for("brain/rooms/scan.json") is rbc.take_ours)
check("پروندهٔ مرز پیشروی handler دارد",
      rbc.handler_for("brain/paper/fill-state.json") is rbc.merge_frontier
      and rbc.handler_for("brain/paper/trainer-state.json") is rbc.merge_frontier)

# مرز فقط جلو می‌رود — max برنده، و هیچ نمادی از هیچ طرف نمی‌افتد
_fr = tmp / "frontier"
(tmp / "brain" / "paper").mkdir(parents=True, exist_ok=True)
git("checkout", "-q", "main", cwd=tmp)
(tmp / "brain/paper/x-state.json").write_text(json.dumps({"A": 100, "B": 200}))
git("add", "-A", cwd=tmp)
git("commit", "-qm", "state base", cwd=tmp)
git("checkout", "-q", "-b", "other2", cwd=tmp)
(tmp / "brain/paper/x-state.json").write_text(json.dumps({"A": 50, "C": 300}))
git("add", "-A", cwd=tmp)
git("commit", "-qm", "state theirs", cwd=tmp)
git("checkout", "-q", "main", cwd=tmp)
(tmp / "brain/paper/x-state.json").write_text(json.dumps({"A": 900, "B": 150}))
git("add", "-A", cwd=tmp)
git("commit", "-qm", "state ours", cwd=tmp)
git("merge", "--no-edit", "other2", cwd=tmp)
r2 = subprocess.run([sys.executable, "scripts/resolve_brain_conflicts.py"],
                    cwd=tmp, capture_output=True, text=True)
check("تعارض مرز پیشروی خودکار حل می‌شود (نه «دستی بماند»)",
      r2.returncode == 0)
_st = json.loads((tmp / "brain/paper/x-state.json").read_text())
check("مرز جلوتر برنده است", _st.get("A") == 900)
check("نماد فقط-در-طرف-مقابل نمی‌افتد", _st.get("C") == 300)
check("نماد فقط-در-خودمان هم نمی‌افتد", _st.get("B") == 150)

# ── گاردِ ساختاری — نسخهٔ دوم، قطعی ───────────────────────────────────────
#
# نسخهٔ اول فایل‌های **واقعیِ لحظه** را زیر brain/ می‌گشت. این یعنی آزمونی
# که به وضعیت متغیرِ runtime وابسته است — و چون همین آزمون داخل دروازهٔ
# self-check چرخه بود، اولین فایل تازه‌ای که خطِ تولید ساخت
# (brain/paper/fill-status.json) کل چرخه را ۱۲ بار قرمز کرد و سه ساعت
# سیگنالِ حمید را خواباند.
#
# درس: آزمونی که جلوی تولید را می‌گیرد باید قطعی باشد. حالا **قاعده‌ها**
# سنجیده می‌شوند، نه محتویات دیسک — با فهرست ثابتِ نمونه‌های بحرانی.
CRITICAL = {
    "brain/paper/closed.jsonl": rbc.merge_jsonl,
    "brain/paper/open.jsonl": rbc.merge_jsonl,
    "brain/learning/experiences.jsonl": rbc.merge_jsonl,
    "brain/memory/lessons.json": rbc.merge_lessons,
    "brain/learning/index.json": rbc.rebuild_index,
    "brain/paper/fill-state.json": rbc.merge_frontier,
    "brain/paper/trainer-state.json": rbc.merge_frontier,
    "brain/telegram-sent.json": rbc.merge_key_list,
    "brain/health.json": rbc.take_ours,
    "signals/latest.json": rbc.take_ours,
}
_wrong = {p: rbc.handler_for(p).__name__ for p, fn in CRITICAL.items()
          if rbc.handler_for(p) is not fn}
check(f"هر مسیر بحرانی handler درست دارد ({len(CRITICAL)} مسیر)", not _wrong)
if _wrong:
    print(f"      ↳ اشتباه: {_wrong}")

# و مهم‌تر: هیچ json تولیدشده‌ای زیر brain/ نباید بی‌پاسخ بماند — چون
# بی‌پاسخ یعنی job قرمز. فایل‌های خیالی، نه فایل‌های روی دیسک.
for _fake in ("brain/paper/fill-status.json", "brain/something-new.json",
              "brain/rooms/whatever.json", "brain/a/b/c/deep.json"):
    check(f"فایل تولیدشدهٔ ناشناخته job را نمی‌کشد: {_fake.split('/')[-1]}",
          rbc.handler_for(_fake) is not None)
check("ولی بیرون از brain/ هنوز حدس زده نمی‌شود",
      rbc.handler_for("index.html") is None
      and rbc.handler_for("claude-liam-signal/python/x.py") is None)
check("پناهِ ناشناخته عکس‌فوری است، نه اجتماعِ کورکورانه",
      rbc.handler_for("brain/something-new.json") is rbc.take_ours)
check("ولی دفتر jsonl هرگز به پناه نمی‌رسد (اجتماع مقدم است)",
      rbc.handler_for("brain/whatever/new-book.jsonl") is rbc.merge_jsonl)
# ۱۷ اوت: heartbeat آرشیو بک‌تست را هم commit می‌کند و resolver برایش
# handler نداشت — None ⇒ exit 1 ⇒ سه شکست Heartbeat در یک صبح.
check("آرشیو بک‌تست عکس‌فوری است، job را نمی‌کشد",
      rbc.handler_for("claude-liam-signal/backtests/backtest-2026-08-17.json")
      is rbc.take_ours
      and rbc.handler_for("claude-liam-signal/backtests/latest.json")
      is rbc.take_ours)
check("و کد کنارش هنوز دستی می‌ماند",
      rbc.handler_for("claude-liam-signal/python/backtest.py") is None)

# ── نام فایل فارسی — شکست واقعی ۱۰:۱۶ روز ۱۷ اوت ─────────────────────────
#
# گیت نام غیر-ASCII را با core.quotepath پیش‌فرض escape می‌کند و در گیومه
# می‌گذارد؛ رشته با «"» شروع می‌شود، startswith("brain/") شکست می‌خورد و
# resolver فایل را «دستی بماند» اعلام می‌کند — exit 1 و مرگ انتشار، در
# حالی که ۲۵ فایل دیگر همه حل شده بودند. آزمون یک تعارض واقعی روی فایلِ
# نام-فارسی می‌سازد و کل اسکریپت را می‌دواند.
git("checkout", "-q", "-b", "fa-base", cwd=tmp)
fa = tmp / "brain/patterns/hamid-reason-الگوی کلاسیک خلاف جهت.json"
fa.parent.mkdir(parents=True, exist_ok=True)
fa.write_text(json.dumps({"v": 0}))
git("add", "-A", cwd=tmp); git("commit", "-qm", "پایهٔ فارسی", cwd=tmp)
git("branch", "fa-other", cwd=tmp)
git("checkout", "-q", "fa-other", cwd=tmp)
fa.write_text(json.dumps({"v": "آن‌ها"})); git("add", "-A", cwd=tmp)
git("commit", "-qm", "طرف مقابل", cwd=tmp)
git("checkout", "-q", "fa-base", cwd=tmp)
fa.write_text(json.dumps({"v": "ما"})); git("add", "-A", cwd=tmp)
git("commit", "-qm", "طرف ما", cwd=tmp)
git("merge", "--no-edit", "fa-other", cwd=tmp)
r_fa = subprocess.run([sys.executable, "scripts/resolve_brain_conflicts.py"],
                      cwd=tmp, capture_output=True, text=True)
check("تعارضِ فایل نام-فارسی job را نمی‌کشد", r_fa.returncode == 0)
check("و عکس‌فوری نسخهٔ همین اجرا را گرفت",
      json.loads(fa.read_text())["v"] == "ما")
check("چیزی حل‌نشده نماند (نام فارسی)",
      not git("diff", "--name-only", "--diff-filter=U", cwd=tmp).stdout.strip())

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون حل تعارض گذشت")
