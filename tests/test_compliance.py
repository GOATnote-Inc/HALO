"""Compliance (legal) agent tests — offline: rules integrity + the verification layer."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from halo import llm
from halo.app import app
from halo.mci import compliance as comp
from halo.mci.board import BOARD

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_board():
    BOARD.reset()
    yield
    BOARD.reset()


def test_rules_are_cited_and_unique() -> None:
    ids = [r["rule_id"] for r in comp.RULES]
    assert len(ids) == len(set(ids))
    for rule in comp.RULES:
        assert rule["text"] and rule["basis"]
    assert any("EMTALA" in r["basis"] for r in comp.RULES)
    assert any("Crisis Standards" in r["basis"] for r in comp.RULES)


def _stub_agent(monkeypatch: pytest.MonkeyPatch, findings: list[dict], summary: str) -> None:
    def fake_agent_loop(prompt: str, tools: list[Any], **_kw: Any) -> tuple[str, list[dict]]:
        report = next(t for t in tools if t.name == "report_findings")
        report.call({"findings_json": json.dumps(findings), "summary": summary})
        return "done", [{"tool": "report_findings", "input": {}}]

    monkeypatch.setattr(llm, "agent_loop", fake_agent_loop)


def test_verified_findings_pass_through(monkeypatch: pytest.MonkeyPatch) -> None:
    BOARD.assess()
    real_line = BOARD.events[-1].text  # the assessment log line
    _stub_agent(
        monkeypatch,
        [
            {
                "rule_id": "R4-AUDIT-TRAIL",
                "status": "pass",
                "evidence": real_line,
                "recommendation": "Continue logging every transition.",
            }
        ],
        "Board is compliant.",
    )
    out = comp.run_compliance_review()
    assert out["summary"] == "Board is compliant."
    assert len(out["findings"]) == 1
    assert out["findings"][0]["basis"].startswith("IOM")
    assert out["dropped_unverified"] == 0


def test_fabricated_evidence_is_dropped_and_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_agent(
        monkeypatch,
        [
            {
                "rule_id": "R1-EMTALA-MSE",
                "status": "flag",
                "evidence": "T+999 PATIENT X: discharged without screening.",  # not in log
                "recommendation": "x",
            },
            {
                "rule_id": "R9-INVENTED",  # unknown rule
                "status": "flag",
                "evidence": "anything",
                "recommendation": "x",
            },
        ],
        "s",
    )
    out = comp.run_compliance_review()
    assert out["findings"] == []
    assert out["dropped_unverified"] == 2  # honesty counter, never hidden


def test_snapshot_evidence_is_verifiable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Quotes from the board snapshot (not just the log) also count as evidence.
    BOARD.waiting_triage("W07", "minimal")
    _stub_agent(
        monkeypatch,
        [
            {
                "rule_id": "R1-EMTALA-MSE",
                "status": "monitor",
                "evidence": '"category": "minimal"',
                "recommendation": "Complete screening for remaining untriaged arrivals.",
            }
        ],
        "s",
    )
    out = comp.run_compliance_review()
    assert len(out["findings"]) == 1


def test_endpoint_fails_closed_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any):
        raise llm.LLMFailure("refusal")

    monkeypatch.setattr(llm, "agent_loop", boom)
    r = client.post("/mci/compliance")
    assert r.status_code == 502
    assert "failed closed" in r.json()["detail"]
