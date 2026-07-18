"""Simulation lab tests — offline: case integrity, endpoints, and the edu shim."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from halo.app import app
from halo.sim import list_cases, load_case, validate_case

client = TestClient(app)


def test_cases_load_and_validate() -> None:
    cases = list_cases()
    assert len(cases) >= 2
    assert all(c["synthetic"] and c["draft"] for c in cases)
    for meta in cases:
        validate_case(load_case(meta["id"]))  # revalidates every branch/goto/outcome


def test_io_case_has_both_endings_and_the_lesson() -> None:
    case = load_case("io_access_penetrating_abdomen")
    tones = {o["tone"] for o in case["outcomes"].values()}
    assert {"good", "bad"} <= tones
    # The fatal branch is the tibia path; the save is the humerus path.
    opts = {o["id"]: o for o in case["decisions"]["access_choice"]["options"]}
    assert opts["humerus"]["goto"] == "humerus_run"
    assert case["states"]["humerus_run"]["resolve"]["outcome"] == "survived"
    assert opts["tibia"]["goto"] == "tibia_run"
    # Tibia path teaches recognition: a rescue decision exists before the crash.
    assert opts["tibia"]["next"]["decision"] == "tibia_recognize"
    died = case["outcomes"]["died"]
    assert "tibial" in died["debrief"] or "tibia" in died["debrief"]
    assert any("humerus" in t.lower() for t in died["teaching"])


def test_organophosphate_case_staff_contamination_branch() -> None:
    case = load_case("organophosphate_decon")
    straight = next(
        o for o in case["decisions"]["door_choice"]["options"] if o["id"] == "straight_in"
    )
    assert case["states"][straight["goto"]]["sprite"]["staff_sick"] is True
    assert case["outcomes"]["survived_contaminated"]["tone"] == "warn"


def test_validation_rejects_broken_cases() -> None:
    case = load_case("io_access_penetrating_abdomen")
    broken = {**case, "decisions": {**case["decisions"]}}
    broken["decisions"]["access_choice"] = {
        "prompt": "x",
        "options": [{"id": "a", "label": "x", "goto": "not_a_state", "log": "x"}],
    }
    with pytest.raises(ValueError):
        validate_case(broken)
    unmarked = {**case, "draft": False}
    with pytest.raises(ValueError):
        validate_case(unmarked)


def test_sim_endpoints() -> None:
    assert client.get("/sim").status_code == 200
    assert "Simulation lab" in client.get("/sim").text
    cases = client.get("/sim/cases").json()["cases"]
    assert {c["id"] for c in cases} >= {
        "io_access_penetrating_abdomen",
        "organophosphate_decon",
    }
    assert client.get("/sim/cases/io_access_penetrating_abdomen").status_code == 200
    assert client.get("/sim/cases/nope").status_code == 404


def test_edu_html_shim_redirects_to_live_card() -> None:
    r = client.get("/edu/lateral_canthotomy.html", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/edu/modules/lateral_canthotomy/card"
    # And the destination actually serves.
    assert client.get("/edu/lateral_canthotomy.html").status_code == 200
