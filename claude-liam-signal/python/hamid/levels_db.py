"""دیتابیس معتبر خطوط — سطح و خط روند، چندتایم‌فریمی، انباشته.

دستور حمید (۱۶ اوت): «انجینی که ترندلاین می‌کشد و حمایت و مقاومت را بررسی
می‌کند باید آپدیت شود و یک دیتابیس قوی و معتبر بهش بدی که بتواند ترندلاین
را در تایم‌فریم‌های مختلف دقیق‌تر بکشد.»

## چرا خطِ محاسبه‌شده در لحظه دقیق نیست

`structure.trendline()` هر بار از صفر روی پنجرهٔ همان لحظه کشیده می‌شود.
دو ضعف دارد و هر دو را حمید در سندش نام برده:

  ۱. **حافظه ندارد.** خطی که سه روز پیش سه واکنش معتبر گرفته بود، امروز
     اگر پنجره جابه‌جا شده باشد اصلاً دیده نمی‌شود. سند حمید صریح است:
     «خط معتبر حذف نمی‌شود؛ وضعیتش به ACTIVE/BROKEN/FLIPPED/HISTORICAL
     تغییر می‌کند.»
  ۲. **اعتبارش انباشته نمی‌شود.** هر برخورد تازه باید خط را **معتبرتر**
     کند. وقتی هر بار از نو ساخته می‌شود، برخوردهای قبلی شمرده نمی‌شوند.

## کاری که این فایل می‌کند

برای هر (نماد، تایم‌فریم) یک پرونده نگه می‌دارد: خطوط روند و سطوح افقی،
با شناسه، تاریخ تولد، شمار برخورد **انباشته**، و وضعیت. هر اجرا:

    ۱. خطوط تازه را از کندل‌های فعلی استخراج می‌کند
    ۲. با خطوط ذخیره‌شده **تطبیق** می‌دهد (همان خط است یا خط تازه؟)
    ۳. برخورد تازه را روی خط قدیمی می‌افزاید — اعتبار انباشته می‌شود
    ۴. شکست بدنه را ثبت می‌کند: ACTIVE → BROKEN، و اگر قیمت از سمت دیگر
       به آن واکنش نشان داد → FLIPPED (همان «نقش‌عوض‌کردن» سند حمید)
    ۵. خطی که خیلی وقت است لمس نشده → HISTORICAL، ولی **پاک نمی‌شود**

## تطبیق دو خط: چرا بر حسب قیمت، نه ضریب

دو خط با شیب و عرض‌از‌مبدأ نزدیک، اگر پنجره جابه‌جا شده باشد، عددهای
کاملاً متفاوتی دارند. مقایسهٔ ضرایب جواب غلط می‌دهد. این‌جا دو خط وقتی
«یکی» شمرده می‌شوند که **قیمتی که در دو زمان مرجع می‌دهند** به هم نزدیک
باشد — یعنی از نظر معامله‌گر روی چارت یک خط‌اند.

اجرا:
    python3 -m hamid.levels_db --symbols 40
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
DB = ROOT / "brain" / "levels"

TIMEFRAMES = (("4h", 300), ("1h", 400), ("15m", 400))
MATCH_TOL_ATR = 0.55        # دو خط یکی‌اند اگر اختلاف قیمتشان < این × ATR
STALE_BARS = 220            # از این بیشتر لمس نشد → تاریخی
KEEP = 40                   # سقف خط ذخیره‌شده در هر (نماد، تایم‌فریم)


def _path(sym, tf):
    return DB / sym / f"{tf}.json"


def load(sym, tf):
    try:
        return json.loads(_path(sym, tf).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001 - اولین بار
        return {"symbol": sym, "tf": tf, "lines": [], "levels": []}


def save(sym, tf, j):
    p = _path(sym, tf)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")


def _line_price(rec, t, step_ms, t0):
    """قیمت خط در یک timestamp — ذخیره بر حسب زمان است نه ایندکس، چون
    ایندکس با جابه‌جا شدن پنجره بی‌معنا می‌شود."""
    if not step_ms:
        return None
    i = (t - t0) / step_ms
    return rec["slope"] * i + rec["intercept"]


def _same_line(a, b, cd, tol):
    """آیا این دو، از نظر کسی که به چارت نگاه می‌کند، یک خط‌اند؟"""
    if a.get("kind") != b.get("kind"):
        return False
    if len(cd) < 2:
        return False
    step = cd[1]["t"] - cd[0]["t"]
    for t in (cd[0]["t"], cd[-1]["t"]):
        pa = _line_price(a, t, step, a["t0"])
        pb = _line_price(b, t, step, b["t0"])
        if pa is None or pb is None or abs(pa - pb) > tol:
            return False
    return True


def update(sym, tf, cd, now_ms=None):
    """خطوط این تایم‌فریم را با کندل‌های تازه به‌روز کن و برگردان."""
    from hamid import structure as st

    if len(cd) < 60:
        return None
    now_ms = now_ms or cd[-1]["t"]
    j = load(sym, tf)
    atr = st.atr(cd) or 0
    tol = atr * MATCH_TOL_ATR
    step = cd[1]["t"] - cd[0]["t"]

    fresh = st.trendline(cd)
    if fresh:
        # مبدأ از خودِ خط می‌آید، نه از کندل اول سری — `trendline` روی
        # پنجرهٔ آخر برازش می‌کند و اگر مبدأ را اشتباه بگیریم، دو خطِ یکسان
        # هرگز با هم تطبیق نمی‌خورند و انباشتگی اتفاق نمی‌افتد.
        rec = {"kind": fresh.kind, "slope": fresh.slope,
               "intercept": fresh.intercept, "t0": fresh.t0,
               "step_ms": fresh.step_ms,
               "touches": fresh.touches, "broken": fresh.broken}
        match = None
        for old in j["lines"]:
            if _same_line(old, rec, cd, tol):
                match = old
                break
        if match:
            # همان خط — اعتبارش **انباشته** می‌شود، از نو شروع نمی‌شود.
            match["touches_total"] = (match.get("touches_total")
                                      or match.get("touches") or 0) + fresh.touches
            match["seen_runs"] = (match.get("seen_runs") or 1) + 1
            match["last_seen"] = now_ms
            match["slope"], match["intercept"] = fresh.slope, fresh.intercept
            match["t0"], match["step_ms"] = fresh.t0, fresh.step_ms
            if fresh.broken and match.get("status") == "ACTIVE":
                match["status"] = "BROKEN"
                match["broken_at"] = now_ms
            elif not fresh.broken and match.get("status") == "BROKEN":
                # قیمت برگشت و از سمت دیگر به همان خط واکنش داد.
                match["status"] = "FLIPPED"
                match["flipped_at"] = now_ms
        else:
            rec.update({"id": f"{tf}-{int(now_ms/1000)}-{fresh.kind[:3]}",
                        "born": now_ms, "last_seen": now_ms,
                        "touches_total": fresh.touches, "seen_runs": 1,
                        "status": "BROKEN" if fresh.broken else "ACTIVE"})
            j["lines"].append(rec)

    # سطوح افقی — همان قاعدهٔ ≥۲ واکنش که از قبل هست، ولی انباشته
    for lv in st.levels(cd)[:8]:
        hit = None
        for old in j["levels"]:
            if abs(old["price"] - lv.price) <= tol:
                hit = old
                break
        if hit:
            hit["reactions_total"] = (hit.get("reactions_total") or 0) + lv.reactions
            hit["seen_runs"] = (hit.get("seen_runs") or 1) + 1
            hit["last_seen"] = now_ms
            hit["price"] = round((hit["price"] + lv.price) / 2, 10)
            if lv.flipped:
                hit["status"] = "FLIPPED"
        else:
            j["levels"].append({
                "price": lv.price, "kind": lv.kind, "born": now_ms,
                "last_seen": now_ms, "reactions_total": lv.reactions,
                "seen_runs": 1,
                "status": "FLIPPED" if lv.flipped else "ACTIVE"})

    # کهنه‌ها تاریخی می‌شوند — **حذف نمی‌شوند** (سند حمید)
    stale_ms = STALE_BARS * step
    for coll in ("lines", "levels"):
        for r in j[coll]:
            if r.get("status") in ("ACTIVE", "BROKEN") and \
               now_ms - (r.get("last_seen") or 0) > stale_ms:
                r["status"] = "HISTORICAL"
        # سقف: تاریخی‌های کم‌اعتبارتر اول کنار می‌روند، فعال‌ها می‌مانند
        j[coll].sort(key=lambda r: (
            {"ACTIVE": 0, "FLIPPED": 1, "BROKEN": 2, "HISTORICAL": 3}
            .get(r.get("status"), 4),
            -(r.get("touches_total") or r.get("reactions_total") or 0)))
        j[coll] = j[coll][:KEEP]

    j["updated"] = now_ms
    save(sym, tf, j)
    return j


def best_line(sym, tf, cd, min_runs=2):
    """معتبرترین خط برای کشیدن — انباشته، نه لحظه‌ای.

    `min_runs` مهم است: خطی که فقط یک بار دیده شده هنوز تأیید مستقل
    ندارد. خطی که در چند اجرای جدا دوباره پیدا شده، همان خطی است که
    حمید دستی هم می‌کشید.
    """
    j = load(sym, tf)
    cands = [r for r in j.get("lines") or []
             if r.get("status") in ("ACTIVE", "FLIPPED")
             and (r.get("seen_runs") or 1) >= min_runs]
    if not cands:
        return None
    cands.sort(key=lambda r: (-(r.get("touches_total") or 0),
                              -(r.get("seen_runs") or 0)))
    return cands[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=40)
    a = ap.parse_args()
    import sources
    from hamid.trainer import top_symbols

    syms = top_symbols(a.symbols)
    tot = {"lines": 0, "levels": 0, "active": 0}
    for sym in syms:
        for tf, n in TIMEFRAMES:
            try:
                rows = sources.klines(sym, tf, n)
                cd = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                       "c": k[4], "v": k[5]} for k in rows]
                j = update(sym, tf, cd)
                if not j:
                    continue
                tot["lines"] += len(j["lines"])
                tot["levels"] += len(j["levels"])
                tot["active"] += sum(1 for r in j["lines"]
                                     if r.get("status") == "ACTIVE")
            except Exception as e:                   # noqa: BLE001
                print(f"{sym} {tf}: {type(e).__name__}")
    print(f"دیتابیس خطوط: {len(syms)} ارز × {len(TIMEFRAMES)} تایم‌فریم")
    print(f"  خط روند ذخیره‌شده {tot['lines']} (فعال {tot['active']}) · "
          f"سطح افقی {tot['levels']}")
    print(f"→ {DB}")


if __name__ == "__main__":
    main()


def as_trendline(rec):
    """رکورد ذخیره‌شده را به شکل `structure.Trendline` دربیاور تا هرجا که
    خط لحظه‌ای مصرف می‌شود، خطِ **انباشته** هم بدون تغییر کد بنشیند."""
    from hamid.structure import Trendline
    return Trendline(
        slope=rec["slope"], intercept=rec["intercept"], kind=rec["kind"],
        touches=rec.get("touches_total") or rec.get("touches") or 0,
        first_i=0, last_i=0,
        broken=rec.get("status") in ("BROKEN", "HISTORICAL"),
        t0=rec.get("t0") or 0, step_ms=rec.get("step_ms") or 0)
