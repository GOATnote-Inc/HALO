"""Hash-chained CME evidence records. Append-only JSONL, tamper-evident.

Each drill completion becomes one record naming the trainee, the exact
content version drilled (``<id>@v<n>+<sha>``), the score, and the critical
misses. Records chain by SHA-256 (each embeds the previous record's hash), so
an edited or deleted line breaks verification — the property a credentialing
process actually needs from self-reported training evidence.

Honest framing (rendered into every record): these are evidence records
suitable for a CME/credentialing workflow, not accredited CME credit.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from halo.edu.models import DrillResult

GENESIS = "genesis"
NOTE = "evidence record for CME/credentialing workflows; not accredited CME credit"


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _hash(record_sans_hash: dict[str, Any], prev_hash: str) -> str:
    return hashlib.sha256((_canonical(record_sans_hash) + prev_hash).encode()).hexdigest()


def make_record(
    result: DrillResult,
    *,
    trainee: str,
    prev_hash: str = GENESIS,
    when_iso: str | None = None,
) -> dict[str, Any]:
    """Build one chained record from a drill result."""
    when = when_iso or datetime.now(timezone.utc).isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "type": "halo.edu.cme",
        "trainee": trainee,
        "module_id": result.module_id,
        "content_version": result.content_version,
        "score": result.score,
        "passed": result.passed,
        "critical_misses": list(result.critical_misses),
        "grades_via": result.grades_via,
        "elapsed_s": result.elapsed_s,
        "when": when,
        "synthetic": True,
        "note": NOTE,
        "prev_hash": prev_hash,
    }
    record["record_hash"] = _hash(record, prev_hash)
    return record


def append_record(
    path: Path,
    result: DrillResult,
    *,
    trainee: str,
    when_iso: str | None = None,
) -> dict[str, Any]:
    """Append a record to the JSONL ledger, chaining from the last line."""
    prev_hash = GENESIS
    if path.exists():
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        if lines:
            prev_hash = json.loads(lines[-1])["record_hash"]
    record = make_record(result, trainee=trainee, prev_hash=prev_hash, when_iso=when_iso)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(_canonical(record) + "\n")
    return record


def verify_chain(path: Path) -> int:
    """Verify the whole ledger. Returns the record count; raises ValueError on tamper."""
    if not path.exists():
        return 0
    prev_hash = GENESIS
    count = 0
    for i, line in enumerate(path.read_text().splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        claimed = record.pop("record_hash")
        if record.get("prev_hash") != prev_hash:
            raise ValueError(f"line {i + 1}: chain break (prev_hash mismatch)")
        if _hash(record, prev_hash) != claimed:
            raise ValueError(f"line {i + 1}: record_hash mismatch — ledger edited?")
        prev_hash = claimed
        count += 1
    return count
