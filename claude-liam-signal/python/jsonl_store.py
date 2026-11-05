"""Bounded, mergeable JSONL ledgers. Keep every record, never a 100 MiB blob.

Large append-only logs are split into hash buckets beside the original file.
Each bucket rolls at 8 MiB. Plain JSONL keeps Git's existing union merge and
the repository's conflict resolver usable. Small and mutable files stay intact.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import threading

ROTATE_BYTES = 32 * 1024 * 1024
PART_BYTES = 8 * 1024 * 1024
_lock = threading.RLock()


def parts(path):
    return Path(str(path) + ".parts")


def managed(path):
    path = Path(path)
    return ((path.parent.name == "paper" and path.name == "closed.jsonl")
            or (path.parent.name == "learning" and path.name in {
                "experiences.jsonl", "positive.jsonl", "negative.jsonl"})
            or (path.name == "log.jsonl" and path.parent.parent.name == "rooms"))


def _lines(path):
    if Path(path).exists():
        with Path(path).open("rb") as stream:
            for line in stream:
                # Preserve even malformed records during storage migration.
                if line.strip():
                    yield line.rstrip(b"\r\n") + b"\n"


def _key(line):
    return hashlib.sha256(line).digest()


def _part_lines(path):
    for part in sorted(parts(path).glob("*.jsonl")):
        yield from _lines(part)


def lines(path):
    """Multiset union handles legacy logs returned by an older running job.

    Multiplicity within a ledger is retained; only overlap between the legacy
    file and its migrated parts is subtracted. This also makes a migration
    interrupted before truncation safe to retry.
    """
    overlap = Counter()
    for line in _part_lines(path):
        overlap[_key(line)] += 1
        yield line
    for line in _lines(path):
        key = _key(line)
        if overlap[key]:
            overlap[key] -= 1
        else:
            yield line


def _append_part(path, line, tails=None):
    directory = parts(path)
    directory.mkdir(parents=True, exist_ok=True)
    if len(line) > PART_BYTES:
        raise ValueError(f"single ledger record exceeds {PART_BYTES} bytes: {path}")
    bucket = hashlib.sha256(line).hexdigest()[:2]
    tail = tails.get(bucket) if tails is not None else None
    if tail is None:
        existing = sorted(directory.glob(f"{bucket}-*.jsonl"))
        tail = existing[-1] if existing else directory / f"{bucket}-000000.jsonl"
    if tail.exists() and tail.stat().st_size + len(line) > PART_BYTES:
        number = int(tail.stem.split("-")[1]) + 1
        tail = directory / f"{bucket}-{number:06d}.jsonl"
    with tail.open("ab") as stream:
        stream.write(line)
    if tails is not None:
        tails[bucket] = tail


def migrate(path, force=False):
    """Copy and verify the full legacy ledger before clearing its old blob."""
    path = Path(path)
    with _lock:
        if not path.exists() or not path.stat().st_size:
            return False
        if not (force or parts(path).exists() or path.stat().st_size >= ROTATE_BYTES):
            return False
        counts = Counter(_key(line) for line in _part_lines(path))
        expected = counts.copy()
        legacy = Counter()
        tails = {}
        for line in _lines(path):
            key = _key(line)
            legacy[key] += 1
            if counts[key]:
                counts[key] -= 1
            else:
                _append_part(path, line, tails)
        expected |= legacy
        actual = Counter(_key(line) for line in _part_lines(path))
        if actual != expected:
            raise RuntimeError(f"ledger verification failed; original retained: {path}")
        # A crash before this point leaves both copies readable without doubles.
        path.write_bytes(b"")
        return True


def append(path, record):
    path = Path(path)
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if managed(path):
            migrate(path)
        if parts(path).exists():
            _append_part(path, line)
        else:
            with path.open("ab") as stream:
                stream.write(line)


def read(path, limit=None):
    rows = []
    with _lock:
        for line in lines(path):
            try:
                rows.append(json.loads(line))
            except (ValueError, UnicodeDecodeError):
                continue  # same torn-record tolerance as the original readers
    if parts(path).exists():
        def timestamp(row):
            value = (row.get("closed") or row.get("t") or 0) if isinstance(row, dict) else 0
            return value if isinstance(value, (int, float)) else 0
        rows.sort(key=timestamp)
    return rows[-limit:] if limit else rows


_analysis_cache = {}


def analysis_read(path, limit=None):
    """Semantic paper results for analytics; read()/lines() remain lossless archival APIs."""
    path = Path(path)
    if path.parts[-3:] != ("brain", "paper", "closed.jsonl"):
        return read(path, limit)
    from copy import deepcopy
    from hamid.settled_evidence import Outcomes
    files = ([path] if path.exists() else []) + sorted(parts(path).glob("*.jsonl"))
    version = tuple((f.name,st.st_size,st.st_mtime_ns) for f in files for st in [f.stat()])
    cached = _analysis_cache.get(path)
    if cached and version == cached[0]:
        rows = cached[1]
        return deepcopy(rows[-limit:] if limit else rows)
    evidence, selected = Outcomes(), {}
    for i, line in enumerate(lines(path)):
        try:
            row = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        ident = evidence.observe(row, i)
        if ident is not None and evidence.first[ident][2] == i:
            selected[ident] = i,row
    records = [r for k,(i,r) in selected.items() if evidence.status(k,i) == "unique"]
    records.sort(key=lambda r:r.get("closed") or 0)
    _analysis_cache[path] = version,records
    return deepcopy(records[-limit:] if limit else records)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    for ledger in sorted((root / "brain").rglob("*.jsonl")):
        if managed(ledger) and migrate(ledger):
            print(f"migrated and verified: {ledger.relative_to(root)}")
