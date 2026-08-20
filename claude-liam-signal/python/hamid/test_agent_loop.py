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
from hamid import memory as _memguard                         # noqa: E402
import brain                                                  # noqa: E402
import sources                                                # noqa: E402

# ── حافظهٔ دائمی، از همان خط اول، برای کل فایل ─────────────────────────────
#
# ۱۶ اوت: این فایل یک درس واقعی («نرخ وتو بالا») را داخل
# brain/memory/lessons.json تولید نوشت. مسیرش این بود: یک بلوک وسط فایل
# `tg.creds` را استاب می‌کرد و بعد **برمی‌گرداند**؛ از آن‌جا به بعد
# `mirror_review` با توکن واقعیِ محیط جلو می‌رفت، شاخهٔ «وتو زیاد است» را
# می‌گرفت و `memory.remember` را صدا می‌زد. در CI توکن همیشه هست، پس این
# در هر اجرای CI اتفاق می‌افتاد.
#
# ایزوله‌کردنِ بلوک‌به‌بلوک همین را ساخت: هر بلوکِ تازه‌ای که کسی اضافه کند
# دوباره در معرض همان است. پس مسیر نوشتنِ حافظه از **اول فایل** منحرف
# می‌شود و هرگز برنمی‌گردد — حمید صریح گفت «حافظه دایمی تحت هیچ شرایطی
# آسیب نبیند»، و «تحت هیچ شرایطی» یعنی حتی وقتی کسی یادش رفت.
_MEM_TMP = Path(tempfile.mkdtemp(prefix="agentloop-mem-"))
_memguard.LESSONS = _MEM_TMP / "lessons.json"
_memguard.HISTORY = _MEM_TMP / "history-stats.json"
# دفترهای تولیدیِ گلوگاه ارسال هم منحرف می‌شوند — نگهبان پایین همین فایل
# اولین نسخهٔ execution_gate را در حال نوشتن exec-outbox واقعی گرفت؛
# viability-gate هم همان کلاس است (paper.open_from می‌نویسدش).
from hamid import execution_gate as _egguard          # noqa: E402
from hamid import paper as _pguard                    # noqa: E402
_egguard.OUTBOX = _MEM_TMP / "exec-outbox.json"
from hamid import rule_gate as _rgguard               # noqa: E402
_rgguard.LOG = _MEM_TMP / "rule-gate-log.json"        # لاگ دروازهٔ قانون، تولید است
_pguard._append_gatelog = lambda *a, **k: None        # لاگ دروازهٔ دوام، تولید است

# عکس اولیه، برای نگهبان پایانی — تفاوت سنجیده می‌شود نه پاکیِ مطلق
import subprocess as _spg                                     # noqa: E402

_REPO = Path(__file__).resolve().parents[3]


def _prod_status():
    return _spg.run(["git", "status", "--porcelain", "--", "brain/", "signals/"],
                    cwd=_REPO, capture_output=True, text=True).stdout


_PROD_BEFORE = _prod_status()

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
def _fake_post(tok, m, f, files=None):
    posts.append(f.get("caption") or f.get("text", ""))
    return {"ok": True, "result": {"message_id": 777}}
tg._post = _fake_post
_opened = []

PX = {"PASSEDUSDT": 0.97, "FARUSDT": 1.06, "OKUSDT": 1.0}
_sources.klines = lambda sym, tf, n, **kw: [
    [i * 300000, 1, 1.001, 0.999, PX.get(sym, 1.0), 1.0] for i in range(n)]
_pm2.review = lambda s, c15: {"pro": ["x"], "con": [], "issue": True,
                              "note": "⚖️", "price": 1.0}
_paper2.open_from = lambda setups, ctx: _opened.extend(setups) or 0


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
check("شناسهٔ پیام برای ریپلای نتیجه ثبت شد (درس TAO)",
      _opened and _opened[0].get("tg_msg_id") == 777)
_led = _json.loads(tg.SENT.read_text())
check("ردشده‌ها سهمیه نمی‌خورند (کلید skip جدا)",
      len([k for k in _led if not k.startswith(("any|", "skip|"))]) == 1
      and len([k for k in _led if k.startswith("skip|")]) == 2)
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

# ── Universe Snapshot (AuraLiam369 §5 — فاز ۱) ────────────────────────────
from hamid import universe as _u                      # noqa: E402
_u.UNI_DIR = _tmp2 / "universe"
_rows = ([{"symbol": f"C{i}USDT", "quoteVolume": str(1000000 - i)} for i in range(230)]
         + [{"symbol": "USDCUSDT", "quoteVolume": "99999999"},
            {"symbol": "WBTCUSDT", "quoteVolume": "88888888"},
            {"symbol": "BTCETH", "quoteVolume": "77777777"}])
snap, created, diff = _u.daily(rows=_rows, venue="تست")
check("Universe ساخته شد: ۲۰۰تایی، بدون استیبل/رپد/غیرUSDT",
      created and snap["n"] == 200
      and all(m["symbol"] not in ("USDCUSDT", "WBTCUSDT", "BTCETH")
              for m in snap["members"]))
check("رتبه بر اساس حجم و متریک صادقانه ثبت شده",
      snap["members"][0]["symbol"] == "C0USDT" and "Market Cap" in snap["rank_metric"])
snap2, created2, _ = _u.daily(rows=[], venue="x")
check("فراخوانی دوم همان روز: فایل یکتا بازنویسی نمی‌شود",
      not created2 and snap2["n"] == 200)
# دیف با روز قبل — فایل دیروز را دستی می‌سازیم
import time as _t2                                    # noqa: E402
_y = _t2.strftime("%Y-%m-%d", _t2.gmtime(_t2.time() - 86400))
(_u.UNI_DIR / f"{_y}.json").write_text(_json.dumps(
    {"date": _y, "members": [{"symbol": "C1USDT"}, {"symbol": "GONEUSDT"}]}))
(_u.UNI_DIR / f"{_t2.strftime('%Y-%m-%d', _t2.gmtime())}.json").unlink()
snap3, _, diff3 = _u.daily(rows=_rows, venue="تست")
check("دیف لیست/دی‌لیست با Snapshot قبلی",
      diff3 and "GONEUSDT" in diff3["dropped"] and "C0USDT" in diff3["listed"])

# ── قانون‌های تأییدشدهٔ تاریخی در بازجویی (دستور حمید ۱۲ اوت) ─────────────
# دفتر شبانه قانونی با CI ردشده از صفر دارد → باید در حکم صدور بنشیند،
# با وزن ۲ و علامت دلتا. INSUFFICIENT یا CI دربرگیرندهٔ صفر → هیچ اثری.
import scan as _scan                                   # noqa: E402
_scan.ROOT = _tmp2                                     # دفتر واقعی دخالت نکند
(_tmp2 / "brain" / "backtests").mkdir(parents=True, exist_ok=True)
(_tmp2 / "brain" / "backtests" / "latest.json").write_text(_json.dumps({
    "reasons": {"ibs": [
        {"condition": "داخل اردر بلاک", "delta": 0.2, "n": 734, "ci": [0.076, 0.338]},
        {"condition": "R:R بالای ۲.۵", "delta": -0.3, "n": 300, "ci": [-0.5, -0.1]},
        {"condition": "CHOCH دارد", "delta": 0.4, "n": 50, "ci": [-0.1, 0.9]},
    ]}}))
premortem.DOM = _tmp2 / "no-dom.json"
_e3 = up15[-1]["c"]
_sig3 = {"sym": "RULEUSDT", "dir": "LONG", "strategy": "ibs",
         "entry": _e3, "sl": _e3 * 0.97, "tp1": _e3 * 1.03,
         "ob": {"low": _e3 * 0.99, "high": _e3 * 1.01}, "rr": 3.0}
_rv = premortem.review(dict(_sig3), up15)
check("قانون مثبت CI-ردشده (داخل OB) → دلیل تارگت با وزن ۲",
      any("داخل اردر بلاک" in x for x in _rv["pro"]))
check("قانون منفی CI-ردشده (RR>2.5) → دلیل استاپ",
      any("R:R بالای ۲.۵" in x for x in _rv["con"]))
check("قانون با CI دربرگیرندهٔ صفر اصلاً ظاهر نمی‌شود",
      not any("CHOCH" in x for x in _rv["pro"] + _rv["con"]))
_sig4 = dict(_sig3, sym="NOOBUSDT", ob={"low": _e3 * 1.05, "high": _e3 * 1.06})
_rv4 = premortem.review(_sig4, up15)
check("ورودِ بیرون OB قانون OB را نمی‌گیرد",
      not any("داخل اردر بلاک" in x for x in _rv4["pro"]))
check("وزن ۲ واقعاً در امتیاز نشسته", _rv["pro_w"] >= _rv4["pro_w"] + 2)

# ── اعلام نتیجه فقط برای سیگنالِ ارسالی (شکایت حمید ۱۲ اوت) ────────────────
# معاملهٔ دفتر داخلی (بدون tg_msg_id) نباید هیچ پیام تلگرامی بگیرد؛
# معاملهٔ ارسالی باید ریپلای روی پیام خودش بگیرد.
from hamid import cycle as _cy, paper as _pp                   # noqa: E402
import time as _tm                                             # noqa: E402
_d3 = Path(_tf.mkdtemp())
_old_pp = (_pp.CLOSED, _pp.OPEN, _pp.EQUITY, _pp.mark)
_pp.CLOSED, _pp.OPEN, _pp.EQUITY = _d3 / "c.jsonl", _d3 / "o.jsonl", _d3 / "e.json"
_pp.mark = lambda: (0, 2)
_fut = int(_tm.time() * 1000) + 5000
_pp._append(_pp.CLOSED, {"sym": "SENTUSDT", "dir": "LONG", "entry": 1.0, "sl": 0.99,
                         "tp1": 1.02, "R": 2.0, "outcome": "target", "closed": _fut,
                         "opened": _fut - 1000, "why": {"stage": "sig-ibs",
                                                        "tg_msg_id": 555}})
_pp._append(_pp.CLOSED, {"sym": "BOOKUSDT", "dir": "SHORT", "entry": 1.0, "sl": 1.01,
                         "tp1": 0.98, "R": -1.0, "outcome": "stop", "closed": _fut,
                         "opened": _fut - 1000, "why": {"stage": "alarm"}})
from hamid import cases as _cs                                 # noqa: E402
from hamid import memory as _mm2                               # noqa: E402
import brain as _br2                                           # noqa: E402
_old_iso = (_cs.CASES, _mm2.LESSONS, _br2.learn, _br2.build_index)
_cs.CASES = _d3 / "cases"          # پروندهٔ جعلی تست نباید در brain واقعی بنشیند
_mm2.LESSONS = _d3 / "lessons.json"
_br2.learn = lambda e: None        # تجربهٔ جعلی هم نباید وارد حافظهٔ واقعی شود
_br2.build_index = lambda: None
_calls = []
tg.creds = lambda: ("tok", "chat")
tg._post = lambda tok, m, f, files=None: (_calls.append((m, dict(f))) or
                                          {"ok": True, "result": {"message_id": 1}})
_old_kl = _sources.klines
def _boom(*a, **k):
    raise RuntimeError("offline")
_sources.klines = _boom
try:
    _cy.settle_books({})
finally:
    _pp.CLOSED, _pp.OPEN, _pp.EQUITY, _pp.mark = _old_pp
    _sources.klines = _old_kl
    _cs.CASES, _mm2.LESSONS, _br2.learn, _br2.build_index = _old_iso
_replies = [f for m, f in _calls if f.get("reply_to_message_id")]
_all_txt = " ".join(str(f.get("text", "")) + str(f.get("caption", "")) for m, f in _calls)
check("سیگنال ارسالی: نتیجه ریپلای همان پیام شد",
      len(_replies) == 1 and str(_replies[0]["reply_to_message_id"]) == "555")
check("معاملهٔ دفتر داخلی هیچ پیام تلگرامی نگرفت", "BOOKUSDT" not in _all_txt,
      _all_txt[:160])

# ── استیبل‌کوین از گلوگاه ارسال رد می‌شود (RLUSD دو جای سهمیه را سوزاند) ──
_calls.clear()
_n_st = tg.send_signals([{"sym": "RLUSDUSDT", "tf": "5m", "dir": "LONG",
                          "entry": 1.0, "sl": 0.99, "tp1": 1.02,
                          "strategy": "ibs"}], lambda s, p: None)
check("سیگنال استیبل‌کوین ارسال نمی‌شود و سهمیه نمی‌خورد",
      _n_st == 0 and not _calls, str(_calls)[:120])

# ── نگهبان: این فایل حق ندارد حافظهٔ دائمی یا دفتر تولید را عوض کند ──────
_leaked = sorted(set(_prod_status().splitlines()) - set(_PROD_BEFORE.splitlines()))
check("هیچ فایل تولیدی (brain/ و signals/) عوض نشد", not _leaked,
      " | ".join(_leaked)[:300])

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های حلقهٔ ایجنت گذشتند")
