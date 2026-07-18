"""Corpus integrity tests — all offline. Bad content must fail at load, not at the bedside."""

from __future__ import annotations

import re
from typing import Any

import pytest

from halo.edu import ReviewStatus, load_corpus, module_version
from halo.edu.corpus import _parse_module

CORPUS = load_corpus()
IDS = [m.id for m in CORPUS]

EXPECTED_MODULES = {
    "breech_delivery",
    "lateral_canthotomy",
    "organophosphate",
    "perimortem_cesarean",
}


def test_expected_modules_present() -> None:
    assert set(IDS) == EXPECTED_MODULES


@pytest.mark.parametrize("module", CORPUS, ids=IDS)
def test_module_shape(module: Any) -> None:
    assert module.one_liner
    assert len(module.references) >= 2
    assert any(s.critical for s in module.steps)
    assert [s.n for s in module.steps] == list(range(1, len(module.steps) + 1))
    assert module.aliases == tuple(a.lower() for a in module.aliases)


@pytest.mark.parametrize("module", CORPUS, ids=IDS)
def test_drills_are_synthetic_and_linked(module: Any) -> None:
    drill = module.drill
    assert drill is not None, "every launch module ships with a drill"
    assert drill.synthetic is True
    assert any(p.critical for p in drill.decision_points)
    step_numbers = {s.n for s in module.steps}
    for point in drill.decision_points:
        assert point.accept, point.prompt
        assert point.ideal
        if point.expected_step is not None:
            assert point.expected_step in step_numbers


@pytest.mark.parametrize("module", CORPUS, ids=IDS)
def test_weight_based_meds_are_capped(module: Any) -> None:
    for med in module.meds:
        for spec in (med.adult, med.peds):
            if spec is not None and spec.per_kg is not None:
                assert spec.max_amount is not None or spec.uncapped, med.name


@pytest.mark.parametrize("module", CORPUS, ids=IDS)
def test_draft_status_until_physician_signoff(module: Any) -> None:
    """Content ships draft; 'reviewed' requires a human name. Nothing auto-approves."""
    if module.review.status is ReviewStatus.REVIEWED:
        assert module.review.reviewed_by
    else:
        assert module.review.status is ReviewStatus.DRAFT


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_content_version_format(module_id: str) -> None:
    assert re.fullmatch(rf"{module_id}@v\d+\+[0-9a-f]{{8}}", module_version(module_id))


def _minimal_raw() -> dict[str, Any]:
    return {
        "id": "x",
        "name": "X",
        "category": "test",
        "one_liner": "x",
        "aliases": ["x"],
        "indications": ["x"],
        "time_target": {"label": "x"},
        "steps": [{"n": 1, "action": "a", "critical": True}],
        "pitfalls": ["x"],
        "success_criteria": ["x"],
        "references": [{"label": "a", "cite": "a"}, {"label": "b", "cite": "b"}],
        "review": {"status": "draft", "author": "t", "date": "2026-07-18", "version": 1},
    }


def test_unknown_key_rejected() -> None:
    raw = _minimal_raw()
    raw["steps"][0]["citical"] = True  # the typo this guard exists for
    with pytest.raises(ValueError, match="unknown key"):
        _parse_module(raw, "test")


def test_uncapped_weight_dose_rejected() -> None:
    raw = _minimal_raw()
    raw["meds"] = [{"name": "m", "role": "r", "route": "IV", "adult": {"text": "t", "per_kg": 1.0}}]
    with pytest.raises(ValueError, match="max_amount"):
        _parse_module(raw, "test")


def test_non_synthetic_drill_rejected() -> None:
    raw = _minimal_raw()
    raw["drill"] = {
        "stem": "s",
        "synthetic": False,
        "decision_points": [{"prompt": "p", "ideal": "i", "accept": [["a"]], "critical": True}],
    }
    with pytest.raises(ValueError, match="synthetic"):
        _parse_module(raw, "test")


def test_dangling_expected_step_rejected() -> None:
    raw = _minimal_raw()
    raw["drill"] = {
        "stem": "s",
        "synthetic": True,
        "decision_points": [
            {"prompt": "p", "ideal": "i", "accept": [["a"]], "critical": True, "expected_step": 9}
        ],
    }
    with pytest.raises(ValueError, match="expected_step"):
        _parse_module(raw, "test")


def test_reviewed_requires_human_name() -> None:
    raw = _minimal_raw()
    raw["review"]["status"] = "reviewed"
    with pytest.raises(ValueError, match="reviewed_by"):
        _parse_module(raw, "test")
