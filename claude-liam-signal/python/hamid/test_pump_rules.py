"""قوانین گزارش پامپ — دستور حمید، ۱۴ اوت.

سه قانون که تا امروز در کد نبودند و شکایت حمید دقیقاً از نبودشان بود:

۱. «لیست ارزایی که دادی همشون توی پامپ بودن» → کاندیدا باید **هنوز نپریده**
   باشد. آستانهٔ ۱۰٪ قبلی بی‌معنا بود؛ ارزی که ۸٪ رفته در حال پامپ است.
۲. «وقتی یک ارزی می‌ره بالای ۱۰ درصد و ۲ روز توی صدر پامپ‌ها می‌مونه نیاز
   نیست هر روز گزارش پامپشو بدی» → رهبر کهنه ماشه نمی‌شود.
۳. «ارزی که پامپ شده رو یه بار تاریخچشو می‌خونی و دیگه ذخیره داریش» →
   تاریخچهٔ عمیق یک بار، بعد فقط دنباله.

همه بدون شبکه: زمان و صفحهٔ کندل تزریق می‌شوند.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import pump_radar as pr                    # noqa: E402
from hamid import pump_study as ps                    # noqa: E402

ok = 0
fail = []
H = 3_600_000


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


print("── قوانین گزارش پامپ ──")

# ── ۱. کاندیدا باید هنوز نپریده باشد ───────────────────────────────────────
def blk(sym, **kw):
    b = {"symbol": sym, "price": 100.0, "role": "دنباله‌رو",
         "now": {"rsi_1h": 55}, "pumps": [],
         "alarm": {"entry": 99.0, "sl": 95.0},
         "event_leaders": [{"symbol": "LEADUSDT", "N": 5, "k_after": 3,
                            "prob": 0.6, "reason": "۳ از ۵"}]}
    b.update(kw)
    return b


quiet = blk("QUIETUSDT", change_24h_pct=1.2, change_60m_pct=0.4, change_30m_pct=0.2)
mid = blk("MIDUSDT", change_24h_pct=8.0, change_60m_pct=0.5, change_30m_pct=0.1)
fast = blk("FASTUSDT", change_24h_pct=2.0, change_60m_pct=4.5, change_30m_pct=4.0)

got = pr.recommend([quiet, mid, fast])
syms = {p["symbol"] for p in got}
check("ارز آرام کاندیدا می‌شود", "QUIETUSDT" in syms)
check("ارز ۸٪/۲۴س دیگر کاندیدا نیست (شکایت اصلی حمید)", "MIDUSDT" not in syms)
check("ارز ۴.۵٪/۱س دیگر کاندیدا نیست", "FASTUSDT" not in syms)
check("دلیل ردشدن نوشته می‌شود، نه سکوت",
      "هنوز-نپریده نیست" in (mid.get("skipped") or ""))
check("درصد واقعی در دلیل رد می‌آید", "+8.0٪ در ۲۴س" in (mid.get("skipped") or ""))

# مرزها: دقیقاً روی آستانه باید رد شود، نه قبول
edge = blk("EDGEUSDT", change_24h_pct=pr.QUIET_24H, change_60m_pct=0,
           change_30m_pct=0)
check("دقیقاً روی آستانه رد می‌شود (>= نه >)",
      "EDGEUSDT" not in {p["symbol"] for p in pr.recommend([edge])})

# ── ۲. رهبر کهنه ───────────────────────────────────────────────────────────
t0 = 1_755_000_000_000
gs = [{"symbol": "OLDUSDT", "change_pct": 42.0},
      {"symbol": "NEWUSDT", "change_pct": 13.0},
      {"symbol": "SWEETUSDT", "change_pct": 6.5}]

a, seen1 = pr.freshness(gs, now_ms=t0, seen={})
check("بار اول هیچ‌کس کهنه نیست", not any(g.get("stale") for g in a))
check("پروندهٔ نمادهای بالای ۱۰٪ باز می‌شود",
      set(seen1) == {"OLDUSDT", "NEWUSDT"})
check("ارز زیر ۱۰٪ پرونده نمی‌گیرد", "SWEETUSDT" not in seen1)
check("حرکت ۵–۱۰٪ به‌عنوان «سریع» علامت می‌خورد",
      next(g for g in a if g["symbol"] == "SWEETUSDT")["sweet"])

# ۴۹ ساعت بعد، هر دو هنوز بالای جدول
later = t0 + 49 * H
b2, seen2 = pr.freshness(gs, now_ms=later, seen=seen1)
old = next(g for g in b2 if g["symbol"] == "OLDUSDT")
check("بعد از ۴۸ ساعت رهبر کهنه می‌شود", old["stale"])
check("سن واقعی گزارش می‌شود", old["top_age_h"] == 49.0)
check("دلیل کهنگی نوشته می‌شود", "روز است بالای" in old["stale_note"])

# همان نماد وقتی برمی‌گردد زیر آستانه، پرونده‌اش بسته می‌شود
gs_down = [{"symbol": "OLDUSDT", "change_pct": 2.0}]
_b3, seen3 = pr.freshness(gs_down, now_ms=later, seen=seen2)
check("برگشت زیر ۱۰٪ پرونده را می‌بندد", "OLDUSDT" not in seen3)
_b4, seen4 = pr.freshness([{"symbol": "OLDUSDT", "change_pct": 30.0}],
                          now_ms=later + H, seen=seen3)
check("پامپ بعدیِ همان ارز دوباره تازه است",
      not _b4[0].get("stale") and seen4["OLDUSDT"]["first_ms"] == later + H)

# نمادی که از جدول افتاده نباید تا ابد در دفتر بماند
_b5, seen5 = pr.freshness([{"symbol": "XUSDT", "change_pct": 20.0}],
                          now_ms=later, seen=seen2)
check("نماد خارج‌شده از جدول از دفتر پاک می‌شود",
      set(seen5) == {"XUSDT"})

# ترتیب ماشه‌ها
trg = pr.triggers_of(b2, ign=[], deep_n=4)
check("رهبر کهنه ماشه نمی‌شود", "OLDUSDT" not in {g["symbol"] for g in trg})
check("حرکت سریع ۵–۱۰٪ اول می‌آید", trg[0]["symbol"] == "SWEETUSDT")
check("همهٔ گینرها کهنه بودند → ماشه‌ای نیست",
      pr.triggers_of([{"symbol": "AUSDT", "change_pct": 40.0, "stale": True}]) == [])

# ── ۳. ترکیب گزارش: رهبر پامپ‌شده + کاندیدای نپریده ───────────────────────
leader_b = {"symbol": "LEADUSDT", "layer": 1, "change_24h_pct": 22.0,
            "change_60m_pct": 9.0,
            "event_study": {"pumps_n": 11, "from_date": "03-02 10:00"}}
picks = pr.recommend([quiet])
msg = pr.tg_message("تست", picks, [leader_b, quiet])
check("رهبر پامپ‌شده با نام در پیام می‌آید", "رهبر (پامپ‌شده): LEADUSDT" in msg)
check("حرکت رهبر در پیام می‌آید", "+22.0٪ در ۲۴س" in msg)
check("تعداد پامپ تاریخی رهبر در پیام می‌آید", "11 پامپ از 03-02" in msg)
check("تصریح می‌شود کاندیداها هنوز پامپ نشده‌اند",
      "هیچ‌کدام هنوز پامپ نشده‌اند" in msg)
check("کاندیدای آرام در پیام هست", "QUIETUSDT" in msg)
check("تاریخ خام (timestamp) روی پیام نمی‌نشیند", "1755" not in msg)

# ── ۴. کش تاریخچه ──────────────────────────────────────────────────────────
def series(n, start_t, base=100.0, pump_at=None):
    """کندل ۱ساعته؛ pump_at ایندکسی که از آن‌جا ۲۰٪ می‌پرد."""
    out, p = [], base
    for i in range(n):
        if pump_at is not None and i == pump_at:
            p *= 1.20
        out.append({"t": start_t + i * H, "o": p, "h": p * 1.001,
                    "l": p * 0.999, "c": p, "v": 10.0})
    return out


calls = {"n": 0}
hist = series(300, t0, pump_at=100)


def fake_page(sym, end_ms):
    calls["n"] += 1
    if end_ms is None:
        return hist[-100:]
    return [c for c in hist if c["t"] < end_ms][-100:]


cache = {}
p1, m1 = ps.leader_pumps("LEADUSDT", fetch_page=fake_page, now_ms=t0, cache=cache)
first_calls = calls["n"]
check("بار اول تاریخچه عمیق خوانده می‌شود", m1["mode"] == "deep" and first_calls > 1)
check("پامپ ۲۰٪ در تاریخچه پیدا شد", len(p1) >= 1)
check("کش نوشته شد", "LEADUSDT" in cache)

calls["n"] = 0
p2, m2 = ps.leader_pumps("LEADUSDT", fetch_page=fake_page,
                         now_ms=t0 + H, cache=cache)
check("اجرای بعدیِ نزدیک، اصلاً شبکه نمی‌زند",
      m2["mode"] == "cache" and calls["n"] == 0)
check("همان پامپ‌ها برمی‌گردند", p2 == p1)

calls["n"] = 0
p3, m3 = ps.leader_pumps("LEADUSDT", fetch_page=fake_page,
                         now_ms=t0 + 20 * H, cache=cache)
check("کش کهنه فقط دنباله می‌گیرد، نه تاریخچهٔ کامل",
      m3["mode"] == "tail" and calls["n"] == 1)
check("رخداد قدیمی با دنبالهٔ تازه پاک نمی‌شود", len(p3) >= len(p1))

# ادغام: دو رخداد در فاصلهٔ کمتر از ۲۴ ساعت یک موج‌اند
merged = ps.merge_pumps([{"t": t0, "ret_pct": 12.0}],
                        [{"t": t0 + 3 * H, "ret_pct": 18.0},
                         {"t": t0 + 60 * H, "ret_pct": 9.0}])
check("رخدادهای هم‌موج یکی می‌شوند", len(merged) == 2)
check("اوج بزرگ‌تر همان موج می‌ماند", merged[0]["ret_pct"] == 18.0)
check("رخداد دور، جدا می‌ماند", merged[1]["t"] == t0 + 60 * H)
check("ادغام مرتب برمی‌گردد", [m["t"] for m in merged] == sorted(m["t"] for m in merged))

# study با pumps تزریقی نباید تاریخچه بخواهد
res = ps.study("LEADUSDT", None, {"FOLUSDT": series(200, t0)},
               pumps=p1, coverage_from=t0)
check("study با pumps کش‌شده بدون کندل لیدر کار می‌کند",
      res["pumps_n"] == len(p1) and res["coverage_from"] == t0)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون قوانین پامپ گذشت")
