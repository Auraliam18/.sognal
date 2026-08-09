#!/usr/bin/env python3
"""رادار پامپ خوشه‌ای — همان تحلیلی که برای BICO دستی انجام شد، به شکل ایجنت.

    python3 -m hamid.pump_radar                # اجرای کامل
    python3 -m hamid.pump_radar --no-telegram  # بدون ارسال
    python3 -m hamid.pump_radar --reapply DIR  # فقط بازنشانی خروجی بعد از reset گیت

روال، دقیقاً به ترتیبی که حمید خواست:

۱. تاپ گینرزهای بیتیونیکس خوانده می‌شود (اگر بیتیونیکس جواب ندهد، از تیکر
   MEXC با محاسبهٔ صریح «آخرین/باز» — و منبع در گزارش نوشته می‌شود).
۲. برای هر گینر: پامپ‌های گذشتهٔ خودش (بازده ۴ساعته + جهش حجم)، و ارزهایی
   که یک روز قبل/بعد از آن پامپ‌ها حرکت کرده‌اند.
۳. نقش خوشه‌ای: «سردسته» است یا خودش «دنباله‌رو»ی پامپ ارز دیگری؟ ملاک:
   اگر ارزی به‌طور میانگین در ۲۴ ساعتِ قبل از پامپ‌هایش جهش بزرگ‌تری داشته
   تا آنچه بعدش در بقیه دیده می‌شود، این ارز دنباله‌رو است.
۴. شبیه‌ترین پامپ قبلی به وضعیت الان: همبستگی چارتِ ۴۸ کندل اخیر با پنجرهٔ
   قبل از هر پامپ تاریخی، و اینکه بعد از آن پامپ چه شد.
۵. لایهٔ دوم: دنباله‌روهای هر گینر هم همین‌طور تحلیل می‌شوند (پامپ‌های
   خودشان + نقطهٔ ورود)، و لایهٔ سوم: دنباله‌روهایِ دنباله‌روها، که گذشتهٔ
   آن‌ها هم چک می‌شود — یک قدم جلوتر از بازار.
۶. نقطهٔ ورود هر ارز: تازه‌ترین اردر بلاک خریدِ مصرف‌نشده روی ۱۵ دقیقه
   (سقف باکس = ورود، استاپ زیر باکس) — همان قاعدهٔ تحلیل‌گر پامپ.
۷. پیشنهاد نهایی با دلایل شفاف امتیازدهی می‌شود، آلارمش در اتاق رادار ثبت
   و اگر توکن تلگرام باشد با سرتیتر «گزینه‌های پامپ» فرستاده می‌شود.

هر عدد از کندل واقعی صرافی است. تعداد رخداد پامپ همیشه کم است، پس نتیجهٔ
خوشه‌ای «مشاهده» گزارش می‌شود، نه قانون — همان قاعده‌ای که جلوی نتیجه‌گیری
از تاپه دوستانه را گرفت.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                                # noqa: E402
from hamid.analyze_pump import cds, pumps, rsi                # noqa: E402
from hamid.structure import atr, channel, trend               # noqa: E402
from hamid import orderblock                                  # noqa: E402

ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "pump-radar.json"
SENT = ROOT / "brain" / "pump-radar-sent.json"
SENT_TTL_MS = 6 * 3600 * 1000        # همان نتیجه دوباره فرستاده نمی‌شود
BITUNIX_TICKERS = "https://fapi.bitunix.com/api/v1/futures/market/tickers"


# ── تاپ گینرز ──────────────────────────────────────────────────────────────

def _parse_bitunix(rows):
    """شکل مشاهده‌شده در پنل: اشیاء با symbol/lastPrice/priceChangePercent یا
    change (کسر). نام فیلدهای حجم برعکس محتوایشان است — quoteVol مقدار پایه
    را دارد؛ برای رتبه‌بندی گینرها فقط بزرگی نسبی مهم است."""
    out = []
    for t in rows or []:
        s = str(t.get("symbol") or "")
        if not s.endswith("USDT"):
            continue
        try:
            chg = t.get("priceChangePercent")
            chg = float(chg) if chg not in (None, "") else float(t.get("change") or 0) * 100
            last = float(t.get("lastPrice") or t.get("last") or t.get("markPrice") or 0)
            vol = float(t.get("quoteVol") or t.get("baseVol") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or abs(chg) > 500:              # عدد بی‌معنا = ردیف خراب
            continue
        out.append({"symbol": s, "change_pct": round(chg, 1), "last": last, "vol": vol})
    return out


def gainers(top=6, min_pct=5.0):
    """(نام منبع، لیست گینرها) — بیتیونیکس اول، چون حمید همان‌جا معامله می‌کند."""
    try:
        rows = sources._rows(sources._json(BITUNIX_TICKERS))
        g = _parse_bitunix(rows)
        if len(g) >= 20:
            g.sort(key=lambda x: -x["change_pct"])
            return "بیتیونیکس (فیوچرز)", [x for x in g if x["change_pct"] >= min_pct][:top]
    except Exception as e:                           # noqa: BLE001 - صرافی بعدی
        print(f"بیتیونیکس جواب نداد: {type(e).__name__}")
    r = sources._json("https://api.mexc.com/api/v3/ticker/24hr")
    out = []
    for t in r:
        s = t.get("symbol", "")
        if not s.endswith("USDT"):
            continue
        try:
            last, op = float(t.get("lastPrice") or 0), float(t.get("openPrice") or 0)
            vol = float(t.get("quoteVolume") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or op <= 0 or vol < 100_000:    # کتاب کم‌عمق، گینر واقعی نیست
            continue
        out.append({"symbol": s, "change_pct": round((last / op - 1) * 100, 1),
                    "last": last, "vol": vol})
    out.sort(key=lambda x: -x["change_pct"])
    return "MEXC (جایگزین — بیتیونیکس در دسترس نبود)", \
        [x for x in out if x["change_pct"] >= min_pct][:top]


# ── ابزار تحلیل ────────────────────────────────────────────────────────────

def _corr(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5


def best_match(cd1h, eps, window=48):
    """شبیه‌ترین «قبل از پامپ» تاریخی به چارت الان، و اینکه بعد از آن پامپ چه شد."""
    if len(cd1h) < window + 2 or not eps:
        return None
    now = [c["c"] for c in cd1h[-window:]]
    best = None
    for e in eps:
        i = e["i"]
        if i - 4 - window < 0:
            continue
        seg = [c["c"] for c in cd1h[i - 4 - window:i - 4]]
        c = _corr(now, seg)
        nxt = cd1h[min(i + 24, len(cd1h) - 1)]["c"] / cd1h[i]["c"] - 1
        cand = {"pump_t": e["t"], "corr_pct": round(c * 100),
                "then_24h_pct": round(nxt * 100, 1)}
        if best is None or cand["corr_pct"] > best["corr_pct"]:
            best = cand
    return best


def role_of(rel, gate=8.0):
    """سردسته یا دنباله‌رو؟ leaders = ارزهایی که قبلش حرکت کرده‌اند،
    followers = ارزهایی که بعدش. نقش از مقایسهٔ بزرگ‌ترینِ این دو درمی‌آید."""
    leaders = sorted([{"symbol": s, **v} for s, v in rel.items()
                      if v["pre_24h_pct"] >= gate and v["n"] >= 2],
                     key=lambda x: -x["pre_24h_pct"])
    followers = sorted([{"symbol": s, **v} for s, v in rel.items()
                        if v["post_24h_pct"] >= gate * 0.75 and v["n"] >= 2],
                       key=lambda x: -x["post_24h_pct"])
    biggest_pre = leaders[0]["pre_24h_pct"] if leaders else 0
    biggest_post = followers[0]["post_24h_pct"] if followers else 0
    role = "دنباله‌رو" if leaders and biggest_pre > biggest_post else "سردسته"
    return role, leaders[:5], followers[:5]


class Kcache:
    """هر نماد یک بار از شبکه؛ تحلیل خوشه‌ای بدون این، صدها فچ تکراری می‌شود."""

    def __init__(self):
        self.d = {}

    def get(self, sym, tf, n):
        k = (sym, tf)
        if k not in self.d:
            try:
                self.d[k] = cds(sym, tf, n)
            except Exception:                        # noqa: BLE001 - نماد بی‌داده
                self.d[k] = []
        return self.d[k]


def related_cached(sym, eps, cd1h, universe, kc, window=24):
    out = {}
    for other in universe:
        if other == sym:
            continue
        oc = kc.get(other, "1h", len(cd1h) + 10)
        if not oc:
            continue
        idx = {c["t"]: k for k, c in enumerate(oc)}
        pre, post = [], []
        for e in eps:
            k = idx.get(cd1h[e["i"]]["t"])
            if k is None or k < window or k + window >= len(oc):
                continue
            pre.append(oc[k]["c"] / oc[k - window]["c"] - 1)
            post.append(oc[k + window]["c"] / oc[k]["c"] - 1)
        if pre:
            out[other] = {"n": len(pre),
                          "pre_24h_pct": round(sum(pre) / len(pre) * 100, 1),
                          "post_24h_pct": round(sum(post) / len(post) * 100, 1)}
    return out


def entry_point(c15):
    """همان قاعدهٔ تحلیل‌گر پامپ: تازه‌ترین اردر بلاک خرید مصرف‌نشده ≤۶۰ کندل."""
    if len(c15) < 60:
        return None
    obs = [b for b in orderblock.find(c15, "bullish")
           if not b.consumed and len(c15) - 1 - b.i < 60]
    if not obs:
        return None
    b = sorted(obs, key=lambda x: -x.i)[0]
    a15 = atr(c15) or 0
    return {"entry": round(b.high, 10), "sl": round(b.low - 0.3 * a15, 10)}


def analyze_one(sym, kc, universe, with_related=True):
    c1h = kc.get(sym, "1h", 1000)
    if len(c1h) < 80:
        return None
    c15 = kc.get(sym, "15m", 400)
    eps = pumps(c1h)
    rel = related_cached(sym, eps, c1h, universe, kc) if (with_related and eps) else {}
    role, leaders, followers = role_of(rel) if rel else ("نامشخص", [], [])
    ch1 = channel(c1h)
    block = {
        "symbol": sym, "price": c1h[-1]["c"],
        "pumps": eps,
        "pump_note": (f"{len(eps)} پامپ در {len(c1h)//24} روز؛ بزرگ‌ترین "
                      f"+{max((e['ret_4h_pct'] for e in eps), default=0)}٪"
                      if eps else "در تاریخچهٔ در دسترس، پامپی با این آستانه ندارد"),
        "role": role, "leaders": leaders, "followers": followers,
        "match": best_match(c1h, eps),
        "now": {"trend_4h": None, "trend_1h": trend(c1h),
                "rsi_1h": rsi(c1h), "rsi_15m": rsi(c15) if c15 else None,
                "channel_pos_1h": round(ch1.position, 2) if ch1 else None},
        "alarm": entry_point(c15) if c15 else None,
    }
    from hamid.cycle import resample
    c4h = resample(c1h, 4)
    block["now"]["trend_4h"] = trend(c4h)
    return block


# ── پیشنهاد ────────────────────────────────────────────────────────────────

def recommend(blocks):
    """امتیازِ هر ارزِ دارای نقطهٔ ورود، با دلیلِ نوشته‌شده برای تک‌تک امتیازها —
    پیشنهادی که دلیلش را نگوید قابل حذف‌کردنِ هوش مصنوعی ضعیف نیست."""
    scored = []
    for b in blocks:
        al = b.get("alarm")
        if not al or not al.get("entry"):
            continue
        s, why = 0, []
        if b["role"] == "دنباله‌رو" and b.get("leaders"):
            s += 2
            why.append(f"دنباله‌روی خوشه است — سردسته‌اش ({b['leaders'][0]['symbol']}) "
                       f"قبل از پامپ‌هایش به‌طور میانگین {b['leaders'][0]['pre_24h_pct']:+}٪ حرکت کرده")
        if len(b.get("pumps") or []) >= 3:
            s += 2
            why.append(f"تکرارکنندهٔ پامپ است ({len(b['pumps'])} بار در تاریخچه)")
        m = b.get("match")
        if m and m["corr_pct"] >= 70:
            if m["then_24h_pct"] > 0:
                s += 2
            why.append(f"چارت الان {m['corr_pct']}٪ شبیه قبل از پامپ قبلی است "
                       f"(آن بار ۲۴ ساعت بعدش {m['then_24h_pct']:+}٪ شد)")
        r1 = b["now"].get("rsi_1h")
        if r1 is not None:
            if r1 < 65:
                s += 1
                why.append(f"RSI یک‌ساعته {r1} — هنوز اشباع نشده")
            elif r1 >= 75:
                s -= 2
                why.append(f"RSI یک‌ساعته {r1} — اشباع خرید؛ دنبالش دویدن همان‌جایی است که استاپ می‌خورد")
        dist = abs(b["price"] - al["entry"]) / al["entry"] * 100
        if dist <= 3:
            s += 2
            why.append(f"قیمت فقط {dist:.1f}٪ با نقطهٔ ورود فاصله دارد")
        elif dist > 15:
            s -= 1
            why.append(f"نقطهٔ ورود {dist:.1f}٪ دورتر است — فقط با صبر و آلارم")
        risk = abs(al["entry"] - al["sl"]) / al["entry"] * 100
        scored.append({"symbol": b["symbol"], "score": s, "reasons": why,
                       "entry": al["entry"], "sl": al["sl"],
                       "dist_pct": round(dist, 1), "risk_pct": round(risk, 1),
                       "price": b["price"]})
    scored.sort(key=lambda x: -x["score"])
    return scored


# ── ثبت آلارم و تلگرام ─────────────────────────────────────────────────────

def merge_alarms(picks):
    """آلارم پیشنهادها در اتاق رادار — idempotent: برای هر نماد فقط یک آلارم
    pump-radar نگه داشته می‌شود تا اجرای هر نیم‌ساعت، لیست را پر نکند."""
    if not picks:
        return
    import brain
    st = brain.room_load("radar", {}) or {}
    al = [a for a in (st.get("alarms") or [])
          if not (a.get("strategy") == "pump-radar"
                  and a.get("sym") in {p["symbol"] for p in picks})]
    for p in reversed(picks):
        al.insert(0, {"sym": p["symbol"], "tf": "15m", "dir": "LONG",
                      "strategy": "pump-radar", "strategyName": "پامپ رادار خوشه‌ای",
                      "price": p["entry"], "now": p["price"],
                      "distancePct": p["dist_pct"],
                      "why": "؛ ".join(p["reasons"][:2]),
                      "stage": "ARMED"})
    brain.room_save("radar", {**st, "alarms": al[:80]})


def _load_sent():
    try:
        d = json.loads(SENT.read_text())
        now = time.time() * 1000
        return {k: v for k, v in d.items() if now - v < SENT_TTL_MS}
    except Exception:                                # noqa: BLE001
        return {}


def tg_message(source, picks, blocks):
    import telegram as tg
    L = [f"🏷 <b>{tg.PANEL_NAME}</b>",
         "🚀 <b>گزینه‌های پامپ — رادار خوشه‌ای</b>",
         f"<i>منبع تاپ گینرز: {source}</i>", ""]
    for rank, p in enumerate(picks, 1):
        head = "انتخاب اول" if rank == 1 else "جایگزین"
        L.append(f"<b>{head}: {p['symbol']}</b>  (امتیاز {p['score']})")
        L += [f"• {w}" for w in p["reasons"]]
        L.append(f"ورود <code>{p['entry']:.10g}</code> · استاپ <code>{p['sl']:.10g}</code>"
                 f" · ریسک {p['risk_pct']}٪ · فاصله {p['dist_pct']}٪")
        L.append("")
    others = [b["symbol"] for b in blocks
              if b["symbol"] not in {p["symbol"] for p in picks}][:6]
    if others:
        L.append("زیر نظر: " + "، ".join(others))
    L.append("<i>آلارم روی نقطهٔ ورود ثبت شد — با رسیدن قیمت، بازبینی و سیگنال. "
             "نمونهٔ پامپ کم است؛ این مشاهده است، نه قانون.</i>")
    return "\n".join(L)


def send_telegram(source, picks, blocks):
    import telegram as tg
    token, chat = tg.creds()
    if not token:
        print("تلگرام: توکن نیست — چیزی فرستاده نشد (پیام در پنل ثبت است)")
        return False
    sent = _load_sent()
    key = "|".join(f"{p['symbol']}@{p['entry']:.6g}" for p in picks)
    if key in sent:
        print("تلگرام: همین نتیجه قبلاً رفته — تکرار نمی‌کنیم")
        return False
    try:
        tg._post(token, "sendMessage",
                 {"chat_id": chat, "text": tg_message(source, picks, blocks),
                  "parse_mode": "HTML", "disable_web_page_preview": "true"})
    except Exception as e:                           # noqa: BLE001
        print(f"تلگرام نفرستاد: {tg.scrub(e)}")
        return False
    sent[key] = time.time() * 1000
    SENT.parent.mkdir(exist_ok=True)
    SENT.write_text(json.dumps(sent, indent=1))
    for p in picks:
        tg._log_final({"sym": p["symbol"], "dir": "LONG", "tf": "15m",
                       "entry": p["entry"], "sl": p["sl"], "tp1": None,
                       "strategyName": "پامپ رادار خوشه‌ای"})
    print(f"تلگرام: گزینه‌های پامپ ({len(picks)} انتخاب) فرستاده شد")
    return True


# ── بازنشانی بعد از git reset (ورک‌فلو) ────────────────────────────────────

def reapply(backup_dir):
    """ورک‌فلو قبل از هر تلاشِ پوش، شاخه را به origin/main برمی‌گرداند تا با
    نوشته‌های همزمانِ چرخه تصادم نکند — همان تصادمی که یک بار نتیجهٔ TUT را
    انداخت. این تابع خروجی‌های ما را روی وضعیت تازه دوباره می‌نشاند:
    فایل‌های خودمان کپی، لاگ تلگرام اجتماع دو نسخه، آلارم‌ها merge."""
    bk = Path(backup_dir)
    for name in ("pump-radar.json",):
        src = bk / name
        if src.exists():
            OUT.parent.mkdir(exist_ok=True)
            shutil.copy(src, OUT)
    if (bk / "pump-radar-sent.json").exists():
        SENT.parent.mkdir(exist_ok=True)
        shutil.copy(bk / "pump-radar-sent.json", SENT)
    tglog_bk = bk / "telegram-log.json"
    tglog = ROOT / "signals" / "telegram-log.json"
    if tglog_bk.exists():
        try:
            ours = json.loads(tglog_bk.read_text()).get("sent", [])
            theirs = json.loads(tglog.read_text()).get("sent", []) if tglog.exists() else []
            seen, union = set(), []
            for e in sorted(ours + theirs, key=lambda x: -(x.get("at") or 0)):
                k = (e.get("at"), e.get("sym"))
                if k not in seen:
                    seen.add(k)
                    union.append(e)
            tglog.write_text(json.dumps({"generated": int(time.time() * 1000),
                                         "sent": union[:40]}, ensure_ascii=False, indent=1))
        except Exception as e:                       # noqa: BLE001
            print(f"اجتماع لاگ تلگرام نشد: {type(e).__name__}")
    try:
        picks = (json.loads(OUT.read_text()).get("recommendation") or [])[:2]
        merge_alarms(picks)
    except Exception as e:                           # noqa: BLE001
        print(f"ثبت آلارم رادار نشد: {type(e).__name__}")


# ── اجرای کامل ─────────────────────────────────────────────────────────────

def run(top=6, min_pct=5.0, deep_n=4, no_telegram=False):
    t0 = time.time()
    source, gs = gainers(top=top, min_pct=min_pct)
    print(f"تاپ گینرز از {source}: " +
          (", ".join(f"{g['symbol']} {g['change_pct']:+}%" for g in gs) or "هیچ"))

    try:
        uni = [s["symbol"] for s in
               sorted(sources.tickers(), key=lambda x: -float(x["quoteVolume"] or 0))
               if s["symbol"].endswith("USDT")][:30]
    except Exception:                                # noqa: BLE001
        uni = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    kc = Kcache()
    blocks, seen = [], set()

    def add(sym, layer, via=None, with_related=True):
        if sym in seen:
            return None
        seen.add(sym)
        b = analyze_one(sym, kc, uni, with_related=with_related)
        if b:
            b["layer"] = layer
            if via:
                b["via"] = via
            blocks.append(b)
            print(f"  لایه {layer} · {sym}: نقش {b['role']} · {b['pump_note']}")
        return b

    for g in gs[:deep_n]:
        b = add(g["symbol"], 1)
        if not b:
            continue
        b["change_24h_pct"] = g["change_pct"]
        # لایهٔ دوم: دنباله‌روهای این گینر — و لایهٔ سوم: دنباله‌روهای آن‌ها
        for f in (b.get("followers") or [])[:3]:
            b2 = add(f["symbol"], 2, via=g["symbol"])
            if not b2:
                continue
            for f3 in (b2.get("followers") or [])[:2]:
                add(f3["symbol"], 3, via=f["symbol"], with_related=False)

    picks = recommend(blocks)[:2]
    picks = [p for p in picks if p["score"] >= 2]

    report = {
        "generated": int(time.time() * 1000),
        "source": source,
        "gainers": gs,
        "universe_n": len(uni),
        "coins": blocks,
        "recommendation": picks,
        "note": ("رخدادهای پامپ کم‌اند؛ روابط خوشه‌ای مشاهده‌اند، نه قانون. "
                 "پیشنهاد یعنی آلارم و بازبینی در لحظهٔ رسیدن قیمت — نه ورود کور."),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"خروجی: {OUT.relative_to(ROOT)} · {len(blocks)} ارز در ۳ لایه")

    try:
        merge_alarms(picks)
    except Exception as e:                           # noqa: BLE001
        print(f"ثبت آلارم رادار نشد: {type(e).__name__}")

    if picks and not no_telegram:
        send_telegram(source, picks, blocks)
    elif not picks:
        print("هیچ گزینه‌ای به آستانهٔ امتیاز نرسید — نفرستادن بهتر از پیشنهاد ضعیف است")
    print(f"تمام شد در {time.time() - t0:.0f} ثانیه")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--min-pct", type=float, default=5.0)
    ap.add_argument("--deep", type=int, default=4)
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--reapply", metavar="DIR",
                    help="فقط بازنشانی خروجی‌های بکاپ‌شده روی درخت تازه")
    a = ap.parse_args()
    if a.reapply:
        reapply(a.reapply)
        return
    run(top=a.top, min_pct=a.min_pct, deep_n=a.deep, no_telegram=a.no_telegram)


if __name__ == "__main__":
    main()
