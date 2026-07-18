"""API surface tests — offline (no Claude calls on these routes)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from halo.app import app

client = TestClient(app)


def test_ui_served_at_root() -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "HALO" in body
    assert "Synthetic data" in body
    assert "not a medical device" in body
    assert "Track board" in body and "Door triage" in body


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_scenarios_endpoint() -> None:
    r = client.get("/mci/scenarios")
    assert r.status_code == 200
    scenarios = r.json()["scenarios"]
    assert len(scenarios) == 6
    assert all(s["synthetic"] is True for s in scenarios)
    assert all(s["note"] and s["title"] and s["pattern"] for s in scenarios)


def test_census_endpoint_offline() -> None:
    r = client.get("/mci/census")
    assert r.status_code == 200
    data = r.json()
    assert data["occupied"] == 23
    assert data["open_beds"] == 7
    assert data["synthetic_only"] is True
    assert all("surge" not in row for row in data["rows"])


def test_surge_endpoint_offline_and_deterministic() -> None:
    r = client.post("/mci/surge")
    assert r.status_code == 200
    data = r.json()
    assert data["freed_now"] == 17
    assert data["freed_by_admission_pull"] == 4
    assert data["held"] == 2
    assert all("surge" in row for row in data["rows"])
    # Deterministic: a second run returns the identical plan.
    assert client.post("/mci/surge").json() == data


def test_triage_observations_offline() -> None:
    r = client.post(
        "/mci/triage/observations",
        json={"observations": {"breathing": False}},
    )
    assert r.status_code == 200
    assert r.json()["category"] == "dead"


def test_triage_observations_fails_closed_on_empty() -> None:
    r = client.post("/mci/triage/observations", json={"observations": {}})
    assert r.status_code == 200
    payload = r.json()
    assert payload["category"] == "unable_to_triage"
    assert "breathing" in payload["missing_fields"]


def test_triage_observations_rejects_unknown_field() -> None:
    r = client.post(
        "/mci/triage/observations",
        json={"observations": {"not_a_field": True}},
    )
    assert r.status_code == 422


def test_expectant_requires_explicit_human_flag_via_api() -> None:
    obs = {
        "breathing": True,
        "obeys_commands": False,
        "peripheral_pulse": False,
        "respiratory_distress": True,
        "major_hemorrhage_uncontrolled": True,
    }
    without = client.post("/mci/triage/observations", json={"observations": obs}).json()
    assert without["category"] == "immediate"
    with_flag = client.post(
        "/mci/triage/observations",
        json={"observations": obs, "likely_survivable": False},
    ).json()
    assert with_flag["category"] == "expectant"
