"""Corpus loader + integrity validation for `content/*.json`.

The corpus is the module's source of clinical truth, so loading is strict and
fail-closed: an unknown key, a weight-based med with no cap, a drill point
that references a missing step, or a non-synthetic drill stem is a load-time
``ValueError`` — bad content never reaches a card, a dose computation, or a
drill. Every module carries a content-addressed version string so CME records
and FHIR drafts can name exactly which revision of the content they saw.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from halo.edu.models import (
    DecisionPoint,
    DoseSpec,
    Drill,
    Med,
    ProcedureModule,
    Reference,
    ReviewInfo,
    ReviewStatus,
    Step,
    TimeTarget,
)

CONTENT_DIR = Path(__file__).parent / "content"


def _check_keys(raw: dict[str, Any], allowed: set[str], where: str) -> None:
    """Reject unknown keys — a typo in content must fail loudly, not silently."""
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {sorted(unknown)} — typo in content?")


def _dose_spec(raw: dict[str, Any], where: str) -> DoseSpec:
    _check_keys(
        raw, {"text", "unit", "per_kg", "fixed", "max_amount", "round_to", "uncapped"}, where
    )
    spec = DoseSpec(
        text=raw["text"],
        unit=raw.get("unit", "mg"),
        per_kg=raw.get("per_kg"),
        fixed=raw.get("fixed"),
        max_amount=raw.get("max_amount"),
        round_to=raw.get("round_to"),
        uncapped=raw.get("uncapped", False),
    )
    if spec.per_kg is not None and spec.max_amount is None and not spec.uncapped:
        raise ValueError(f"{where}: weight-based dose has no max_amount and is not 'uncapped'")
    if spec.per_kg is not None and spec.fixed is not None:
        raise ValueError(f"{where}: dose is both per_kg and fixed — pick one")
    return spec


def _med(raw: dict[str, Any], where: str) -> Med:
    _check_keys(raw, {"name", "role", "route", "adult", "peds", "cautions", "notes"}, where)
    adult = _dose_spec(raw["adult"], f"{where}/adult") if "adult" in raw else None
    peds = _dose_spec(raw["peds"], f"{where}/peds") if "peds" in raw else None
    if adult is None and peds is None:
        raise ValueError(f"{where}: med has neither adult nor peds spec")
    return Med(
        name=raw["name"],
        role=raw["role"],
        route=raw["route"],
        adult=adult,
        peds=peds,
        cautions=tuple(raw.get("cautions", ())),
        notes=tuple(raw.get("notes", ())),
    )


def _accept(raw: list[Any], where: str) -> tuple[tuple[str, ...], ...]:
    groups = tuple(tuple(str(p).lower() for p in group) for group in raw)
    if any(not group or any(not p.strip() for p in group) for group in groups):
        raise ValueError(f"{where}: empty accept group or phrase")
    return groups


def _step(raw: dict[str, Any], where: str) -> Step:
    _check_keys(raw, {"n", "action", "detail", "critical", "accept", "media"}, where)
    return Step(
        n=raw["n"],
        action=raw["action"],
        detail=raw.get("detail", ""),
        critical=raw.get("critical", False),
        accept=_accept(raw.get("accept", []), where),
        media=raw.get("media"),
    )


def _decision_point(raw: dict[str, Any], where: str) -> DecisionPoint:
    _check_keys(raw, {"prompt", "ideal", "accept", "critical", "expected_step"}, where)
    accept = _accept(raw["accept"], where)
    if not accept:
        raise ValueError(f"{where}: decision point has no accept groups")
    return DecisionPoint(
        prompt=raw["prompt"],
        ideal=raw["ideal"],
        accept=accept,
        critical=raw.get("critical", False),
        expected_step=raw.get("expected_step"),
    )


def _drill(raw: dict[str, Any], step_numbers: set[int], where: str) -> Drill:
    _check_keys(raw, {"stem", "synthetic", "pass_threshold", "decision_points"}, where)
    if raw.get("synthetic") is not True:
        raise ValueError(f"{where}: drill stem must be marked synthetic: true")
    threshold = raw.get("pass_threshold", 0.8)
    if not 0 < threshold <= 1:
        raise ValueError(f"{where}: pass_threshold {threshold} not in (0, 1]")
    points = tuple(
        _decision_point(p, f"{where}/decision_points[{i}]")
        for i, p in enumerate(raw["decision_points"])
    )
    if not points:
        raise ValueError(f"{where}: drill has no decision points")
    if not any(p.critical for p in points):
        raise ValueError(f"{where}: drill has no critical decision point")
    for i, p in enumerate(points):
        if p.expected_step is not None and p.expected_step not in step_numbers:
            raise ValueError(
                f"{where}/decision_points[{i}]: expected_step {p.expected_step} not a step"
            )
    return Drill(
        stem=raw["stem"],
        decision_points=points,
        pass_threshold=threshold,
        synthetic=True,
    )


_MODULE_KEYS = {
    "id",
    "name",
    "category",
    "one_liner",
    "aliases",
    "indications",
    "contraindications",
    "time_target",
    "team_calls",
    "equipment",
    "steps",
    "meds",
    "pitfalls",
    "success_criteria",
    "aftercare",
    "references",
    "review",
    "drill",
}


def _parse_module(raw: dict[str, Any], where: str) -> ProcedureModule:
    _check_keys(raw, _MODULE_KEYS, where)
    for key in ("id", "name", "category", "one_liner"):
        if not raw.get(key):
            raise ValueError(f"{where}: missing required field '{key}'")
    for key in ("aliases", "indications", "steps", "pitfalls", "success_criteria"):
        if not raw.get(key):
            raise ValueError(f"{where}: '{key}' must be non-empty")
    if len(raw.get("references", [])) < 2:
        raise ValueError(f"{where}: clinical content needs at least 2 references")

    steps = tuple(_step(s, f"{where}/steps[{i}]") for i, s in enumerate(raw["steps"]))
    if [s.n for s in steps] != list(range(1, len(steps) + 1)):
        raise ValueError(f"{where}: steps must be numbered 1..{len(steps)} in order")
    if not any(s.critical for s in steps):
        raise ValueError(f"{where}: no step is marked critical")

    review_raw = raw["review"]
    _check_keys(
        review_raw, {"status", "author", "date", "version", "reviewed_by"}, f"{where}/review"
    )
    review = ReviewInfo(
        status=ReviewStatus(review_raw["status"]),
        author=review_raw["author"],
        date=review_raw["date"],
        version=review_raw["version"],
        reviewed_by=review_raw.get("reviewed_by"),
    )
    if review.status is ReviewStatus.REVIEWED and not review.reviewed_by:
        raise ValueError(f"{where}: status 'reviewed' requires reviewed_by (a human name)")

    tt = raw["time_target"]
    _check_keys(tt, {"label", "minutes"}, f"{where}/time_target")

    return ProcedureModule(
        id=raw["id"],
        name=raw["name"],
        category=raw["category"],
        one_liner=raw["one_liner"],
        aliases=tuple(a.lower() for a in raw["aliases"]),
        indications=tuple(raw["indications"]),
        contraindications=tuple(raw.get("contraindications", ())),
        time_target=TimeTarget(label=tt["label"], minutes=tt.get("minutes")),
        team_calls=tuple(raw.get("team_calls", ())),
        equipment=tuple(raw.get("equipment", ())),
        steps=steps,
        meds=tuple(_med(m, f"{where}/meds[{i}]") for i, m in enumerate(raw.get("meds", []))),
        pitfalls=tuple(raw["pitfalls"]),
        success_criteria=tuple(raw["success_criteria"]),
        aftercare=tuple(raw.get("aftercare", ())),
        references=tuple(Reference(**r) for r in raw["references"]),
        review=review,
        drill=_drill(raw["drill"], {s.n for s in steps}, f"{where}/drill")
        if raw.get("drill")
        else None,
    )


def content_version(raw: dict[str, Any]) -> str:
    """Content-addressed version: ``<id>@v<n>+<sha256[:8]>`` over canonical JSON."""
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:8]
    return f"{raw['id']}@v{raw['review']['version']}+{digest}"


@lru_cache(maxsize=1)
def _load() -> tuple[tuple[ProcedureModule, ...], dict[str, str]]:
    modules: list[ProcedureModule] = []
    versions: dict[str, str] = {}
    paths = sorted(CONTENT_DIR.glob("*.json"))
    if not paths:
        raise ValueError(f"no content found in {CONTENT_DIR}")
    for path in paths:
        raw = json.loads(path.read_text())
        module = _parse_module(raw, path.name)
        if module.id != path.stem:
            raise ValueError(f"{path.name}: id '{module.id}' does not match filename")
        if module.id in versions:
            raise ValueError(f"duplicate module id '{module.id}'")
        modules.append(module)
        versions[module.id] = content_version(raw)
    return tuple(sorted(modules, key=lambda m: m.id)), versions


def load_corpus() -> tuple[ProcedureModule, ...]:
    """All validated modules, sorted by id. Cached; raises ValueError on bad content."""
    return _load()[0]


def module_version(module_id: str) -> str:
    """The content-addressed version string for one module."""
    return _load()[1][module_id]


def get_module(module_id: str) -> ProcedureModule:
    """Fetch one module by id. KeyError if absent — callers decide the UX."""
    for module in load_corpus():
        if module.id == module_id:
            return module
    raise KeyError(module_id)
