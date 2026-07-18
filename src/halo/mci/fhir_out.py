"""FHIR R4 write-back: the triage result as a minimal, structured Bundle.

Anti-bloat contract: HALO writes one Observation with coded components — no
narrative note, no copy-forward, nothing a downstream reader has to skim past.
The subject is the *unidentified-patient alias* (Epic-style quick-registration
record, e.g. "Trauma, Alpha"): identity candidates are deliberately NOT written
to any chart, because identity is unconfirmed until a human merges records
through the EHR's normal identity-governance process (see docs/INTEGRATION.md).
"""

from __future__ import annotations

from typing import Any

from halo.mci.models import Observations, TriageResult

# Local CodeSystem — SALT categories have no universal FHIR/SNOMED coding; a real
# deployment maps these to the site's dictionary during integration.
SALT_SYSTEM = "https://github.com/GOATnote-Inc/HALO/fhir/CodeSystem/salt-triage"

_COMPONENT_FIELDS = (
    "breathing",
    "obeys_commands",
    "peripheral_pulse",
    "respiratory_distress",
    "major_hemorrhage_uncontrolled",
    "minor_injuries_only",
    "can_walk",
)


def triage_bundle(
    observations: Observations,
    result: TriageResult,
    *,
    incident_date: str,
    evidence: dict[str, str],
    alias_display: str = "Unidentified patient (MCI alias)",
) -> dict[str, Any]:
    """One Observation in a collection Bundle — ready to POST to a FHIR R4 server."""
    components: list[dict[str, Any]] = []
    for name in _COMPONENT_FIELDS:
        value = getattr(observations, name)
        if value is None:
            continue
        component: dict[str, Any] = {
            "code": {"text": name.replace("_", " ")},
            "valueBoolean": value,
        }
        quote = evidence.get(name)
        if quote:
            component["extension"] = [
                {
                    "url": f"{SALT_SYSTEM}/evidence-quote",
                    "valueString": quote,
                }
            ]
        components.append(component)
    if observations.respiratory_rate is not None:
        components.append(
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "9279-1",
                            "display": "Respiratory rate",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": observations.respiratory_rate,
                    "unit": "breaths/min",
                    "system": "http://unitsofmeasure.org",
                    "code": "/min",
                },
            }
        )

    observation: dict[str, Any] = {
        "resourceType": "Observation",
        "status": "preliminary",  # door triage — physician secondary triage supersedes
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": SALT_SYSTEM,
                    "code": result.category.value,
                    "display": f"SALT triage: {result.category.value.replace('_', ' ')}",
                }
            ],
            "text": "Mass casualty triage category (SALT)",
        },
        "subject": {"display": alias_display},
        "effectiveDateTime": incident_date,
        "valueCodeableConcept": {
            "coding": [{"system": SALT_SYSTEM, "code": result.category.value}],
            "text": result.category.value.replace("_", " "),
        },
        "note": [{"text": result.rationale}]
        + [{"text": f"Derived: {d}"} for d in result.derivations],
        "component": components,
    }
    if result.missing_fields:
        observation["dataAbsentReason"] = {
            "text": "Not documented at door triage: " + ", ".join(result.missing_fields)
        }

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": observation}],
    }
