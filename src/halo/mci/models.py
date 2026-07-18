"""Core data types for MCI triage. Stdlib dataclasses — no framework in the core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TriageCategory(str, Enum):
    """SALT triage categories plus the fail-closed escalation state."""

    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    MINIMAL = "minimal"
    EXPECTANT = "expectant"
    DEAD = "dead"
    UNABLE_TO_TRIAGE = "unable_to_triage"


@dataclass(frozen=True)
class Observations:
    """Structured SALT observations. ``None`` means not documented in the note.

    ``breathing`` is assessed after airway-opening per SALT. All values are
    observations extracted from the record — none of them is a triage decision.
    """

    breathing: bool | None = None
    obeys_commands: bool | None = None
    peripheral_pulse: bool | None = None
    respiratory_distress: bool | None = None
    major_hemorrhage_uncontrolled: bool | None = None
    minor_injuries_only: bool | None = None
    can_walk: bool | None = None  # SALT global sort; informs assessment order, not category


@dataclass(frozen=True)
class TriageResult:
    category: TriageCategory
    rationale: str
    missing_fields: tuple[str, ...] = ()
    evidence: dict[str, str] = field(default_factory=dict)  # observation field -> note quote
