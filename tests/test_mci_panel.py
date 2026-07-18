"""Deterministic panel-store tests — offline, run against the committed dataset."""

from __future__ import annotations

from halo.mci.panel import (
    IdentityCues,
    care_flags,
    chart_context,
    load_panel,
    match_candidates,
    score_candidate,
)

ON_DATE = "2026-07-18"


def test_panel_loads_25_patients() -> None:
    panel = load_panel()
    assert len(panel) == 25
    assert all(p.patient_id and p.family_name and p.birth_date for p in panel)


def _by_family(name: str):  # type: ignore[no-untyped-def]
    return next(p for p in load_panel() if p.family_name == name)


def test_antithrombotic_and_beta_blockade_flags() -> None:
    wilkinson = _by_family("Wilkinson")  # clopidogrel + metoprolol
    ids = {f.flag_id for f in care_flags(wilkinson)}
    assert "antithrombotic_therapy" in ids
    assert "beta_blockade" in ids
    # High-severity flags sort first.
    assert care_flags(wilkinson)[0].severity == "high"


def test_pregnancy_flag() -> None:
    thiel = _by_family("Thiel")
    ids = {f.flag_id for f in care_flags(thiel)}
    assert "pregnancy" in ids
    assert "baseline_anemia" in ids


def test_hospice_goals_flag() -> None:
    kling = _by_family("Kling")
    ids = {f.flag_id for f in care_flags(kling)}
    assert "comfort_focused_goals" in ids


def test_flags_carry_provenance() -> None:
    for flag in care_flags(_by_family("Wilkinson")):
        assert flag.provenance, flag.flag_id


def test_gender_mismatch_zeroes_score() -> None:
    wilkinson = _by_family("Wilkinson")
    cues = IdentityCues(family_name="Wilkinson", gender="male")
    assert score_candidate(wilkinson, cues, on_date=ON_DATE).score == 0.0


def test_partial_family_name_matches() -> None:
    cues = IdentityCues(family_name="Wilk", gender="female", approximate_age=80)
    status, candidates = match_candidates(cues, on_date=ON_DATE)
    assert status in ("strong_candidate", "possible")
    assert candidates[0].patient.family_name == "Wilkinson"


def test_full_identity_is_strong_candidate() -> None:
    cues = IdentityCues(
        family_name="Wilkinson", given_name="Latoyia", gender="female", approximate_age=81
    )
    status, candidates = match_candidates(cues, on_date=ON_DATE)
    assert status == "strong_candidate"
    assert candidates[0].patient.family_name == "Wilkinson"


def test_demographics_only_never_strong() -> None:
    # An 80-year-old male with no name cue matches Macejkovic on age+gender alone;
    # that must never rank "strong" — demographics are not identifying.
    cues = IdentityCues(gender="male", approximate_age=80)
    status, candidates = match_candidates(cues, on_date=ON_DATE)
    assert status == "possible"
    assert candidates  # candidates surface, but a human must adjudicate


def test_no_cues_is_no_match() -> None:
    status, candidates = match_candidates(IdentityCues(), on_date=ON_DATE)
    assert status == "no_match"
    assert candidates == ()


def test_status_never_confirmed() -> None:
    for cues in (
        IdentityCues(family_name="Wilkinson", given_name="Latoyia", gender="female"),
        IdentityCues(family_name="Kling"),
        IdentityCues(),
    ):
        status, _ = match_candidates(cues, on_date=ON_DATE)
        assert status in ("strong_candidate", "possible", "no_match")


def test_chart_context_unknown_id_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        chart_context("not-a-real-id")
