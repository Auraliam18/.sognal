"""خودآزمایی پاسبان نتیجه‌گیری‌ها — python3 -m hamid.test_conformance"""
import json
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import conformance as cf                  # noqa: E402


def w(root, rel, obj):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False)
                 if not isinstance(obj, str) else obj)


def run():
    now = int(time.time() * 1000)
    root = Path(tempfile.mkdtemp())
    cf.ROOT = root
    cf.OUT = root / "signals" / "conformance.json"

    # صحنهٔ سالم — هیچ تخلفی
    w(root, "signals/pump-radar.json",
      {"generated": now, "picks": [{"symbol": "AAAUSDT"}],
       "blocks": [{"symbol": "AAAUSDT", "change_24h_pct": 1.0,
                   "change_60m_pct": 0.5, "change_30m_pct": 0.2}],
       "verdict": None})
    w(root, "signals/latest.json", {"generated": now})
    w(root, "signals/hamid-latest.json", {"generated": now})
    w(root, "signals/dominance.json", {"generated": now})
    w(root, "brain/pump-watchlist.json", {"XUSDT": {}})
    w(root, "brain/memory/lessons.json", [])
    rep = cf.check(now_ms=now)
    assert rep["ok"], rep["violations"]
    print("۱ ✅ صحنهٔ سالم: صفر تخلف")

    # C1 — پیشنهادِ پریده
    w(root, "signals/pump-radar.json",
      {"generated": now, "picks": [{"symbol": "BBBUSDT"}],
       "blocks": [{"symbol": "BBBUSDT", "change_24h_pct": 9.0}],
       "verdict": None})
    rep = cf.check(now_ms=now)
    assert any(x["rule"] == "C1" for x in rep["violations"])
    print("۲ ✅ C1: پیشنهاد پامپِ پریده گرفته شد")

    # C2 — دیر بدون دفتر
    w(root, "signals/pump-radar.json",
      {"generated": now, "picks": [], "blocks": [],
       "verdict": "خوشه قبل از رسیدن ما دویده"})
    w(root, "brain/pump-watchlist.json", {"_graveyard": {}})
    rep = cf.check(now_ms=now)
    assert any(x["rule"] == "C2" for x in rep["violations"])
    print("۳ ✅ C2: حکم دیر با دفتر خالی گرفته شد")

    # C3 — درس تکراری
    w(root, "brain/memory/lessons.json",
      [{"text": "همان درس", "at": now}] * 6)
    rep = cf.check(now_ms=now)
    assert any(x["rule"] == "C3" for x in rep["violations"])
    print("۴ ✅ C3: درس ×۶ گرفته شد")

    # C4 — قفسه دارد، findings خالی
    w(root, "brain/library/index.jsonl",
      json.dumps({"status": "VERIFIED", "engine": "E07"}, ensure_ascii=False))
    rep = cf.check(now_ms=now)
    assert any(x["rule"] == "C4" for x in rep["violations"])
    w(root, "brain/research/E07/findings.jsonl", '{"claim_id":"x"}')
    rep = cf.check(now_ms=now)
    assert not any(x["rule"] == "C4" and x["sym"] == "E07"
                   for x in rep["violations"])
    print("۵ ✅ C4: نخواندن گرفته شد؛ بعد از خواندن پاک شد")

    # C5 — دادهٔ کهنه
    w(root, "signals/latest.json", {"generated": now - 3 * 3600 * 1000})
    rep = cf.check(now_ms=now)
    assert any(x["rule"] == "C5" for x in rep["violations"])
    print("۶ ✅ C5: خروجی کهنه گرفته شد")

    print("\nهمهٔ ۶ آزمون پاسبان گذشت")


if __name__ == "__main__":
    run()
