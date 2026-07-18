"""Core data types for the readiness & CME module. Stdlib dataclasses — no framework.

The corpus is *data, not model output*: every ``ProcedureModule`` is a curated,
versioned, citable artifact. Clinical facts (steps, doses, contraindications)
live here and in ``content/*.json`` — never in a prompt, never generated at
runtime. ``review.status`` stays ``draft`` until a physician signs off, and the
draft state is rendered on every surface that shows the content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReviewStatus(str, Enum):
    """Editorial state of a content module. Only a human sets ``reviewed``."""

    DRAFT = "draft"
    REVIEWED = "reviewed"


class DoseStatus(str, Enum):
    """Outcome of a dose computation. ``refused`` is the fail-closed state."""

    COMPUTED = "computed"  # arithmetic performed from patient context
    REFERENCE = "reference"  # curated dose text returned verbatim (no arithmetic)
    REFUSED = "refused"  # required patient context missing — no number invented


@dataclass(frozen=True)
class ReviewInfo:
    """Provenance of a content module. ``reviewed_by`` is a human name or None."""

    status: ReviewStatus
    author: str
    date: str  # ISO date the content was authored/last edited
    version: int
    reviewed_by: str | None = None


@dataclass(frozen=True)
class DoseSpec:
    """One dosing rule for one population (adult or peds).

    ``text`` is the curated, human-readable dose line and is always present —
    it is what a clinician sees even when nothing is computable. The numeric
    fields make the spec computable: ``per_kg`` implies weight-based dosing
    (and requires ``max_amount`` at validation time unless explicitly
    uncapped); ``fixed`` is a single computable amount.
    """

    text: str
    unit: str = "mg"
    per_kg: float | None = None
    fixed: float | None = None
    max_amount: float | None = None
    round_to: float | None = None
    uncapped: bool = False  # explicit opt-out of max_amount (e.g. RSI paralytic)


@dataclass(frozen=True)
class Med:
    """A medication used in the procedure, with population-specific specs."""

    name: str
    role: str  # why it appears, e.g. "antidote — muscarinic antagonist"
    route: str
    adult: DoseSpec | None = None
    peds: DoseSpec | None = None
    cautions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    """One numbered procedural step.

    ``accept`` powers deterministic drill grading: an answer matches when any
    inner group has all of its phrases present (OR of ANDs, case-insensitive).
    ``critical`` steps are the ones whose omission is graded as a critical
    miss. ``media`` names a 2D diagram id from ``diagrams.py`` (a ``model3d:``
    prefix is reserved for future 3D assets — none ship today).
    """

    n: int
    action: str
    detail: str = ""
    critical: bool = False
    accept: tuple[tuple[str, ...], ...] = ()
    media: str | None = None


@dataclass(frozen=True)
class TimeTarget:
    """The clock the team is racing. ``minutes`` is None when narrative-only."""

    label: str
    minutes: int | None = None


@dataclass(frozen=True)
class DecisionPoint:
    """One graded prompt in a drill. ``ideal`` is the model answer shown after."""

    prompt: str
    ideal: str
    accept: tuple[tuple[str, ...], ...]
    critical: bool = False
    expected_step: int | None = None  # links back to Step.n when applicable


@dataclass(frozen=True)
class Drill:
    """A scripted scenario over one module. Stems are fictional — synthetic only."""

    stem: str
    decision_points: tuple[DecisionPoint, ...]
    pass_threshold: float = 0.8
    synthetic: bool = True


@dataclass(frozen=True)
class Reference:
    """A citation. ``label`` is the short display name, ``cite`` the full form."""

    label: str
    cite: str


@dataclass(frozen=True)
class ProcedureModule:
    """One HALO procedure: just-in-time card + drill + med table, fully cited."""

    id: str
    name: str
    category: str
    one_liner: str
    aliases: tuple[str, ...]
    indications: tuple[str, ...]
    contraindications: tuple[str, ...]
    time_target: TimeTarget
    team_calls: tuple[str, ...]  # who to summon in parallel, never instead
    equipment: tuple[str, ...]
    steps: tuple[Step, ...]
    meds: tuple[Med, ...]
    pitfalls: tuple[str, ...]
    success_criteria: tuple[str, ...]
    aftercare: tuple[str, ...]
    references: tuple[Reference, ...]
    review: ReviewInfo
    drill: Drill | None = None


@dataclass(frozen=True)
class PatientContext:
    """What dosing needs to know. ``None`` means not available — never guessed.

    Sourced from CLI flags or a FHIR bundle (``halo.edu.fhir``). Synthetic
    data only, per repo policy.
    """

    weight_kg: float | None = None
    age_years: float | None = None
    sex: str | None = None
    pregnant: bool | None = None
    allergies: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoseResult:
    """Outcome of dosing one med for one patient. Total — every input maps here."""

    status: DoseStatus
    med: str
    route: str
    text: str  # the line a clinician reads, whatever the status
    reason: str | None = None  # populated when status is REFUSED
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepGrade:
    """Deterministic grade for one decision point."""

    prompt: str
    hit: bool
    critical: bool
    matched_group: tuple[str, ...] | None = None  # the accept group that fired
    ideal: str = ""
    via: str = "keyword"  # "keyword" | "llm" — how the hit was adjudicated


@dataclass(frozen=True)
class DrillResult:
    """Outcome of one drill run. ``passed`` requires score AND zero critical misses."""

    module_id: str
    content_version: str
    grades: tuple[StepGrade, ...]
    score: float
    critical_misses: tuple[str, ...]
    passed: bool
    elapsed_s: float | None = None
    trainee: str | None = None
    grades_via: str = "keyword"  # "keyword" | "keyword+llm"
    events: dict[str, str] = field(default_factory=dict)  # prompt -> raw answer
