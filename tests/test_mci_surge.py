"""Surge bed-clearance tests — offline, deterministic, run against the committed census."""

from __future__ import annotations

from itertools import product

from halo.mci.census import CareFeatures, CensusEntry, load_census
from halo.mci.panel import load_panel
from halo.mci.surge import SurgeAction, classify, surge_plan

CENSUS = load_census()
PLAN = surge_plan(CENSUS)
BY_FAMILY = {d.entry.patient.family_name: d for d in PLAN.decisions}


def test_census_loads_and_links_to_panel() -> None:
    assert len(CENSUS.entries) == 23
    assert CENSUS.department_beds == 30
    beds = [e.bed for e in CENSUS.entries]
    assert len(set(beds)) == len(beds)  # no double-booked beds


def test_mci_arrivals_are_not_in_the_census() -> None:
    # Wilkinson and Macejkovic arrive with the incident — they can't also be in beds.
    families = {e.patient.family_name for e in CENSUS.entries}
    assert "Wilkinson" not in families
    assert "Macejkovic" not in families
    assert len(load_panel()) - len(CENSUS.entries) == 2


def test_expected_plan_shape() -> None:
    counts = {a: sum(1 for d in PLAN.decisions if d.action is a) for a in SurgeAction}
    assert counts[SurgeAction.DISCHARGE_NOW] == 11
    assert counts[SurgeAction.VERTICAL_CHAIRS] == 6
    assert counts[SurgeAction.EXPEDITE_ADMIT] == 4
    assert counts[SurgeAction.HOLD_BED] == 2
    assert PLAN.freed_now == 17
    assert PLAN.freed_by_admission_pull == 4
    assert PLAN.monitors_freed == 2  # NSTEMI + post-tPA leave with their monitors freed


def test_nstemi_and_post_tpa_are_expedite_admit() -> None:
    assert BY_FAMILY["Howell"].action is SurgeAction.EXPEDITE_ADMIT  # NSTEMI on heparin
    assert BY_FAMILY["Ernser"].action is SurgeAction.EXPEDITE_ADMIT  # post-thrombolytic CVA
    assert not BY_FAMILY["Ernser"].frees_bed_now  # freed only by inpatient pull


def test_hospice_patient_gets_goals_of_care_path_not_chairs() -> None:
    kling = BY_FAMILY["Kling"]
    assert kling.action is SurgeAction.EXPEDITE_ADMIT
    assert "goals of care" in kling.rationale


def test_monitor_and_oxygen_tethers_hold_the_bed() -> None:
    assert BY_FAMILY["Crooks"].action is SurgeAction.HOLD_BED  # rule-out ACS on monitor
    assert BY_FAMILY["Ankunding"].action is SurgeAction.HOLD_BED  # COPD on O2


def test_missing_data_fails_closed_to_hold() -> None:
    entry = CensusEntry(
        bed="X01",
        patient=CENSUS.entries[0].patient,
        esi=3,
        chief_complaint="undocumented",
        status="no assessment recorded",
        features=CareFeatures(),  # everything None
    )
    decision = classify(entry)
    assert decision.action is SurgeAction.HOLD_BED
    assert "missing data" in decision.rationale


def test_never_moves_a_tethered_patient() -> None:
    for d in PLAN.decisions:
        f = d.entry.features
        if f.cardiac_monitor_required or f.oxygen_required or f.continuous_infusion:
            assert d.action in (SurgeAction.HOLD_BED, SurgeAction.EXPEDITE_ADMIT), d.entry.bed


def test_totality_over_feature_space() -> None:
    """Every combination of tri-state features maps to exactly one action."""
    tri = (True, False, None)
    base = CENSUS.entries[0]
    count = 0
    for combo in product(tri, repeat=6):
        adm, comfort, monitor, amb, wc, safe = combo
        entry = CensusEntry(
            bed="X",
            patient=base.patient,
            esi=3,
            chief_complaint="x",
            status="x",
            features=CareFeatures(
                admission_indicated=adm,
                comfort_focused=comfort,
                cardiac_monitor_required=monitor,
                ambulatory=amb,
                workup_complete=wc,
                safe_for_discharge=safe,
            ),
        )
        decision = classify(entry)
        assert isinstance(decision.action, SurgeAction)
        # A tethered patient is never sent home or to chairs.
        if monitor is True and adm is not True:
            assert decision.action is SurgeAction.HOLD_BED
        count += 1
    assert count == 3**6


def test_summary_math_is_consistent() -> None:
    text = PLAN.summary()
    assert "17 beds freed" in text
    open_now = CENSUS.department_beds - len(CENSUS.entries)
    assert f"{open_now + 17} beds now" in text
    assert f"{open_now + 17 + 4} after pull" in text
