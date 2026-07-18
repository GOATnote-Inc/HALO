"""Deterministic SALT triage tests — all offline. Goldset gate: under-triage FN = 0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from halo.mci import Observations, TriageCategory, salt_triage

GOLDSET = json.loads((Path(__file__).parent / "fixtures" / "mci_goldset.json").read_text())
CASES: list[dict[str, Any]] = GOLDSET["cases"]

# Categories that are unsafe to assign to a gold-IMMEDIATE patient (under-triage).
UNSAFE_FOR_IMMEDIATE = {
    TriageCategory.DELAYED,
    TriageCategory.MINIMAL,
    TriageCategory.EXPECTANT,
    TriageCategory.DEAD,
}


def _obs(case: dict[str, Any]) -> Observations:
    return Observations(**case["gold_observations"])


def test_goldset_is_synthetic() -> None:
    assert GOLDSET["synthetic"] is True
    assert all(c["synthetic"] is True for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_goldset_category(case: dict[str, Any]) -> None:
    result = salt_triage(_obs(case))
    assert result.category is TriageCategory(case["gold_category"])


def test_zero_under_triage_on_goldset() -> None:
    """The cardinal metric: no gold-IMMEDIATE patient may be triaged down."""
    misses = [
        c["id"]
        for c in CASES
        if c["gold_category"] == "immediate"
        and salt_triage(_obs(c)).category in UNSAFE_FOR_IMMEDIATE
    ]
    assert misses == []


def test_expectant_requires_explicit_human_decision() -> None:
    obs = Observations(
        breathing=True,
        obeys_commands=False,
        peripheral_pulse=False,
        respiratory_distress=True,
    )
    # Without the human flag: IMMEDIATE, never expectant.
    assert salt_triage(obs).category is TriageCategory.IMMEDIATE
    assert salt_triage(obs, likely_survivable=None).category is TriageCategory.IMMEDIATE
    assert salt_triage(obs, likely_survivable=True).category is TriageCategory.IMMEDIATE
    # Only an explicit False produces EXPECTANT.
    assert salt_triage(obs, likely_survivable=False).category is TriageCategory.EXPECTANT


def test_missing_breathing_fails_closed() -> None:
    result = salt_triage(Observations())
    assert result.category is TriageCategory.UNABLE_TO_TRIAGE
    assert "breathing" in result.missing_fields


def test_known_life_threat_dominates_unknowns() -> None:
    # Only one screen answer known — and it is bad. Must be IMMEDIATE, not escalate-and-wait.
    result = salt_triage(Observations(breathing=True, peripheral_pulse=False))
    assert result.category is TriageCategory.IMMEDIATE


def test_all_yes_with_unknown_screen_field_fails_closed() -> None:
    result = salt_triage(
        Observations(
            breathing=True,
            obeys_commands=True,
            peripheral_pulse=True,
            respiratory_distress=False,
            # major_hemorrhage_uncontrolled unknown -> cannot rule out life threat
        )
    )
    assert result.category is TriageCategory.UNABLE_TO_TRIAGE
    assert "hemorrhage_controlled" in result.missing_fields


def test_unknown_injury_extent_defaults_up_to_delayed() -> None:
    result = salt_triage(
        Observations(
            breathing=True,
            obeys_commands=True,
            peripheral_pulse=True,
            respiratory_distress=False,
            major_hemorrhage_uncontrolled=False,
            minor_injuries_only=None,
        )
    )
    assert result.category is TriageCategory.DELAYED


def test_not_breathing_is_dead() -> None:
    assert salt_triage(Observations(breathing=False)).category is TriageCategory.DEAD


def test_totality_over_full_input_space() -> None:
    """Every combination of tri-state inputs maps to a category (no exceptions)."""
    tri = (True, False, None)
    count = 0
    for b in tri:
        for oc in tri:
            for pp in tri:
                for rd in tri:
                    for mh in tri:
                        for mi in tri:
                            for ls in tri:
                                result = salt_triage(
                                    Observations(
                                        breathing=b,
                                        obeys_commands=oc,
                                        peripheral_pulse=pp,
                                        respiratory_distress=rd,
                                        major_hemorrhage_uncontrolled=mh,
                                        minor_injuries_only=mi,
                                    ),
                                    likely_survivable=ls,
                                )
                                assert isinstance(result.category, TriageCategory)
                                # EXPECTANT only ever with the explicit human flag.
                                if result.category is TriageCategory.EXPECTANT:
                                    assert ls is False
                                count += 1
    assert count == 3**7
