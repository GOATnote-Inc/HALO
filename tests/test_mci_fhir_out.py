"""FHIR write-back bundle tests — offline, deterministic."""

from __future__ import annotations

from typing import Any

from halo.mci.fhir_out import SALT_SYSTEM, triage_bundle
from halo.mci.models import Observations
from halo.mci.triage import salt_triage

OBS = Observations(
    breathing=True,
    obeys_commands=True,
    peripheral_pulse=True,
    respiratory_rate=38,
    major_hemorrhage_uncontrolled=False,
)
EVIDENCE = {"breathing": "breathing on own", "peripheral_pulse": "radial present"}


def _bundle() -> dict[str, Any]:
    result = salt_triage(OBS)
    return triage_bundle(OBS, result, incident_date="2026-07-18", evidence=EVIDENCE)


def test_bundle_shape() -> None:
    bundle = _bundle()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) == 1


def test_observation_is_preliminary_on_alias() -> None:
    obs = _bundle()["entry"][0]["resource"]
    assert obs["resourceType"] == "Observation"
    # Door triage — physician secondary triage supersedes.
    assert obs["status"] == "preliminary"
    # Targets the MCI alias record, never an unconfirmed identity.
    assert "alias" in obs["subject"]["display"].lower()
    assert obs["valueCodeableConcept"]["coding"][0]["system"] == SALT_SYSTEM
    assert obs["valueCodeableConcept"]["coding"][0]["code"] == "immediate"


def test_respiratory_rate_is_loinc_coded() -> None:
    obs = _bundle()["entry"][0]["resource"]
    rr = [
        c
        for c in obs["component"]
        if c["code"].get("coding", [{}])[0].get("system") == "http://loinc.org"
    ]
    assert len(rr) == 1
    assert rr[0]["code"]["coding"][0]["code"] == "9279-1"
    assert rr[0]["valueQuantity"]["value"] == 38


def test_evidence_quotes_ride_as_extensions() -> None:
    obs = _bundle()["entry"][0]["resource"]
    quoted = [
        c
        for c in obs["component"]
        if any("evidence-quote" in e["url"] for e in c.get("extension", []))
    ]
    assert len(quoted) == len(EVIDENCE)


def test_undocumented_fields_are_omitted_not_fabricated() -> None:
    obs = _bundle()["entry"][0]["resource"]
    names = [c["code"].get("text") for c in obs["component"]]
    assert "minor injuries only" not in names  # None -> omitted entirely


def test_derivation_recorded_in_notes() -> None:
    obs = _bundle()["entry"][0]["resource"]
    assert any("Derived:" in n["text"] for n in obs["note"])


def test_no_narrative_bloat() -> None:
    """The anti-bloat contract: no narrative text block, only coded structure."""
    obs = _bundle()["entry"][0]["resource"]
    assert "text" not in obs  # no Observation.text narrative
    assert all(len(n["text"]) < 300 for n in obs["note"])
