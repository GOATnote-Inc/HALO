"""Export HALO CME evidence records into a receipts-compatible attestation.

``halo.edu.attest`` already produces hash-chained CME evidence. The ``receipts``
project (GOATnote's public attestation ledger) chains rows in its ``attestation``
table by the identical primitive: ``sha256(canonical_json(payload) + prev_hash)``
with ``canonical_json = json.dumps(payload, sort_keys=True, separators=(",",":"))``.
Because the primitive is byte-identical, a HALO record can be handed to the
receipts ledger and re-chained there with no transformation of the payload — the
two ecosystems interoperate by *schema alignment*, not by a runtime import (which
the cross-repo architecture forbids).

This module produces the envelope ``receipts.ledger.MerkleLog.append`` expects
(``payload`` + ``kind`` + ``target_kind`` + a target reference) and re-exports
the shared hash primitive so callers — and a test — can verify compatibility.

Note the one intentional difference: HALO's standalone JSONL ledger uses the
genesis marker ``"genesis"``; receipts uses ``""``. Genesis is a ledger-boundary
choice, not part of the record, so it does not affect payload compatibility.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Receipts' target_kind for a person-scoped attestation node.
TARGET_KIND = "trainee"


def canonical_json(payload: Any) -> str:
    """The canonical form both ledgers hash over. Identical to receipts'."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def receipt_hash(payload: dict[str, Any], prev_hash: str) -> str:
    """The shared chain primitive: ``sha256(canonical_json(payload) + prev_hash)``.

    Mirrors ``receipts.ledger.merkle.compute_hash`` exactly; kept here so HALO
    can verify a record's receipts-side hash without importing the receipts repo.
    """
    return hashlib.sha256((canonical_json(payload) + prev_hash).encode("utf-8")).hexdigest()


def to_receipt_envelope(record: dict[str, Any]) -> dict[str, Any]:
    """Map a HALO CME record to a receipts ``MerkleLog.append`` envelope.

    ``target_id`` is intentionally omitted: it is a receipts-side foreign key the
    ledger resolves from ``target_ref`` at ingest. The ``payload`` is the HALO
    record verbatim, so its own hash chain (``record_hash`` / ``prev_hash``)
    survives as auditable content inside the receipts attestation.
    """
    return {
        "kind": record.get("type", "halo.edu.cme"),
        "target_kind": TARGET_KIND,
        "target_ref": record.get("trainee", ""),
        "payload": record,
    }
