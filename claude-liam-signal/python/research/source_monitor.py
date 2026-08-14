"""مانیتور منابع — Python تغییر واقعی را می‌بیند، نه LLM.

قانون ۶ و ۷ سند حمید: Fetch/Hash/Diff/Dedup کار Python است و LLM فقط
روی «آیتم جدید و مرتبط» صدا می‌شود. این ماژول همان صافی است: منبع هر
انجین را می‌گیرد، هش می‌کند، با آخرین دیده مقایسه می‌کند و فقط تغییر
واقعی را به‌عنوان DISCOVERED در دفتر Claim ثبت می‌کند.

وضعیت هر منبع (brain/research/{engine}/last-seen.json):
  url · tier · content hash · etag/last-modified · retrieved_at ·
  parser_version · failure_count · next_retry

خطای شبکه چرخه را نمی‌کشد: failure_count بالا می‌رود و next_retry با
backoff نمایی جلو می‌رود.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "brain" / "research"
REGISTRY = ROOT / "config" / "engine_learning_registry.yaml"

PARSER_VERSION = 1
PHASE1 = ["E00", "E02", "E18", "E21", "E23"]     # زیرساخت اول — سند حمید، بند F


def load_registry():
    import yaml
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def _state_path(engine_id):
    d = RESEARCH / engine_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "last-seen.json"


def _load_state(engine_id):
    p = _state_path(engine_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_state(engine_id, st):
    _state_path(engine_id).write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def _default_fetch(url, etag=None):
    """برگرداندن (body, etag) — پاسخ 304 یعنی تغییری نیست."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "LIAM-knowledge-loop/1.0",
        **({"If-None-Match": etag} if etag else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read(), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, etag
        raise


def check_source(engine_id, url, tier, fetch=None, now=None):
    """یک منبع را بسنج. خروجی: 'new' | 'unchanged' | 'skipped' | 'failed'."""
    fetch = fetch or _default_fetch
    now = now or time.time()
    st = _load_state(engine_id)
    s = st.get(url, {})

    if s.get("next_retry", 0) > now:
        return "skipped"

    try:
        body, etag = fetch(url, s.get("etag"))
    except Exception as e:                        # noqa: BLE001 - یک منبع خراب حلقه را نمی‌کشد
        s["failure_count"] = s.get("failure_count", 0) + 1
        s["last_error"] = f"{type(e).__name__}"
        s["next_retry"] = now + min(3600 * 24, 300 * (2 ** min(s["failure_count"], 8)))
        st[url] = s
        _save_state(engine_id, st)
        return "failed"

    if body is None:                              # 304 — بدون تغییر
        s["retrieved_at"] = int(now * 1000)
        s["failure_count"] = 0
        st[url] = s
        _save_state(engine_id, st)
        return "unchanged"

    h = hashlib.sha256(body).hexdigest()
    changed = h != s.get("content_hash")
    st[url] = {"tier": tier, "content_hash": h, "etag": etag,
               "retrieved_at": int(now * 1000), "parser_version": PARSER_VERSION,
               "failure_count": 0, "next_retry": 0}
    _save_state(engine_id, st)

    if not changed:
        return "unchanged"

    # تغییر واقعی → DISCOVERED در دفتر Claim؛ استخراج Claim دقیق با ایجنت
    # است (فقط روی همین آیتم‌های جدید — نه هر تیک)
    from research import claim_registry
    claim_registry.new_claim(
        engine_id,
        claim=f"SOURCE_CHANGED: {url} (hash {h[:12]})",
        source_url=url, source_tier=tier)
    return "new"


def run(engines=None, fetch=None, quiet=False):
    """همهٔ منابع انجین‌های داده‌شده (پیش‌فرض: پنج انجین فاز ۱)."""
    reg = load_registry()
    rows = {e["id"]: e for e in reg["engines"]}
    results = {}
    for eid in (engines or PHASE1):
        e = rows.get(eid)
        if not e:
            continue
        for url, tier in ((e.get("primary_source"), 1),
                          (e.get("secondary_source"), 4)):
            if not url:
                continue
            r = check_source(eid, url, tier, fetch=fetch)
            results[f"{eid}:{url}"] = r
            if not quiet:
                print(f"  {eid} {r:9s} {url[:70]}")
    return results


if __name__ == "__main__":
    import sys
    eng = sys.argv[1:] or None
    out = run(engines=eng)
    from collections import Counter
    print(dict(Counter(out.values())))
