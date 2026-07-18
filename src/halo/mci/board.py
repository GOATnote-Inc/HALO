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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from halo.mci.census import Census, CensusEntry, load_census
from halo.mci.surge import SurgeAction, SurgeDecision, classify

# Where a patient can be on the board.
LOC_BED = "bed"
LOC_CHAIRS = "chairs"
LOC_DEPARTED = "departed"

# High-acuity bays and the pool of open ED bed labels (7 open of 30 at declaration).
BAYS = ("RESUS-1", "RESUS-2", "TRAUMA-1", "TRAUMA-2")
_OPEN_BED_LABELS = tuple(f"D{i:02d}" for i in range(1, 8))
WAITING_PATH = Path(__file__).parents[3] / "tests" / "fixtures" / "ed_waiting.json"

TRIAGE_CATEGORIES = {"immediate", "delayed", "minimal", "expectant", "dead", "unable_to_triage"}

# Which destinations each SALT category may route to (fail-closed: triage first).
_ROUTE_RULES: dict[str, tuple[str, ...]] = {
    "immediate": ("resus", "trauma", "bed"),
    "unable_to_triage": ("resus", "trauma", "bed"),
    "delayed": ("bed", "waiting"),
    "minimal": ("waiting", "discharged"),
    "expectant": ("comfort",),
    "dead": ("morgue",),
}

# Wall-clock is intentionally logical (T+n events), not real time — deterministic demos.


@dataclass
class PatientState:
    entry: CensusEntry
    decision: SurgeDecision | None = None
    location: str = LOC_BED
    disposition: str | None = None  # "discharged" | "admitted" when departed
    pull_escalated: bool = False


@dataclass
class Arrival:
    """A waiting-room check-in: quick-registration alias until identity is confirmed."""

    arrival_id: str
    name: str
    mrn: str
    arrived_min: int
    complaint: str
    source: str
    note: str
    category: str | None = None  # SALT category once door-triaged
    destination: str = "waiting"
    location: str | None = None  # bay name or bed label once routed


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
        waiting = json.loads(WAITING_PATH.read_text(encoding="utf-8"))
        if waiting.get("synthetic") is not True:
            raise ValueError("waiting-room fixture must be marked synthetic")
        self.arrivals: dict[str, Arrival] = {
            a["id"]: Arrival(
                arrival_id=a["id"],
                name=a["name"],
                mrn=a["mrn"],
                arrived_min=a["arrived_min"],
                complaint=a["complaint"],
                source=a["source"],
                note=a["note"],
            )
            for a in waiting["arrivals"]
        }
        self.open_bed_labels: list[str] = list(_OPEN_BED_LABELS)
        self.bays: dict[str, str | None] = {b: None for b in BAYS}
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
            undo: dict[str, Any] = {"bed": bed, "location": prev}
            if prev == LOC_BED:
                self.open_bed_labels.append(bed)
                undo["freed_label"] = bed
            self._log(f"{bed} {name}: discharged.", undo)
            return

        if action == "to_chairs":
            if classified is not SurgeAction.VERTICAL_CHAIRS or ps.location != LOC_BED:
                raise BoardError(
                    409,
                    f"classified {classified.value} — only VERTICAL_CHAIRS patients move "
                    "to chairs.",
                )
            ps.location = LOC_CHAIRS
            self.open_bed_labels.append(bed)
            self._log(
                f"{bed} {name}: moved to chairs (vertical care) — bed freed.",
                {"bed": bed, "location": LOC_BED, "freed_label": bed},
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
            self.open_bed_labels.append(bed)
            self._log(
                f"{bed} {name}: inpatient bed assigned — transported, ED bed freed.",
                {"bed": bed, "location": LOC_BED, "freed_label": bed},
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
            if "arrival" in event.undo:
                a = self.arrivals[event.undo["arrival"]]
                if "category" in event.undo:
                    a.category = event.undo["category"]
                if "destination" in event.undo:
                    if event.undo.get("return_label"):
                        self.open_bed_labels.append(event.undo["return_label"])
                    if event.undo.get("free_bay"):
                        self.bays[event.undo["free_bay"]] = None
                    a.destination = event.undo["destination"]
                    a.location = event.undo.get("prev_location")
                return
            ps = self.patients[event.undo["bed"]]
            if "pull" in event.undo:
                ps.pull_escalated = event.undo["pull"]
            if "location" in event.undo:
                ps.location = event.undo["location"]
                ps.disposition = None
            if "freed_label" in event.undo and event.undo["freed_label"] in self.open_bed_labels:
                self.open_bed_labels.remove(event.undo["freed_label"])
            return

    # -- waiting room ----------------------------------------------------------

    def waiting_triage(self, arrival_id: str, category: str) -> None:
        a = self.arrivals.get(arrival_id)
        if a is None:
            raise BoardError(404, f"unknown arrival: {arrival_id}")
        if category not in TRIAGE_CATEGORIES:
            raise BoardError(422, f"unknown SALT category: {category}")
        if a.destination != "waiting":
            raise BoardError(409, f"{a.name} has already been routed ({a.destination})")
        prev = a.category
        a.category = category
        self._log(
            f"{a.mrn} {a.name}: door triage — {category.replace('_', ' ').upper()}.",
            {"arrival": arrival_id, "category": prev},
        )

    def waiting_route(self, arrival_id: str, destination: str) -> None:
        a = self.arrivals.get(arrival_id)
        if a is None:
            raise BoardError(404, f"unknown arrival: {arrival_id}")
        if a.destination != "waiting":
            raise BoardError(409, f"{a.name} has already been routed ({a.destination})")
        if a.category is None:
            raise BoardError(
                409,
                "triage first — every arrival gets a medical screening exam before "
                "disposition (EMTALA).",
            )
        allowed = _ROUTE_RULES[a.category]
        if destination not in allowed:
            raise BoardError(
                409,
                f"{a.category.replace('_', ' ')} routes to {', '.join(allowed)} — "
                f"not {destination}.",
            )
        undo: dict[str, Any] = {
            "arrival": arrival_id,
            "destination": "waiting",
            "prev_location": a.location,
        }
        label: str | None = None
        if destination in ("resus", "trauma"):
            free = [
                b
                for b, occ in self.bays.items()
                if occ is None and b.startswith(destination.upper())
            ]
            if not free:
                raise BoardError(409, f"no open {destination} bay — all occupied.")
            label = free[0]
            self.bays[label] = arrival_id
            undo["free_bay"] = label
        elif destination == "bed":
            if not self.open_bed_labels:
                raise BoardError(409, "no open ED beds — execute the surge plan first.")
            self.open_bed_labels.sort()
            label = self.open_bed_labels.pop(0)
            undo["return_label"] = label
        a.destination = destination
        a.location = label
        where = label or destination.replace("_", " ")
        self._log(f"{a.mrn} {a.name}: routed to {where}.", undo)

    # -- views ---------------------------------------------------------------

    def counts(self) -> dict[str, int]:
        in_bed = [p for p in self.patients.values() if p.location == LOC_BED]
        arrivals_in_beds = sum(1 for a in self.arrivals.values() if a.destination == "bed")
        occupied = len(in_bed) + arrivals_in_beds
        return {
            "department_beds": self.department_beds,
            "occupied": occupied,
            "open_beds": self.department_beds - occupied,
            "in_chairs": sum(1 for p in self.patients.values() if p.location == LOC_CHAIRS),
            "departed": sum(1 for p in self.patients.values() if p.location == LOC_DEPARTED),
            "awaiting_pull": sum(
                1 for p in self.patients.values() if p.pull_escalated and p.location == LOC_BED
            ),
            "waiting": sum(1 for a in self.arrivals.values() if a.destination == "waiting"),
            "bays_occupied": sum(1 for occ in self.bays.values() if occ is not None),
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
