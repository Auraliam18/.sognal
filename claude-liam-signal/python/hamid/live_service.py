"""حلقهٔ زندهٔ محلی — ضربان ۳۰ ثانیه، طبق قانون ۰۲ (معماری v2.1).

GitHub Actions حلقهٔ بازار نیست؛ کفِ آن ~۳ دقیقه است. این سرویس روی ماشین
خود حمید می‌نشیند و مسیرهای حساس-به-ثانیه را هر ۳۰ ثانیه می‌زند:

  هر ۳۰ ثانیه  — شعله‌گیری ۱۵د (early_movers) + پایش دفتر انتظار پامپ؛
                 شلیک = سیگنال فوری تلگرام با علامت 🧠 و دلیل تاریخی.
  هر ۵ دقیقه   — رادار کامل پامپ (تحلیل خوشه، ثبت کاندیدای جدید در دفتر).
  هر ۲ دقیقه   — همگام‌سازی گیت: pull نوشته‌های Actions؛ push دفترها تا
                 فرستندهٔ Actions همان سیگنال را دوباره نفرستد.

Actions خاموش نمی‌شود (قانون: هیچ‌چیزِ کارکرده قبل از جایگزین اثبات‌شده
خاموش نمی‌شود) — پشتیبان می‌ماند: اگر این سرویس بمیرد، کف ۳ دقیقه‌ای
برمی‌گردد ولی سیستم زنده است. ضدتکرارِ دفترهای brain/ دوفرستادن را می‌گیرد.

آلارم (قانون حمید): تیکِ کندتر از SLA یا شکست پیاپی منبع داده → گزارش
فوری، حداکثر یک بار در ساعت برای هر عارضه.

اجرا:  python3 -m hamid.live_service          (از پوشهٔ python)
توقف:  Ctrl+C
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent

TICK_S = 30                 # ضربان — قانون ۰۲
RADAR_EVERY_S = 300         # رادار کامل
SYNC_EVERY_S = 120          # گیت pull/push
UNI_EVERY_S = 600           # تازه‌سازی لیست ۳۰ ارز پرحجم
SLA_TICK_S = 60             # تیک بیش از این = آلارم
ALARM_COOLDOWN_S = 3600     # هر عارضه حداکثر یک آلارم در ساعت
HB = ROOT / "signals" / "live-heartbeat.json"


def _env_file():
    """live.env در ریشهٔ ریپو — KEY=VALUE ساده؛ توکن تلگرام بدون ترمینال.
    (قانون ۰۵: سکرت در گیت نه — فایل در .gitignore است.)"""
    f = ROOT / "live.env"
    if not f.exists():
        return
    for ln in f.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _git(*args, timeout=60):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=timeout)


class Alarm:
    def __init__(self):
        self.last = {}

    def fire(self, kind, msg):
        now = time.time()
        if now - self.last.get(kind, 0) < ALARM_COOLDOWN_S:
            return
        self.last[kind] = now
        text = f"🚨 حلقهٔ زنده — {kind}: {msg}"
        print(text, flush=True)
        try:
            import telegram as tg
            token, chat = tg.creds()
            if token:
                tg._post(token, "sendMessage",
                         {"chat_id": chat, "text": text})
        except Exception:                            # noqa: BLE001
            pass


def run():
    _env_file()
    from hamid.pump_radar import Kcache, early_movers
    from hamid import pump_watchlist
    import sources

    alarm = Alarm()
    last_radar = last_sync = last_uni = 0.0
    uni = []
    fails = 0
    n_tick = 0
    print(f"حلقهٔ زندهٔ محلی روشن شد — ضربان {TICK_S}س · رادار هر "
          f"{RADAR_EVERY_S//60}د · ریشه: {ROOT}", flush=True)

    while True:
        t0 = time.time()
        n_tick += 1
        try:
            if t0 - last_uni > UNI_EVERY_S or not uni:
                uni = [s["symbol"] for s in
                       sorted(sources.tickers(),
                              key=lambda x: -float(x["quoteVolume"] or 0))
                       if s["symbol"].endswith("USDT")][:30]
                last_uni = t0

            kc = Kcache()

            # ۱) دفتر انتظار — لحظهٔ حجم خوردن، نه ۳ دقیقه بعد
            ignited, notes = pump_watchlist.sweep(kc)
            if ignited:
                n = pump_watchlist.send_ignitions(ignited, kc)
                print(f"⚡ شلیک دفتر انتظار: "
                      + "، ".join(x['symbol'] for x in ignited)
                      + (f" ({n} تلگرام)" if n else " (بدون توکن — فقط پنل)"),
                      flush=True)
            for wn in notes:
                print(f"  دفتر انتظار: {wn}", flush=True)

            # ۲) شعله‌گیری — خبرِ زودتر از جدول گینرها
            ign = early_movers(kc, uni)
            if ign:
                print("  شعله‌ور: " + ", ".join(
                    f"{x['symbol']} {x['change_pct']:+}%" for x in ign[:5]),
                    flush=True)

            # ۳) رادار کامل — کشف خوشه و ثبت کاندیدای تازه در دفتر
            if t0 - last_radar > RADAR_EVERY_S:
                from hamid import pump_radar
                pump_radar.run()
                last_radar = time.time()

            # ۴) همگام‌سازی گیت — دفترها مشترک‌اند با Actions
            if t0 - last_sync > SYNC_EVERY_S:
                _git("fetch", "origin", "main")
                _git("stash", "--include-untracked")
                _git("rebase", "origin/main")
                _git("stash", "pop")
                st = _git("status", "--porcelain",
                          "brain/", "signals/").stdout.strip()
                if st:
                    _git("add", "brain/", "signals/")
                    _git("commit", "-m", "حلقهٔ زنده — دفترها و سیگنال‌ها")
                    p = _git("push", "origin", "HEAD:main")
                    if p.returncode != 0:
                        _git("fetch", "origin", "main")
                        _git("rebase", "origin/main")
                        _git("push", "origin", "HEAD:main")
                last_sync = time.time()

            fails = 0
        except KeyboardInterrupt:
            raise
        except Exception as e:                       # noqa: BLE001
            fails += 1
            print(f"تیک {n_tick}: {type(e).__name__}: {e}", flush=True)
            if fails >= 3:
                alarm.fire("منبع داده",
                           f"{fails} تیک پیاپی شکست — {type(e).__name__}. "
                           "منابع جایگزین sources.py در حال چرخش‌اند؛ اگر "
                           "ادامه یافت اینترنت/فیلترینگ ماشین را چک کن.")

        dt = time.time() - t0
        try:
            HB.parent.mkdir(exist_ok=True)
            HB.write_text(json.dumps(
                {"ts": int(time.time() * 1000), "tick": n_tick,
                 "tick_s": round(dt, 1), "watch": len(pump_watchlist._load()),
                 "fails": fails}, ensure_ascii=False))
        except Exception:                            # noqa: BLE001
            pass
        if dt > SLA_TICK_S:
            alarm.fire("SLA", f"تیک {dt:.0f} ثانیه طول کشید (سقف {SLA_TICK_S}س)")
        time.sleep(max(1.0, TICK_S - dt))


def main():
    try:
        run()
    except KeyboardInterrupt:
        print("\nحلقهٔ زنده خاموش شد — Actions به‌عنوان پشتیبان فعال است.")


if __name__ == "__main__":
    main()
