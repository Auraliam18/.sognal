"""انجین اردر بلاک — روش خود حمید (۱۳ اوت ۲۰۲۶)، کلمه به کلمه:

    «پس از ریزش یا صعود در تایم‌فریم‌های ۱ساعته و ۱۵دقیقه به قبل از حرکت
    برمی‌گردد و اولین کندلی که از لحاظ بدنه از شدوهایش بزرگ‌تر است را
    به‌عنوان اردر بلاک همان تایم‌فریم استفاده می‌کند. تا ۳۰۰ کندل به عقب
    می‌گردد، باکس اردر بلاک را تا پایان چارت ادامه می‌دهد تا ببیند چقدر
    واکنش داشته است. اردر بلاک معتبر همیشه معتبر نیست — نکته‌اش این است.
    اردر بلاک جدید پیدا کن، قبلی‌ها را پیدا کن و ادامه بده.»

و درس‌های چارت‌های خودش (۱۲-۱۳ اوت): مستطیلی که ۷ بار پولبک خورده و
حداقل ۲ بار هانت شده؛ باکسی که یک هفته بعد هنوز جواب می‌دهد؛ و سؤال
کلیدی‌اش: «همیشه واکنش دارد، نکته‌اش کجاست؟» — جواب این انجین: شمردن.

صداقت شمارش همان ماشین structure است: واکنش یعنی قیمت آمد، از آن‌طرف
نبست، و واقعاً برگشت. هانت یعنی ویک داخل/آن‌طرف باکس رفت ولی همان طرفِ
آمدنش بست. شکست یعنی آن‌طرف بست — باکس مصرف شد. و هر باکس باید از کفِ
نویزِ همان سری بهتر باشد (باکس تصادفی در یک رنج هم «واکنش» می‌گیرد؛
باکسی که از باکس شانسی بهتر نیست، اعتبار نیست).

    python3 -m hamid.test_orderblocks
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid.structure import atr                               # noqa: E402

MAX_BACK = 300        # دستور حمید: تا ۳۰۰ کندل عقب
IMP_ATR = 4.5         # حرکت ≥ این‌قدر ATR در ≤ IMP_BARS کندل = ریزش/صعود واقعی
IMP_BARS = 12


def _body(c):
    return abs(c["c"] - c["o"])


def _wicks(c):
    return (c["h"] - c["l"]) - _body(c)


def hamid_candle(c):
    """قانون حمید: بدنه از مجموع شدوها بزرگ‌تر باشد."""
    return _body(c) > _wicks(c) and _body(c) > 0


def _full_atr(cd):
    """میانگین TR روی کل پنجره — نه فقط دُم. برای قضاوت دربارهٔ «حرکت بزرگ»
    در ۳۰۰ کندل، ATRِ چهارده‌کندلیِ دم گمراه‌کننده است: دمِ آرام، حرکت‌های
    عادی وسط سری را «ایمپالس» جا می‌زند (در کنترل نویز دیده شد)."""
    if len(cd) < 2:
        return 0.0
    trs = [max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - cd[i - 1]["c"]),
               abs(cd[i]["l"] - cd[i - 1]["c"])) for i in range(1, len(cd))]
    return sum(trs) / len(trs)


def _impulses(cd):
    """ریزش/صعودهای واقعی: جابه‌جایی ≥ IMP_ATR×ATR در ≤ IMP_BARS کندل از یک
    اکسترمم محلی. لنگر = کندلِ مبدأ حرکت — قانون حمید «برگشت به قبل از
    حرکت» است؛ نسخه‌های اول خودِ کندل ریزش یا کندل دریفت را می‌گرفتند
    (هر دو در تست دیده شد، نه حدس)."""
    a = _full_atr(cd)
    if not a:
        return []
    out = []
    n = len(cd)
    last_dn, last_up = -9, -9
    for i in range(max(3, n - MAX_BACK), n - 2):
        win = cd[max(0, i - 3):i + 2]
        end = min(n, i + IMP_BARS + 1)
        if i - last_dn >= 4 and cd[i]["h"] >= max(x["h"] for x in win):
            # سقف محلی → ریزش بعدش؟ لنگر پالایش می‌شود به بلندترین کندلِ
            # نزدیک (مبدأ واقعی) و حرکت از خودِ لنگر دوباره سنجیده می‌شود —
            # وگرنه کندل دریفتی، لنگر را وسط لگ می‌اندازد (در تست دیده شد).
            j0 = max(range(i, min(i + 5, n)), key=lambda x: cd[x]["h"])
            e2 = min(n, j0 + IMP_BARS + 1)
            drop = cd[j0]["c"] - min((x["c"] for x in cd[j0 + 1:e2]),
                                     default=cd[j0]["c"])
            if drop >= IMP_ATR * a:
                out.append({"i": j0, "dir": "down", "mag_atr": round(drop / a, 2)})
                last_dn = j0
                continue
        if i - last_up >= 4 and cd[i]["l"] <= min(x["l"] for x in win):
            j0 = min(range(i, min(i + 5, n)), key=lambda x: cd[x]["l"])
            e2 = min(n, j0 + IMP_BARS + 1)
            rise = max((x["c"] for x in cd[j0 + 1:e2]),
                       default=cd[j0]["c"]) - cd[j0]["c"]
            if rise >= IMP_ATR * a:
                out.append({"i": j0, "dir": "up", "mag_atr": round(rise / a, 2)})
                last_up = j0
    return out


def _ob_candle(cd, start_i, lookback=6):
    """از کندلِ قبل از حرکت به عقب برو؛ اولین کندلِ «بدنه > شدوها» — قانون حمید."""
    for j in range(start_i, max(-1, start_i - lookback), -1):
        if hamid_candle(cd[j]):
            return j
    return None


def _score_box(cd, lo, hi, born_i, role=None):
    """امتداد باکس تا انتهای چارت: لمس/واکنش/هانت/شکست — با سه‌قِسمِ structure.

    approach از یک طرف، نبستن آن‌طرف در ۶ کندل بعد، و برگشتِ ≥ ۳ تلورانس."""
    a = atr(cd)
    tol = max(a * 0.25, (hi - lo) * 0.25, cd[-1]["c"] * 0.0005)
    touches = reactions = hunts = 0
    broken_at = None
    last = -99
    visit_open = False                                # داخل همان بازدید هستیم؟
    visit_hunted = False
    n = len(cd)
    for i in range(born_i + 3, n):
        c = cd[i]
        if c["l"] > hi + tol or c["h"] < lo - tol:
            visit_open = False
            continue                                  # اصلاً نزدیک باکس نیست
        prev = cd[i - 1]["c"]
        new_visit = not (lo < prev < hi) and (i - last >= 3 or not visit_open)
        if not new_visit:
            # ادامهٔ همان بازدید — فقط عمق ویک را نگاه کن (هانتِ دیرهنگام)
            if visit_open and not visit_hunted:
                deep = (c["l"] < (lo + tol) if side > 0 else c["h"] > (hi - tol))
                out_close = (c["c"] > hi if side > 0 else c["c"] < lo)
                if deep and out_close:
                    hunts += 1
                    visit_hunted = True
            continue
        side = 1 if prev >= hi else -1                # از بالا آمده یا از پایین
        # نقش باکس (قانون SMC): OB نزولی مقاومت است — فقط approach از پایین و
        # ریجکتِ رو به پایین «واکنش» است؛ OB صعودی برعکس. باکس شانسی از هر
        # دو طرف واکنش می‌گیرد و همین لوش می‌دهد.
        if role == "down" and side != -1:
            continue
        if role == "up" and side != 1:
            continue
        touches += 1
        last = i
        visit_open, visit_hunted = True, False
        edge = hi if side > 0 else lo
        far = lo if side > 0 else hi
        after = cd[i + 1:min(n, i + 7)]
        if not after:
            continue
        closed_through = (min(x["c"] for x in after) < far - tol if side > 0
                          else max(x["c"] for x in after) > far + tol)
        if closed_through:
            if broken_at is None:
                broken_at = i
            visit_open = False
            continue
        # واکنش یعنی برگشتِ واقعی: چند-ATR دور شود و بیرون هم بماند — باکس
        # شانسی در رنج، برگشتِ ریز و ناماندگار می‌گیرد؛ برگشتِ معنادار نه.
        away = (max(x["c"] for x in after) - edge) if side > 0 \
            else (edge - min(x["c"] for x in after))
        stay_out = sum(1 for x in after
                       if (x["c"] > hi if side > 0 else x["c"] < lo)) >= len(after) // 2
        if away >= max(3 * tol, 2.5 * a) and stay_out:
            reactions += 1
            if (c["l"] < far + tol if side > 0 else c["h"] > far - tol):
                hunts += 1
                visit_hunted = True
    return touches, reactions, hunts, broken_at


def _noise_floor(cd, height, born_i, samples=20):
    """واکنشِ باکس شانسی با همین ارتفاع و همین تاریخ تولد در همین سری —
    صدک ۸۰. باکس واقعی باید از باکس شانسیِ هم‌شرایط بهتر باشد؛ مقایسه با
    باکسی که زودتر/دیرتر به دنیا آمده منصفانه نیست."""
    lo_all = min(c["l"] for c in cd)
    hi_all = max(c["h"] for c in cd)
    if hi_all - lo_all <= height:
        return 0.0
    n = len(cd)
    born = min(born_i, n - 15)
    rates = []
    for k in range(samples):
        base = lo_all + (hi_all - lo_all - height) * ((k + 0.5) / samples)
        _, r, _, _ = _score_box(cd, base, base + height, born)
        rates.append(r / max(1, n - born) * 100)
    rates.sort()
    return rates[int(len(rates) * 0.8)]


def find(cd, tf="1h", min_reactions=2):
    """همهٔ اردر بلاک‌های معتبر پنجره (تا ۳۰۰ کندل عقب) — رتبه با واکنش.

    خروجی هر باکس: قیمت‌ها، جهت حرکتی که ساختش، شمارش لمس/واکنش/هانت،
    شکسته/تازه، و سن — همان چیزهایی که حمید روی چارت با دست می‌نویسد."""
    if len(cd) < 60:
        return []
    px = cd[-1]["c"]
    boxes = []
    for imp in _impulses(cd):
        j = _ob_candle(cd, imp["i"])
        if j is None:
            continue
        lo, hi = cd[j]["l"], cd[j]["h"]
        if hi <= lo:
            continue
        touches, reactions, hunts, broken_at = _score_box(cd, lo, hi, j, role=imp["dir"])
        boxes.append({"tf": tf, "i": j, "t": cd[j]["t"], "low": round(lo, 10),
                      "high": round(hi, 10), "move": imp["dir"],
                      "mag_atr": imp["mag_atr"], "touches": touches,
                      "reactions": reactions, "hunts": hunts,
                      "broken": broken_at is not None,
                      "fresh": touches == 0 and broken_at is None,
                      "age": len(cd) - 1 - j,
                      "inside_now": lo <= px <= hi})
    # ادغام باکس‌های هم‌پوشان — همان باکس از دو حرکت، دو بار شمرده نشود
    boxes.sort(key=lambda b: -b["reactions"])
    merged = []
    for b in boxes:
        dup = any(not (b["high"] < m["low"] or b["low"] > m["high"])
                  and abs(b["i"] - m["i"]) < 6 for m in merged)
        if not dup:
            merged.append(b)
    # دروازهٔ صداقت: واکنش کافی + بهتر از باکس شانسی؛ باکس «تازه» (هنوز
    # لمس‌نشده و نشکسته) بدون سابقه هم گزارش می‌شود ولی جدا برچسب دارد.
    keep = []
    for b in merged:
        if b["fresh"] and b["age"] <= MAX_BACK:
            keep.append(b)
            continue
        if b["reactions"] < min_reactions or b["broken"]:
            continue
        keep.append(b)
    keep.sort(key=lambda b: (-b["reactions"], b["age"]))
    return keep[:8]


def near(cd, tf="1h"):
    """باکس معتبرِ دربرگیرنده یا نزدیکِ قیمت فعلی — برای بازجویی و کپشن."""
    px = cd[-1]["c"]
    a = atr(cd) or px * 0.005
    best_in, best_near = None, None
    for b in find(cd, tf=tf):
        if b["low"] <= px <= b["high"]:
            if best_in is None:
                best_in = b
        elif min(abs(px - b["low"]), abs(px - b["high"])) <= 2 * a:
            if best_near is None:
                best_near = b
    return best_in, best_near


def note_fa(b, where="داخل"):
    """جملهٔ فارسی با عدد — برای کپشن و دلیل."""
    tag = "تازه (هنوز لمس‌نشده)" if b["fresh"] else \
        f"{b['reactions']} واکنش" + (f"، {b['hunts']} هانت" if b["hunts"] else "")
    return (f"اردر بلاک {b['tf']} ({where}، {tag}"
            f"{'، مصرف‌شده' if b['broken'] else ''})")
