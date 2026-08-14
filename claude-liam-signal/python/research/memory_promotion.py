"""دروازهٔ حافظهٔ مرجع — فقط E21، فقط با مدرک کافی.

قانون ۵ سند حمید: «فقط E21 Memory Curator حق Promotion به Canonical
Memory دارد.» و معیار Canonical:
  منبع/citation مشخص · قابل بازتولید · OOS و Regime Split ·
  CI و Effect Size · تعارض‌ها ثبت · نسخهٔ استراتژی مشخص ·
  expiry/recheck مشخص · تک‌نمونه‌ای نباشد

نسخهٔ قبلی حذف نمی‌شود — SUPERSEDED می‌گیرد و می‌ماند.

جدا از brain/memory/lessons.json فعلی است: آن لایهٔ ۲ (تجربی) است و
دست‌نخورده می‌ماند؛ این لایهٔ مرجعِ نسخه‌دار با استاندارد بالاتر است.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANONICAL = ROOT / "brain" / "memory" / "canonical" / "lessons.jsonl"
PRIVATE = ROOT / "brain" / "memory" / "private"

MIN_SAMPLE = 30          # کف نمونه — تک‌نمونه و ده‌نمونه «درس مرجع» نیست
ALLOWED_STATUS = {"PAPER_VALIDATED", "SHADOW_VALIDATED", "PRODUCTION_VALIDATED"}


class PromotionRefused(ValueError):
    """رد ارتقا — پیامش دقیقاً می‌گوید چه مدرکی کم است."""


def _check(lesson):
    missing = []
    if not lesson.get("claim"):
        missing.append("claim")
    if not lesson.get("source_url"):
        missing.append("source_url")
    if not lesson.get("experiment_id"):
        missing.append("experiment_id (قابل بازتولید نیست)")
    if not lesson.get("dataset_snapshot_id"):
        missing.append("dataset_snapshot_id (دادهٔ آزمایش قابل بازتولید نیست)")
    if not lesson.get("strategy_version"):
        missing.append("strategy_version")
    if (lesson.get("sample_size") or 0) < MIN_SAMPLE:
        missing.append(f"sample_size ≥ {MIN_SAMPLE} (فعلی: {lesson.get('sample_size')})")
    ci = lesson.get("confidence_interval")
    if not ci or len(ci) != 2:
        missing.append("confidence_interval")
    elif ci[0] <= 0 <= ci[1]:
        missing.append(f"CI صفر را در بر می‌گیرد {ci} — قانون LIAM: اثر اثبات‌نشده ارتقا نمی‌گیرد")
    if lesson.get("status") not in ALLOWED_STATUS:
        missing.append(f"status باید حداقل PAPER_VALIDATED باشد (فعلی: {lesson.get('status')})")
    if lesson.get("regime") is None:
        missing.append("regime (بدون regime split نتیجه قابل‌تعمیم نیست)")
    if "conflicts" not in lesson:
        missing.append("conflicts (حتی اگر خالی — باید صریح بررسی شده باشد)")
    if "expires_at" not in lesson:
        missing.append("expires_at (حتی null — بازبینی باید تعریف شده باشد)")
    return missing


def load_canonical():
    if not CANONICAL.exists():
        return []
    return [json.loads(l) for l in CANONICAL.read_text(encoding="utf-8").splitlines() if l.strip()]


def promote(lesson, actor):
    """ارتقا به حافظهٔ مرجع. فقط E21؛ هر کمبود مدرک، با نامش رد می‌شود."""
    if actor != "E21":
        raise PromotionRefused(
            f"فقط E21 Memory Curator حق ارتقا دارد — {actor} نمی‌تواند (قانون ۵)")
    missing = _check(lesson)
    if missing:
        raise PromotionRefused("ارتقا رد شد، مدرک کم است: " + "؛ ".join(missing))

    row = dict(lesson)
    row["lesson_id"] = row.get("lesson_id") or uuid.uuid4().hex[:12]
    row["promoted_at"] = int(time.time() * 1000)
    row["promoted_by"] = "E21"

    # هم‌موضوع قدیمی حذف نمی‌شود — SUPERSEDED می‌گیرد و در تاریخ می‌ماند
    superseded = []
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    if row.get("supersedes"):
        for old in load_canonical():
            if old["lesson_id"] == row["supersedes"] and old.get("status") != "SUPERSEDED":
                old2 = dict(old)
                old2["status"] = "SUPERSEDED"
                old2["superseded_by"] = row["lesson_id"]
                old2["superseded_at"] = row["promoted_at"]
                with open(CANONICAL, "a", encoding="utf-8") as f:
                    f.write(json.dumps(old2, ensure_ascii=False) + "\n")
                superseded.append(old["lesson_id"])

    with open(CANONICAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row, superseded


def private_note(engine_id, note):
    """حافظهٔ خصوصی انجین — بدون دروازه، ولی جدا از مرجع و جدا از تولید."""
    d = PRIVATE / engine_id
    d.mkdir(parents=True, exist_ok=True)
    row = {"at": int(time.time() * 1000), "engine_id": engine_id, "note": note}
    with open(d / "notes.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row
