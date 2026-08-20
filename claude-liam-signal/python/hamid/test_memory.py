"""آزمون آفلاین حافظهٔ ایجنت — چرخهٔ تحلیل → یادگیری → ذخیره → استفاده.

    python3 -m hamid.test_memory
"""
import json
import json as _json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import memory                                      # noqa: E402
import brain                                                  # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


tmp = Path(tempfile.mkdtemp())
memory.LESSONS = tmp / "lessons.json"

LEARNED, INDEXED = [], []
_orig = (brain.learn, brain.build_index, brain.recall)
brain.learn = lambda e: LEARNED.append(e)
brain.build_index = lambda: INDEXED.append(1)

# ── ذخیره و بازیابی درس ────────────────────────────────────────────────────
memory.remember("تحلیل", "AUSDT", "درس اول دربارهٔ A")
memory.remember("ضعف", "-", "دیر رسیدیم به خوشه")
memory.remember("نتیجه", "AUSDT", "برد A با روند موافق")
check("درس‌ها ذخیره و جدیدترین اول", memory.lessons()[0]["text"].startswith("برد A"))
check("فیلتر بر اساس ارز", [l["kind"] for l in memory.lessons(sym="AUSDT")] == ["نتیجه", "تحلیل"])
check("فیلتر بر اساس نوع", memory.lessons(kind="ضعف")[0]["sym"] == "-")

# ── هضم معامله‌های بسته ────────────────────────────────────────────────────
trades = [
    {"sym": "BUSDT", "dir": "LONG", "R": 1.5, "outcome": "target",
     "why": {"stage": "second", "trend_4h": "up", "fear": 40}},
    {"sym": "CUSDT", "dir": "SHORT", "R": -1.0, "outcome": "stop",
     "why": {"stage": "practice", "trend_4h": "down"}},
    {"sym": "DUSDT", "dir": "LONG", "R": None, "outcome": "expired", "why": {}},
]
fed = memory.digest_closed(trades)
check("دو معامله هضم شد، منقضی نه", fed == 2 and len(LEARNED) == 2)
check("تجربه با شرایط لحظهٔ باز شدن رفت",
      LEARNED[0]["strategy"] == "second" and LEARNED[0]["trend_4h"] == "up")
check("ایندکس دانش بازسازی شد", len(INDEXED) == 1)
lb = memory.lessons(sym="BUSDT")[0]
check("درسِ برد دلیلش را دارد", "✅ برد" in lb["text"] and "trend_4h=up" in lb["text"])
lc = memory.lessons(sym="CUSDT")[0]
check("درسِ باخت علتش را دارد", "❌ باخت" in lc["text"])

# ── مشورت قبل از صدور ──────────────────────────────────────────────────────
brain.recall = lambda **k: {"symbol": {"n": 14, "hit": 64.3, "ev": 0.21}, "verdict": "good"}
m = memory.consult("BUSDT", "LONG")
check("جملهٔ صریح با عدد", m["note"] and "14 مورد" in m["note"] and "64.3٪" in m["note"])
check("نمونهٔ کافیِ خوب → رتبهٔ مثبت", m["adj"] > 0)

brain.recall = lambda **k: {"symbol": {"n": 9, "hit": 22.0, "ev": -0.3}, "verdict": "bad"}
check("نمونهٔ کافیِ بد → رتبهٔ منفی", memory.consult("X", "LONG")["adj"] < 0)

brain.recall = lambda **k: {"symbol": {"n": 4, "hit": 100.0, "ev": 0.9}, "verdict": "thin"}
m4 = memory.consult("X", "LONG")
check("زیر ۸ مورد: ذکر می‌شود ولی رتبه دست نمی‌خورد", m4["note"] and m4["adj"] == 0)

brain.recall = lambda **k: {"verdict": "thin"}
mA = memory.consult("AUSDT", "LONG")
check("بدون آمار، آخرین درس ذکر می‌شود", mA["note"] and "آخرین تجربه" in mA["note"])

# ── تمرین تاریخی — «هزار بار استفاده کن و یاد بگیر» ───────────────────────
memory.HISTORY = tmp / "history-stats.json"
memory.HISTORY.write_text(json.dumps({"stats": {
    "HUSDT|LONG": {"n": 120, "ev": 0.21, "win": 34.0, "ci": [0.09, 0.33]},
    "HUSDT|SHORT": {"n": 80, "ev": -0.15, "win": 18.0, "ci": [-0.28, -0.03]},
    "THINUSDT|LONG": {"n": 12, "ev": 0.5, "win": 60.0, "ci": [0.1, 0.9]},
    "SPANUSDT|LONG": {"n": 90, "ev": 0.02, "win": 25.0, "ci": [-0.05, 0.09]},
}}))
hn, ha = memory.history("HUSDT", "LONG")
check("ریپلی با CI بالای صفر → ذکر + رتبهٔ مثبت", hn and "120 ریپلی" in hn and ha > 0)
hn2, ha2 = memory.history("HUSDT", "SHORT")
check("CI زیر صفر → احتیاط و رتبهٔ منفی", "احتیاط" in (hn2 or "") and ha2 < 0)
check("زیر ۳۰ ریپلی حرفی نمی‌زند", memory.history("THINUSDT", "LONG") == (None, 0.0))
hn4, ha4 = memory.history("SPANUSDT", "LONG")
check("CI دربرگیرندهٔ صفر: ذکر بدون اثر رتبه", hn4 and ha4 == 0.0)
brain.recall = lambda **k: {"verdict": "thin"}
mh = memory.consult("HUSDT", "LONG")
check("مشورت، تمرین تاریخی را هم می‌آورد", "تمرین تاریخی" in (mh["note"] or ""))

# ── بازسنجی حافظه (Memory Curator — دستور حمید) ───────────────────────────
from hamid import revalidate                          # noqa: E402
_now = __import__("time").time() * 1000
_D = 86400e3
_hist = {"stats": {"GOODUSDT|LONG": {"n": 50, "ev": 0.4, "win": 40.0, "ci": [0.1, 0.7]},
                   "SPANUSDT|LONG": {"n": 40, "ev": 0.05, "win": 30.0, "ci": [-0.1, 0.2]}}}
_uni = {"GOODUSDT", "SPANUSDT", "NEWUSDT"}
J = lambda l: revalidate.judge(l, _hist, _uni, _now)  # noqa: E731
check("نتیجهٔ واقعی = فاکت، هرگز بازنشسته نمی‌شود",
      J({"kind": "نتیجه", "sym": "GONEUSDT", "at": _now - 200 * _D}) == "fact")
check("درس ارزِ دارای پیکرهٔ CI-روشن → تأیید",
      J({"kind": "تحلیل", "sym": "GOODUSDT", "at": _now - 40 * _D}) == "confirmed")
check("پیکره هست ولی CI دربرگیرندهٔ صفر → در انتظار (پاکِ بی‌شاهد ممنوع)",
      J({"kind": "تحلیل", "sym": "SPANUSDT", "at": _now - 10 * _D}) == "pending")
check("ارز خارج از Universe + درس کهنه → بازنشسته",
      J({"kind": "تحلیل", "sym": "GONEUSDT", "at": _now - 45 * _D}) == "retired")
check("درس تازهٔ بی‌شاهد می‌ماند",
      J({"kind": "کشف", "sym": "NEWUSDT", "at": _now - 3 * _D}) == "pending")
check("دو ماه بی‌شاهد → تأییدنشده، بازنشسته",
      J({"kind": "کشف", "sym": "NEWUSDT", "at": _now - 70 * _D}) == "retired")

brain.learn, brain.build_index, brain.recall = _orig

# ضدتکرار (عیب‌یابی ۱۳ اوت): همان درس در پنجرهٔ ۱۲ساعته یک ردیف با شمارنده
for _ in range(4):
    memory.remember("ضعف", "-", "پامپ رادار دیر رسید")
_d = [l for l in memory.lessons() if l["text"] == "پامپ رادار دیر رسید"]
check("درس تکراری یک ردیف با شمارنده می‌شود، نه ۴ ردیف",
      len(_d) == 1 and _d[0].get("seen") == 4, str(_d))

# ۱۶ اوت — این‌جا بود که ضدتکرار در عمل شکست. آزمون بالا فقط چهار نوشتنِ
# پشت‌سرهم را می‌سنجید؛ در تولید بین دو تکرار، ده‌ها درسِ نمادهای دیگر
# می‌نشست، ردیف زیر پنجرهٔ ۸۰تایی سُر می‌خورد و ردیف تازه ساخته می‌شد.
# نتیجه: ۱۹۷ درس تکراری از ۳۰۰ و حافظهٔ دائمی به ۸.۶ ساعت آب رفت.
for _i in range(150):
    memory.remember("درس", f"NOISE{_i}USDT", f"نویز {_i}")
memory.remember("ضعف", "-", "پامپ رادار دیر رسید")
_all = memory._load()["lessons"]
_d2 = [l for l in _all if l.get("text") == "پامپ رادار دیر رسید"]
check("۱۵۰ درسِ دیگر وسط، باز هم یک ردیف — نه ردیف تازه",
      len(_d2) == 1 and _d2[0].get("seen") == 5, f"{len(_d2)} ردیف")
check("ردیفِ دوباره‌دیده‌شده می‌آید جلوی صف (قرارداد: جدیدترین اول)",
      _all and _all[0].get("text") == "پامپ رادار دیر رسید")

# و ضدتکرار نباید ابدی شود: بعد از پنجرهٔ ۱۲ساعته درس تازه ردیف خودش را دارد
_d2[0]["at"] -= memory.DEDUP_MS + 1000
memory.LESSONS.write_text(_json.dumps({"lessons": _all}, ensure_ascii=False))
memory.remember("ضعف", "-", "پامپ رادار دیر رسید")
check("بعد از ۱۲ ساعت، همان درس ردیف تازه می‌گیرد (ضدتکرار ابدی نیست)",
      len([l for l in memory._load()["lessons"]
           if l.get("text") == "پامپ رادار دیر رسید"]) == 2)


# ── پاسبان: سیلِ «نتیجه» حق ندارد دانش را از حافظه بیرون بیندازد ──────────
# اندازه‌گیری ۲۰ اوت روی دفتر تولید: ۲۴۰ ردیف از ۳۰۰ از نوع «نتیجه» بود و
# قدیمی‌ترین درسِ حافظهٔ «دائمی» فقط ۵.۲ ساعت عمر داشت. این آزمون همان
# صحنه را بازمی‌سازد تا برگشتش ناممکن شود.
memory.LESSONS = tmp / "flood.json"
KNOW = [("درس", f"K{i}", f"دانشِ ماندنی شمارهٔ {i}") for i in range(6)]
for k, s, t in KNOW:
    memory.remember(k, s, t)
for i in range(1500):                                  # سیل نتیجه‌ها
    memory.remember("نتیجه", f"S{i}USDT", f"✅ برد S{i}USDT خرید (+1.50R) — {i}")

_flood = memory._load()["lessons"]
_facts = [l for l in _flood if l.get("kind") in memory.FACT_KINDS]
_know = [l for l in _flood if l.get("kind") not in memory.FACT_KINDS]
check(f"سقف کل رعایت شد ({len(_flood)} ≤ {memory.CAP})", len(_flood) <= memory.CAP)
check(f"نتیجه‌ها از سهمیه رد نشدند ({len(_facts)} ≤ {memory.FACT_QUOTA})",
      len(_facts) <= memory.FACT_QUOTA)
_texts = {l.get("text") for l in _know}
check("هر ۶ درسِ دانش بعد از ۱۵۰۰ نتیجه هنوز در حافظه‌اند",
      all(t in _texts for _, _, t in KNOW),
      f"{len(_texts & {t for _, _, t in KNOW})} از ۶ ماند")
check("جای دانش واقعاً باز ماند (سقف منهای سهمیه)",
      len(_know) >= memory.CAP - memory.FACT_QUOTA - len(KNOW)
      or len(_know) == len(KNOW))

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های حافظه گذشتند")
