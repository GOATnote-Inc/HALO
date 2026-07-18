"""ED census: the department's occupied beds at the moment an MCI is declared.

Each census entry is a panel patient (chart-consistent presentation) plus the
structured care-requirement features the surge rules read. Synthetic data only.
Wilkinson and Macejkovic are deliberately absent from the census — they are in
the community and arrive with the incident (the reconciliation scenarios).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from halo.mci.panel import PanelPatient, load_panel

DEFAULT_CENSUS_PATH = Path(__file__).parents[3] / "tests" / "fixtures" / "ed_census.json"


@dataclass(frozen=True)
class CareFeatures:
    """Care requirements. ``None`` means undetermined — surge rules fail closed on it."""

    admission_indicated: bool | None = None
    comfort_focused: bool | None = None
    cardiac_monitor_required: bool | None = None
    oxygen_required: bool | None = None
    continuous_infusion: bool | None = None
    post_thrombolytic: bool | None = None
    ambulatory: bool | None = None
    workup_complete: bool | None = None
    safe_for_discharge: bool | None = None


@dataclass(frozen=True)
class CensusEntry:
    bed: str
    patient: PanelPatient
    esi: int  # Emergency Severity Index, 1 (most acute) .. 5
    chief_complaint: str
    status: str
    features: CareFeatures


@dataclass(frozen=True)
class Census:
    department_beds: int
    entries: tuple[CensusEntry, ...]

    @property
    def open_beds(self) -> int:
        return self.department_beds - len(self.entries)


def load_census(path: str | Path | None = None) -> Census:
    p = Path(path or os.environ.get("HALO_CENSUS_PATH", DEFAULT_CENSUS_PATH))
    return _load_census_cached(str(p.resolve()))


@lru_cache(maxsize=4)
def _load_census_cached(resolved: str) -> Census:
    data = json.loads(Path(resolved).read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("census fixture must be marked synthetic")
    by_id = {p.patient_id: p for p in load_panel()}
    entries = []
    for row in data["census"]:
        patient = by_id.get(row["patient_id"])
        if patient is None:
            raise ValueError(f"census references unknown panel patient: {row['patient_id']}")
        entries.append(
            CensusEntry(
                bed=row["bed"],
                patient=patient,
                esi=row["esi"],
                chief_complaint=row["chief_complaint"],
                status=row["status"],
                features=CareFeatures(**row["features"]),
            )
        )
    return Census(department_beds=data["department_beds"], entries=tuple(entries))
