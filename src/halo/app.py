"""API surface + demo UI. Run locally: ``make serve`` -> http://127.0.0.1:8000"""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from halo.edu.routes import router as edu_router
from halo.llm import LLMFailure, model_name
from halo.mci import Observations, salt_triage
from halo.mci.extract import extract_observations
from halo.mci.scenarios import SCENARIOS

app = FastAPI(title="HALO")
app.include_router(edu_router)

_STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    """Dependency-free demo UI — works on a hospital intranet with no internet."""
    return FileResponse(_STATIC / "index.html", media_type="text/html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": model_name()}


@app.get("/edu/{module_id}.html", include_in_schema=False)
def edu_html_shim(module_id: str) -> Any:
    """The /edu/ index emits static-export-style links; redirect them to live cards."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=f"/edu/modules/{module_id}/card", status_code=307)


def _census_row(entry: Any, decision: Any | None = None) -> dict[str, Any]:
    from halo.mci.edu_links import edu_links
    from halo.mci.panel import care_flags

    row: dict[str, Any] = {
        "bed": entry.bed,
        "patient_id": entry.patient.patient_id,
        "mrn": entry.patient.mrn,
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
        "edu_links": [
            link.__dict__ for link in edu_links(f"{entry.chief_complaint} {entry.status}")
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


def _board_state() -> dict[str, Any]:
    from halo.mci.board import BOARD, LOC_BED, LOC_CHAIRS, LOC_DEPARTED

    def rows(location: str) -> list[dict[str, Any]]:
        out = []
        for ps in BOARD.patients.values():
            if ps.location != location:
                continue
            row = _census_row(ps.entry, ps.decision)
            row["pull_escalated"] = ps.pull_escalated
            row["disposition"] = ps.disposition
            out.append(row)
        return out

    return {
        **BOARD.counts(),
        "assessed": BOARD.assessed,
        "plan_summary": BOARD.plan_summary,
        "beds": rows(LOC_BED),
        "chairs": rows(LOC_CHAIRS),
        "departed_entries": rows(LOC_DEPARTED),
        "activity": [e.text for e in BOARD.events][::-1],
        "synthetic_only": True,
    }


@app.get("/mci/board")
def board_view() -> dict[str, Any]:
    """Live board state — census, chairs, departed, audit log."""
    return _board_state()


@app.post("/mci/board/assess")
def board_assess() -> dict[str, Any]:
    """Run the reverse-triage assessment on the live board (deterministic)."""
    from halo.mci.board import BOARD

    BOARD.assess()
    return _board_state()


class BoardActionRequest(BaseModel):
    bed: str = Field(min_length=1)
    action: str = Field(min_length=1)


@app.post("/mci/board/action")
def board_action(req: BoardActionRequest) -> dict[str, Any]:
    """Execute one board transition. Refuses actions the classification forbids."""
    from halo.mci.board import BOARD, BoardError

    try:
        BOARD.act(req.bed, req.action)
    except BoardError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    return _board_state()


@app.post("/mci/board/undo")
def board_undo() -> dict[str, Any]:
    from halo.mci.board import BOARD

    BOARD.undo()
    return _board_state()


@app.post("/mci/board/reset")
def board_reset() -> dict[str, Any]:
    from halo.mci.board import BOARD

    BOARD.reset()
    return _board_state()


@app.get("/sim", include_in_schema=False)
def sim_ui() -> FileResponse:
    """Simulation lab — deterministic 2D patient sims (no model in the loop)."""
    return FileResponse(_STATIC / "sim.html", media_type="text/html")


@app.get("/sim/cases")
def sim_cases() -> dict[str, Any]:
    from halo.sim import list_cases

    return {"cases": list_cases(), "synthetic_only": True}


@app.get("/sim/cases/{case_id}")
def sim_case(case_id: str) -> dict[str, Any]:
    from halo.sim import load_case

    try:
        return dict(load_case(case_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
                "mrn": c.patient.mrn,
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

    from halo.mci.edu_links import edu_links

    return {
        "triage": _result_payload(triage, observations, evidence),
        # Just-in-time readiness: procedure indicated in the note -> link staff to the card.
        "edu_links": [link.__dict__ for link in edu_links(req.note)],
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
