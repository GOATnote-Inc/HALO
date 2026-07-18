"""API surface + demo UI. Run locally: ``make serve`` -> http://127.0.0.1:8000"""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from halo.llm import LLMFailure, model_name
from halo.mci import Observations, salt_triage
from halo.mci.extract import extract_observations
from halo.mci.scenarios import SCENARIOS

app = FastAPI(title="HALO")

_STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    """Dependency-free demo UI — works on a hospital intranet with no internet."""
    return FileResponse(_STATIC / "index.html", media_type="text/html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": model_name()}


def _census_row(entry: Any, decision: Any | None = None) -> dict[str, Any]:
    from halo.mci.panel import care_flags

    row: dict[str, Any] = {
        "bed": entry.bed,
        "patient_id": entry.patient.patient_id,
        "name": entry.patient.display_name,
        "gender": entry.patient.gender,
        "birth_date": entry.patient.birth_date,
        "esi": entry.esi,
        "chief_complaint": entry.chief_complaint,
        "status": entry.status,
        "features": {k: v for k, v in entry.features.__dict__.items() if v is not None},
        "care_flags": [
            {"flag": f.flag_id, "severity": f.severity, "why": f.why}
            for f in care_flags(entry.patient)
        ],
    }
    if decision is not None:
        row["surge"] = {
            "action": decision.action.value,
            "rationale": decision.rationale,
            "required_steps": list(decision.required_steps),
            "frees_bed_now": decision.frees_bed_now,
        }
    return row


@app.get("/mci/census")
def census() -> dict[str, Any]:
    """The department at the moment of declaration — synthetic, chart-linked."""
    from halo.mci.census import load_census

    c = load_census()
    return {
        "department_beds": c.department_beds,
        "occupied": len(c.entries),
        "open_beds": c.open_beds,
        "rows": [_census_row(e) for e in c.entries],
        "synthetic_only": True,
    }


@app.post("/mci/surge")
def surge() -> dict[str, Any]:
    """Reverse-triage the census (Kelen et al. 2006). Deterministic — no model call."""
    from halo.mci.census import load_census
    from halo.mci.surge import surge_plan

    c = load_census()
    plan = surge_plan(c)
    return {
        "department_beds": c.department_beds,
        "occupied": len(c.entries),
        "open_beds": c.open_beds,
        "freed_now": plan.freed_now,
        "freed_by_admission_pull": plan.freed_by_admission_pull,
        "held": plan.held,
        "monitors_freed": plan.monitors_freed,
        "summary": plan.summary(),
        "rows": [_census_row(d.entry, d) for d in plan.decisions],
        "synthetic_only": True,
    }


@app.get("/mci/scenarios")
def scenarios() -> dict[str, Any]:
    """Scripted scenarios (synthetic) — one source of truth with the CLI demo."""
    return {
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "title": s.title,
                "pattern": s.pattern,
                "expect": s.expect,
                "note": s.note,
                "synthetic": s.synthetic,
            }
            for s in SCENARIOS
        ]
    }


class TriageNoteRequest(BaseModel):
    """Free-text field/EMS note. Claude extracts; the SALT algorithm decides."""

    note: str = Field(min_length=1)
    likely_survivable: bool | None = Field(
        default=None,
        description="Human resource decision. Only an explicit false can yield EXPECTANT.",
    )


class TriageObservationsRequest(BaseModel):
    """Pre-structured observations — deterministic path, no model call."""

    observations: dict[str, bool | None] = Field(default_factory=dict)
    likely_survivable: bool | None = None


def _result_payload(
    result: Any, observations: Observations, evidence: dict[str, str]
) -> dict[str, Any]:
    return {
        "category": result.category.value,
        "rationale": result.rationale,
        "missing_fields": list(result.missing_fields),
        "derivations": list(result.derivations),
        "observations": asdict(observations),
        "evidence": evidence,
        "synthetic_only": True,
    }


@app.post("/mci/triage/note")
def triage_note(req: TriageNoteRequest) -> dict[str, Any]:
    try:
        observations, evidence = extract_observations(req.note)
    except LLMFailure as exc:
        # Fail closed: no category is better than a wrong one.
        raise HTTPException(status_code=502, detail=f"extraction failed closed: {exc}") from exc
    result = salt_triage(observations, likely_survivable=req.likely_survivable)
    return _result_payload(result, observations, evidence)


@app.post("/mci/triage/observations")
def triage_observations(req: TriageObservationsRequest) -> dict[str, Any]:
    try:
        observations = Observations(**req.observations)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = salt_triage(observations, likely_survivable=req.likely_survivable)
    return _result_payload(result, observations, {})


class HandoffRequest(BaseModel):
    """Full MCI handoff: triage + chart reconciliation against the panel.

    ``likely_survivable`` is a physician secondary-triage decision — the nurse
    door-triage flow never sets it.
    """

    note: str = Field(min_length=1)
    incident_date: str = Field(default="2026-07-18", pattern=r"^\d{4}-\d{2}-\d{2}$")
    likely_survivable: bool | None = None


@app.post("/mci/handoff")
def handoff(req: HandoffRequest) -> dict[str, Any]:
    from halo.mci.fhir_out import triage_bundle
    from halo.mci.panel import care_flags
    from halo.mci.reconcile import reconcile

    try:
        observations, evidence = extract_observations(req.note)
        recon = reconcile(req.note, on_date=req.incident_date)
    except LLMFailure as exc:
        raise HTTPException(status_code=502, detail=f"failed closed: {exc}") from exc
    triage = salt_triage(observations, likely_survivable=req.likely_survivable)

    candidates = []
    for c in recon.candidates:
        flags = care_flags(c.patient)
        candidates.append(
            {
                "patient_id": c.patient.patient_id,
                "name": c.patient.display_name,
                "gender": c.patient.gender,
                "birth_date": c.patient.birth_date,
                "match_score": round(c.score, 2),
                "match_reasons": list(c.reasons),
                "agent_rationale": recon.agent_rationales.get(c.patient.patient_id),
                # Chart-bloat counter: the full record vs what actually changes care now.
                "chart_resource_count": c.patient.chart_resource_count,
                "care_flags_if_matched": [
                    {
                        "flag": f.flag_id,
                        "severity": f.severity,
                        "why": f.why,
                        "provenance": list(f.provenance),
                    }
                    for f in flags
                ],
            }
        )

    return {
        "triage": _result_payload(triage, observations, evidence),
        "identity": {
            "status": recon.status,  # never "confirmed" — human adjudicates
            "method": recon.method,
            "cues": recon.cues.__dict__,
            "candidates": candidates,
            "agent_trail": list(recon.trail),
        },
        # Write-back preview: one structured Observation on the MCI alias record.
        # Candidate flags are intentionally NOT in the bundle — identity is unconfirmed.
        "fhir": triage_bundle(
            observations, triage, incident_date=req.incident_date, evidence=evidence
        ),
        "synthetic_only": True,
    }
