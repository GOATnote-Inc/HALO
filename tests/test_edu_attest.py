"""CME attestation ledger tests — the chain must catch edits, not just look official."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from halo.edu import get_module
from halo.edu.attest import GENESIS, append_record, make_record, verify_chain
from halo.edu.drill import run_drill
from tests.test_edu_drill import OP_PERFECT

OP = get_module("organophosphate")
RESULT = run_drill(OP, OP_PERFECT, trainee="dr-test", elapsed_s=240.0)


def test_record_shape_and_versioned_content() -> None:
    record = make_record(RESULT, trainee="dr-test", when_iso="2026-07-18T20:00:00+00:00")
    assert record["type"] == "halo.edu.cme"
    assert record["content_version"].startswith("organophosphate@v1+")
    assert record["passed"] is True
    assert record["synthetic"] is True
    assert "not accredited" in record["note"]
    assert record["prev_hash"] == GENESIS
    assert len(record["record_hash"]) == 64


def test_record_hash_is_deterministic() -> None:
    a = make_record(RESULT, trainee="dr-test", when_iso="2026-07-18T20:00:00+00:00")
    b = make_record(RESULT, trainee="dr-test", when_iso="2026-07-18T20:00:00+00:00")
    assert a["record_hash"] == b["record_hash"]


def test_append_chains_and_verifies(tmp_path: Path) -> None:
    ledger = tmp_path / "cme.jsonl"
    first = append_record(ledger, RESULT, trainee="dr-a", when_iso="2026-07-18T20:00:00+00:00")
    second = append_record(ledger, RESULT, trainee="dr-b", when_iso="2026-07-18T20:05:00+00:00")
    assert second["prev_hash"] == first["record_hash"]
    assert verify_chain(ledger) == 2


def test_edited_ledger_fails_verification(tmp_path: Path) -> None:
    ledger = tmp_path / "cme.jsonl"
    append_record(ledger, RESULT, trainee="dr-a", when_iso="2026-07-18T20:00:00+00:00")
    append_record(ledger, RESULT, trainee="dr-b", when_iso="2026-07-18T20:05:00+00:00")
    lines = ledger.read_text().splitlines()
    doctored = json.loads(lines[0])
    assert doctored["trainee"] == "dr-a"
    doctored["trainee"] = "dr-impostor"  # claim someone else's completion
    lines[0] = json.dumps(doctored, sort_keys=True, separators=(",", ":"))
    ledger.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="line 1"):
        verify_chain(ledger)


def test_deleted_line_breaks_chain(tmp_path: Path) -> None:
    ledger = tmp_path / "cme.jsonl"
    append_record(ledger, RESULT, trainee="dr-a", when_iso="2026-07-18T20:00:00+00:00")
    append_record(ledger, RESULT, trainee="dr-b", when_iso="2026-07-18T20:05:00+00:00")
    lines = ledger.read_text().splitlines()
    ledger.write_text(lines[1] + "\n")  # drop the first record
    with pytest.raises(ValueError, match="chain break"):
        verify_chain(ledger)


def test_missing_ledger_is_zero_records(tmp_path: Path) -> None:
    assert verify_chain(tmp_path / "absent.jsonl") == 0
