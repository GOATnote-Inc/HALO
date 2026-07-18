"""Surge bed clearance — reverse triage of the existing ED census.

When an MCI is declared, the first battle is the department you already have:
which of the current patients can move so beds exist when the wave arrives.
The concept is published as **reverse triage** (Kelen et al., *Lancet*
2006;368:1984-90 — creating surge capacity by disposition-classifying current
patients) and appears in ACEP/ASPR surge doctrine as vertical care and
immediate bed availability.

Deterministic rule table — no model in the loop for moving patients. The
asymmetry INVERTS here relative to door triage: at the door, missing data
escalates the patient UP; in the census, missing data means DON'T MOVE
(HOLD_BED). Both are the same principle — never let absent documentation
produce the dangerous action.

Actions:
- EXPEDITE_ADMIT — already needs inpatient care; the bed is freed by pulling
  the patient upstairs, not by moving them to a chair (NSTEMI on heparin,
  post-thrombolytic stroke, hypoxemic pneumonia, comfort-focused hospice).
- DISCHARGE_NOW  — workup complete, stable, safe to go.
- VERTICAL_CHAIRS — stable and ambulatory with no monitor/O2/infusion tether;
  workup continues in chairs / results-waiting.
- HOLD_BED       — tethered to the bed (monitor, oxygen, infusion,
  post-thrombolytic checks) or not determinable -> do not move.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from halo.mci.census import Census, CensusEntry


class SurgeAction(str, Enum):
    EXPEDITE_ADMIT = "expedite_admit"
    DISCHARGE_NOW = "discharge_now"
    VERTICAL_CHAIRS = "vertical_chairs"
    HOLD_BED = "hold_bed"


@dataclass(frozen=True)
class SurgeDecision:
    entry: CensusEntry
    action: SurgeAction
    rationale: str
    required_steps: tuple[str, ...]
    frees_bed_now: bool  # True: bed empties on execution without an upstream dependency


@dataclass(frozen=True)
class SurgePlan:
    decisions: tuple[SurgeDecision, ...]
    department_beds: int

    @property
    def freed_now(self) -> int:
        return sum(1 for d in self.decisions if d.frees_bed_now)

    @property
    def freed_by_admission_pull(self) -> int:
        return sum(1 for d in self.decisions if d.action is SurgeAction.EXPEDITE_ADMIT)

    @property
    def held(self) -> int:
        return sum(1 for d in self.decisions if d.action is SurgeAction.HOLD_BED)

    @property
    def monitors_freed(self) -> int:
        return sum(
            1
            for d in self.decisions
            if d.action is SurgeAction.EXPEDITE_ADMIT
            and d.entry.features.cardiac_monitor_required is True
        )

    def summary(self) -> str:
        dc = sum(1 for d in self.decisions if d.action is SurgeAction.DISCHARGE_NOW)
        ch = sum(1 for d in self.decisions if d.action is SurgeAction.VERTICAL_CHAIRS)
        open_now = self.department_beds - len(self.decisions)
        return (
            f"{dc} discharge + {ch} to chairs = {self.freed_now} beds freed by ED action alone; "
            f"{self.freed_by_admission_pull} more (incl. {self.monitors_freed} monitored) free "
            f"when inpatient pull completes; {self.held} hold. "
            f"Capacity if fully executed: {open_now + self.freed_now} beds now, "
            f"{open_now + self.freed_now + self.freed_by_admission_pull} after pull, "
            f"of {self.department_beds}."
        )


def _tethers(entry: CensusEntry) -> list[str]:
    f = entry.features
    tethers = []
    if f.post_thrombolytic:
        tethers.append("post-thrombolytic monitoring")
    if f.cardiac_monitor_required:
        tethers.append("cardiac monitor")
    if f.oxygen_required:
        tethers.append("oxygen")
    if f.continuous_infusion:
        tethers.append("continuous infusion")
    return tethers


def classify(entry: CensusEntry) -> SurgeDecision:
    """Total function: every census entry maps to exactly one surge action."""
    f = entry.features

    if f.admission_indicated is True:
        if f.comfort_focused is True:
            return SurgeDecision(
                entry,
                SurgeAction.EXPEDITE_ADMIT,
                "Comfort-focused care — move to a quiet inpatient bed, not a hallway; "
                "align with documented goals of care.",
                ("Confirm goals of care with family", "Request inpatient hospice/private bed"),
                frees_bed_now=False,
            )
        tethers = _tethers(entry)
        return SurgeDecision(
            entry,
            SurgeAction.EXPEDITE_ADMIT,
            "Inpatient care already indicated"
            + (f" ({', '.join(tethers)})" if tethers else "")
            + " — the bed frees when the floor pulls the patient, so escalate the pull now.",
            ("Escalate bed assignment to inpatient charge", "Transport on arrival of bed"),
            frees_bed_now=False,
        )

    tethers = _tethers(entry)
    if tethers:
        return SurgeDecision(
            entry,
            SurgeAction.HOLD_BED,
            f"Tethered to the bed: {', '.join(tethers)}. Re-assess when the tether clears.",
            ("Re-evaluate disposition at next assessment",),
            frees_bed_now=False,
        )

    if f.workup_complete is True and f.safe_for_discharge is True:
        return SurgeDecision(
            entry,
            SurgeAction.DISCHARGE_NOW,
            "Workup complete and documented safe for discharge.",
            ("Discharge instructions", "Prescriptions to pharmacy", "Bed to environmental"),
            frees_bed_now=True,
        )

    if f.ambulatory is True and f.safe_for_discharge is False and f.workup_complete is False:
        return SurgeDecision(
            entry,
            SurgeAction.VERTICAL_CHAIRS,
            "Stable and untethered with workup in progress — continue as vertical care "
            "in chairs/results-waiting.",
            ("Move to chairs with belongings", "Flag pending results to chairs team"),
            frees_bed_now=True,
        )

    # Anything else is undetermined — fail closed: do not move a patient on missing data.
    unknowns = [
        name
        for name in (
            "admission_indicated",
            "ambulatory",
            "workup_complete",
            "safe_for_discharge",
        )
        if getattr(f, name) is None
    ]
    return SurgeDecision(
        entry,
        SurgeAction.HOLD_BED,
        "Not determinable from the record"
        + (f" (undocumented: {', '.join(unknowns)})" if unknowns else "")
        + " — do not move a patient on missing data; assess at the bedside.",
        ("Bedside re-assessment by charge nurse",),
        frees_bed_now=False,
    )


def surge_plan(census: Census) -> SurgePlan:
    return SurgePlan(
        decisions=tuple(classify(e) for e in census.entries),
        department_beds=census.department_beds,
    )
