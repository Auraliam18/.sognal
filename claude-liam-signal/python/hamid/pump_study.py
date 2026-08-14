"""مطالعهٔ رویدادی پامپ — مدل دقیق حمید (۱۴ اوت).

«وقتی ارز در تایم ۱۵ دقیقه بیشتر از ۵ تا ۱۰٪ پامپ شد، وظیفهٔ ایجنت این
است که سریعاً تاریخچهٔ ارز را کامل از روز اول لانچ بررسی کند؛ هر پامپی
در تاریخچه دیده شد، تا ۲۴ ساعت قبل و بعدش بررسی شود تا بدانیم چه
ارزهایی واکنش داشتند؛ اگر ارزی مثلاً ۳ بار از ۱۰ پامپ این ارز رشد کرده،
در تاریخچه ثبت می‌شود؛ رابطهٔ معقول پیدا شد → ارز زیر نظر می‌رود و با
تکرار شرایط مشابه، به‌عنوان "ارز با احتمال پامپ" سیگنال می‌شود.»

تقسیم کار: این فایل تماماً Python قطعی است (فچ صفحه‌بندی‌شده، شمارش،
نسبت، دفتر ماندگار). ماشهٔ ۱۵د ≥۵٪ در خود رادار است؛ اینجا مغز آماری
پشت آن ماشه است.

صداقت پوشش: صرافی برای هر کندل سقف ۱۰۰۰تایی دارد؛ تاریخچهٔ کامل با
صفحه‌بندی endTime گرفته می‌شود (MEXC سازگار با بایننس). برای هر ارز
کاندیدا فقط پامپ‌هایی شمرده می‌شوند که دادهٔ کاندیدا آن بازه را پوشش
می‌دهد — N هر جفت جداست و کنار k گزارش می‌شود؛ «۳ از ۵» با «۳ از ۱۰»
یکی نیست.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
LEDGER = ROOT / "brain" / "pump-followers.json"

H1 = 3_600_000
PAGE = 1000                 # سقف هر درخواست صرافی
MAX_BARS = 6000             # ~۲۵۰ روز ۱س — «از روز اول» برای اکثر پامپی‌ها
REACT_PCT = 5.0             # واکنش = ≥۵٪ رشد در پنجرهٔ ۲۴س
WINDOW_H = 24
MIN_K = 3                   # مثال خود حمید: «۳ بار از ۱۰»
MIN_PROB = 0.30


def _mexc_page(sym, end_ms=None, tf="1h", n=PAGE):
    """یک صفحهٔ کندل؛ endTime برای رفتن به عقب. خطا بالا می‌رود."""
    itv = {"5m": "5m", "15m": "15m", "1h": "60m", "1d": "1d"}[tf]
    url = (f"https://api.mexc.com/api/v3/klines?symbol={sym}"
           f"&interval={itv}&limit={n}" + (f"&endTime={end_ms}" if end_ms else ""))
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "LIAM/1"}),
            timeout=25) as r:
        rows = json.load(r)
    return [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in rows]


def deep_history(sym, tf="1h", max_bars=MAX_BARS, fetch_page=None):
    """تاریخچهٔ کامل با صفحه‌بندی به عقب — تا روز لانچ یا سقف max_bars.

    fetch_page(sym, end_ms) قابل تزریق است تا بدون شبکه تست شود.
    """
    fetch_page = fetch_page or (lambda s, e: _mexc_page(s, e, tf))
    out = fetch_page(sym, None)
    if not out:
        return []
    while len(out) < max_bars:
        first = out[0]["t"]
        page = fetch_page(sym, first - 1)
        page = [c for c in page if c["t"] < first]
        if not page:                                  # روز اول لانچ — قبلش چیزی نیست
            break
        out = page + out
    return out[-max_bars:]


def find_pumps(c1h, gate_pct=8.0, window_h=4):
    """پامپ‌های تاریخچه: رشد ≥gate در پنجرهٔ چند ساعته. خروجی: [{t, ret_pct}]

    رخدادهای هم‌پوشان یکی شمرده می‌شوند (اوج همان موج، نه چند پامپ)."""
    out, last_t = [], 0
    w = window_h
    for i in range(w, len(c1h)):
        base = c1h[i - w]["c"]
        if not base:
            continue
        ret = (max(c["h"] for c in c1h[i - w + 1:i + 1]) / base - 1) * 100
        if ret >= gate_pct:
            t = c1h[i - w]["t"]
            if t - last_t >= WINDOW_H * H1:           # ضدهم‌پوشانی
                out.append({"t": t, "ret_pct": round(ret, 1)})
                last_t = t
    return out


def _reacted(cand, t0, direction=1):
    """آیا کاندیدا در پنجرهٔ [t0, t0+24س] (یا قبلش با direction=-1) ≥۵٪ رشد کرد؟"""
    lo, hi = (t0, t0 + WINDOW_H * H1) if direction > 0 else (t0 - WINDOW_H * H1, t0)
    seg = [c for c in cand if lo <= c["t"] <= hi]
    if len(seg) < 4:
        return None                                   # پوشش ندارد — شمرده نمی‌شود
    base = seg[0]["c"]
    if not base:
        return None
    peak = max(c["h"] for c in seg)
    lag_h = round((next(c["t"] for c in seg if c["h"] == peak) - lo) / H1, 1)
    return {"hit": (peak / base - 1) * 100 >= REACT_PCT, "lag_h": lag_h,
            "ret_pct": round((peak / base - 1) * 100, 1)}


def study(leader_sym, leader_c1h, candidates):
    """شمارش واکنش هر کاندیدا به همهٔ پامپ‌های تاریخی لیدر.

    candidates: {sym: c1h}. خروجی هر کاندیدا:
      N (پامپ‌های پوشش‌داده)، k_after، prob، میانهٔ تأخیر، k_before
    و فقط رابطهٔ ازقاعده‌گذشته qualified می‌شود (k≥۳ و prob≥۳۰٪).
    """
    pumps = find_pumps(leader_c1h)
    res = {"leader": leader_sym, "pumps_n": len(pumps),
           "coverage_from": leader_c1h[0]["t"] if leader_c1h else None,
           "followers": {}}
    for sym, cand in candidates.items():
        if sym == leader_sym or not cand:
            continue
        k_after = k_before = N = 0
        lags = []
        for p in pumps:
            after = _reacted(cand, p["t"], +1)
            if after is None:
                continue
            N += 1
            if after["hit"]:
                k_after += 1
                lags.append(after["lag_h"])
            before = _reacted(cand, p["t"], -1)
            if before and before["hit"]:
                k_before += 1
        if N == 0:
            continue
        prob = k_after / N
        row = {"N": N, "k_after": k_after, "prob": round(prob, 2),
               "k_before": k_before,
               "med_lag_h": sorted(lags)[len(lags) // 2] if lags else None,
               "qualified": k_after >= MIN_K and prob >= MIN_PROB}
        res["followers"][sym] = row
    return res


def reason_fa(leader, sym, row):
    lag = f"، معمولاً ~{row['med_lag_h']}س بعد" if row.get("med_lag_h") is not None else ""
    return (f"در {row['k_after']} از {row['N']} پامپ قبلی {leader.replace('USDT','')}، "
            f"{sym.replace('USDT','')} هم تا ۲۴س بعد ≥۵٪ رشد کرد "
            f"({round(row['prob']*100)}٪{lag})")


def save_ledger(res):
    """دفتر ماندگار — union: لیدرهای قبلی می‌مانند، همین لیدر تازه می‌شود."""
    led = {}
    if LEDGER.exists():
        try:
            led = json.loads(LEDGER.read_text())
        except Exception:                             # noqa: BLE001
            led = {}
    led[res["leader"]] = {**res, "checked_at": int(time.time() * 1000)}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1))
    return led


def run_for_leader(leader_sym, kc, universe, fetch_page=None, max_candidates=60):
    """کل چرخه برای یک لیدر تازه‌پامپ‌شده. خروجی: نتیجهٔ study + دفتر."""
    lead = deep_history(leader_sym, fetch_page=fetch_page)
    if len(lead) < 60:
        return None
    cands = {}
    for sym in list(universe)[:max_candidates]:
        if sym == leader_sym:
            continue
        try:
            cands[sym] = kc.get(sym, "1h", 1000)
        except Exception:                             # noqa: BLE001 - کاندیدای خراب حذف
            continue
    res = study(leader_sym, lead, cands)
    save_ledger(res)
    q = {s: r for s, r in res["followers"].items() if r["qualified"]}
    days = round((lead[-1]["t"] - lead[0]["t"]) / (24 * H1))
    print(f"  مطالعهٔ رویدادی {leader_sym}: {res['pumps_n']} پامپ در {days} روز "
          f"({len(lead)} کندل) · {len(q)} دنباله‌روی ازقاعده‌گذشته")
    return res
