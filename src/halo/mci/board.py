"""Live track-board state: execute, move, clear — the way an EHR anticipates.

The census is the starting state; the surge plan is a *proposal*; this module is
the execution layer. EHR-real semantics:

- Actions are validated against the deterministic surge classification. A bed
  classified HOLD cannot be discharged from the board — the API refuses with
  the rationale (override is a bedside re-assessment, not a click).
- EXPEDITE_ADMIT is two-phase, like real bed management: escalate the pull
  (bed still occupied) -> inpatient bed assigned -> transport (bed freed).
- Chairs patients remain on the board in the chairs area and can be discharged
  from there when results clear.
- Every transition is stamped into an activity log (the audit trail), and every
  transition is undoable — mistakes are an anticipated part of a real board.

State is in-memory and per-process: a demo of the interaction model, not a
persistence layer. ``reset()`` restores the declared-moment census.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from halo.mci.census import Census, CensusEntry, load_census
from halo.mci.surge import SurgeAction, SurgeDecision, classify

# Where a patient can be on the board.
LOC_BED = "bed"
LOC_CHAIRS = "chairs"
LOC_DEPARTED = "departed"

# Wall-clock is intentionally logical (T+n events), not real time — deterministic demos.


@dataclass
class PatientState:
    entry: CensusEntry
    decision: SurgeDecision | None = None
    location: str = LOC_BED
    disposition: str | None = None  # "discharged" | "admitted" when departed
    pull_escalated: bool = False


@dataclass
class BoardEvent:
    seq: int
    text: str
    undo: dict[str, Any] = field(default_factory=dict)


class Board:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        census: Census = load_census()
        self.department_beds = census.department_beds
        self.assessed = False
        self.plan_summary: str | None = None
        self.patients: dict[str, PatientState] = {
            e.bed: PatientState(entry=e) for e in census.entries
        }
        self.events: list[BoardEvent] = []
        self._seq = 0

    # -- transitions ---------------------------------------------------------

    def assess(self) -> None:
        from halo.mci.surge import surge_plan

        for ps in self.patients.values():
            ps.decision = classify(ps.entry)
        self.assessed = True
        self.plan_summary = surge_plan(load_census()).summary()
        self._log("Surge assessment run — reverse triage classified every occupied bed.", {})

    def act(self, bed: str, action: str) -> None:
        ps = self.patients.get(bed)
        if ps is None:
            raise BoardError(404, f"no patient on the board at bed {bed}")
        if not self.assessed or ps.decision is None:
            raise BoardError(409, "run the surge assessment before executing board actions")
        name = ps.entry.patient.display_name
        classified = ps.decision.action

        if action == "reassess":
            self._log(f"{bed} {name}: bedside re-assessment requested.", {"noop": True})
            return

        if ps.location == LOC_DEPARTED:
            raise BoardError(409, f"{name} has already departed the board")

        if action == "discharge":
            if ps.location == LOC_CHAIRS:
                pass  # discharge from chairs is always the natural exit
            elif classified is not SurgeAction.DISCHARGE_NOW:
                raise BoardError(
                    409,
                    f"classified {classified.value} — {ps.decision.rationale} "
                    "Override is a bedside re-assessment, not a click.",
                )
            prev = ps.location
            ps.location = LOC_DEPARTED
            ps.disposition = "discharged"
            self._log(f"{bed} {name}: discharged.", {"bed": bed, "location": prev})
            return

        if action == "to_chairs":
            if classified is not SurgeAction.VERTICAL_CHAIRS or ps.location != LOC_BED:
                raise BoardError(
                    409,
                    f"classified {classified.value} — only VERTICAL_CHAIRS patients move "
                    "to chairs.",
                )
            ps.location = LOC_CHAIRS
            self._log(
                f"{bed} {name}: moved to chairs (vertical care) — bed freed.",
                {"bed": bed, "location": LOC_BED},
            )
            return

        if action == "escalate_pull":
            if classified is not SurgeAction.EXPEDITE_ADMIT or ps.pull_escalated:
                raise BoardError(409, "escalate_pull applies once, to EXPEDITE_ADMIT beds")
            ps.pull_escalated = True
            self._log(
                f"{bed} {name}: inpatient pull escalated — awaiting bed assignment.",
                {"bed": bed, "pull": False},
            )
            return

        if action == "assign_bed":
            if classified is not SurgeAction.EXPEDITE_ADMIT or not ps.pull_escalated:
                raise BoardError(409, "assign_bed requires an escalated EXPEDITE_ADMIT pull")
            ps.location = LOC_DEPARTED
            ps.disposition = "admitted"
            self._log(
                f"{bed} {name}: inpatient bed assigned — transported, ED bed freed.",
                {"bed": bed, "location": LOC_BED},
            )
            return

        raise BoardError(422, f"unknown board action: {action}")

    def undo(self) -> None:
        while self.events:
            event = self.events.pop()
            if event.undo.get("noop"):
                continue
            if not event.undo:
                self.events.append(event)  # assessment marker — nothing to undo
                return
            ps = self.patients[event.undo["bed"]]
            if "pull" in event.undo:
                ps.pull_escalated = event.undo["pull"]
            if "location" in event.undo:
                ps.location = event.undo["location"]
                ps.disposition = None
            return

    # -- views ---------------------------------------------------------------

    def counts(self) -> dict[str, int]:
        in_bed = [p for p in self.patients.values() if p.location == LOC_BED]
        return {
            "department_beds": self.department_beds,
            "occupied": len(in_bed),
            "open_beds": self.department_beds - len(in_bed),
            "in_chairs": sum(1 for p in self.patients.values() if p.location == LOC_CHAIRS),
            "departed": sum(1 for p in self.patients.values() if p.location == LOC_DEPARTED),
            "awaiting_pull": sum(
                1 for p in self.patients.values() if p.pull_escalated and p.location == LOC_BED
            ),
        }

    def _log(self, text: str, undo: dict[str, Any]) -> None:
        self._seq += 1
        self.events.append(BoardEvent(seq=self._seq, text=f"T+{self._seq:03d}  {text}", undo=undo))


class BoardError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


# Process-wide board instance — demo state, reset-able from the UI.
BOARD = Board()
