"""آزمون دسته‌بندی — جدول‌ها باید بشمارند، نه ادعا کنند.

خطرِ واقعی این فایل خراب‌شدن نیست؛ **درست‌به‌نظر‌رسیدنِ غلط** است. یک
جدول با ۳ معامله در هر خانه همیشه یک برنده نشان می‌دهد و هیچ‌کس شک نمی‌کند.
پس بیشترِ این آزمون‌ها روی همان چیزهایی است که جلوی حکمِ بی‌پشتوانه را
می‌گیرند: کف نمونه، فاصلهٔ اطمینان، آلفای بونفرونی، و UNKNOWN که حدس
زده نمی‌شود.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import classify as cl                      # noqa: E402

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


print("── دسته‌بندی استراتژی/اردر بلاک ──")


def tr(r, sym="AUSDT", tf="15m", setup="ob_pullback", outcome="target", **why):
    w = {"stage": "practice", "setup": setup, "tf": tf}
    w.update(why)
    return {"sym": sym, "R": r, "outcome": outcome, "why": w, "tf": tf}


# ── کف نمونه ───────────────────────────────────────────────────────────────
few = [tr(1.0) for _ in range(5)]
c = cl.cell(few)
check("خانهٔ کم‌نمونه حکم نمی‌گیرد", c["verdict"] == "نمونه کم")
check("کم‌نمونه هم عددش گزارش می‌شود", c["n"] == 5 and c["mean_r"] == 1.0)
check("دلیل کم‌بودن نوشته می‌شود", str(cl.MIN_N) in c["note"])

# ── حکم مثبت فقط وقتی CI صفر را رد کند ────────────────────────────────────
strong = [tr(2.0) for _ in range(40)]
c2 = cl.cell(strong)
check("خانهٔ قوی حکم مثبت می‌گیرد", c2["verdict"] == "مثبت")
check("کف فاصلهٔ اطمینان بالای صفر است", c2["ci"][0] > 0)

mixed = [tr(1.0 if i % 2 else -1.0) for i in range(60)]
c3 = cl.cell(mixed)
check("خانهٔ نوسانیِ حول صفر «نامعلوم» می‌ماند", c3["verdict"] == "نامعلوم")
check("«نامعلوم» صریح می‌گوید هنوز تصمیم‌گرفتنی نیست",
      "تصمیم‌گرفتنی نیست" in c3["note"])

weak = [tr(-1.0, outcome="stop") for _ in range(40)]
check("خانهٔ بازنده حکم منفی می‌گیرد", cl.cell(weak)["verdict"] == "منفی")

# برد/باخت درست شمرده شود
c4 = cl.cell([tr(1.0), tr(-1.0), tr(0.5)])
check("برد و استاپ درست شمرده می‌شوند",
      c4["wins"] == 2 and c4["stops"] == 1)

# ── UNKNOWN حدس زده نمی‌شود ───────────────────────────────────────────────
old = {"sym": "OLDUSDT", "R": 1.0, "outcome": "target",
       "why": {"stage": "first"}}
check("ردیف بی‌برچسب UNKNOWN می‌شود، نه ۱۵د", cl._tf(old) == "UNKNOWN")
check("ردیف برچسب‌دار تایم‌فریمش را می‌دهد", cl._tf(tr(1.0, tf="1h")) == "1h")
check("tf از داخل why هم خوانده می‌شود",
      cl._tf({"why": {"tf": "5m"}}) == "5m")

# ── کلاس اردر بلاک ─────────────────────────────────────────────────────────
obt = tr(1.0, ob_align="with", ob_fresh=True, ob_hunts=0, reactions=3)
check("کلاس OB از تازگی/هانت/واکنش ساخته می‌شود",
      cl.ob_class(obt) == "تازه · دست‌نخورده · ۳+ واکنش")
check("OB کهنهٔ هانت‌خورده جدا کلاس می‌شود",
      cl.ob_class(tr(1.0, ob_align="with", ob_fresh=False, ob_hunts=2,
                     reactions=1)) == "کهنه · هانت‌خورده · ۰-۱ واکنش")
check("معاملهٔ بدون اردر بلاک کلاس نمی‌گیرد",
      cl.ob_class(tr(1.0, setup="bos_continuation")) is None)

# ── آلفای بونفرونی ─────────────────────────────────────────────────────────
rows = []
for i in range(4):                                    # ۴ خانهٔ بزرگ
    rows += [tr(0.4, tf=f"tf{i}") for _ in range(40)]
rows += [tr(3.0, tf="tiny") for _ in range(3)]        # خانهٔ کوچک
t = cl.strategy_by_tf(rows)
check("فقط خانه‌های واجدشرایط شمرده می‌شوند", t["tested"] == 4)
check("آلفا بین همان‌ها تقسیم می‌شود", abs(t["alpha"] - 0.05 / 4) < 1e-9)
# ۰.۰۵/۴ = ۰.۰۱۲۵ است؛ اگر خانهٔ ۳تایی هم شمرده می‌شد ۰.۰۵/۵ = ۰.۰۱ می‌شد.
check("خانهٔ کوچک آلفا را رقیق نمی‌کند (تقسیم بر ۵ نشد)",
      abs(t["alpha"] - 0.01) > 1e-9 and abs(t["alpha"] - 0.0125) < 1e-9)
check("خانهٔ کوچک با میانگین بزرگ هم حکم نمی‌گیرد",
      t["cells"]["ob_pullback @ tiny"]["verdict"] == "نمونه کم")
check("کلید جدول شامل استراتژی و تایم‌فریم است",
      "ob_pullback @ tf0" in t["cells"])

# جدول OB فقط ردیف‌های OBدار را می‌گیرد
mix = ([tr(1.0, ob_align="with", ob_fresh=True, ob_hunts=0, reactions=3)
        for _ in range(30)]
       + [tr(1.0, setup="bos_continuation") for _ in range(30)])
ot = cl.ob_by_tf(mix)
check("جدول OB معاملهٔ بدون OB را نمی‌شمارد",
      sum(v["n"] for v in ot["cells"].values()) == 30)

# ── خروجی کامل ─────────────────────────────────────────────────────────────
j = cl.build(rows + mix)
check("خروجی هر سه جدول را دارد",
      all(k in j for k in ("strategy_by_tf", "ob_by_tf", "ob_by_symbol")))
check("تعداد کل معامله‌ها گزارش می‌شود", j["n_trades"] == len(rows) + len(mix))
check("منبع صادقانه ذکر می‌شود (پیپر، نه اجرای واقعی)",
      "نه اجرای واقعی" in j["source"])
check("قانون حکم در خروجی نوشته شده", "فاصلهٔ اطمینان" in j["rule"])
check("خط فارسی خواندنی ساخته می‌شود", cl.fa_lines(j))

# ── «چقدر مانده تا حکم» — نقشهٔ راهِ سرعت‌بخشیدن ───────────────────────────
# خانهٔ پرنوسان با میانگین کوچک باید نمونهٔ خیلی بیشتری بخواهد از خانهٔ
# کم‌نوسان با میانگین بزرگ. اگر این وارونه باشد، وقت بازپخش جای غلط می‌رود.
noisy = [tr(2.0 if i % 2 else -1.8) for i in range(60)]
tight = [tr(0.6 if i % 5 else 0.4) for i in range(60)]
n_noisy, n_tight = cl.needed_n([t["R"] for t in noisy]), cl.needed_n([t["R"] for t in tight])
check("خانهٔ پرنوسان نمونهٔ بیشتری لازم دارد", n_noisy > n_tight)
check("خانهٔ کم‌نوسانِ مثبت نمونهٔ کمی لازم دارد", n_tight <= 60)
check("میانگین منفی یعنی هیچ نمونه‌ای نجاتش نمی‌دهد",
      cl.needed_n([-1.0] * 40) is None)
check("نمونهٔ خیلی کم عدد نمی‌دهد (حدس ممنوع)", cl.needed_n([1.0, 2.0]) is None)

c_noisy = cl.cell(noisy)
check("کمبود روی خانه نوشته می‌شود",
      c_noisy["short_by"] == max(0, c_noisy["need_n"] - c_noisy["n"]))
check("جملهٔ فارسی «چقدر مانده» ساخته می‌شود", "معامله لازم است" in c_noisy["eta"])
c_neg = cl.cell([tr(-0.5) for _ in range(40)])
check("خانهٔ زیان‌ده صریح می‌گوید با نمونهٔ بیشتر درست نمی‌شود",
      "مثبت نمی‌شود" in c_neg["eta"])

jj = cl.build(noisy + tight + [tr(0.5, tf="1h") for _ in range(40)])
cw = jj["closest_to_verdict"]
check("فهرست نزدیک‌ترین‌به‌حکم ساخته می‌شود", isinstance(cw, list))
check("مرتب بر کمبود است (کم‌ترین کمبود اول)",
      [c["short_by"] for c in cw] == sorted(c["short_by"] for c in cw))
check("خانهٔ حکم‌گرفته در فهرست «مانده» نمی‌آید",
      all(c["short_by"] > 0 for c in cw))

empty = cl.build([])
check("دفتر خالی کرش نمی‌کند", empty["n_trades"] == 0)
check("بدون حکم، صادقانه می‌گوید حکمی نیست",
      "حکمی ندارد" in " ".join(cl.fa_lines(empty)))

# ── ردیف‌های بی‌ارزش کنار گذاشته می‌شوند ──────────────────────────────────
import json as _json                                  # noqa: E402
import tempfile                                       # noqa: E402

p = Path(tempfile.mkdtemp()) / "closed.jsonl"
p.write_text("\n".join([
    _json.dumps({"sym": "A", "R": 1.0, "outcome": "target", "why": {"tf": "15m"}}),
    _json.dumps({"sym": "B", "R": None, "outcome": "expired", "why": {}}),
    _json.dumps({"sym": "C", "R": 0.5, "outcome": "expired", "why": {}}),
    "{ خراب",
    "",
]), encoding="utf-8")
loaded = cl.load(p)
check("سفارش منقضی و ردیف خراب شمرده نمی‌شوند", len(loaded) == 1)
check("مسیر دفتر واقعی دست نخورد", p != cl.CLOSED)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون دسته‌بندی گذشت")
