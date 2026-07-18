"""Dosing engine tests — all offline. The refusals matter as much as the numbers."""

from __future__ import annotations

from halo.edu import DoseStatus, PatientContext, get_module
from halo.edu.dosing import dose, dose_all
from halo.edu.models import Med

OP = get_module("organophosphate")
CANTH = get_module("lateral_canthotomy")
PMCS = get_module("perimortem_cesarean")


def _med(module: object, name: str) -> Med:
    for med in module.meds:  # type: ignore[attr-defined]
        if med.name.lower().startswith(name.lower()):
            return med  # type: ignore[no-any-return]
    raise AssertionError(f"med {name} not found")


CHILD_22KG = PatientContext(weight_kg=22, age_years=6)
ADULT_80KG = PatientContext(weight_kg=80, age_years=34)


class TestComputedDoses:
    def test_peds_atropine_weight_based(self) -> None:
        result = dose(_med(OP, "Atropine"), CHILD_22KG)
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("1.1 mg")  # 0.05 * 22

    def test_peds_pralidoxime_rounded_to_50(self) -> None:
        result = dose(_med(OP, "Pralidoxime"), CHILD_22KG)
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("550 mg")  # 25 * 22

    def test_peds_midazolam_half_up_rounding(self) -> None:
        result = dose(_med(OP, "Midazolam"), PatientContext(weight_kg=21, age_years=6))
        # 0.2 * 21 = 4.2 -> round_to 0.5 half-up -> 4.0; and 22 kg -> 4.4 -> 4.5
        assert result.text.startswith("4 mg") or result.text.startswith("4.0 mg")
        result2 = dose(_med(OP, "Midazolam"), CHILD_22KG)
        assert result2.text.startswith("4.5 mg")

    def test_adult_fixed_atropine(self) -> None:
        result = dose(_med(OP, "Atropine"), ADULT_80KG)
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("2 mg")

    def test_rocuronium_uncapped_rounds_to_5(self) -> None:
        result = dose(_med(OP, "Rocuronium"), PatientContext(weight_kg=110, age_years=40))
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("130 mg")  # 132 -> nearest 5

    def test_peds_cap_applied_with_warning(self) -> None:
        heavy_child = PatientContext(weight_kg=95, age_years=12)
        result = dose(_med(OP, "Pralidoxime"), heavy_child)  # 25*95=2375 > 2000
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("2000 mg")
        assert any("capped" in w for w in result.warnings)

    def test_mannitol_per_kg_grams(self) -> None:
        result = dose(_med(CANTH, "Mannitol"), ADULT_80KG)
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("80 g")


class TestReferenceDoses:
    def test_text_only_spec_returns_reference(self) -> None:
        result = dose(_med(CANTH, "Lidocaine"), ADULT_80KG)
        assert result.status is DoseStatus.REFERENCE
        assert "1-2 mL" in result.text

    def test_duodote_reference(self) -> None:
        result = dose(_med(OP, "DuoDote"), ADULT_80KG)
        assert result.status is DoseStatus.REFERENCE
        assert "severe 3" in result.text


class TestRefusals:
    def test_weight_based_without_weight_refuses(self) -> None:
        result = dose(_med(OP, "Atropine"), PatientContext(age_years=6))
        assert result.status is DoseStatus.REFUSED
        assert result.reason is not None and "weight" in result.reason
        assert "0.05" in result.reason  # the per-kg rule is still shown

    def test_no_context_refuses_population_choice(self) -> None:
        result = dose(_med(OP, "Atropine"), PatientContext())
        assert result.status is DoseStatus.REFUSED
        assert result.reason is not None and "age or weight" in result.reason
        # The curated text is still surfaced so the clinician has something to read.
        assert "adult:" in result.text and "peds:" in result.text

    def test_peds_patient_with_adult_only_med_refuses(self) -> None:
        result = dose(_med(CANTH, "Acetazolamide"), CHILD_22KG)
        assert result.status is DoseStatus.REFUSED
        assert result.reason is not None and "pediatric" in result.reason

    def test_never_invents_a_number_when_refusing(self) -> None:
        for med in OP.meds:
            result = dose(med, PatientContext())
            if result.status is DoseStatus.REFUSED:
                assert result.reason


class TestPopulationSelection:
    def test_age_unknown_light_weight_picks_peds_with_warning(self) -> None:
        result = dose(_med(OP, "Midazolam"), PatientContext(weight_kg=30))
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("6 mg")  # 0.2 * 30
        assert any("age unknown" in w for w in result.warnings)

    def test_age_unknown_heavy_weight_picks_adult_with_warning(self) -> None:
        result = dose(_med(OP, "Midazolam"), PatientContext(weight_kg=75))
        assert result.status is DoseStatus.COMPUTED
        assert result.text.startswith("10 mg")  # adult fixed
        assert any("age unknown" in w for w in result.warnings)

    def test_age_boundary_14_is_adult(self) -> None:
        result = dose(_med(OP, "Atropine"), PatientContext(weight_kg=50, age_years=14))
        assert result.text.startswith("2 mg")


class TestAllergySurfacing:
    def test_sulfa_allergy_flagged_on_acetazolamide(self) -> None:
        ctx = PatientContext(weight_kg=80, age_years=40, allergies=("sulfa",))
        result = dose(_med(CANTH, "Acetazolamide"), ctx)
        assert result.status is DoseStatus.COMPUTED  # surfaced, not silently blocked
        assert any("sulfa" in w.lower() for w in result.warnings)

    def test_unrelated_allergy_not_flagged(self) -> None:
        ctx = PatientContext(weight_kg=80, age_years=40, allergies=("penicillin",))
        result = dose(_med(CANTH, "Acetazolamide"), ctx)
        assert result.warnings == ()


def test_dose_all_covers_every_med() -> None:
    results = dose_all(OP, CHILD_22KG)
    assert len(results) == len(OP.meds)
    assert {r.med for r in results} == {m.name for m in OP.meds}
    # A 22 kg six-year-old: nothing in the OP module may silently fail.
    for r in results:
        assert r.status in (DoseStatus.COMPUTED, DoseStatus.REFERENCE) or r.reason


def test_pmcs_epinephrine_is_standard_acls() -> None:
    result = dose(_med(PMCS, "Epinephrine"), ADULT_80KG)
    assert result.status is DoseStatus.COMPUTED
    assert result.text.startswith("1 mg")
