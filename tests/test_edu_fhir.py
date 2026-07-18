"""FHIR seam tests — synthetic bundle in, dosing context out; session in, draft docs out."""

from __future__ import annotations

from datetime import date
from typing import Any

from halo.edu import DoseStatus, PatientContext, get_module
from halo.edu.dosing import dose_all
from halo.edu.fhir import draft_bundle, patient_context_from_bundle

ON_DATE = date(2026, 7, 18)


def _bundle(*resources: dict[str, Any]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "synthetic": True,
        "entry": [{"resource": r} for r in resources],
    }


CHILD_PATIENT = {
    "resourceType": "Patient",
    "id": "synthetic-child",
    "gender": "female",
    "birthDate": "2020-07-18",  # 6 years old on ON_DATE
}

WEIGHT_22KG = {
    "resourceType": "Observation",
    "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7"}]},
    "valueQuantity": {"value": 22, "unit": "kg"},
    "effectiveDateTime": "2026-07-18T11:00:00Z",
}


class TestInbound:
    def test_child_context_extracted(self) -> None:
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, WEIGHT_22KG), on_date=ON_DATE)
        assert ctx.weight_kg == 22
        assert ctx.age_years == 6.0
        assert ctx.sex == "female"
        assert ctx.pregnant is None

    def test_weight_units_converted(self) -> None:
        grams = dict(WEIGHT_22KG, valueQuantity={"value": 22000, "unit": "g"})
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, grams), on_date=ON_DATE)
        assert ctx.weight_kg == 22.0
        pounds = dict(WEIGHT_22KG, valueQuantity={"value": 100, "unit": "[lb_av]"})
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, pounds), on_date=ON_DATE)
        assert ctx.weight_kg is not None and abs(ctx.weight_kg - 45.36) < 0.01

    def test_unknown_weight_unit_yields_none_not_a_guess(self) -> None:
        stones = dict(WEIGHT_22KG, valueQuantity={"value": 5, "unit": "stone"})
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, stones), on_date=ON_DATE)
        assert ctx.weight_kg is None

    def test_latest_weight_wins(self) -> None:
        old = dict(WEIGHT_22KG, valueQuantity={"value": 18, "unit": "kg"})
        old["effectiveDateTime"] = "2025-01-01T00:00:00Z"
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, old, WEIGHT_22KG), on_date=ON_DATE)
        assert ctx.weight_kg == 22

    def test_pregnancy_status_extracted(self) -> None:
        pregnant_obs = {
            "resourceType": "Observation",
            "code": {"coding": [{"code": "82810-3"}]},
            "valueCodeableConcept": {"coding": [{"code": "LA15173-0"}]},
        }
        adult = {"resourceType": "Patient", "gender": "female", "birthDate": "1994-03-02"}
        ctx = patient_context_from_bundle(_bundle(adult, pregnant_obs), on_date=ON_DATE)
        assert ctx.pregnant is True

    def test_allergies_extracted(self) -> None:
        allergy = {"resourceType": "AllergyIntolerance", "code": {"text": "sulfa"}}
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, allergy), on_date=ON_DATE)
        assert ctx.allergies == ("sulfa",)

    def test_empty_bundle_yields_empty_context(self) -> None:
        ctx = patient_context_from_bundle(_bundle(), on_date=ON_DATE)
        assert ctx == PatientContext()

    def test_malformed_entries_are_skipped_not_fatal(self) -> None:
        bundle = {
            "resourceType": "Bundle",
            "synthetic": True,
            "entry": ["garbage", 42, {"resource": "also garbage"}, {"resource": WEIGHT_22KG}],
        }
        ctx = patient_context_from_bundle(bundle, on_date=ON_DATE)
        assert ctx.weight_kg == 22  # the one valid resource still counts

    def test_non_list_entry_is_empty_context(self) -> None:
        ctx = patient_context_from_bundle({"entry": "not-a-list"}, on_date=ON_DATE)
        assert ctx == PatientContext()

    def test_future_birthdate_yields_no_age(self) -> None:
        unborn = {"resourceType": "Patient", "birthDate": "2030-01-01"}
        ctx = patient_context_from_bundle(_bundle(unborn, WEIGHT_22KG), on_date=ON_DATE)
        assert ctx.age_years is None  # bad data is not an age; dosing decides by weight


class TestBundleToBedside:
    """The integration the module exists for: EHR bundle -> computed peds antidotes."""

    def test_child_op_doses_computed_from_bundle(self) -> None:
        ctx = patient_context_from_bundle(_bundle(CHILD_PATIENT, WEIGHT_22KG), on_date=ON_DATE)
        results = {r.med: r for r in dose_all(get_module("organophosphate"), ctx)}
        assert results["Atropine"].text.startswith("1.1 mg")
        assert results["Pralidoxime (2-PAM)"].text.startswith("550 mg")
        assert results["Midazolam"].text.startswith("4.5 mg")


class TestOutbound:
    def test_draft_bundle_shape(self) -> None:
        module = get_module("organophosphate")
        ctx = PatientContext(weight_kg=22, age_years=6)
        doses = [d for d in dose_all(module, ctx) if d.status is DoseStatus.COMPUTED]
        bundle = draft_bundle(module, doses, when_iso="2026-07-18T12:00:00Z")
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert types[0] == "Composition"
        assert types[1] == "Procedure"
        assert types.count("MedicationAdministration") == len(doses)

    def test_every_resource_tagged_synthetic_and_draft(self) -> None:
        module = get_module("lateral_canthotomy")
        bundle = draft_bundle(module, [], when_iso="2026-07-18T12:00:00Z")
        for entry in bundle["entry"]:
            codes = {t["code"] for t in entry["resource"]["meta"]["tag"]}
            assert {"synthetic", "draft"} <= codes

    def test_composition_is_preliminary_never_final(self) -> None:
        module = get_module("perimortem_cesarean")
        bundle = draft_bundle(module, [], when_iso="2026-07-18T12:00:00Z")
        composition = bundle["entry"][0]["resource"]
        assert composition["status"] == "preliminary"
        assert composition["title"].startswith("DRAFT")

    def test_composition_narrative_is_escaped(self) -> None:
        from halo.edu.models import DoseResult

        module = get_module("organophosphate")
        hostile = DoseResult(
            status=DoseStatus.COMPUTED,
            med="Atropine<script>alert(1)</script>",
            route="IV",
            text='2 mg IV <img src=x onerror="x">',
        )
        bundle = draft_bundle(module, [hostile], when_iso="2026-07-18T12:00:00Z")
        div = bundle["entry"][0]["resource"]["section"][0]["text"]["div"]
        assert "<script>" not in div
        assert "<img" not in div
        assert "&lt;script&gt;" in div

    def test_refused_doses_never_documented(self) -> None:
        module = get_module("organophosphate")
        doses = dose_all(module, PatientContext())  # everything refused or reference
        bundle = draft_bundle(module, list(doses), when_iso="2026-07-18T12:00:00Z")
        admins = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"]["resourceType"] == "MedicationAdministration"
        ]
        assert all("refused" not in a["dosage"]["text"].lower() for a in admins)
