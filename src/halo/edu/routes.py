"""FastAPI surface for the readiness & CME module.

A self-contained ``APIRouter`` — mounting into ``halo.app`` is one line
(``app.include_router(edu.routes.router)``) and is deliberately left to the
demo-surface lane owner; everything here is exercised standalone via
TestClient. All GET paths and the default POST paths are offline and
deterministic; LLM assistance is opt-in per request and fails closed.

Deployment note (red-team): ``find?llm=true`` and ``llm_adjudicate`` trigger a
paid Claude call with no auth on this router — fine for a research demo on an
intranet, but gate or strip them before any exposed deployment.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, StringConstraints

from halo.edu.corpus import load_corpus, module_version
from halo.edu.dosing import dose_all
from halo.edu.drill import run_drill
from halo.edu.lookup import resolve, route_with_claude
from halo.edu.models import PatientContext
from halo.edu.render import card_html, index_html

router = APIRouter(prefix="/edu", tags=["edu"])


def _module_or_404(module_id: str) -> Any:
    for module in load_corpus():
        if module.id == module_id:
            return module
    raise HTTPException(status_code=404, detail=f"no module '{module_id}'")


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    return index_html(load_corpus())


@router.get("/modules")
def list_modules() -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "name": m.name,
            "category": m.category,
            "one_liner": m.one_liner,
            "aliases": m.aliases,
            "review_status": m.review.status.value,
            "content_version": module_version(m.id),
            "time_target": asdict(m.time_target),
        }
        for m in load_corpus()
    ]


@router.get("/modules/{module_id}")
def get_module_json(module_id: str) -> dict[str, Any]:
    module = _module_or_404(module_id)
    payload = asdict(module)
    payload["content_version"] = module_version(module.id)
    return payload


@router.get("/modules/{module_id}/card", response_class=HTMLResponse)
def get_card(module_id: str) -> str:
    return card_html(_module_or_404(module_id))


@router.get("/find")
def find(q: str = Query(min_length=1), llm: bool = False) -> dict[str, Any]:
    matches = resolve(q)
    routed = route_with_claude(q) if llm else None  # fail-closed: None on any failure
    return {
        "query": q,
        "routed_id": routed,
        "matches": [
            {
                "id": m.module.id,
                "name": m.module.name,
                "one_liner": m.module.one_liner,
                "score": m.score,
                "why": m.why,
            }
            for m in matches
        ],
        "all_module_ids": [m.id for m in load_corpus()] if not matches else [],
    }


class DoseRequest(BaseModel):
    module_id: str
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    age_years: float | None = Field(default=None, ge=0, lt=130)
    allergies: list[str] = []


@router.post("/dose")
def compute_doses(body: DoseRequest) -> dict[str, Any]:
    module = _module_or_404(body.module_id)
    ctx = PatientContext(
        weight_kg=body.weight_kg,
        age_years=body.age_years,
        allergies=tuple(body.allergies),
    )
    return {
        "module_id": module.id,
        "content_version": module_version(module.id),
        "doses": [asdict(d) for d in dose_all(module, ctx)],
    }


class DrillGradeRequest(BaseModel):
    module_id: str
    answers: list[Annotated[str, StringConstraints(max_length=5000)]] = Field(max_length=64)
    trainee: str | None = None
    elapsed_s: float | None = None
    llm_adjudicate: bool = False


@router.post("/drill/grade")
def grade_drill(body: DrillGradeRequest) -> dict[str, Any]:
    module = _module_or_404(body.module_id)
    try:
        result = run_drill(
            module,
            body.answers,
            trainee=body.trainee,
            elapsed_s=body.elapsed_s,
            llm_adjudicate=body.llm_adjudicate,
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return asdict(result)
