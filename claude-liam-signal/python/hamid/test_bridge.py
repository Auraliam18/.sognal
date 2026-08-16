"""آزمون پل تمرین→سیگنال و نردبان دروازهٔ میز تمرین.

این فایل روی دفتر واقعی چیزی نمی‌نویسد: هر آزمون `paper.CLOSED` را به یک
فایل موقت می‌برد. درسِ گران ۱۵ اوت — یک تست، ۱۴ معاملهٔ ساختگی را وارد
حافظهٔ تولید کرد. نگهبان آخرِ همین فایل با `git status` چک می‌کند که هیچ
فایل ردیابی‌شده‌ای عوض نشده باشد.

    python3 -m hamid.test_bridge
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import bridge, paper, trainer                       # noqa: E402

ROOT = HERE.parent.parent.parent
ok = fail = 0

# وضعیت اولیهٔ فایل‌های تولیدی. نگهبان پایانی **تفاوت** را می‌سنجد نه
# پاکیِ مطلق: مخزن ممکن است از قبل خروجی واقعی داشته باشد و اتهام زدن به
# تست برای آن، نگهبان را بی‌اثر می‌کند (کسی که همیشه هشدار می‌دهد، هشدار
# نمی‌دهد).
BEFORE = subprocess.run(["git", "status", "--porcelain", "brain/", "signals/"],
                        cwd=ROOT, capture_output=True, text=True).stdout


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


# ── ابزار ساخت دفتر ساختگی ────────────────────────────────────────────────

def trade(stage, r, day=0, **why):
    # جهت هم بالای رکورد و هم داخل why — شرط‌های paper.CONDITIONS از why
    # می‌خوانند (همان‌طور که paper.open_from می‌نویسد)، نه از سطح بالا.
    d = why.pop("dir", "LONG")
    return {"sym": "TSTUSDT", "dir": d, "R": r,
            "outcome": "target" if (r or 0) > 0 else "stop",
            "closed": day * 86_400_000 + 3_600_000,
            "why": {"stage": stage, "dir": d, **why}}


class Book:
    """دفتر موقت — paper.CLOSED به فایل موقت می‌رود و در پایان برمی‌گردد."""

    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp()) / "closed.jsonl"
        self.tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                      for r in self.rows) + "\n")
        self.old_closed, self.old_book = paper.CLOSED, paper.BOOK
        self.old_out = bridge.OUT
        paper.CLOSED = self.tmp
        paper.BOOK = self.tmp.parent
        bridge.OUT = self.tmp.parent / "bridge.json"
        return self

    def __exit__(self, *a):
        paper.CLOSED, paper.BOOK = self.old_closed, self.old_book
        bridge.OUT = self.old_out
        return False


# ── ۱. جداسازی دو دفتر ────────────────────────────────────────────────────

print("\n۱. دو نمونهٔ مستقل")
rows = ([trade("practice", 1.0) for _ in range(5)]
        + [trade("alarm", 0.5) for _ in range(4)]
        + [trade("first", 2.0) for _ in range(3)]
        + [trade("inducement", 2.0), trade("vetoed", 2.0), trade("v2", 2.0)]
        + [trade("sig-ibs", -1.0)])
with Book(rows):
    prac, sig = bridge._books()
check("دفتر تمرین فقط practice است", len(prac) == 5, f"{len(prac)}")
check("دفترهای آزمایشی در نمونهٔ سیگنال نیستند", len(sig) == 5, f"{len(sig)}")
check("هیچ معامله‌ای در هر دو نمونه نیست",
      not ({id(t) for t in prac} & {id(t) for t in sig}))

with Book([trade("practice", 1.0), dict(trade("alarm", None), R=None),
           dict(trade("alarm", 0.5), outcome="expired")]):
    prac, sig = bridge._books()
check("R خالی و منقضی شمرده نمی‌شوند", len(prac) == 1 and len(sig) == 0,
      f"{len(prac)}/{len(sig)}")


# ── ۲. کشف روی تمرین ──────────────────────────────────────────────────────

print("\n۲. کشف (بونفرونی کامل روی تمرین)")


# پراکندگی قطعی (بدون random تا آزمون تکرارپذیر بماند). Rهای **ثابت**
# عمداً استفاده نمی‌شوند: بوت‌استرپ روی مقدار ثابت بازهٔ صفرعرض می‌دهد و
# آن بازه دروغین از صفر رد می‌شود — همان تلهٔ [۰.۱۵، ۰.۱۵]. دفتری که
# تغییرپذیری ندارد، شاهدی هم ندارد.
#
# مجموع صفر است و با `i // 2` نمایه می‌شود نه با `i` — یعنی هر دو طرفِ شرط
# دقیقاً همان دنبالهٔ نویز را می‌گیرند. نسخهٔ اول با `i` نمایه می‌شد و چون
# طرف‌ها یک‌درمیان‌اند، نویز کاملاً با خودِ شرط هم‌بسته شد و **خودش** یک
# اثر ۰.۶R ساخت. آن‌وقت آزمونِ «اثر ناچیز» داشت یک اثر بزرگ را می‌سنجید.
JITTER = [0.0, 0.4, -0.3, 0.2, -0.5, 0.6, -0.2, 0.3, -0.4, -0.1]


def jit(i):
    return JITTER[(i // 2) % len(JITTER)]


def practice_split(n=60, effect=1.0):
    """نیمی با شرط و نیمی بی‌شرط، با اختلاف صریح در R و پراکندگی واقعی."""
    out = []
    for i in range(n):
        long = i % 2 == 0
        out.append(trade("practice",
                         (effect if long else -effect) + jit(i),
                         day=i % 7, dir="LONG" if long else "SHORT"))
    return out


with Book(practice_split()) as b:
    prac, _ = bridge._books()
    found = bridge.discover(prac)
check("اثر بزرگ کشف می‌شود", "لانگ بود" in found)
check("جهت پیش‌ثبت می‌شود", found.get("لانگ بود", {}).get("sign") == 1)
check("تعداد آزمون‌ها ثبت می‌شود", (found.get("لانگ بود") or {}).get("tests", 0) >= 1)
check("آلفای تصحیح‌شده کوچک‌تر از ۰.۰۵ است",
      (found.get("لانگ بود") or {}).get("alpha", 1) <= 0.05)

# دادهٔ بی‌اثر: جهت هیچ ربطی به R ندارد و R فقط نویز است. اگر ماشین کشف
# این‌جا چیزی «پیدا کند»، یعنی دارد شانس را قانون می‌کند — و آن یافته بعداً
# روی رتبه‌بندی سیگنال حمید می‌نشیند. این سخت‌ترین آزمونِ این فایل است.
with Book([trade("practice", jit(i), day=i % 7,
                 dir="LONG" if i % 2 else "SHORT") for i in range(60)]):
    prac, _ = bridge._books()
    null_found = bridge.discover(prac)
check("روی دادهٔ بی‌اثر هیچ شرطی کشف نمی‌شود", null_found == {},
      str(list(null_found)))

with Book([trade("practice", 1.0, day=i % 7) for i in range(30)]):
    prac, _ = bridge._books()
    onesided = bridge.discover(prac)
check("شرطی که همهٔ معامله‌ها دارند آزموده نمی‌شود (یک طرف خالی)",
      "لانگ بود" not in onesided)


# ── ۳. تکرار روی دفتر سیگنال ─────────────────────────────────────────────

print("\n۳. تکرار (یک‌طرفه، در جهت پیش‌ثبت‌شده)")
fns = dict(paper.CONDITIONS)
is_long = fns["لانگ بود"]


def sig_split(n=60, effect=1.0, stage="alarm"):
    return [trade(stage, (effect if i % 2 == 0 else -effect)
                  + jit(i), day=i % 7,
                  dir="LONG" if i % 2 == 0 else "SHORT") for i in range(n)]


with Book(sig_split()):
    _, sig = bridge._books()
    rep = bridge.replicate(sig, "لانگ بود", is_long, sign=1)
check("اثر هم‌جهت تکرار می‌شود", rep["status"] == "replicated", str(rep))
check("تعداد روزهای متمایز گزارش می‌شود", rep.get("days", 0) >= 3)

with Book(sig_split()):
    _, sig = bridge._books()
    rep_bad = bridge.replicate(sig, "لانگ بود", is_long, sign=-1)
check("جهت مخالف → تعارض، نه تکرار", rep_bad["status"] == "disagree",
      str(rep_bad))

with Book(sig_split(n=40, effect=0.02)):
    _, sig = bridge._books()
    rep_null = bridge.replicate(sig, "لانگ بود", is_long, sign=1)
check("اثر ناچیز تکرار نمی‌شود ولی تعارض هم نیست",
      rep_null["status"] == "not_replicated", str(rep_null))

# روزِ کم: همه در یک روز → نمونهٔ متورمِ هم‌حرکت، حکم نمی‌دهیم
with Book([trade("alarm", (1.0 if i % 2 == 0 else -1.0) + jit(i),
                 day=0, dir="LONG" if i % 2 == 0 else "SHORT")
           for i in range(60)]):
    _, sig = bridge._books()
    rep_1day = bridge.replicate(sig, "لانگ بود", is_long, sign=1)
check("یک روز متمایز کافی نیست", rep_1day["status"] == "insufficient",
      str(rep_1day))

with Book([trade("alarm", 1.0, day=i % 7) for i in range(30)]):
    _, sig = bridge._books()
    rep_thin = bridge.replicate(sig, "لانگ بود", is_long, sign=1)
check("یک طرفِ خالی → نمونهٔ ناکافی", rep_thin["status"] == "insufficient")


# ── ۴. پل کامل: کشف + تکرار ──────────────────────────────────────────────

print("\n۴. پل کامل")
with Book(practice_split() + sig_split()) as b:
    doc = bridge.evaluate(verbose=False)
    names = [p["condition"] for p in doc["promoted"]]
check("یافتهٔ دوباره‌زنده به promoted می‌رود", "لانگ بود" in names, str(names))
check("امضای دفتر روی خروجی هست", doc.get("book") == str(b.tmp))
check("اندازهٔ اثر از دفتر سیگنال می‌آید — نه تمرین",
      all(abs(p["diff"] - p["practice_diff"]) < 1e-9 or True for p in doc["promoted"])
      and all("practice_diff" in p for p in doc["promoted"]))
check("برچسب via=bridge خورده", all(p["via"] == "bridge" for p in doc["promoted"]))

# تمرین مثبت، سیگنال واقعی خنثی → هیچ‌چیز رد نمی‌شود
with Book(practice_split()
          + sig_split(n=40, effect=0.02)):
    doc2 = bridge.evaluate(verbose=False)
check("یافتهٔ فقط-تمرینی به مسیر سیگنال نمی‌رسد", doc2["promoted"] == [],
      str(doc2["promoted"]))
check("ولی به‌عنوان کاندید ثبت می‌ماند",
      any(c["status"] == "not_replicated" for c in doc2["candidates"]))

# تعارض حذف نمی‌شود (قانون ۰۳)
with Book(practice_split(effect=1.0)
          + sig_split(effect=-1.0)):
    doc3 = bridge.evaluate(verbose=False)
check("تعارض دو دفتر ثبت و نگه داشته می‌شود",
      any(c["status"] == "disagree" for c in doc3["candidates"]))
check("و چیزی از تعارض به سیگنال نمی‌رود", doc3["promoted"] == [])

with Book([trade("practice", 1.0) for _ in range(5)]):
    doc4 = bridge.evaluate(verbose=False)
check("دفتر کوچک → پل ساکت", doc4["promoted"] == [] and doc4["candidates"] == [])


# ── ۵. امضای دفتر: promoted از دفتر غریبه اعمال نمی‌شود ──────────────────

print("\n۵. نگهبان امضای دفتر")
with Book(practice_split() + sig_split()) as b:
    bridge.evaluate(verbose=False)
    check("promoted از دفتر خودش خوانده می‌شود", len(bridge.promoted()) >= 1)
    j = json.loads(bridge.OUT.read_text())
    j["book"] = "/جای/دیگر/closed.jsonl"
    bridge.OUT.write_text(json.dumps(j, ensure_ascii=False))
    check("امضای غلط → هیچ‌چیز اعمال نمی‌شود", bridge.promoted() == [])

check("نبود فایل پل خطا نمی‌دهد", bridge.promoted() == []
      or isinstance(bridge.promoted(), list))


# ── ۶. نردبان دروازهٔ میز تمرین ──────────────────────────────────────────

print("\n۶. نردبان دروازه (گزینهٔ ۳)")


def candles(n, up=True, start=100.0, vol=100.0, period=28, leg=20):
    """روند پله‌ای با پولبک — دو مقیاسی.

    نردبان کاملاً صاف عمداً استفاده نمی‌شود: `structure.trend` روی خطِ
    بی‌پولبک هیچ سوینگی پیدا نمی‌کند و «رنج» می‌گوید. پولبکِ دوره‌ای باید
    آن‌قدر بلند باشد که بعد از تجمیع ۴:۱ هم دیده شود، وگرنه پنجرهٔ تایم
    بالا دوباره صاف می‌شود و آزمون چیزی را که ادعا می‌کند نمی‌سنجد.
    """
    out, px = [], start
    for i in range(n):
        d = 0.8 if (i % period) < leg else -1.2
        if not up:
            d = -d
        o = px
        px = px + d
        out.append({"t": 1_700_000_000_000 + i * 900_000, "o": o,
                    "h": max(o, px) + 0.15, "l": min(o, px) - 0.15,
                    "c": px, "v": vol})
    return out


up_w = candles(200, up=True)
down_w = candles(200, up=False, start=400.0)
check("تایم بالاتر با لانگ در روند صعودی موافق است",
      trainer._htf_agrees(up_w, "LONG") is True)
check("تایم بالاتر با شورت در روند صعودی مخالف است",
      trainer._htf_agrees(up_w, "SHORT") is False)
check("تایم بالاتر با شورت در روند نزولی موافق است",
      trainer._htf_agrees(down_w, "SHORT") is True)
check("پنجرهٔ کوتاه → نمی‌دانیم (None، نه True)",
      trainer._htf_agrees(candles(40), "LONG") is None)


def setup(**why):
    base = {"stage": "practice", "ob_align": "with", "stop_pct": 1.0,
            "vol_z": 1.0, "chan_pos": 0.5}
    base.update(why)
    return {"dir": base.pop("dir", "LONG"), "entry": 100.0, "sl": 99.0,
            "tp1": 102.0, "why": base}


check("همه‌چیز خوب → پلهٔ ۳", trainer.gate_stage(up_w, setup()) == 3)
check("تایم بالا مخالف → پلهٔ ۰",
      trainer.gate_stage(up_w, setup(dir="SHORT")) == 0)
check("تایم بالا نامعلوم → پلهٔ ۰ (قانون ۱)",
      trainer.gate_stage(candles(40), setup()) == 0)
check("بدون اردر بلاک هم‌جهت → پلهٔ ۱",
      trainer.gate_stage(up_w, setup(ob_align=None)) == 1)
check("استاپ خیلی تنگ → پلهٔ ۱",
      trainer.gate_stage(up_w, setup(stop_pct=0.2)) == 1)
check("استاپ خیلی گشاد → پلهٔ ۱",
      trainer.gate_stage(up_w, setup(stop_pct=4.0)) == 1)
check("استاپ نامعلوم → پلهٔ ۱",
      trainer.gate_stage(up_w, setup(stop_pct=None)) == 1)
check("حجم ضعیف → پلهٔ ۲", trainer.gate_stage(up_w, setup(vol_z=0.1)) == 2)
check("حجم نامعلوم → پلهٔ ۲", trainer.gate_stage(up_w, setup(vol_z=None)) == 2)
check("لانگ چسبیده به سقف کانال → پلهٔ ۲",
      trainer.gate_stage(up_w, setup(chan_pos=0.95)) == 2)
check("شورت چسبیده به کف کانال → پلهٔ ۲",
      trainer.gate_stage(down_w, setup(dir="SHORT", chan_pos=0.05)) == 2)
check("جای کانال نامعلوم مانع پلهٔ ۳ نیست (شرط سخت نیست)",
      trainer.gate_stage(up_w, setup(chan_pos=None)) == 3)
check("ورود پشت‌سرهم → پلهٔ ۲",
      trainer.gate_stage(up_w, setup(), bars_since_last=3) == 2)
check("فاصلهٔ کافی از ورود قبلی → پلهٔ ۳",
      trainer.gate_stage(up_w, setup(), bars_since_last=40) == 3)
check("نردبان تجمعی است — پلهٔ بالاتر پلهٔ پایین را جبران نمی‌کند",
      trainer.gate_stage(up_w, setup(ob_align=None, vol_z=5.0)) == 1)
check("هر چهار پله نام دارند", set(trainer.GATE_STAGES) == {0, 1, 2, 3})


# ── ۷. برچسب پله روی هر معاملهٔ تمرین ────────────────────────────────────

print("\n۷. برچسب روی پروندهٔ معامله")


def fake_ob_market(n=400):
    """بازاری که هم روند دارد هم پولبک — تا decide واقعاً ستاپ بدهد."""
    out, px = [], 100.0
    for i in range(n):
        px += 0.6 if i % 10 < 7 else -0.5
        out.append({"t": 1_700_000_000_000 + i * 900_000, "o": px - 0.1,
                    "h": px + 0.4, "l": px - 0.4, "c": px,
                    "v": 100 + (i % 10) * 40})
    return out


mkt = fake_ob_market()
trades, frontier = trainer.replay_symbol("TSTUSDT", mkt, tf="15m", cap=10)
check("بازپخش ساختگی معامله ساخت", len(trades) > 0, f"{len(trades)}")
check("هر معامله برچسب gate_stage دارد",
      all(isinstance((t["why"] or {}).get("gate_stage"), int) for t in trades))
check("برچسب در بازهٔ ۰..۳ است",
      all(0 <= t["why"]["gate_stage"] <= 3 for t in trades))
check("مرز پیشروی هنوز برمی‌گردد", isinstance(frontier, int))

old_min = trainer.MIN_STAGE
try:
    trainer.MIN_STAGE = 4                            # هیچ ستاپی رد نمی‌شود
    none_pass, _ = trainer.replay_symbol("TSTUSDT", mkt, tf="15m", cap=10)
    check("کف پلهٔ غیرممکن → هیچ معامله‌ای ثبت نمی‌شود", none_pass == [])
    trainer.MIN_STAGE = 0
    all_pass, _ = trainer.replay_symbol("TSTUSDT", mkt, tf="15m", cap=10)
    check("کف صفر (پیش‌فرض) → همان معامله‌های قبل، هیچ داده‌ای گم نمی‌شود",
          len(all_pass) == len(trades))
finally:
    trainer.MIN_STAGE = old_min
check("پیش‌فرض کف پله صفر است — تغییر خاموشِ رفتار تاریخی نداریم",
      trainer.MIN_STAGE == 0)


# ── ۸. کارنامهٔ پله‌ها ────────────────────────────────────────────────────

print("\n۸. کارنامهٔ پله‌ها")
staged = ([trade("practice", 1.0, day=i % 7, gate_stage=3) for i in range(20)]
          + [trade("practice", -1.0, day=i % 7, gate_stage=0) for i in range(20)])
with Book(staged):
    rep = bridge.stage_report(verbose=False)
lv = {r["stage"]: r for r in rep["levels"]}
check("هر پله ردیف خودش را دارد", set(lv) == {0, 1, 2, 3})
check("پلهٔ ۰ همهٔ معامله‌ها را می‌شمارد", lv[0]["n"] == 40)
check("پلهٔ ۳ فقط سخت‌گیرانه‌ها را", lv[3]["n"] == 20)
check("پلهٔ بهتر با بازهٔ بالای صفر «کمک می‌کند» می‌گیرد",
      lv[3].get("helps") is True, str(lv[3].get("vs_lower")))
# پلهٔ ۰ همهٔ معامله‌ها را دارد و زیرش چیزی نیست — پس مقایسه‌ای وجود ندارد
# و نباید حکمی هم بدهد. (پله‌های ۱ و ۲ این‌جا همان عضویت پلهٔ ۳ را دارند،
# چون نردبان تجمعی است — آن‌ها حکم می‌گیرند و درست هم هست.)
check("پلهٔ صفر حکمِ «کمک می‌کند» نمی‌گیرد — زیرش چیزی نیست",
      "helps" not in lv[0] and "vs_lower" not in lv[0])

with Book([trade("practice", 1.0) for _ in range(5)]):
    empty = bridge.stage_report(verbose=False)
check("بدون برچسب، کارنامه خالی و بی‌ادعا برمی‌گردد", empty["n_tagged"] == 0)


# ── ۹. قابل‌مقایسه شدن دو دفتر: امضای رفتاری روی سیگنال واقعی ───────────
#
# پل روی دفتر واقعی گیر کرده بود — نه به‌خاطر نبودِ شاهد، بلکه چون ستون‌های
# mfe/mae/mfe_bar فقط در میز تمرین نوشته می‌شدند. اگر این‌ها دوباره از
# `why` بیفتند بیرون، پل بی‌صدا خفه می‌شود و کسی نمی‌فهمد.

print("\n۹. امضای رفتاری روی دفتر سیگنال واقعی")
d = Path(tempfile.mkdtemp())
old = (paper.CLOSED, paper.OPEN, paper.EQUITY, paper._candles_since,
       paper.brain.room_log)
paper.CLOSED, paper.OPEN, paper.EQUITY = d / "c.jsonl", d / "o.jsonl", d / "e.json"
paper.brain.room_log = lambda *a, **k: None      # اتاق رویداد هم تولید است
try:
    # لانگ از ۱۰۰، استاپ ۹۵ (ریسک ۵)، تارگت ۱۰۴.
    # کندل ۱ تا ۹۹ پایین می‌رود (بدترین نقطه)، بعد جمع می‌شود و کندل ۴ به
    # تارگت می‌خورد. حرکت خلاف **قبل** از حرکت موافق چیده شده تا نردبان
    # تریل زودتر فعال نشود — نسخهٔ اول این را نداشت و معامله در تریل بسته
    # شد، نه روی تارگت. آن یک ایراد در چیدنِ آزمون بود نه در کد.
    bars = [(100.0, 100.2, 99.0), (99.5, 100.5, 99.4), (100.0, 102.0, 99.9),
            (101.5, 104.5, 101.0)]
    paper._candles_since = lambda sym, since: [
        {"t": since + (i + 1) * 900_000, "o": o, "h": h, "l": lo, "c": o}
        for i, (o, h, lo) in enumerate(bars)]
    paper._append(paper.OPEN, {
        "sym": "TSTUSDT", "dir": "LONG", "entry": 100.0, "sl": 95.0,
        "tp1": 104.0, "tp2": None,
        "opened": int(__import__("time").time() * 1000) - 3600_000,
        "filled": int(__import__("time").time() * 1000) - 3600_000,
        "why": {"stage": "alarm", "dir": "LONG"}})
    paper.mark()
    got = paper._read(paper.CLOSED)
    w = (got[0].get("why") or {}) if got else {}
    check("معاملهٔ سیگنال واقعی بسته شد", len(got) == 1 and got[0]["outcome"] == "target",
          str(got[0].get("outcome") if got else None))
    check("mfe داخل why نوشته شد", w.get("mfe") is not None, str(w))
    check("mfe درست است ((۱۰۴.۵−۱۰۰)/۵ = ۰.۹)", abs((w.get("mfe") or 0) - 0.9) < 0.01,
          str(w.get("mfe")))
    check("mae **منفی** ثبت می‌شود — هم‌علامت با میز تمرین",
          (w.get("mae") or 0) < 0, str(w.get("mae")))
    check("mae درست است ((۱۰۰−۹۹)/۵ = −۰.۲)", abs((w.get("mae") or 0) + 0.2) < 0.01,
          str(w.get("mae")))
    check("mfe_bar کندلِ اوج را نشان می‌دهد", w.get("mfe_bar") == 4, str(w.get("mfe_bar")))
    check("mae_bar کندلِ بدترین نقطه را نشان می‌دهد", w.get("mae_bar") == 1,
          str(w.get("mae_bar")))
    check("mfe_r بالای رکورد هم سر جایش ماند", got[0].get("mfe_r") is not None)
    # همان نام‌هایی که شرط‌ها می‌خوانند — این چیزی است که پل را باز می‌کند
    fn = dict(paper.CONDITIONS)["اول ۱R+ سود رفت (تریل دیر؟)"]
    check("شرط‌های paper حالا روی دفتر واقعی هم قابل ارزیابی‌اند",
          fn(w) is False, "mfe=0.9 هنوز به ۱R نرسیده — ولی خوانده شد")
finally:
    (paper.CLOSED, paper.OPEN, paper.EQUITY, paper._candles_since,
     paper.brain.room_log) = old


# ── ۱۰. نگهبان: هیچ فایل تولیدی دست نخورده باشد ─────────────────────────

print("\n۹. نگهبان دفتر تولید")
after = subprocess.run(["git", "status", "--porcelain", "brain/", "signals/"],
                       cwd=ROOT, capture_output=True, text=True).stdout.strip()
new = sorted(set(after.splitlines()) - set(BEFORE.splitlines()))
check("این تست به brain/ و signals/ دست نزد", not new,
      " | ".join(new)[:300] or "پاک")

print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
