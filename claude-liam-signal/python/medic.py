#!/usr/bin/env python3
"""ایجنت نگهبان — هر ۱۵ دقیقه پنل را از همان جایی که حمید می‌بیند معاینه می‌کند،
و اگر ضربان خوابیده باشد خودش بیدارش می‌کند.

چرا از بیرون معاینه می‌کند: تجربهٔ این مخزن بارها نشان داد سرور می‌تواند سبز
باشد و پنل کهنه — چرخه فقط به main منتشر می‌شد و gh-pages دو روز عقب بود.
پس ملاک، فایل‌هایی است که مرورگر حمید واقعاً می‌خواند، نه لاگ سرور.

معاینه‌ها:
  ۱. hamid-latest.json روی gh-pages تازه است (<۴۵ دقیقه) و شکل درست دارد
     (setups و paper و reads>0) — یعنی خط تولید سیگنال زنده است.
  ۲. latest.json (اسکن استراتژی‌های قبلی) تازه است (<۶۰ دقیقه).
  ۳. خود صفحهٔ پنل با HTTP 200 می‌آید.
  ۴. تلگرام آماده هست یا نه (فقط گزارش — راهش ثبت دو Secret است).

درمان: اگر خط تولید کهنه بود و REVIVE=1 و GITHUB_TOKEN موجود، ورک‌فلوی
Heartbeat را dispatch می‌کند. این همان کاری است که تا امروز دست آدم می‌خواست.

خروجی: brain/medic.json — فقط وقتی وضعیت «عوض شود» نوشته می‌شود (سالم→خراب یا
برعکس، یا متن یافته‌ها تغییر کند)، که تاریخچهٔ گیت پر از کامیت تکراری نشود.
کد خروج: 0 سالم، 1 خراب — تا ورک‌فلو بتواند روی خرابی رفتار متفاوت کند.

اجرای دستی:  python3 claude-liam-signal/python/medic.py
"""
import json, os, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "brain" / "medic.json"

PAGES = "https://auraliam18.github.io/.sognal"
HAMID_MAX_MIN = 45      # ضربان هر ۲۰ دقیقه می‌زند؛ دو چرخهٔ ازدست‌رفته یعنی مشکل
SCAN_MAX_MIN = 60


def fetch(url, timeout=25):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"t={int(time.time())}",
                                 headers={"User-Agent": "medic/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def age_min(j):
    g = j.get("generated")
    return None if not g else (time.time() * 1000 - g) / 60000


def examine():
    finds, sick = [], False

    try:
        st, body = fetch(f"{PAGES}/signals/hamid-latest.json")
        j = json.loads(body)
        a = age_min(j)
        setups, paper, reads = j.get("setups"), j.get("paper"), j.get("reads", 0)
        if a is None or a > HAMID_MAX_MIN:
            sick = True
            finds.append(f"خط تولید سیگنال کهنه است — آخرین چرخه {round(a) if a else '؟'} دقیقه پیش (آستانه {HAMID_MAX_MIN})")
        elif not isinstance(setups, list) or not isinstance(paper, dict) or reads < 10:
            sick = True
            finds.append(f"فایل چرخه شکل درست ندارد (reads={reads}) — چرخه می‌دود ولی چیزی که پنل لازم دارد نمی‌سازد")
        else:
            ready = sum(1 for s in setups if not s.get("waiting"))
            finds.append(f"چرخه سالم: {round(a)} دقیقه پیش، {reads} ارز، {ready} سیگنال آماده، {len(setups) - ready} منتظر، دفتر {paper.get('balance')}$")
    except Exception as e:                            # noqa: BLE001 - unreachable is itself the finding
        sick = True
        finds.append(f"hamid-latest.json در دسترس نیست: {type(e).__name__}")

    try:
        st, body = fetch(f"{PAGES}/signals/latest.json")
        j = json.loads(body)
        a = age_min(j)
        if a is None or a > SCAN_MAX_MIN:
            sick = True
            finds.append(f"اسکن استراتژی‌های قبلی کهنه است — {round(a) if a else '؟'} دقیقه (آستانه {SCAN_MAX_MIN})")
        else:
            finds.append(f"اسکن قبلی سالم: {round(a)} دقیقه پیش، {len(j.get('signals', []))} سیگنال")
    except Exception as e:                            # noqa: BLE001
        sick = True
        finds.append(f"latest.json در دسترس نیست: {type(e).__name__}")

    try:
        st, body = fetch(f"{PAGES}/index.html")
        if st != 200 or b"Hamid Signal Agent" not in body:
            sick = True
            finds.append(f"صفحهٔ پنل درست سرو نمی‌شود (HTTP {st})")
        else:
            finds.append("صفحهٔ پنل بالا است")
    except Exception as e:                            # noqa: BLE001
        sick = True
        finds.append(f"صفحهٔ پنل در دسترس نیست: {type(e).__name__}")

    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        finds.append("تلگرام آماده است")
    else:
        finds.append("تلگرام وصل نیست — دو Secret هنوز ثبت نشده (سیگنال فقط روی پنل می‌ماند)")

    return sick, finds


def revive():
    """ضربان را با همان API که دکمهٔ Run workflow می‌زند بیدار می‌کند."""
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok or os.environ.get("REVIVE") != "1":
        return "درمان غیرفعال است (REVIVE=1 و GITHUB_TOKEN لازم دارد)"
    req = urllib.request.Request(
        "https://api.github.com/repos/Auraliam18/.sognal/actions/workflows/heartbeat.yml/dispatches",
        data=json.dumps({"ref": "main"}).encode(),
        headers={"Authorization": f"Bearer {tok}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "medic/1"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return f"ضربان دوباره روشن شد (HTTP {r.status})"
    except Exception as e:                            # noqa: BLE001 - the failure text is the report
        return f"روشن کردن ضربان شکست خورد: {type(e).__name__}"


def main():
    sick, finds = examine()
    treated = revive() if sick else None
    state = {"at": int(time.time() * 1000),
             "atText": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
             "sick": sick, "findings": finds, "treated": treated}

    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
        except Exception:                             # noqa: BLE001
            prev = {}
    changed = prev.get("sick") != sick or prev.get("findings") != finds
    if changed:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    for f in finds:
        print(("⛔ " if sick else "✓ ") + f)
    if treated:
        print("⚕ " + treated)
    print("state changed" if changed else "state unchanged")
    sys.exit(1 if sick else 0)


if __name__ == "__main__":
    main()
