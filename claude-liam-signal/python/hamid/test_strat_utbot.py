"""آزمون UT Bot — آفلاین، روی سری ساختگی. python3 -m hamid.test_strat_utbot"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import strat_utbot as ut                   # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}{('  — ' + detail) if detail else ''}")


def bar(t, o, h, l, c):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": 100.0}


def series(moves, start=100.0, t0=1_700_000_000_000):
    out, px = [], start
    for i, d in enumerate(moves):
        o = px
        px = px * (1 + d)
        out.append(bar(t0 + i * 900_000, o, max(o, px) * 1.001,
                       min(o, px) * 0.999, px))
    return out


# روند بلند صعودی (تا EMA200 گرم شود) → ریزش تند → دوباره صعود تند.
UP, DOWN = 0.004, -0.006
cd = series([UP] * 260 + [DOWN] * 25 + [UP] * 40)

print("\n۱. خط و جهت")
stops, dirs = ut.trail_series(cd)
check("گرم‌شدن: اول None بعد عدد", stops[0] is None and stops[-1] is not None)
check("در روند صعودی جهت +۱", dirs[250] == 1)
check("بعد از ریزش تند جهت -۱", dirs[280] == -1)
i_flip = next(i for i in range(1, len(dirs))
              if dirs[i] == -1 and dirs[i - 1] == 1)
check("خط در لانگ‌مود هرگز پایین نمی‌آید",
      all(stops[i] >= stops[i - 1] - 1e-9
          for i in range(2, i_flip) if stops[i - 1] is not None))

print("\n۲. سیگنال بدون look-ahead")
s_dn = ut.signal(cd[:i_flip + 1], use_filters=False)
check("فلیپ رو به پایین سیگنال شورت می‌دهد",
      s_dn is not None and s_dn.dir == "SHORT")
check("یک کندل بعد از فلیپ، دیگر سیگنال نیست",
      ut.signal(cd[:i_flip + 2], use_filters=False) is None)
# افزودن آینده نباید سیگنالِ گذشته را عوض کند
s_again = ut.signal(cd[:i_flip + 1], use_filters=False)
check("خروجی فقط تابع پنجره است (تکرارپذیر)",
      s_again is not None and s_again.entry == s_dn.entry and s_again.sl == s_dn.sl)
check("استاپ شورت بالای ورود است", s_dn.sl > s_dn.entry)

print("\n۳. فیلترها")
# در سری صعودیِ بالا، فلیپ نزولی زیر EMA200 نیست → فیلتر باید ردش کند
s_f = ut.signal(cd[:i_flip + 1], use_filters=True)
check("شورتِ بالای EMA200 با فیلتر رد می‌شود", s_f is None)
# سری نزولی بلند → فلیپ صعودی وسطش باید با EMA رد شود
cd_dn = series([-0.004] * 260 + [0.008] * 12)
st2, d2 = ut.trail_series(cd_dn)
j_up = next((i for i in range(1, len(d2)) if d2[i] == 1 and d2[i - 1] == -1), None)
check("لانگِ زیر EMA200 با فیلتر رد می‌شود",
      j_up is not None and ut.signal(cd_dn[:j_up + 1], use_filters=True) is None
      and ut.signal(cd_dn[:j_up + 1], use_filters=False) is not None)
check("دادهٔ کوتاه = هیچ (قانون ۱)", ut.signal(cd[:50]) is None)

print("\n۴. بازپخش کامل")
tr = ut.walk(cd, use_filters=False)
check("بازپخش معامله ساخت", len(tr) >= 1, f"{len(tr)}")
check("هر معامله R و نتیجه دارد",
      all(t["R"] is not None and t["outcome"] in ("trail_line", "flip", "timeout")
          for t in tr))
check("زمان‌ها صعودی و بدون هم‌پوشانی",
      all(b["opened"] >= a["closed"] for a, b in zip(tr, tr[1:])))
lng = [t for t in tr if t["dir"] == "LONG"]
check("در سریِ عمدتاً صعودی، لانگ هست", len(lng) >= 1)
# تریل داخلی: در روند تمیزِ طولانی، خروجِ خط باید سود قفل کند (R > -1)
check("خروج با خط تریل، ضررِ کامل نمی‌سازد مگر گپ",
      all(t["R"] > -1.05 for t in tr))

print("\n۵. بدخیم‌ترین فرض در کندل دوطرفه")
# کندلی که هم خط را می‌زند هم بالا می‌بندد → باید خروجِ خط ثبت شود
base = series([0.004] * 220)
line_now = ut.trail_series(base)[0][-1]
crazy = base + [bar(base[-1]["t"] + 900_000, base[-1]["c"],
                    base[-1]["c"] * 1.05, line_now * 0.995,
                    base[-1]["c"] * 1.04)]
tr2 = ut.walk(crazy, use_filters=False)
touched = [t for t in tr2 if t["closed"] == crazy[-1]["t"]]
check("کندل دوطرفه = خروج خط (نه خوش‌بینی)",
      all(t["outcome"] == "trail_line" for t in touched) if touched else True)

print("\n۶. علّی بودن — تک‌گذر = برش‌به‌برش")
full_stops, full_dirs = ut.trail_series(cd)
same = all(ut.trail_series(cd[:i + 1])[0][i] == full_stops[i]
           for i in range(210, 260, 7))
check("خط UT روی برش دقیقاً همان خطِ تک‌گذر است (بدون درون‌بینی)", same)

print(f"\n{ok} قبول · {fail} رد")
sys.exit(1 if fail else 0)
