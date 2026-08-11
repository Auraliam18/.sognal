"""آزمون آفلاین سه اتاق جدید ایجنت: میز تمرین، پایش آلارم، مرور دوساعته.

    python3 -m hamid.test_agent_loop
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import cycle                                       # noqa: E402
from hamid import paper                                       # noqa: E402
import brain                                                  # noqa: E402
import sources                                                # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


# ── میز تمرین ──────────────────────────────────────────────────────────────
reads = [
    SimpleNamespace(symbol="AUSDT", setup=None, trend_4h="up",
                    blocks=[{"low": 1.0, "high": 1.1, "dir": "bullish"}]),
    SimpleNamespace(symbol="BUSDT", setup={"dir": "LONG"}, trend_4h="up",
                    blocks=[{"low": 1.0, "high": 1.1, "dir": "bullish"}]),
    SimpleNamespace(symbol="CUSDT", setup=None, trend_4h="down",
                    blocks=[{"low": 2.0, "high": 2.2, "dir": "bearish"}]),
    SimpleNamespace(symbol="DUSDT", setup=None, trend_4h="up", blocks=[]),
]
pc = cycle.practice_candidates(reads)
syms = [x["symbol"] for x in pc]
check("ستاپ‌دار و بی‌بلاک حذف، بقیه تمرین", syms == ["AUSDT", "CUSDT"])
check("همه برچسب practice دارند", all(x["stage_tag"] == "practice" for x in pc))
lng = pc[0]
check("لانگ: ورود سقف باکس، استاپ زیر", lng["dir"] == "LONG" and lng["entry"] == 1.1 and lng["sl"] < 1.0)
sht = pc[1]
check("شورت آینه است", sht["dir"] == "SHORT" and sht["entry"] == 2.0 and sht["sl"] > 2.2)
check("هدف‌ها ۱.۵ و ۲.۵ برابر ریسک", abs((lng["tp1"] - lng["entry"]) / (lng["entry"] - lng["sl"]) - 1.5) < 1e-9)

# ── پایش آلارم (شبکه و اتاق شبیه‌سازی‌شده) ────────────────────────────────
ROOM = {"alarms": [
    {"sym": "HITUSDT", "price": 1.0, "dir": "LONG", "stage": "ARMED", "strategy": "pump"},
    {"sym": "FARUSDT", "price": 5.0, "dir": "LONG", "stage": "ARMED"},
    {"sym": "GONEUSDT", "price": 2.0, "dir": "LONG", "stage": "ARMED"},
    {"sym": "OLDUSDT", "price": 9.0, "stage": "TRIGGERED"},
]}
SAVED = {}


def fake_room_load(room, default=None):
    return json.loads(json.dumps(ROOM)) if room == "radar" else (default or {})


def fake_room_save(room, st):
    SAVED[room] = st


def fake_klines(sym, tf, n):
    # (t,o,h,l,c,v) — HIT ورود را لمس می‌کند، FAR دور است، GONE ۸٪ زیر ورود بسته
    px = {"HITUSDT": (0.98, 1.05, 1.02), "FARUSDT": (5.5, 5.9, 5.8),
          "GONEUSDT": (1.80, 1.86, 1.84)}[sym]
    lo, hi, c = px
    return [[i, c, hi, lo, c, 100] for i in range(3)]


_orig = (brain.room_load, brain.room_save, sources.klines)
brain.room_load, brain.room_save, sources.klines = fake_room_load, fake_room_save, fake_klines
cycle.brain.room_load, cycle.brain.room_save = fake_room_load, fake_room_save
cycle.sources.klines = fake_klines
fired = cycle.watch_alarms()
brain.room_load, brain.room_save, sources.klines = _orig
cycle.brain.room_load, cycle.brain.room_save = _orig[0], _orig[1]
cycle.sources.klines = _orig[2]

check("فقط آلارم لمس‌شده فعال شد", [a["sym"] for a in fired] == ["HITUSDT"])
kept = {a["sym"]: a for a in SAVED["radar"]["alarms"]}
check("فعال‌شده TRIGGERED شد", kept["HITUSDT"]["stage"] == "TRIGGERED")
check("دور هنوز مسلح است", kept["FARUSDT"]["stage"] == "ARMED")
check("۷٪ آن‌طرف ورود → باطل با دلیل", kept["GONEUSDT"]["stage"] == "DEAD" and "از دست رفت" in kept["GONEUSDT"]["why_dead"])
check("آلارم قبلاً فعال‌شده دست نخورد", kept["OLDUSDT"]["stage"] == "TRIGGERED")

# ── مرور دوساعته ───────────────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp())
_closed_orig = paper.CLOSED
paper.CLOSED = tmp / "closed.jsonl"
now = int(time.time() * 1000)
rows = [{"sym": "XUSDT", "dir": "LONG", "R": 1.5, "outcome": "target",
         "closed": now - 1000, "why": {"stage": "second"}},
        {"sym": "YUSDT", "dir": "LONG", "R": -1.0, "outcome": "stop",
         "closed": now - 2000, "why": {"stage": "practice"}},
        {"sym": "ZUSDT", "dir": "LONG", "R": None, "outcome": "expired",
         "closed": now - 3000, "why": {"stage": "second"}}]
paper.CLOSED.write_text("\n".join(json.dumps(r) for r in rows))

RSTATE = {}
def rl2(room, default=None):
    return RSTATE.get(room, default or {})
def rs2(room, st):
    RSTATE[room] = st
cycle.brain.room_load, cycle.brain.room_save = rl2, rs2
rv = cycle.review_cycle()
check("مرور اول اجرا شد و دو دفتر را جدا شمرد",
      rv and rv["closed"] == 2 and "second" in rv["books"] and "practice" in rv["books"])
check("منقضی شمرده نشد", rv and "expired" not in str(rv["books"]))
rv2 = cycle.review_cycle()
check("قبل از ۲ ساعت دوباره مرور نمی‌کند", rv2 is None)
cycle.brain.room_load, cycle.brain.room_save = _orig[0], _orig[1]
paper.CLOSED = _closed_orig

# ── resample قفل به ساعت (اصلاح بازبینی کد) ───────────────────────────────
H=3600_000
cd1h=[{"t":i*H,"o":1,"h":2,"l":0.5,"c":1.5,"v":1} for i in range(1,302)]  # از ۰۱:۰۰
r4=cycle.resample(cd1h,4)
check("مرز ۴ساعته به ساعت جهانی قفل است", all(x["t"]%(4*H)==0 for x in r4))
check("کندل باز آخر داخل هیچ گروهی نیست", r4[-1]["t"] < cd1h[-1]["t"] - 3*H)
r4b=cycle.resample(cd1h[1:],4)  # پنجره یک کندل لغزید
check("لغزش پنجره فاز گروه‌ها را عوض نمی‌کند", r4b[0]["t"]%(4*H)==0 and r4b[-1]["t"]==r4[-1]["t"])

# ── نقشهٔ لیکوییدیشن (تخمین سبک kCEX از کندل واقعی) ────────────────────────
from hamid import liqmap                              # noqa: E402
lq_cd = [{"t": i * H, "o": 100, "h": 100.5, "l": 99.5, "c": 100.0,
          "v": 500.0 if i >= 250 else 50.0} for i in range(300)]
lm = liqmap.build(lq_cd)
check("نقشه ساخته شد و دو طرف خوشه دارد", lm and lm["above"] and lm["below"])
check("خوشه‌های بالا واقعاً بالای قیمت‌اند",
      lm and all(c["pct_away"] > 0 for c in lm["above"])
      and all(c["pct_away"] < 0 for c in lm["below"]))
check("نزدیک‌ترین خوشهٔ بالا حوالی +۱٪ است (اهرم ۱۰۰×)",
      lm and abs(lm["above"][0]["pct_away"] - 1.0) < 0.5)
check("قیمت متقارن → آهن‌ربا متعادل", lm and lm["magnet"] == "balanced")
ln = liqmap.note(lm, "LONG")
check("جملهٔ کپشن ساخته می‌شود", ln and "لیکویید" in ln)
check("دادهٔ کم → بدون ادعا", liqmap.build(lq_cd[:20]) is None)

# ── بازجویی پیش از صدور — «اول ببین چه چیزی استاپت می‌کند» ────────────────
from hamid import premortem                           # noqa: E402
from pathlib import Path as _P                        # noqa: E402
premortem.DOM = _P("/nonexistent/dominance.json")     # دامیننس واقعی در آزمون دخالت نکند

Q = 900_000
def _mk15(d_up, d_dn, n=120):
    """زیگزاگ: کندل صعودی/نزولی یک‌درمیان — سوینگ و RSI واقعی می‌سازد."""
    out, p = [], 100.0
    for i in range(n):
        d = d_up if i % 2 == 0 else d_dn
        p *= 1 + d
        out.append({"t": i * Q, "o": p / (1 + d), "h": p * 1.004,
                    "l": p * 0.996, "c": p, "v": 100.0})
    return out

up15 = _mk15(0.006, -0.005)
e = up15[-1]["c"]
good = premortem.review({"sym": "TESTUPUSDT", "dir": "LONG",
                         "entry": e, "sl": e * 0.97, "tp1": e * 1.03}, up15)
check("ستاپ سالم: دلایل تارگت بیشتر و صادر می‌شود",
      good["issue"] and len(good["pro"]) > len(good["con"]))
check("استاپ بیرون نویز جزو دلایل تارگت است",
      any("بیرون نویز" in w for w in good["pro"]))

down15 = _mk15(-0.006, 0.005)
e2 = down15[-1]["c"]
bad = premortem.review({"sym": "TESTDNUSDT", "dir": "LONG",
                        "entry": e2, "sl": e2 * 0.998, "tp1": e2 * 1.05}, down15)
check("استاپ داخل نویز + روند مخالف → صادر نمی‌شود", not bad["issue"])
check("دلیل استاپ داخل نویز صریح نوشته شده",
      any("داخل نویز" in w for w in bad["con"]))
check("حکم در یادداشت است", "صادر نشد" in bad["note"])

# ── دروازهٔ هم‌زمانی + ضدتکرار بین‌استراتژی (شکایت حمید) ──────────────────
import json as _json                                  # noqa: E402
import tempfile as _tf                                # noqa: E402
import telegram as tg                                 # noqa: E402
import sources as _sources                            # noqa: E402
from hamid import premortem as _pm2, paper as _paper2  # noqa: E402

_tmp2 = Path(_tf.mkdtemp())
tg.SENT, tg.TGLOG = _tmp2 / "sent.json", _tmp2 / "tglog.json"
_orig_env = (tg.creds, tg._post, _sources.klines, _pm2.review, _paper2.open_from)
tg.creds = lambda: ("tok", "chat")
posts = []
tg._post = lambda tok, m, f, files=None: posts.append(f.get("caption") or f.get("text", ""))
PX = {"PASSEDUSDT": 0.97, "FARUSDT": 1.06, "OKUSDT": 1.0}
_sources.klines = lambda sym, tf, n, **kw: [
    [i * 300000, 1, 1.001, 0.999, PX.get(sym, 1.0), 1.0] for i in range(n)]
_pm2.review = lambda s, c15: {"pro": ["x"], "con": [], "issue": True,
                              "note": "⚖️", "price": 1.0}
_paper2.open_from = lambda *a, **k: 0


def _sig(sym, strat="ibs"):
    return {"sym": sym, "tf": "15m", "dir": "LONG", "entry": 1.0, "sl": 0.99,
            "tp1": 1.02, "tp2": 1.03, "rr": 2.0,
            "strategy": strat, "strategyName": strat}


n_ok = tg.send_signals([_sig("PASSEDUSDT"), _sig("FARUSDT"), _sig("OKUSDT")],
                       lambda s, p: None)
check("ردشده از ورود و دورافتاده صادر نشدند، هم‌زمانِ سالم رفت",
      n_ok == 1 and len(posts) == 1 and "OKUSDT" in posts[0])
check("قیمت لحظهٔ ارسال و فاصله در پیام است",
      "⏱" in posts[0] and "فاصله تا ورود" in posts[0])
n2 = tg.send_signals([_sig("OKUSDT", strat="alarm")], lambda s, p: None)
check("همان ستاپ با برچسب استراتژی دیگر دوباره نمی‌رود", n2 == 0)
# تنوع: بعد از ۲ ارسال برای یک ارز، سومی (حتی جهت/تایم دیگر) نمی‌رود
sent_now = _json.loads(tg.SENT.read_text())
sent_now["any|OKUSDT|5m|SHORT"] = sent_now["any|OKUSDT|15m|LONG"]
tg.SENT.write_text(_json.dumps(sent_now))
s3 = _sig("OKUSDT")
s3["tf"], s3["dir"], s3["entry"], s3["sl"] = "1h", "SHORT", 1.0, 1.01
n3 = tg.send_signals([s3], lambda s, p: None)
check("سقف ۲ ارسال به ازای هر ارز در ۱۲ ساعت", n3 == 0)
tg.creds, tg._post, _sources.klines, _pm2.review, _paper2.open_from = _orig_env

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های حلقهٔ ایجنت گذشتند")
