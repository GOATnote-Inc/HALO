"""EHR seams: FHIR R4 in, FHIR R4 out. Synthetic data only.

Inbound — ``patient_context_from_bundle``: pulls exactly what dosing needs
(weight, age, sex, pregnancy, allergies) from a FHIR bundle. Extraction is
tolerant (a missing or malformed resource yields ``None`` fields, and the
fail-closed dosing layer handles the rest); it never fabricates a value.

Outbound — ``draft_bundle``: turns a crisis-mode session (module + doses
given) into draft FHIR resources: one MedicationAdministration per dose, a
Procedure, and a ``status: preliminary`` Composition. Every resource is
tagged ``synthetic`` + ``draft`` — nothing here is a signed clinical record;
a clinician attests in the EHR, not in HALO.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from halo.edu.models import DoseResult, DoseStatus, PatientContext, ProcedureModule

LOINC_WEIGHT = "29463-7"
LOINC_PREGNANCY_STATUS = "82810-3"
LOINC_PREGNANT = "LA15173-0"
LOINC_NOT_PREGNANT = "LA26683-5"

_TAGS = [
    {"system": "urn:halo:tag", "code": "synthetic", "display": "synthetic data"},
    {"system": "urn:halo:tag", "code": "draft", "display": "draft — requires clinician review"},
]


def _resources(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    out = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == resource_type:
            out.append(resource)
    return out


def _has_code(resource: dict[str, Any], code: str) -> bool:
    return any(c.get("code") == code for c in resource.get("code", {}).get("coding", []))


def _weight_kg(observations: list[dict[str, Any]]) -> float | None:
    weights = [o for o in observations if _has_code(o, LOINC_WEIGHT)]
    if not weights:
        return None
    # Latest wins when effectiveDateTime is present; content order breaks ties.
    weights.sort(key=lambda o: o.get("effectiveDateTime", ""))
    quantity = weights[-1].get("valueQuantity", {})
    value, unit = quantity.get("value"), (quantity.get("unit") or quantity.get("code") or "")
    if not isinstance(value, (int, float)):
        return None
    unit = unit.lower()
    if unit in ("kg", "kilogram", "kilograms"):
        return float(value)
    if unit in ("g", "gram", "grams"):
        return float(value) / 1000
    if unit in ("lb", "lbs", "[lb_av]", "pound", "pounds"):
        return float(value) * 0.453592
    return None  # unknown unit — refuse to guess


def _pregnant(observations: list[dict[str, Any]]) -> bool | None:
    for obs in observations:
        if not _has_code(obs, LOINC_PREGNANCY_STATUS):
            continue
        for coding in obs.get("valueCodeableConcept", {}).get("coding", []):
            if coding.get("code") == LOINC_PREGNANT:
                return True
            if coding.get("code") == LOINC_NOT_PREGNANT:
                return False
    return None


def _age_years(patient: dict[str, Any], on_date: date) -> float | None:
    birth = patient.get("birthDate")
    if not birth:
        return None
    try:
        born = date.fromisoformat(birth[:10])
    except ValueError:
        return None
    return round((on_date - born).days / 365.25, 2)


def patient_context_from_bundle(
    bundle: dict[str, Any], *, on_date: date | None = None
) -> PatientContext:
    """Extract dosing context from a FHIR bundle. Missing data stays None."""
    today = on_date or date.today()
    patients = _resources(bundle, "Patient")
    patient = patients[0] if patients else {}
    observations = _resources(bundle, "Observation")
    allergies = tuple(
        a.get("code", {}).get("text")
        or next(
            (c.get("display") for c in a.get("code", {}).get("coding", []) if c.get("display")),
            "",
        )
        for a in _resources(bundle, "AllergyIntolerance")
    )
    return PatientContext(
        weight_kg=_weight_kg(observations),
        age_years=_age_years(patient, today),
        sex=patient.get("gender"),
        pregnant=_pregnant(observations),
        allergies=tuple(a for a in allergies if a),
    )


def _tagged(resource: dict[str, Any]) -> dict[str, Any]:
    resource["meta"] = {"tag": list(_TAGS)}
    return resource


def draft_bundle(
    module: ProcedureModule,
    doses_given: list[DoseResult],
    *,
    when_iso: str,
    patient_ref: str = "Patient/synthetic-example",
) -> dict[str, Any]:
    """Draft FHIR documentation for a crisis-mode session. Preliminary, never signed."""
    computed = [d for d in doses_given if d.status is not DoseStatus.REFUSED]
    admins = [
        _tagged(
            {
                "resourceType": "MedicationAdministration",
                "id": f"halo-edu-med-{i + 1}",
                "status": "completed",
                "medicationCodeableConcept": {"text": dose.med},
                "subject": {"reference": patient_ref},
                "effectiveDateTime": when_iso,
                "dosage": {"text": dose.text, "route": {"text": dose.route}},
            }
        )
        for i, dose in enumerate(computed)
    ]
    procedure = _tagged(
        {
            "resourceType": "Procedure",
            "id": "halo-edu-procedure",
            "status": "completed",
            "code": {"text": module.name},
            "subject": {"reference": patient_ref},
            "performedDateTime": when_iso,
        }
    )
    med_lines = "".join(f"<li>{d.med}: {d.text}</li>" for d in computed)
    composition = _tagged(
        {
            "resourceType": "Composition",
            "id": "halo-edu-note",
            "status": "preliminary",
            "type": {"text": "Emergency procedure note (draft)"},
            "title": f"DRAFT — {module.name}",
            "date": when_iso,
            "subject": {"reference": patient_ref},
            "section": [
                {
                    "title": "Procedure",
                    "text": {
                        "status": "generated",
                        "div": f'<div xmlns="http://www.w3.org/1999/xhtml">'
                        f"<p>{module.name} — content {module.review.status.value}, "
                        f"requires clinician attestation.</p><ul>{med_lines}</ul></div>",
                    },
                    "entry": [{"reference": f"Procedure/{procedure['id']}"}]
                    + [{"reference": f"MedicationAdministration/{a['id']}"} for a in admins],
                }
            ],
        }
    )
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in (composition, procedure, *admins)],
    }
