"""Simulation lab tests — offline: case integrity, endpoints, and the edu shim."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from halo.app import app
from halo.sim import list_cases, load_case, validate_case

client = TestClient(app)


def test_cases_load_and_validate() -> None:
    cases = list_cases()
    assert len(cases) >= 5
    assert all(c["synthetic"] and c["draft"] for c in cases)
    for meta in cases:
        validate_case(load_case(meta["id"]))  # revalidates every branch/goto/outcome


def test_every_case_is_evidence_based_and_cme_structured() -> None:
    for meta in list_cases():
        case = load_case(meta["id"])
        assert case["references"], meta["id"]
        for ref in case["references"]:
            assert ref["citation"] and ref["note"]
        cme = case["cme"]
        assert cme["audiences"] == ["physician", "nursing", "ems"]
        for role in ("physician", "nursing", "ems"):
            assert len(cme["objectives"][role]) >= 2, (meta["id"], role)
        assert "not accredited" in cme["note"].lower()


def test_organophosphate_presents_crashing() -> None:
    case = load_case("organophosphate_decon")
    start = case["states"][case["start"]["state"]]
    assert start["vitals"]["spo2"] <= 84
    assert start["vitals"]["hr"] <= 50
    assert start["drift"]["spo2"] <= -1.0  # untreated trajectory visibly deteriorates
    # The oxime/paralytic teaching exists: rocuronium correct, succinylcholine consequences.
    text = str(case["decisions"]) + str(case["outcomes"])
    assert "rocuronium" in text.lower()
    assert "succinylcholine" in text.lower()
    assert any(
        "2-PAM" in str(o) or "pralidoxime" in str(o).lower() for o in case["outcomes"].values()
    )


def test_io_case_shows_landmark_diagrams() -> None:
    case = load_case("io_access_penetrating_abdomen")
    assert case["decisions"]["access_choice"]["diagram"] == ["io_humerus", "io_tibia"]
    assert case["decisions"]["tibia_recognize"]["diagram"] == "io_humerus"


def test_new_cases_link_their_readiness_cards() -> None:
    expected = {
        "organophosphate_decon": "organophosphate",
        "perimortem_cesarean": "perimortem_cesarean",
        "lateral_canthotomy": "lateral_canthotomy",
        "breech_delivery": "breech_delivery",
    }
    for case_id, module in expected.items():
        assert load_case(case_id)["edu_module"] == module


def test_diagram_templates_exist_for_every_referenced_diagram() -> None:
    html = client.get("/sim").text
    referenced: set[str] = set()
    for meta in list_cases():
        for decision in load_case(meta["id"])["decisions"].values():
            d = decision.get("diagram")
            if isinstance(d, str):
                referenced.add(d)
            elif isinstance(d, list):
                referenced.update(d)
    assert referenced  # diagrams are actually in use
    for name in referenced:
        assert f'id="dg-{name}"' in html, name


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
