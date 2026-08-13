#!/usr/bin/env python3
"""اسکنر پرسرعت محلی — برای لپ‌تاپ حمید («این را برای همین کارها گرفتم»).

ابر (GitHub Actions) ستون فقرات ۲۴/۷ است و می‌ماند؛ این اسکریپت لایهٔ
سرعت است: روی لپ‌تاپ، ۲۰۰ ارز برتر را در حلقهٔ چند-ده-ثانیه‌ای با هر دو
استراتژی اسکن می‌کند و ستاپ تازه‌ای که SIGNAL شد را همان لحظه به تلگرام
می‌فرستد — با برچسب جدا «اسکنر محلی» و توکن جدا، تا با کانال ابری قاطی
نشود و دفتر ضدتکرار ابر دست نخورد.

صداقت دربارهٔ سرعت: کف واقعی را صرافی تعیین می‌کند، نه لپ‌تاپ. حد نرخ
عمومی کندل حدود ۱۲۰۰ واحد در دقیقه است؛ ۲۰۰ ارز × ۲ تایم‌فریم در هر دور
یعنی هر دور ~۸۰۰ واحد — پس دورِ کامل زیر ~۴۵ ثانیه از سقف صرافی رد
می‌شود و بن می‌خوری. پیش‌فرض ۴۵ ثانیه است؛ با --interval 30 هم می‌توانی
ولی اسکریپت خودش اگر خطای 429/418 دید، صادقانه کند می‌شود و می‌گوید.
مدت واقعی هر دور در هر خط لاگ چاپ می‌شود — ادعا نکن، بخوان.

اجرا روی لپ‌تاپ (به پایتون ۳ و Node نیاز دارد — هر دو رایگان):
    export LOCAL_TG_TOKEN="توکن ربات جدا"     # اختیاری؛ بدون آن فقط لاگ
    export LOCAL_TG_CHAT="شناسهٔ چت"
    python3 local_scanner.py --symbols 200 --interval 45
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SEEN = HERE / ".local-scanner-seen.json"


def _load_seen():
    try:
        return json.loads(SEEN.read_text())
    except Exception:                                # noqa: BLE001
        return {}


def _tg(text):
    tok = os.environ.get("LOCAL_TG_TOKEN", "").strip()
    chat = os.environ.get("LOCAL_TG_CHAT", "").strip()
    if not tok or not chat:
        return False
    import urllib.request
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{tok}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": text,
                         "parse_mode": "HTML"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return bool(json.load(r).get("ok"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=200)
    ap.add_argument("--interval", type=int, default=45,
                    help="کف فاصلهٔ دورها به ثانیه (کمتر از ۳۰ توصیه نمی‌شود)")
    ap.add_argument("--tf", default="5m,15m")
    a = ap.parse_args()
    interval = max(20, a.interval)
    seen = _load_seen()
    backoff = 0
    print(f"اسکنر محلی: {a.symbols} ارز × {a.tf} — گام {interval}ث "
          f"(Ctrl+C برای توقف)", flush=True)
    while True:
        t0 = time.time()
        try:
            r = subprocess.run(
                [sys.executable, str(HERE / "scan.py"),
                 "--symbols", str(a.symbols), "--tf", a.tf],
                capture_output=True, text=True, timeout=interval * 4)
            out = r.stdout + r.stderr
            if "429" in out or "418" in out or "banned" in out.lower():
                backoff = min((backoff or 30) * 2, 600)
                print(f"⚠ صرافی حد نرخ زد — {backoff}ث عقب‌نشینی صادقانه", flush=True)
            else:
                backoff = 0
            latest = json.loads((HERE.parent.parent / "signals" /
                                 "latest.json").read_text())
            fresh = []
            for s in latest.get("signals") or []:
                if s.get("stage") != "SIGNAL":
                    continue
                key = f"{s.get('sym')}|{s.get('tf')}|{s.get('dir')}"
                if time.time() * 1000 - seen.get(key, 0) < 3 * 3600e3:
                    continue
                seen[key] = time.time() * 1000
                fresh.append(s)
            for s in fresh[:4]:
                txt = (f"⚡ <b>اسکنر محلی</b> — ستاپ SIGNAL همین لحظه\n"
                       f"<b>{s.get('dir')} {s.get('sym')}</b> <code>{s.get('tf')}</code>\n"
                       f"ورود <code>{s.get('entry')}</code> · استاپ <code>{s.get('sl')}</code> "
                       f"· تارگت <code>{s.get('tp1')}</code>\n"
                       f"<i>تأیید نهایی و چارت از کانال ابری می‌آید — این فقط "
                       f"هشدار سرعت است.</i>")
                ok = _tg(txt)
                print(("✓ تلگرام: " if ok else "• لاگ: ") + txt.split("\n")[1], flush=True)
            SEEN.write_text(json.dumps(seen))
            took = time.time() - t0
            print(f"دور در {took:.0f}ث — {len(fresh)} ستاپ تازهٔ SIGNAL", flush=True)
        except Exception as e:                       # noqa: BLE001
            print(f"دور شکست خورد: {type(e).__name__}: {e}", flush=True)
        wait = max(5, interval - (time.time() - t0)) + backoff
        time.sleep(wait)


if __name__ == "__main__":
    main()
