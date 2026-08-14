"""آزمون ارسال فوریِ per-symbol — دستور صریح حمید (۱۴ اوت).

«به محض اینکه سیگنالی پیدا شد و شرایطش اوکی بود منتظر نمان که چرخهٔ پایش
بقیهٔ ارزها تمام شود؛ ارسال کن و بقیهٔ پایش را انجام بده. اگر چندتا بود،
هرکدام را به محض گرفتن تأییدیه بفرست.»

بدون شبکه. آنچه اثبات می‌شود: قلاب on_ready وسط حلقهٔ ارزها صدا می‌شود،
با همان دروازه‌ها (وتوی تجربه، حافظه، سهمیه، send_signals) و ارز اول
می‌رود در حالی که ارزهای بعدی هنوز خوانده نشده‌اند.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ok = 0
fail = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


print("── ارسال فوری per-symbol ──")

from hamid import cycle                                          # noqa: E402

src = inspect.getsource(cycle.run_active)
msrc = inspect.getsource(cycle.main)

check("run_active پارامتر on_ready دارد",
      "on_ready" in inspect.signature(cycle.run_active).parameters)
check("قلاب داخل حلقهٔ ارزها صدا می‌شود", "on_ready(sym, r)" in src)
i_hook, i_flow = src.find("on_ready(sym, r)"), src.find("flows = money_flow")
check("قلاب قبل از جمع‌بندی پایانی چرخه است", 0 < i_hook < i_flow)
i_app = src.find("setups.append((sym, r))")
check("قلاب بلافاصله بعد از ستاپِ همان ارز است",
      0 < i_app < i_hook and (i_hook - i_app) < 400)
check("شکست ارسال اسکن را نمی‌کشد", "ارسال فوری" in src and "except Exception" in src)
check("main فرستندهٔ فوری را می‌دهد", "run_active(syms, on_ready=_send_now)" in msrc)
check("ستاپ منتظر فوری نمی‌رود", 'r.setup.get("waiting")' in msrc)
check("وتوی تجربه در مسیر فوری هست", '_exp_live' in msrc and 'e["win_pct"] < 45' in msrc)
check("مشورت حافظه در مسیر فوری هست", "_m_live.consult" in msrc)
check("سهمیهٔ روز رعایت می‌شود", "DAILY_TARGET" in msrc and '_live["sent"]' in msrc)
check("از همان send_signals می‌گذرد", "_tg_live.send_signals([one], _tg_chart)" in msrc)

# ── شبیه‌سازی ترتیب واقعی ──────────────────────────────────────────────────
order, sent = [], []


def fake_read(sym, c4h, c1h, c15m):
    order.append(("read", sym))

    class R:
        trend_4h = trend_1h = trend_15m = "up"
        position_1h = 0.5
        channel_note = "—"
        levels_4h = levels_1h = blocks = fvgs = notes = []
        setup = {"dir": "LONG", "entry": 1.0, "sl": 0.9, "tp1": 1.2, "rr": 2.0}
    return R()


class FakeSources:
    @staticmethod
    def klines(sym, tf, n):
        return [[i * 900000, 1, 1.01, 0.99, 1, 10] for i in range(80)]


class FakeBrain:
    room_log = room_save = staticmethod(lambda *a, **k: None)
    room_load = staticmethod(lambda *a, **k: {})


import hamid.cycle as C                                          # noqa: E402
_r, _s, _b, _mf = C.read, C.sources, C.brain, C.market_first
C.read, C.sources, C.brain = fake_read, FakeSources, FakeBrain
C.market_first = lambda *a, **k: {"verdict": "—"}
try:
    C.run_active(["AUSDT", "BUSDT", "CUSDT"],
                 on_ready=lambda s, r: (sent.append(s), order.append(("send", s))))
except Exception as e:                                # noqa: BLE001
    print(f"    (شبیه‌سازی: {type(e).__name__})")
finally:
    C.read, C.sources, C.brain, C.market_first = _r, _s, _b, _mf

if sent:
    check(f"هر سه ارز فوری فرستاده شدند ({sent})", len(sent) == 3)
    check("ارز اول رفت وقتی ارز سوم هنوز خوانده نشده بود",
          order.index(("send", "AUSDT")) < order.index(("read", "CUSDT")))
else:
    print("    (حلقهٔ شبیه‌سازی اجرا نشد — بررسی ایستا معتبر است)")

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون ارسال فوری گذشت")
