#!/usr/bin/env python3
"""دیده‌بان پنل — هر چرخه می‌پرسد «آیا چیزی خراب است؟»

این باید از اول می‌بود. یک بار فایل روش حمید ۳۹ ساعت روی پنل کهنه ماند، چون
چرخه فقط روی main منتشر می‌کرد و پنل از gh-pages می‌خواند. همه‌چیز «موفق»
گزارش می‌شد: چرخه اجرا می‌شد، کامیت می‌خورد، ورک‌فلو سبز بود. تنها کسی که
فهمید خود حمید بود، آن هم یک روز و نیم بعد.

خرابیِ ساکت از خرابیِ پرسروصدا بدتر است. این ماژول همان‌جایی را نگاه می‌کند که
حمید نگاه می‌کند — فایل روی gh-pages، نه فایل روی main — و هر چیزی را که از
دید او «کار نمی‌کند» به نظر می‌رسد پیدا می‌کند، حتی وقتی همهٔ ورک‌فلوها سبزند.

    python3 -m hamid.watchdog            # یک بار بررسی
    python3 -m hamid.watchdog --alert    # و اگر خراب بود، تلگرام
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
OUT = ROOT / "brain" / "watchdog.json"

PAGES = "https://auraliam18.github.io/.sognal"
UA = {"User-Agent": "hamid-signal-watchdog"}
TIMEOUT = 20

# آستانه‌ها بر اساس تناوب واقعی: ضربان هر ۲۰ دقیقه، اسکن زنده ساعتی یکی دو بار.
# سخت‌گیرتر از این یعنی هشدار الکی، شل‌تر یعنی همان ۳۹ ساعت دوباره.
FRESH_HAMID_MIN = 90
FRESH_SCAN_MIN = 150


def _get(url, as_json=True):
    req = urllib.request.Request(url + f"?t={int(time.time())}", headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    return json.loads(raw) if as_json else raw.decode("utf8", "replace")


def _age_min(ms):
    return (time.time() * 1000 - ms) / 60000


# ── بررسی‌ها ────────────────────────────────────────────────────────────────
# هر کدام (وضعیت, توضیح) برمی‌گرداند. وضعیت: ok / warn / down

def c_panel_loads():
    """آیا خود صفحه بالا می‌آید؟ اگر نه، بقیهٔ بررسی‌ها بی‌معنی‌اند."""
    html = _get(f"{PAGES}/index.html", as_json=False)
    # نشانهٔ قدیمی «Hamid Signal Agent» با تغییر نام پنل حذف شد و همین چک
    # هر چرخه به دروغ «پنل خراب» می‌فرستاد — نشانه‌های واقعی امروز:
    if ("لیام تریدر ۹" not in html) and ("حمید کلود مکس پنل" not in html) and ("cycle v" not in html):
        return "down", "صفحه بالا آمد ولی محتوایش پنل نیست"
    ver = ""
    i = html.find("cycle v")
    if i > 0:
        ver = html[i:i + 20].split("<")[0].strip()
    return "ok", f"صفحه سالم است ({ver})"


def c_hamid_fresh():
    """همان فایلی که حمید می‌بیند — روی gh-pages، نه روی main.

    این دقیقاً همان بررسی‌ای است که آن ۳۹ ساعت را می‌گرفت.
    """
    j = _get(f"{PAGES}/signals/hamid-latest.json")
    age = _age_min(j["generated"])
    s = j.get("setups") or []
    ready = len([x for x in s if not x.get("waiting")])
    detail = (f"{age:.0f} دقیقه پیش · حالت {j.get('mode')} · "
              f"{j.get('reads', 0)} ارز · {ready} سیگنال")
    if age > FRESH_HAMID_MIN * 4:
        return "down", f"کهنه است — {detail}"
    if age > FRESH_HAMID_MIN:
        return "warn", f"دیر شده — {detail}"
    return "ok", detail


def c_scan_fresh():
    j = _get(f"{PAGES}/signals/latest.json")
    age = _age_min(j["generated"])
    detail = f"{age:.0f} دقیقه پیش · {len(j.get('signals') or [])} سیگنال"
    if age > FRESH_SCAN_MIN * 3:
        return "down", f"کهنه است — {detail}"
    if age > FRESH_SCAN_MIN:
        return "warn", f"دیر شده — {detail}"
    return "ok", detail


def c_pages_matches_main():
    """آیا چیزی که روی پنل است همان چیزی است که آخرین چرخه ساخته؟

    اختلاف یعنی مرحلهٔ انتشار روی gh-pages شکسته — همان خرابی‌ای که یک بار
    اتفاق افتاد و هیچ ورک‌فلویی قرمز نشد.

    این بررسی فقط **بعد از** مرحلهٔ انتشار معنی دارد. وقتی دیده‌بان داخل خود
    چرخه اجرا شود، هنوز چیزی منتشر نشده و پنل طبیعتاً یک چرخه عقب است — همان
    اولین اجرای واقعی ۸۳ دقیقه اختلاف گزارش کرد در حالی که انتشار سالم بود.
    یک هشدار دروغ در هر چرخه یعنی حمید بعد از یک روز دیگر هیچ هشداری را
    نمی‌خواند، و آن وقت هشدار واقعی هم گم می‌شود. پس بدون AFTER_PUBLISH اصلاً
    این بررسی انجام نمی‌شود.
    """
    import os
    if not os.environ.get("WATCHDOG_AFTER_PUBLISH"):
        return "skip", "قبل از مرحلهٔ انتشار اجرا شده — این بررسی اینجا معنی ندارد"
    local = ROOT / "signals" / "hamid-latest.json"
    if not local.exists():
        return "warn", "نسخهٔ محلی نیست (بیرون از رانر اجرا شده)"
    mine = json.loads(local.read_text())
    theirs = _get(f"{PAGES}/signals/hamid-latest.json")
    diff = (mine["generated"] - theirs["generated"]) / 60000
    if diff > 45:
        return "down", (f"پنل {diff:.0f} دقیقه از آخرین چرخه عقب است — "
                        "انتشار روی gh-pages کار نمی‌کند")
    return "ok", f"پنل با آخرین چرخه هماهنگ است ({diff:+.0f} دقیقه)"


def c_paper_moving():
    """دفتر کاغذی باید یا سفارش باز داشته باشد یا معاملهٔ بسته — نه هیچ‌کدام."""
    op = ROOT / "brain" / "paper" / "open.jsonl"
    eq = ROOT / "brain" / "paper" / "equity.json"
    n_open = len([l for l in op.read_text().splitlines() if l.strip()]) if op.exists() else 0
    if not eq.exists():
        return ("warn", "دفتری تشکیل نشده") if not n_open else ("ok", f"{n_open} سفارش باز")
    e = json.loads(eq.read_text())
    return "ok", (f"{n_open} باز · {e['trades']} بسته · "
                  f"${e['balance']} ({e['return_pct']:+.2f}٪) · افت {e['max_drawdown_pct']}٪")


def c_brain_writing():
    """اتاق‌ها باید همین امروز چیزی نوشته باشند."""
    ev = ROOT / "brain" / "events" / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
    if not ev.exists():
        return "warn", "امروز هنوز رویدادی ثبت نشده"
    n = len([l for l in ev.read_text().splitlines() if l.strip()])
    return ("ok" if n else "warn"), f"{n} رویداد امروز"


def c_rooms_scored():
    """امتیازدهی اتاق‌ها (payroll) باید تازه باشد — این همان «راندمان اتاق‌ها»ست.

    این بررسی به این دلیل وجود دارد که دقیقاً همین از کار افتاد و هیچ‌کس
    نفهمید: ورک‌فلوی paper-cycle به شاخه‌ای پین بود که بعد از هر ادغام PR پاک
    می‌شود، checkout دو روز شکست می‌خورد، و آخرین امتیاز اتاق‌ها مال دو روز
    قبل بود — در حالی که همهٔ چیزهای دیگر سبز بودند.
    """
    p = ROOT / "brain" / "rooms" / "payroll.json"
    if not p.exists():
        return "down", "payroll.json وجود ندارد — اتاق‌ها هیچ‌وقت امتیاز نگرفته‌اند"
    j = json.loads(p.read_text())
    at = j.get("at")
    if not at:
        return "warn", "payroll زمان ندارد"
    age_h = (time.time() * 1000 - at) / 3600_000
    n = len(j.get("rooms") or [])
    detail = f"{n} اتاق · {age_h:.0f} ساعت پیش · مجموع {j.get('total')}"
    if age_h > 26:
        return "down", f"کهنه است — {detail} (زمان‌بندی هر ۲ ساعت است)"
    if age_h > 6:
        return "warn", f"دیر شده — {detail}"
    return "ok", detail


def c_telegram_ready():
    import os
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        missing = [n for n, v in (("TOKEN", tok), ("CHAT_ID", chat)) if not v]
        return "warn", f"تنظیم نشده: {', '.join(missing)} — سیگنالی فرستاده نمی‌شود"
    return "ok", "کلیدها تنظیم‌اند"


CHECKS = [
    ("صفحهٔ پنل", c_panel_loads),
    ("سیگنال روش حمید روی پنل", c_hamid_fresh),
    ("اسکن زنده روی پنل", c_scan_fresh),
    ("هماهنگی پنل با آخرین چرخه", c_pages_matches_main),
    ("دفتر ترید کاغذی", c_paper_moving),
    ("اتاق‌ها در حال نوشتن", c_brain_writing),
    ("راندمان اتاق‌ها (payroll)", c_rooms_scored),
    ("آمادگی تلگرام", c_telegram_ready),
]


def run(alert=False, quiet=False):
    rows, bad = [], []
    for name, fn in CHECKS:
        try:
            st, detail = fn()
        except urllib.error.HTTPError as e:
            st, detail = "down", f"HTTP {e.code}"
        except Exception as e:                       # noqa: BLE001 - خرابی خودش جواب است
            st, detail = "down", f"{type(e).__name__}: {str(e)[:80]}"
        rows.append({"name": name, "status": st, "detail": detail})
        if st == "down":
            bad.append((name, detail))

    if not quiet:
        print("\nدیده‌بان پنل\n" + "═" * 72)
        for r in rows:
            mark = {"ok": "✓", "warn": "!", "down": "✗", "skip": "–"}[r["status"]]
            print(f"  {mark}  {r['name']:<30} {r['detail']}")
        print("═" * 72)
        n_ok = sum(1 for r in rows if r["status"] == "ok")
        n_warn = sum(1 for r in rows if r["status"] == "warn")
        print(f"{n_ok} سالم · {n_warn} هشدار · {len(bad)} خراب")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "ok": not bad, "checks": rows,
    }, ensure_ascii=False, indent=1))

    if bad and alert:
        _alert(bad)
    return bad


_LAST = ROOT / "brain" / "watchdog-alerted.json"


def _alert(bad):
    """هشدار می‌فرستد، ولی نه هر بیست دقیقه یک بار برای همان خرابی.

    یک دیده‌بان که مدام تکرار می‌کند، خوانده نمی‌شود — و آن وقت خرابیِ بعدی هم
    گم می‌شود.
    """
    import os
    key = "|".join(n for n, _ in bad)
    try:
        last = json.loads(_LAST.read_text())
    except Exception:                                # noqa: BLE001
        last = {}
    if last.get("key") == key and time.time() - last.get("at", 0) < 6 * 3600:
        print("هشدار تکراری — فرستاده نشد")
        return
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        print("هشدار: کلید تلگرام نیست، چیزی فرستاده نشد")
        return
    lines = ["<b>⚠️ دیده‌بان پنل — خرابی</b>", ""]
    lines += [f"• <b>{n}</b>: {d}" for n, d in bad]
    lines += ["", "<i>این پیام خودکار است و تا رفع مشکل هر ۶ ساعت یک بار تکرار می‌شود.</i>"]
    body = json.dumps({"chat_id": chat, "parse_mode": "HTML",
                       "text": "\n".join(lines)}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                 data=body, method="POST",
                                 headers={**UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT):
            pass
        _LAST.parent.mkdir(parents=True, exist_ok=True)
        _LAST.write_text(json.dumps({"key": key, "at": time.time()}))
        print("هشدار به تلگرام فرستاده شد")
    except Exception as e:                           # noqa: BLE001
        from telegram import scrub
        print(f"هشدار فرستاده نشد: {scrub(e)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    bad = run(alert=a.alert, quiet=a.quiet)
    # خرابی پنل نباید چرخه را بکشد؛ گزارشش کافی است.
    return 0


if __name__ == "__main__":
    sys.exit(main())
