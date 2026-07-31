"""Receipts interop: HALO CME records map onto the receipts attestation chain."""

from __future__ import annotations

import hashlib
import json

from halo.edu.attest import make_record
from halo.edu.models import DrillResult
from halo.edu.receipts_export import (
    canonical_json,
    receipt_hash,
    to_receipt_envelope,
)


def _record() -> dict:
    result = DrillResult(
        module_id="organophosphate",
        content_version="organophosphate@v1+abc123",
        grades=(),
        score=1.0,
        critical_misses=(),
        passed=True,
        elapsed_s=42.0,
        grades_via="keyword",
    )
    return make_record(result, trainee="synthetic-trainee", when_iso="2026-07-30T00:00:00+00:00")


def test_envelope_shape_matches_merkle_append() -> None:
    env = to_receipt_envelope(_record())
    # Keys receipts.ledger.MerkleLog.append consumes (target_id resolved ledger-side).
    assert set(env) == {"kind", "target_kind", "target_ref", "payload"}
    assert env["kind"] == "halo.edu.cme"
    assert env["target_kind"] == "trainee"
    assert env["target_ref"] == "synthetic-trainee"
    assert env["payload"]["module_id"] == "organophosphate"


def test_hash_primitive_is_byte_identical_to_receipts() -> None:
    # Reproduce receipts.ledger.merkle.compute_hash inline (no cross-repo import)
    # and assert our re-export matches it exactly for the same payload + prev.
    payload = {"b": 2, "a": 1}
    prev = "deadbeef"

    def receipts_compute_hash(p: dict, prev_hash: str) -> str:
        blob = (json.dumps(p, sort_keys=True, separators=(",", ":")) + prev_hash).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    assert receipt_hash(payload, prev) == receipts_compute_hash(payload, prev)


def test_canonical_json_is_sorted_and_compact() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_payload_preserves_halo_chain() -> None:
    record = _record()
    env = to_receipt_envelope(record)
    # HALO's own record_hash / prev_hash ride along inside the receipts payload.
    assert env["payload"]["record_hash"] == record["record_hash"]
    assert env["payload"]["prev_hash"] == record["prev_hash"]
