"""پاسبان نتیجه‌گیری‌ها — دستور حمید (۱۶ اوت): «روتین و تایمری که مرتب
پیام‌ها/نتیجه‌گیری‌ها را بخواند و با رفتار انجین‌ها بسنجد که همخوانی دارد
یا نه.»

هر ۲ ساعت (هم‌قدم با آهنگ بازبینی دوساعته) اجرا می‌شود و «آخرین
نتیجه‌گیری‌ها» را — که حالا در CLAUDE.md و قوانین ثبت‌اند — در برابر
خروجی واقعی انجین‌ها می‌سنجد. فقط تخلف گزارش می‌شود؛ سکوت = همخوان.

سنجش‌های نسخهٔ ۱ (هر کدام به یک نتیجه‌گیری ثبت‌شده برمی‌گردد):

C1  ترکیب پیشنهاد پامپ: پیشنهاد فقط ارزِ هنوز-نپریده (نتیجه‌گیری ۱۴ اوت
    «همشون توی پامپ بودن»). pickِ بالای آستانه‌های QUIET = تخلف.
C2  «دیر رسید» بدون دفتر انتظار: حکم late در حالی که دفتر خالی است =
    همان ضعف ۶۳باره دارد برمی‌گردد (نتیجه‌گیری ۱۵ اوت).
C3  تکرار درس: متنِ یکسان ≥۵ بار در ۲۴س در حافظه = یک نتیجه‌گیری دارد
    مکرر نقض می‌شود و کسی نمی‌بیند (کلاس همان باگ ۱۶ کپی).
C4  وظیفهٔ مطالعه: قفسهٔ کتابخانه مدخل VERIFIED دارد ولی findings انجین
    مربوط خالی است، یا صف بررسی ورودیِ مانده >۴۸س دارد (دستور ۱۶ اوت).
C5  پنجرهٔ رسیدن داده (قانون ۵ حمید): تازگی خروجی هر انجین از سقفش
    گذشته = همان لحظه گزارش.

خروجی: signals/conformance.json + تلگرام فقط در صورت تخلف.
"""
import json
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "conformance.json"

# سقف تازگی هر خروجی (دقیقه) — قانون ۵: دیر رسیدن داده = رویداد
FRESHNESS_MAX_MIN = {
    "signals/pump-radar.json": 20,       # هر ~۳د می‌دود؛ ۲۰د یعنی مرده
    "signals/latest.json": 45,           # اسکن کامل
    "signals/hamid-latest.json": 45,
    "signals/dominance.json": 90,
}
QUIET_24H, QUIET_60M, QUIET_30M = 5.0, 3.0, 3.0   # هم‌مقدار با رادار
LESSON_REPEAT_MAX = 5


def _read(rel):
    try:
        return json.loads((ROOT / rel).read_text())
    except Exception:                                # noqa: BLE001
        return None


def check(now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    v = []                                           # violations

    # C1 — پیشنهاد پامپ فقط هنوز-نپریده
    pr = _read("signals/pump-radar.json") or {}
    for p in (pr.get("picks") or []):
        b = next((x for x in (pr.get("blocks") or [])
                  if x.get("symbol") == p.get("symbol")), {})
        c24, c60, c30 = (b.get("change_24h_pct"), b.get("change_60m_pct"),
                         b.get("change_30m_pct"))
        moved = [f"{lbl}{x:+}٪" for lbl, x, th in
                 [("۲۴س ", c24, QUIET_24H), ("۱س ", c60, QUIET_60M),
                  ("۳۰د ", c30, QUIET_30M)] if x is not None and x >= th]
        if moved:
            v.append(dict(rule="C1", sev="high", sym=p.get("symbol"),
                          msg=f"پیشنهاد پامپ {p.get('symbol')} هنوز-نپریده نیست "
                              f"({'، '.join(moved)}) — نقض نتیجه‌گیری ۱۴ اوت"))

    # C2 — حکم دیر بدون دفتر انتظار
    verdict = pr.get("verdict") or ""
    wl = _read("brain/pump-watchlist.json") or {}
    wl_n = len([k for k in wl if k != "_graveyard"])
    if "دویده" in verdict and wl_n == 0:
        v.append(dict(rule="C2", sev="high", sym="-",
                      msg="حکم «خوشه دویده/دیر» صادر شده ولی دفتر انتظار خالی است "
                          "— ضعف ۶۳باره دارد برمی‌گردد"))

    # C3 — درس تکراری در حافظه
    mem = _read("brain/memory/lessons.json")
    lessons = mem if isinstance(mem, list) else (mem or {}).get("lessons", [])
    day_ago = now_ms - 24 * 3600e3
    cnt = Counter((l.get("text") or l.get("lesson") or "")[:80]
                  for l in lessons
                  if (l.get("at") or l.get("t") or now_ms) > day_ago)
    for txt, n in cnt.most_common(10):
        if n >= LESSON_REPEAT_MAX and txt.strip():
            v.append(dict(rule="C3", sev="med", sym="-",
                          msg=f"درسِ یکسان ×{n} در ۲۴س: «{txt[:60]}…» — "
                              f"نتیجه‌گیری دارد مکرر نقض می‌شود"))

    # C4 — وظیفهٔ مطالعه و صف کتابخانه
    lib = ROOT / "brain" / "library" / "index.jsonl"
    if lib.exists():
        engines = set()
        for ln in lib.read_text().splitlines():
            try:
                r = json.loads(ln)
                if r.get("status") == "VERIFIED" and r.get("engine"):
                    engines.add(r["engine"])
            except Exception:                        # noqa: BLE001
                pass
        for e in sorted(engines):
            f = ROOT / "brain" / "research" / e / "findings.jsonl"
            n = len(f.read_text().splitlines()) if f.exists() else 0
            if n == 0:
                v.append(dict(rule="C4", sev="med", sym=e,
                              msg=f"قفسه برای {e} مدخل VERIFIED دارد ولی "
                                  f"findings آن خالی است — نخوانده"))
    q = ROOT / "brain" / "library" / "queue.jsonl"
    if q.exists():
        for ln in q.read_text().splitlines():
            try:
                r = json.loads(ln)
            except Exception:                        # noqa: BLE001
                continue
            if (r.get("status") == "QUEUED" and
                    now_ms - (r.get("queued_at") or now_ms) > 48 * 3600e3):
                v.append(dict(rule="C4", sev="low", sym=r.get("id") or "-",
                              msg=f"مدخل صف کتابخانه >۴۸س بی‌بررسی مانده: "
                                  f"{(r.get('title') or '?')[:50]}"))

    # C5 — پنجرهٔ رسیدن داده
    for rel, mx in FRESHNESS_MAX_MIN.items():
        d = _read(rel)
        ts = (d or {}).get("generated")
        if not ts:
            continue
        age_min = (now_ms - ts) / 60000
        if age_min > mx:
            v.append(dict(rule="C5", sev="high", sym=rel.split("/")[-1],
                          msg=f"{rel} از پنجرهٔ داده‌اش گذشته: {age_min:.0f}د "
                              f"(سقف {mx}د) — قانون ۵ حمید"))

    return dict(generated=now_ms,
                generatedText=time.strftime("%Y-%m-%d %H:%M UTC",
                                            time.gmtime(now_ms / 1000)),
                checks=["C1", "C2", "C3", "C4", "C5"],
                violations=v, ok=not v)


def run():
    rep = check()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    if rep["ok"]:
        print("پاسبان نتیجه‌گیری‌ها: همه‌چیز همخوان ✅")
        return rep
    print(f"پاسبان: {len(rep['violations'])} ناهمخوانی:")
    for x in rep["violations"]:
        print(f"  [{x['rule']}/{x['sev']}] {x['msg']}")
    try:
        import telegram as tg
        token, chat = tg.creds()
        if token:
            head = "🛡 <b>لیام تریدر ۹ — پاسبان نتیجه‌گیری‌ها</b>\n"
            body = "\n".join(f"• [{x['rule']}] {x['msg']}"
                             for x in rep["violations"][:8])
            tg._post(token, "sendMessage",
                     {"chat_id": chat, "text": head + body,
                      "parse_mode": "HTML"})
    except Exception as e:                           # noqa: BLE001
        print(f"تلگرام پاسبان: {type(e).__name__}")
    return rep


if __name__ == "__main__":
    run()
