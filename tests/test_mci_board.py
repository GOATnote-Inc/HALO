"""Interactive board lifecycle tests — offline, exercised through the API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from halo.app import app
from halo.mci.panel import load_panel

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_board():
    client.post("/mci/board/reset")
    yield
    client.post("/mci/board/reset")


def _assess() -> dict:
    return client.post("/mci/board/assess").json()


def _act(bed: str, action: str):
    return client.post("/mci/board/action", json={"bed": bed, "action": action})


def test_initial_state() -> None:
    s = client.get("/mci/board").json()
    assert s["occupied"] == 23 and s["open_beds"] == 7
    assert s["assessed"] is False
    assert all(row["mrn"] for row in s["beds"])


def test_mrns_are_unique_and_derived_from_fhir_ids() -> None:
    panel = load_panel()
    mrns = {p.mrn for p in panel}
    assert len(mrns) == len(panel)  # no collisions across the 25 patients
    for p in panel:
        assert p.mrn == p.patient_id.replace("-", "")[:8].upper()


def test_actions_refused_before_assessment() -> None:
    r = _act("C03", "discharge")
    assert r.status_code == 409
    assert "assessment" in r.json()["detail"]


def test_discharge_frees_bed_and_logs() -> None:
    _assess()
    s = _act("C03", "discharge").json()
    assert s["occupied"] == 22 and s["open_beds"] == 8
    assert s["departed"] == 1
    assert s["departed_entries"][0]["disposition"] == "discharged"
    assert any("discharged" in line for line in s["activity"])


def test_hold_bed_refuses_discharge_with_rationale() -> None:
    _assess()
    r = _act("A05", "discharge")  # rule-out ACS on monitor — classified HOLD
    assert r.status_code == 409
    assert "bedside re-assessment" in r.json()["detail"].lower()


def test_chairs_flow_and_discharge_from_chairs() -> None:
    _assess()
    s = _act("B01", "to_chairs").json()
    assert s["in_chairs"] == 1 and s["open_beds"] == 8
    assert s["chairs"][0]["name"].endswith("Kuhic")
    s = _act("B01", "discharge").json()  # discharge from chairs is the natural exit
    assert s["in_chairs"] == 0 and s["departed"] == 1


def test_expedite_admit_is_two_phase() -> None:
    _assess()
    r = _act("A01", "assign_bed")  # cannot transport before the pull is escalated
    assert r.status_code == 409
    s = _act("A01", "escalate_pull").json()
    assert s["awaiting_pull"] == 1
    assert s["occupied"] == 23  # bed still occupied until the floor pulls
    s = _act("A01", "assign_bed").json()
    assert s["occupied"] == 22 and s["departed"] == 1
    assert s["departed_entries"][0]["disposition"] == "admitted"


def test_undo_restores_prior_state() -> None:
    _assess()
    _act("C03", "discharge")
    s = client.post("/mci/board/undo").json()
    assert s["occupied"] == 23 and s["departed"] == 0
    assert any(row["bed"] == "C03" for row in s["beds"])


def test_reset_restores_declared_moment() -> None:
    _assess()
    _act("C03", "discharge")
    _act("B01", "to_chairs")
    s = client.post("/mci/board/reset").json()
    assert s == client.get("/mci/board").json()
    assert s["occupied"] == 23 and s["assessed"] is False and s["activity"] == []


def test_unknown_bed_and_action() -> None:
    _assess()
    assert _act("Z99", "discharge").status_code == 404
    assert _act("C03", "teleport").status_code == 422
