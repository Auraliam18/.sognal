"""دو انجین کشف — خواستهٔ حمید، با صداقت دربارهٔ منبع:

۱. «ارزهای تازه لانچ‌شده»: راه قابل‌اتکای بدون لاگین، دیفِ لیست خود
   صرافی‌هاست — نمادی که امروز در تیکر هست و دیروز نبود، همان لحظهٔ
   لیست‌شدن دیده می‌شود. اینستاگرام/فیس‌بوک بدون اکانت و API قابل
   خواندنِ ماشینی نیستند و ادعایش دروغ می‌شد؛ سر و صدای شبکه‌ای از
   مسیر جستجوی وب (اتاق اطلاعات) پوشش داده می‌شود.

۲. «دسته‌بندی خبرها»: تیترهای داغِ اتاق اطلاعات به دسته‌های معنادار
   تقسیم و به اتاق مقصد مسیردهی می‌شوند — لیست‌شدن/هک/قانون‌گذاری/
   نهنگ‌ها/کلان‌اقتصاد — تا اتاق آمار و اتاق یادگیری خوراک ساخت‌یافته
   بگیرند، نه متن خام.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
KNOWN = ROOT / "brain" / "known-symbols.json"

NEWS_BUCKETS = [
    ("لیست‌شدن/لانچ", ("list", "launch", "debut", "airdrop", "ieo", "ido", "mainnet")),
    ("هک/امنیت", ("hack", "exploit", "stolen", "breach", "drain", "rug")),
    ("قانون‌گذاری", ("sec", "etf", "regulat", "lawsuit", "ban", "court", "license")),
    ("نهنگ/جریان پول", ("whale", "outflow", "inflow", "transfer", "liquidat", "treasury")),
    ("کلان/فدرال", ("fed", "rate", "cpi", "inflation", "fomc", "treasur", "dollar")),
]


def classify_news(hot):
    """تیترهای داغ → دسته + اتاق مقصد. بدون دسته = «عمومی» و مسیر نمی‌گیرد."""
    out = []
    for it in hot or []:
        t = (it.get("title") or "").lower()
        cat, room = "عمومی", None
        for name, keys in NEWS_BUCKETS:
            if any(k in t for k in keys):
                cat = name
                room = "learn" if name in ("لیست‌شدن/لانچ", "نهنگ/جریان پول") else "intel"
                break
        out.append({"title": it.get("title"), "cat": cat, "room": room,
                    "url": it.get("url") or it.get("link")})
    return out


def new_listings(tickers, keep=400):
    """دیفِ نمادها با حافظهٔ دیروز — نماد تازه = لانچ/لیست تازه در صرافی.
    اولین اجرا فقط حافظه می‌سازد و ادعای «تازه» نمی‌کند (وگرنه ۴۰۰ نماد
    قدیمی را کشف تازه جا می‌زدیم)."""
    syms = sorted({t.get("symbol") for t in tickers or []
                   if t.get("symbol") and t["symbol"].endswith("USDT")})[:2000]
    try:
        prev = json.loads(KNOWN.read_text())
    except Exception:                                # noqa: BLE001
        prev = None
    KNOWN.parent.mkdir(parents=True, exist_ok=True)
    KNOWN.write_text(json.dumps({"at": int(time.time() * 1000), "symbols": syms}))
    if not prev or not prev.get("symbols"):
        return {"first_run": True, "new": []}
    fresh = [s for s in syms if s not in set(prev["symbols"])]
    return {"first_run": False, "new": fresh[:12]}
