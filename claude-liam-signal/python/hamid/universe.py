"""Universe Engine (E01) — سند AuraLiam369 §5، فاز ۱.

هر روز یک Snapshot مستقل از ۲۰۰ نماد برتر ساخته می‌شود:
· رتبه بر اساس حجم معاملات (نزدیک‌ترین معیار نقدشوندگیِ در دسترس؛
  Market Cap صرافی‌محور نداریم — همین صادقانه ثبت می‌شود)
· حذف استیبل‌کوین‌ها و Wrappedهای تکراری
· ثبت venue (کدام صرافی جواب داد)
· دیف با Snapshot قبلی: لیست‌شده‌ها و حذف‌شده‌ها
· فایل یکتای روزانه brain/universe/YYYY-MM-DD.json — append-only،
  ضد survivorship bias (اعضای همان روز برای همیشه می‌مانند) و ضد تصادم
  (دو ورک‌فلو هرگز روی یک فایل نمی‌نویسند؛ اولین نویسندهٔ روز برنده است)
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
UNI_DIR = ROOT / "brain" / "universe"

STABLES = {"USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "PYUSD",
           "EUR", "EURI", "USDE", "FDUSD", "GUSD", "LUSD", "USD1", "XUSD"}
WRAPPED = {"WBTC", "WETH", "WBNB", "WSOL", "STETH", "WSTETH", "CBBTC", "CBETH",
           "RETH", "WEETH"}


def _base(sym):
    return sym[:-4] if sym.endswith("USDT") else sym


def build_snapshot(rows, venue, top=200):
    """از ردیف‌های تیکر، Snapshot امروز — خالص و تست‌پذیر."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: -float(x.get("quoteVolume") or 0)):
        s = str(r.get("symbol") or "")
        if not s.endswith("USDT"):
            continue
        b = _base(s)
        if b in STABLES or b in WRAPPED or b in seen:
            continue
        seen.add(b)
        out.append({"symbol": s, "quote_vol": round(float(r.get("quoteVolume") or 0))})
        if len(out) >= top:
            break
    return {"date": time.strftime("%Y-%m-%d", time.gmtime()),
            "generated": int(time.time() * 1000),
            "venue": venue,
            "rank_metric": "quoteVolume 24h (نه Market Cap — در دسترس نیست)",
            "n": len(out), "members": out}


def _latest_before(date):
    if not UNI_DIR.exists():
        return None
    older = sorted(p.stem for p in UNI_DIR.glob("*.json") if p.stem < date)
    if not older:
        return None
    try:
        return json.loads((UNI_DIR / f"{older[-1]}.json").read_text())
    except Exception:                                # noqa: BLE001
        return None


def daily(rows=None, venue=None, top=200):
    """Snapshot امروز را بساز اگر هنوز ساخته نشده — ایمن برای فراخوانی مکرر.

    برگشتی: (snapshot, created, diff) — diff فقط وقتی snapshot قبلی هست."""
    date = time.strftime("%Y-%m-%d", time.gmtime())
    path = UNI_DIR / f"{date}.json"
    if path.exists():                                # اولین نویسندهٔ روز برنده است
        try:
            return json.loads(path.read_text()), False, None
        except Exception:                            # noqa: BLE001
            return None, False, None
    if rows is None:
        import sources
        rows = sources.tickers()
        venue = venue or sources.used().get("tickers")
    snap = build_snapshot(rows, venue, top=top)
    prev = _latest_before(date)
    diff = None
    if prev:
        cur = {m["symbol"] for m in snap["members"]}
        old = {m["symbol"] for m in prev.get("members", [])}
        diff = {"listed": sorted(cur - old), "dropped": sorted(old - cur),
                "vs": prev.get("date")}
        snap["diff"] = diff
    UNI_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1))
    return snap, True, diff
