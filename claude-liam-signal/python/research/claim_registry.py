"""دفتر Claim — مسیر اجباری دانش، بدون میان‌بر.

هر یافته (از کتاب، مقاله، مستندات، X، GitHub…) اول Claim می‌شود و فقط
پله‌پله بالا می‌رود:

  DISCOVERED → SOURCE_VERIFIED → CLAIM_EXTRACTED → HYPOTHESIS
  → BACKTESTED → WALK_FORWARD_VALIDATED → PAPER_VALIDATED
  → SHADOW_VALIDATED → PRODUCTION_VALIDATED

قوانین سخت (سند حمید):
- پرش از پله ممنوع — BACKTESTED نمی‌تواند یک‌باره PRODUCTION شود.
- هر گذار evidence می‌خواهد؛ گذار بی‌مدرک برنمی‌گردد بلکه TypeError نیست،
  ValueError صریح است.
- REJECTED هم ذخیره می‌شود تا دوباره تکرار نشود (قانون ۱۲).
- هیچ رکوردی حذف نمی‌شود — append-only؛ آخرین رکورد هر claim_id حاکم است.

فایل‌ها: brain/research/{engine}/findings.jsonl و rejected.jsonl
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "brain" / "research"

PIPELINE = ["DISCOVERED", "SOURCE_VERIFIED", "CLAIM_EXTRACTED", "HYPOTHESIS",
            "BACKTESTED", "WALK_FORWARD_VALIDATED", "PAPER_VALIDATED",
            "SHADOW_VALIDATED", "PRODUCTION_VALIDATED"]
TERMINAL = {"REJECTED", "SUPERSEDED"}

SOURCE_TIERS = {1: "official", 2: "peer_reviewed", 3: "preprint",
                4: "aggregator", 5: "lead_only"}


def _dir(engine_id):
    d = RESEARCH / engine_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load(engine_id):
    """آخرین وضعیت هر claim — append-only، آخرین رکورد حاکم است."""
    out = {}
    for name in ("findings.jsonl", "rejected.jsonl"):
        p = _dir(engine_id) / name
        if not p.exists():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                out[r["claim_id"]] = r
    return out


def new_claim(engine_id, claim, source_url, source_tier, retrieved_at=None):
    """ثبت یافتهٔ تازه — همیشه از DISCOVERED شروع می‌شود، بدون استثنا."""
    if source_tier not in SOURCE_TIERS:
        raise ValueError(f"tier نامعتبر: {source_tier} (۱ تا ۵)")
    if not claim or not source_url:
        raise ValueError("claim و source_url اجباری‌اند — یافتهٔ بی‌منبع ثبت نمی‌شود")
    row = {
        "claim_id": uuid.uuid4().hex[:12],
        "engine_id": engine_id,
        "claim": claim,
        "source_url": source_url,
        "source_tier": source_tier,
        "source_type": SOURCE_TIERS[source_tier],
        "retrieved_at": retrieved_at or int(time.time() * 1000),
        "status": "DISCOVERED",
        "history": [{"to": "DISCOVERED", "at": int(time.time() * 1000)}],
        "evidence_ids": [],
    }
    _append(_dir(engine_id) / "findings.jsonl", row)
    return row


def advance(engine_id, claim_row, to_status, evidence=None, note=None):
    """یک پله جلو، یا REJECTED/SUPERSEDED. پرش ممنوع.

    Tier 5 (X/کامیونیتی) بدون SOURCE_VERIFIED واقعی جلوتر نمی‌رود —
    «هرگز fact بدون راستی‌آزمایی».
    """
    cur = claim_row["status"]
    if cur in TERMINAL:
        raise ValueError(f"claim در وضعیت پایانی {cur} است — گذار ممنوع")

    if to_status in TERMINAL:
        if not note:
            raise ValueError(f"{to_status} بدون علت ثبت نمی‌شود — تا تکرار نشود باید بدانیم چرا")
    else:
        i, j = PIPELINE.index(cur), PIPELINE.index(to_status)
        if j != i + 1:
            raise ValueError(f"پرش از {cur} به {to_status} ممنوع — مسیر پله‌پله است")
        if j >= PIPELINE.index("HYPOTHESIS") and not (evidence or claim_row.get("evidence_ids")):
            raise ValueError(f"گذار به {to_status} بدون evidence ممنوع")
        if claim_row.get("source_tier") == 5 and j > PIPELINE.index("SOURCE_VERIFIED") \
                and not any("verify" in str(e).lower() for e in claim_row.get("evidence_ids", []) + ([evidence] if evidence else [])):
            raise ValueError("منبع Tier 5 فقط سرنخ است — بدون evidence راستی‌آزمایی (verify:...) جلو نمی‌رود")

    row = dict(claim_row)
    row["status"] = to_status
    row["history"] = claim_row.get("history", []) + [
        {"to": to_status, "at": int(time.time() * 1000),
         **({"note": note} if note else {})}]
    if evidence:
        row["evidence_ids"] = claim_row.get("evidence_ids", []) + [evidence]
    dest = "rejected.jsonl" if to_status == "REJECTED" else "findings.jsonl"
    _append(_dir(engine_id) / dest, row)
    return row
