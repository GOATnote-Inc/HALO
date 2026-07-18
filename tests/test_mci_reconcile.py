"""Reconciliation tests — offline. Claude calls are stubbed; the safety boundary
(re-verification of agent proposals) is exercised directly."""

from __future__ import annotations

from typing import Any

import pytest

from halo import llm
from halo.mci import reconcile as rec
from halo.mci.panel import IdentityCues, load_panel

ON_DATE = "2026-07-18"


def _stub_cues(monkeypatch: pytest.MonkeyPatch, cues: IdentityCues) -> None:
    monkeypatch.setattr(rec, "extract_cues", lambda _note: cues)


def _stub_agent(
    monkeypatch: pytest.MonkeyPatch, proposed_ids: list[str], rationale: str = "r"
) -> None:
    def fake_agent_loop(prompt: str, tools: list[Any], **_kw: Any) -> tuple[str, list[dict]]:
        propose = next(t for t in tools if t.name == "propose_candidates")
        propose.call({"candidate_patient_ids": proposed_ids, "rationale": rationale})
        return "done", [{"tool": "propose_candidates", "input": {}}]

    monkeypatch.setattr(llm, "agent_loop", fake_agent_loop)


def test_strong_deterministic_match_skips_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_cues(
        monkeypatch,
        IdentityCues(
            family_name="Wilkinson", given_name="Latoyia", gender="female", approximate_age=81
        ),
    )

    def boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("agent must not run on a strong deterministic match")

    monkeypatch.setattr(llm, "agent_loop", boom)
    result = rec.reconcile("note", on_date=ON_DATE)
    assert result.status == "strong_candidate"
    assert result.method == "deterministic"


def test_no_identity_content_skips_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_cues(monkeypatch, IdentityCues())
    result = rec.reconcile("note", on_date=ON_DATE)
    assert result.status == "no_match"
    assert result.method == "deterministic"
    assert result.candidates == ()


def test_agent_proposals_are_verified_and_capped_at_possible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = load_panel()
    macejkovic = next(p for p in panel if p.family_name == "Macejkovic")
    # Garbled name: deterministic scoring alone is inconclusive.
    _stub_cues(monkeypatch, IdentityCues(family_name="Masikovich", gender="male"))
    _stub_agent(monkeypatch, [macejkovic.patient_id, "hallucinated-id-123"])
    result = rec.reconcile("note", on_date=ON_DATE)
    assert result.method == "agent"
    assert result.status == "possible"  # never strong via agent
    ids = {c.patient.patient_id for c in result.candidates}
    assert macejkovic.patient_id in ids
    assert "hallucinated-id-123" not in ids
    assert macejkovic.patient_id in result.agent_rationales


def test_agent_gender_mismatch_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = load_panel()
    thiel = next(p for p in panel if p.family_name == "Thiel")  # female
    _stub_cues(monkeypatch, IdentityCues(family_name="Teal", gender="male"))
    _stub_agent(monkeypatch, [thiel.patient_id])
    result = rec.reconcile("note", on_date=ON_DATE)
    assert all(c.patient.patient_id != thiel.patient_id for c in result.candidates)
    assert result.status == "no_match"


def test_agent_empty_proposal_is_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_cues(monkeypatch, IdentityCues(family_name="Zzyzx", gender="male"))
    _stub_agent(monkeypatch, [])
    result = rec.reconcile("note", on_date=ON_DATE)
    assert result.status == "no_match"
    assert result.method == "agent"
