"""FHIR panel store over the Abridge synthetic-ambient-fhir-25 dataset.

Everything in this module is deterministic: patient search, candidate scoring,
and the care-modifier flag rules. Claude proposes; this module verifies and
decides. Synthetic data only.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PANEL_PATH = (
    Path(__file__).parents[3] / "synthetic-ambient-fhir-25" / "synthetic-ambient-fhir-25.jsonl"
)


@dataclass(frozen=True)
class PanelPatient:
    patient_id: str
    given_names: tuple[str, ...]
    family_name: str
    gender: str  # FHIR administrative gender
    birth_date: str  # ISO date
    medication_labels: tuple[str, ...]
    condition_labels: tuple[str, ...]
    visit_titles: tuple[str, ...]

    @property
    def display_name(self) -> str:
        return f"{' '.join(self.given_names)} {self.family_name}"

    def age_on(self, iso_date: str) -> int:
        by, bm, bd = (int(x) for x in self.birth_date.split("-"))
        y, m, d = (int(x) for x in iso_date.split("-"))
        return y - by - ((m, d) < (bm, bd))


@dataclass(frozen=True)
class CareFlag:
    flag_id: str
    severity: str  # "high" | "moderate"
    summary: str
    why: str
    provenance: tuple[str, ...]  # the chart labels that triggered the rule


@dataclass(frozen=True)
class Candidate:
    patient: PanelPatient
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityCues:
    """Cues extracted from a field note. ``None`` = not documented."""

    family_name: str | None = None
    given_name: str | None = None
    gender: str | None = None  # "male" | "female"
    approximate_age: int | None = None


def load_panel(path: str | Path | None = None) -> tuple[PanelPatient, ...]:
    p = Path(path or os.environ.get("HALO_PANEL_PATH", DEFAULT_PANEL_PATH))
    return _load_panel_cached(str(p.resolve()))


@lru_cache(maxsize=4)
def _load_panel_cached(resolved: str) -> tuple[PanelPatient, ...]:
    patients: list[PanelPatient] = []
    with open(resolved, encoding="utf-8") as fh:
        for line in fh:
            rec: dict[str, Any] = json.loads(line)
            fhir_patient = rec["patient_context"]["patient"]
            summary = rec["patient_context"]["longitudinal_summary"]
            name = fhir_patient["name"][0]
            patients.append(
                PanelPatient(
                    patient_id=rec["id"].split("::")[0],
                    given_names=tuple(name.get("given", [])),
                    family_name=name["family"],
                    gender=fhir_patient["gender"],
                    birth_date=fhir_patient["birthDate"],
                    medication_labels=tuple(summary.get("medication_labels", [])),
                    condition_labels=tuple(summary.get("condition_labels", [])),
                    visit_titles=(rec["metadata"]["visit_title"],),
                )
            )
    return tuple(patients)


# --- Deterministic identity scoring -------------------------------------------------

_STRONG = 0.80
_POSSIBLE = 0.50


def _name_similarity(a: str, b: str) -> float:
    a, b = a.lower().strip(". "), b.lower().strip(". ")
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Field notes often carry initials or truncations ("Latoyia W.", "Wilk-something").
    if a.startswith(b) or b.startswith(a):
        return 0.9 if min(len(a), len(b)) > 1 else 0.6
    return SequenceMatcher(None, a, b).ratio()


def score_candidate(patient: PanelPatient, cues: IdentityCues, *, on_date: str) -> Candidate:
    """Deterministic match score in [0, 1]. A hard demographic mismatch zeroes it."""
    reasons: list[str] = []
    parts: list[float] = []

    if cues.gender is not None:
        if cues.gender != patient.gender:
            return Candidate(patient, 0.0, ("gender mismatch",))
        reasons.append("gender matches")

    if cues.family_name is not None:
        s = _name_similarity(cues.family_name, patient.family_name)
        parts.append(s * 0.5)
        reasons.append(f"family-name similarity {s:.2f}")
    if cues.given_name is not None:
        s = max(_name_similarity(cues.given_name, g) for g in patient.given_names)
        parts.append(s * 0.3)
        reasons.append(f"given-name similarity {s:.2f}")
    if cues.approximate_age is not None:
        diff = abs(patient.age_on(on_date) - cues.approximate_age)
        s = max(0.0, 1.0 - diff / 10.0)
        parts.append(s * 0.2)
        reasons.append(f"age delta {diff}y")

    if not parts:
        return Candidate(patient, 0.0, ("no usable cues",))
    # Normalize by the weight actually in play so sparse cues aren't punished twice.
    weight = (
        (0.5 if cues.family_name is not None else 0)
        + (0.3 if cues.given_name is not None else 0)
        + (0.2 if cues.approximate_age is not None else 0)
    )
    return Candidate(patient, sum(parts) / weight, tuple(reasons))


def match_candidates(
    cues: IdentityCues, *, on_date: str, panel: tuple[PanelPatient, ...] | None = None
) -> tuple[str, tuple[Candidate, ...]]:
    """Return (status, ranked candidates). Status is fail-closed:

    - ``strong_candidate`` — exactly one candidate scores strong and it leads
      the runner-up by a clear margin. Still requires human confirmation.
    - ``possible`` — one or more plausible candidates; human must adjudicate.
    - ``no_match`` — treat as unknown patient.

    Never returns "confirmed": identity confirmation is a human act.
    """
    ranked = sorted(
        (score_candidate(p, cues, on_date=on_date) for p in (panel or load_panel())),
        key=lambda c: c.score,
        reverse=True,
    )
    top = [c for c in ranked if c.score >= _POSSIBLE][:5]
    if not top:
        return "no_match", ()
    # Demographics alone (gender/age) are not identifying — a name cue is
    # required before any candidate may rank "strong".
    has_name_cue = cues.family_name is not None or cues.given_name is not None
    lead = top[0]
    runner_up = top[1].score if len(top) > 1 else 0.0
    if has_name_cue and lead.score >= _STRONG and lead.score - runner_up >= 0.15:
        return "strong_candidate", tuple(top)
    return "possible", tuple(top)


# --- Deterministic care-modifier flag rules ------------------------------------------

_MED_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        r"clopidogrel|warfarin|apixaban|rivaroxaban|dabigatran|enoxaparin|heparin",
        "antithrombotic_therapy",
        "high",
        "On antithrombotic therapy — occult hemorrhage risk; low threshold for "
        "imaging and for upgrading triage after any significant mechanism.",
    ),
    (
        r"metoprolol|atenolol|propranolol|carvedilol|bisoprolol",
        "beta_blockade",
        "high",
        "Beta-blocked — tachycardic response to hemorrhage may be masked; do not "
        "rely on heart rate to recognize shock.",
    ),
    (
        r"epinephrine .*auto-injector",
        "anaphylaxis_history",
        "moderate",
        "Carries an epinephrine auto-injector — documented severe allergy; "
        "screen exposures before medications are given.",
    ),
    (
        r"nitroglycerin",
        "coronary_disease",
        "moderate",
        "On nitrate therapy — known coronary disease; physiologic stress of the "
        "incident may precipitate ischemia.",
    ),
    (
        r"hydrocodone|tramadol|meperidine|oxycodone|morphine|fentanyl",
        "opioid_therapy",
        "moderate",
        "Baseline opioid therapy — factor tolerance into analgesia dosing and "
        "mental-status interpretation.",
    ),
)

_CONDITION_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        r"normal pregnancy \(finding\)",
        "pregnancy",
        "high",
        "Documented current pregnancy — left-lateral positioning, early OB "
        "involvement, and fetal assessment; vitals interpretation differs.",
    ),
    (
        r"anemia \(disorder\)",
        "baseline_anemia",
        "moderate",
        "Baseline anemia — reduced physiologic reserve for hemorrhage.",
    ),
)

_VISIT_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        r"hospice",
        "comfort_focused_goals",
        "high",
        "Documented hospice enrollment — confirm goals of care before "
        "resource-intensive interventions; align with recorded wishes.",
    ),
)


def care_flags(patient: PanelPatient) -> tuple[CareFlag, ...]:
    flags: dict[str, CareFlag] = {}

    def apply(
        rules: tuple[tuple[str, str, str, str], ...], labels: tuple[str, ...], kind: str
    ) -> None:
        for pattern, flag_id, severity, why in rules:
            hits = tuple(lb for lb in labels if re.search(pattern, lb, re.IGNORECASE))
            if hits and flag_id not in flags:
                flags[flag_id] = CareFlag(
                    flag_id=flag_id,
                    severity=severity,
                    summary=f"{flag_id.replace('_', ' ')} ({kind})",
                    why=why,
                    provenance=hits,
                )

    apply(_MED_RULES, patient.medication_labels, "active medication")
    apply(_CONDITION_RULES, patient.condition_labels, "active condition")
    apply(_VISIT_RULES, patient.visit_titles, "documented encounter")
    ordered = sorted(flags.values(), key=lambda f: (f.severity != "high", f.flag_id))
    return tuple(ordered)


@dataclass(frozen=True)
class ChartContext:
    patient: PanelPatient
    flags: tuple[CareFlag, ...] = field(default_factory=tuple)


def chart_context(patient_id: str, panel: tuple[PanelPatient, ...] | None = None) -> ChartContext:
    for p in panel or load_panel():
        if p.patient_id == patient_id:
            return ChartContext(patient=p, flags=care_flags(p))
    raise KeyError(f"unknown patient_id: {patient_id}")
