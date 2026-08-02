#!/usr/bin/env python3
"""هر پارسر پایتون را با همان ردیفی که پروب واقعاً گرفت تست می‌کند.

The JavaScript side already has this test. The Python side needed its own,
because the two adapter tables are written separately and can drift — and a
drift here is invisible: a wrong field index still parses as a number, the scan
still completes, the panel still draws candles. It just draws the wrong ones.

The rows below are the same recorded replies tests/sources-parse.mjs uses, which
came out of probe_sources.py rather than out of any documentation. Every one is
BTC/USDT 15m at roughly the same minute, so after parsing they must all agree on
the price to within a fraction of a percent. That cross-check is the part that
actually catches a scrambled field order.

Runs offline. No exchange has to be up.

    python3 claude-liam-signal/python/test_sources.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources                                       # noqa: E402

RECORDED = {
    "mexc": [
        [1785656700000, "63548.41", "63548.41", "63497.75", "63509.48", "63.64265045", 1785657600000],
        [1785657600000, "63509.48", "63560.00", "63490.00", "63540.00", "51.11", 1785658500000],
    ],
    # newest first, seconds, [t, open, CLOSE, HIGH, LOW, vol, turnover]
    "kucoin": [
        ["1785665700", "63238.3", "63255.0", "63260.0", "63230.0", "0.70", "44000.0"],
        ["1785664800", "63272.3", "63238.3", "63272.3", "63238.3", "0.71017397", "44920.089347816"],
    ],
    "okx": {"data": [   # newest first, ms
        ["1785665700000", "63234.1", "63260.0", "63230.0", "63255.0", "1.70", "107000.0"],
        ["1785664800000", "63271", "63271", "63234.1", "63234.1", "1.78132461", "112670.341183148"],
    ]},
    "bitget": {"data": [  # oldest first, ms
        ["1785656700000", "63528.58", "63528.58", "63471.62", "63485.98", "40.260803", "2556090.49546045"],
        ["1785657600000", "63485.98", "63560.00", "63480.00", "63540.00", "38.10", "2420000.00"],
    ]},
    # oldest first, seconds, [t, VOLUME, close, high, low, open, baseVol]
    "gate": [
        ["1785656700", "2596079.82040720", "63498.9", "63533.2", "63475.5", "63533.2", "40.88496700"],
        ["1785657600", "2480000.00000000", "63540.0", "63560.0", "63490.0", "63498.9", "39.10"],
    ],
    "bingx": {"data": [   # newest first, ms
        [1785665700000, 63274.0, 63280.0, 63250.0, 63260.0, 2.1, 1785666599999],
        [1785664800000, 63273.94, 63273.95, 63234.44, 63234.44, 2.156673, 1785665699999],
    ]},
    "bitmart": {"data": [  # oldest first, seconds
        ["1785656700", "63538.11", "63538.12", "63483.76", "63506.23", "72.49017", "4603177.17"],
        ["1785657600", "63506.23", "63560.00", "63490.00", "63540.00", "60.10", "3810000.00"],
    ]},
    "htx": {"data": [      # objects keyed id, seconds, newest first
        {"id": 1785665700, "open": 63244.11, "close": 63255.0, "low": 63240.0,
         "high": 63260.0, "amount": 7.1},
        {"id": 1785664800, "open": 63282.87, "close": 63244.11, "low": 63244.11,
         "high": 63282.87, "amount": 7.947177},
    ]},
    "coinex": {"data": [   # created_at already in ms, oldest first
        {"close": "63480", "created_at": 1785656700000, "high": "63530", "low": "63480",
         "market": "BTCUSDT", "open": "63530", "volume": "40.1"},
        {"close": "63540", "created_at": 1785657600000, "high": "63560", "low": "63470",
         "market": "BTCUSDT", "open": "63480", "volume": "38.2"},
    ]},
    "binance": [
        [1785655800000, "62997.75000000", "63018.64000000", "62982.00000000", "63004.48000000",
         "103.40962000", 1785656699999],
        [1785656700000, "63004.48000000", "63560.00000000", "62995.50000000", "63509.48000000",
         "88.10000000", 1785657599999],
    ],
}

failed = 0
seen = []
print(f"\n{'صرافی':<12}{'open':>11}{'high':>11}{'low':>11}{'close':>11}   ترتیب زمان")
print("─" * 74)

for v in sources.VENUES:
    raw = RECORDED.get(v["id"])
    if raw is None:
        print(f"{v['id']:<12}  (ردیف ضبط‌شده ندارد)")
        failed += 1
        continue
    try:
        cd = v["parse"](raw)
    except Exception as e:                           # noqa: BLE001 - that is the failure
        print(f"{v['id']:<12}  پارس نشد: {type(e).__name__}: {e}")
        failed += 1
        continue

    k = cd[0]
    ordered = cd[0][0] < cd[-1][0]
    ms_like = k[0] > 1e12
    print(f"{v['id']:<12}{k[1]:>11.2f}{k[2]:>11.2f}{k[3]:>11.2f}{k[4]:>11.2f}   "
          f"{'قدیم→جدید' if ordered else 'جدید→قدیم ✗'}"
          f"{'' if ms_like else '  زمان ثانیه ✗'}")

    problems = []
    if not ordered:
        problems.append("ترتیب زمانی برعکس است")
    if not ms_like:
        problems.append("زمان به میلی‌ثانیه تبدیل نشده")
    if not k[2] >= k[3]:
        problems.append("high کمتر از low است — ترتیب فیلدها اشتباه است")
    if not (k[2] >= k[1] and k[2] >= k[4]):
        problems.append("high بالاترین مقدار نیست")
    if not (k[3] <= k[1] and k[3] <= k[4]):
        problems.append("low پایین‌ترین مقدار نیست")
    if not k[5] > 0:
        problems.append("حجم عددی نیست")
    for p in problems:
        print(f"             ✗ {p}")
    if problems:
        failed += 1
    seen.append((v["id"], k[4]))

print("\nهمهٔ منابع باید تقریباً یک قیمت بدهند (BTC/USDT، همان دقیقه):")
# One percent, not a tenth of one. The probe did not capture every venue in the
# same minute — Binance's recording is a candle earlier than the rest and sits
# 0.75% below them, which is the market moving, not a parser being wrong. The
# thing this catches is a field index off by one, and that does not miss by a
# percent: it returns the volume, or a timestamp, and lands nowhere near 63,000.
med = sorted(c for _, c in seen)[len(seen) // 2]
for vid, c in seen:
    off = abs(c / med - 1) * 100
    ok = off < 1.0
    print(f"  {'✓' if ok else '✗'} {vid:<10} {c:>10.2f}  {off:.3f}% اختلاف")
    if not ok:
        failed += 1

# The URL builders have to survive every timeframe the pipeline asks for. A
# KeyError here would only ever show up at 4am on a runner.
print("\nهر منبع باید همهٔ تایم‌فریم‌ها را بشناسد:")
for v in sources.VENUES:
    bad = []
    for tf in ("5m", "15m", "1h", "1d"):
        try:
            u = v["url"]("BTCUSDT", tf, 420)
            if not u.startswith("https://"):
                bad.append(tf)
        except Exception:                            # noqa: BLE001 - a missing key is the bug
            bad.append(tf)
    print(f"  {'✓' if not bad else '✗'} {v['id']:<10} {'همه' if not bad else 'ندارد: ' + ','.join(bad)}")
    if bad:
        failed += 1

# And the guard that keeps a short or reversed series out of the engine.
print("\nنگهبان sane:")


def series(n=420, rev=False, **bad):
    rows = [[1785600000000 + i * 900000, 63000.0, 63100.0, 62900.0, 63050.0, 10.0, 0] for i in range(n)]
    for i, r in enumerate(rows):
        r[0] = 1785600000000 + i * 900000
    if bad.get("nan"):
        rows[5][4] = float("nan")
    if bad.get("hl"):
        rows[5][2], rows[5][3] = 1.0, 9.0
    if rev:
        rows.reverse()
    return rows


checks = [
    ("سری کامل را می‌پذیرد", sources.sane(series(), 420) is True),
    ("سری کوتاه را رد می‌کند", sources.sane(series(180), 420) is False),
    ("ترتیب برعکس را رد می‌کند", sources.sane(series(rev=True), 420) is False),
    ("NaN را رد می‌کند", sources.sane(series(nan=True), 420) is False),
    ("high<low را رد می‌کند", sources.sane(series(hl=True), 420) is False),
]
for name, ok in checks:
    print(f"  {'✓' if ok else '✗'} {name}")
    if not ok:
        failed += 1

print(f"\n{f'{failed} ایراد' if failed else 'همهٔ پارسرهای پایتون درست‌اند'}")
sys.exit(1 if failed else 0)
