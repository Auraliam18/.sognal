#!/usr/bin/env python3
"""ارسال دسته‌ای سیگنال + چارت به تلگرام، با دفترچهٔ «چی قبلاً رفته».

از فایل‌های منتشرشدهٔ همین مخزن می‌خواند (همان‌که پنل می‌خواند)، هر سیگنالی
که قبلاً نفرستاده باشد را با چارت می‌فرستد، و کلیدش را در
brain/telegram-sent.json ثبت می‌کند تا هیچ سیگنالی دو بار نرود.

توکن فقط از env می‌آید (Secret یا ورودی workflow_dispatch) — هرگز در فایل.
بدون توکن، ساکت و سبز خارج می‌شود تا کرونِ بی‌Secret قرمز نزند.
"""
import io, json, os, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SENT = ROOT / "brain" / "telegram-sent.json"
TGLOG = ROOT / "signals" / "telegram-log.json"   # «سیگنال نهایی» — پنل همین را نشان می‌دهد
CAP = 5                        # سقف هر اجرا — سیل پیام اعتماد را می‌کشد


def tg(method, payload=None, files=None, tok=""):
    url = f"https://api.telegram.org/bot{tok}/{method}"
    if files:
        import requests                                # فقط وقتی عکس هست لازم می‌شود
        r = requests.post(url, data=payload, files=files, timeout=30)
        return r.json()
    req = urllib.request.Request(url, data=json.dumps(payload or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def klines(sym, tf="15m", n=96):
    u = f"https://api.mexc.com/api/v3/klines?symbol={sym}&interval={tf}&limit={n}"
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "tg/1"}), timeout=20) as r:
        return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
                 "l": float(k[3]), "c": float(k[4])} for k in json.loads(r.read())]


def chart(sym, cd, entry, sl, tp1, tp2, dir_):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5), dpi=110)
    for i, k in enumerate(cd):
        up = k["c"] >= k["o"]
        ax.plot([i, i], [k["l"], k["h"]], color="#666", lw=0.7, zorder=1)
        ax.add_patch(plt.Rectangle((i - 0.33, min(k["o"], k["c"])), 0.66,
                     max(abs(k["c"] - k["o"]), 1e-12),
                     color="#26a69a" if up else "#ef5350", zorder=2))
    for v, c, lb in [(entry, "#42a5f5", "ورود"), (sl, "#ef5350", "استاپ"),
                     (tp1, "#26a69a", "تارگت۱"), (tp2, "#66bb6a", "تارگت۲")]:
        if v:
            ax.axhline(v, color=c, lw=1.1, ls="--")
            ax.text(len(cd) + 1, v, lb, color=c, fontsize=8, va="center")
    ax.set_title(f"{sym}  {dir_}", loc="left")
    ax.set_xlim(-1, len(cd) + 8)
    ax.grid(alpha=0.15)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def collect():
    """سیگنال‌های الان، از همان فایل‌هایی که پنل نشان می‌دهد."""
    out = []
    try:
        h = json.loads((ROOT / "signals" / "hamid-latest.json").read_text())
    except Exception:                                  # noqa: BLE001
        h = {}
    usdt = (((h.get("world") or {}).get("dominance")) or {}).get("usdt")
    for s in h.get("setups", []):
        if s.get("waiting"):
            continue
        out.append({"key": f"hamid|{s['symbol']}|{s['dir']}|{round(s['entry'], 8)}",
                    "sym": s["symbol"], "dir": s["dir"], "tf": "15m",
                    "entry": s["entry"], "sl": s["sl"], "tp1": s.get("tp1"), "tp2": s.get("tp2"),
                    "name": "روش حمید — پولبک دوم", "elite": False, "usdt": usdt})
    try:
        r = json.loads((ROOT / "signals" / "latest.json").read_text())
    except Exception:                                  # noqa: BLE001
        r = {}
    for s in r.get("signals", []):
        out.append({"key": f"{s.get('strategy')}|{s['sym']}|{s['tf']}|{s['dir']}|{round(s['entry'], 8)}",
                    "sym": s["sym"], "dir": s["dir"], "tf": s.get("tf", "15m"),
                    "entry": s["entry"], "sl": s["sl"], "tp1": s.get("tp1"), "tp2": s.get("tp2"),
                    "name": s.get("strategyName", ""), "elite": bool(s.get("elite")),
                    "usdt": usdt, "candles": s.get("candles")})
    return out


def main():
    tok = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not tok or not chat:
        print("توکن یا chat id نیست — تا Secret ثبت نشود این اجرا کاری نمی‌کند")
        return
    sent = []
    if SENT.exists():
        try:
            sent = json.loads(SENT.read_text())
        except Exception:                              # noqa: BLE001
            sent = []
    seen = set(sent)
    log = []
    if TGLOG.exists():
        try:
            log = json.loads(TGLOG.read_text()).get("sent", [])
        except Exception:                              # noqa: BLE001
            log = []
    new = [s for s in collect() if s["key"] not in seen]
    # ردهٔ مسابقه اول می‌رود — بهترین‌ها نباید پشت سقف ارسال بمانند
    new.sort(key=lambda s: (not s["elite"],))
    delivered = 0
    for s in new[:CAP]:
        cap = (f"{'🏆 ' if s['elite'] else ''}🚨 {s['sym']} — "
               f"{'خرید' if s['dir'] == 'LONG' else 'فروش'} ({s['tf']})\n"
               f"استراتژی: {s['name']}\n"
               f"ورود: {s['entry']}\nاستاپ: {s['sl']}\n"
               f"تارگت۱: {s['tp1']}" + (f"\nتارگت۲: {s['tp2']}" if s.get("tp2") else "") +
               (f"\nدامیننس تتر: {s['usdt']}٪" if s.get("usdt") else "") +
               f"\n\nپنل: auraliam18.github.io/.sognal")
        try:
            cd = s.get("candles") or klines(s["sym"], s["tf"])
            png = chart(s["sym"], cd[-96:], s["entry"], s["sl"], s.get("tp1"), s.get("tp2"), s["dir"])
            j = tg("sendPhoto", {"chat_id": chat, "caption": cap},
                   {"photo": (f"{s['sym']}.png", png, "image/png")}, tok)
        except Exception as e:                         # noqa: BLE001 - fall back to text-only
            print(f"  چارت {s['sym']} نشد ({type(e).__name__}) — متنی می‌فرستم")
            try:
                j = tg("sendMessage", {"chat_id": chat, "text": cap}, tok=tok)
            except Exception as e2:                    # noqa: BLE001
                print(f"  ارسال {s['sym']} شکست: {type(e2).__name__}")
                continue
        if j.get("ok"):
            seen.add(s["key"])
            delivered += 1
            log.insert(0, {"at": int(time.time() * 1000),
                           "sym": s["sym"], "dir": s["dir"], "tf": s["tf"],
                           "entry": s["entry"], "sl": s["sl"], "tp1": s.get("tp1"),
                           "tp2": s.get("tp2"), "name": s["name"], "elite": s["elite"]})
            print(f"✓ {s['sym']} {s['dir']} رفت")
        else:
            print(f"✗ {s['sym']}: {j.get('description')}")
    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(list(seen)[-500:], ensure_ascii=False))
    TGLOG.write_text(json.dumps({"generated": int(time.time() * 1000),
                                 "sent": log[:40]}, ensure_ascii=False, indent=1))
    print(f"{delivered} سیگنال فرستاده شد · {len(new) - delivered if len(new) > CAP else 0} ماند برای اجرای بعد")


if __name__ == "__main__":
    main()
