"""Scripted demo scenarios — one source of truth for the CLI demo and the web UI.

Each mirrors a failure mode documented in published MCI after-action reports
(see docs/GOVERNANCE.md §1). All content is synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass

INCIDENT_DATE = "2026-07-18"


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    pattern: str  # the published failure mode this mirrors
    expect: str  # what the system should demonstrably do
    note: str
    synthetic: bool = True


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        scenario_id="route-91-pattern",
        title="Self-transported, partial identity, head strike",
        pattern=(
            "Las Vegas Route 91 (2017): most casualties arrived by private vehicle — no EMS "
            "tag, no registration, identity fragments only (Menes et al., EP Monthly 2017)."
        ),
        expect=(
            "Deterministic identity resolution (strong candidate, agent skipped), and the "
            "antithrombotic care flag turns a routine-looking DELAYED patient into an "
            "upgrade-consideration conversation: head strike + clopidogrel."
        ),
        note=(
            "Pt 14: elderly female pulled from the collapsed section, brought in by a "
            "bystander's truck. States her name is Latoyia, last name sounded like "
            "'Wilkerson' — daughter says she takes a blood thinner and a heart pill. Struck "
            "head on debris, GCS now improving, follows commands, breathing without distress, "
            "radial pulse present, scalp laceration bleeding controlled. Looks about 80."
        ),
    ),
    Scenario(
        scenario_id="beirut-pattern",
        title="Bystander-reported phonetic name, unresponsive to questions",
        pattern=(
            "Beirut port explosion (2020): hundreds of casualties within hours, "
            "identification chaos, names arriving second-hand and garbled (published AUBMC "
            "accounts)."
        ),
        expect=(
            "Deterministic matching is inconclusive, so the bounded agent loop searches name "
            "variants, corroborates 'blood thinner' against chart clopidogrel, and proposes a "
            "candidate — capped at 'possible', with a documented-hospice goals-of-care flag "
            "for the human to weigh."
        ),
        note=(
            "Pt 19: male, roughly 80, oriented x1, cannot state his own name reliably. "
            "Neighbor at the scene thought his name was something like 'Masikovich' or "
            "'Majkovic'. Medical alert bracelet notes a blood thinner. Breathing, follows "
            "simple commands, radial pulse present, no respiratory distress, no external "
            "bleeding seen."
        ),
    ),
    Scenario(
        scenario_id="nurse-vitals-pattern",
        title="Numbers, not judgments — 30-2-Can Do",
        pattern=(
            "Door triage is a nursing workflow: at even the largest trauma centers a handful "
            "of physicians may be on shift when 100+ present. Nurses chart numbers (RR 38), "
            "not judgments (respiratory distress) — START's 30-2-Can Do."
        ),
        expect=(
            "The distress judgment is not documented, but the charted rate is. The "
            "deterministic layer derives the screen answer at the START threshold (RR >= 30) "
            "and reports the derivation openly: IMMEDIATE, from the nurse's own numbers."
        ),
        note=(
            "Pt 31: adult male, ambulatory to cot then unable to continue. RR 38, radial "
            "pulse present, follows commands, no external bleeding. No other assessment "
            "documented yet."
        ),
    ),
    Scenario(
        scenario_id="fail-closed-showcase",
        title="Sparse documentation under surge",
        pattern=(
            "Boston Marathon bombing (2013): documentation collapses under surge; notes "
            "arrive incomplete (Landman et al., Ann Emerg Med 2015;66(1):51-59)."
        ),
        expect=(
            "The system refuses to guess: UNABLE_TO_TRIAGE with the exact missing fields "
            "listed, and no identity match — an honest escalation instead of a confident "
            "wrong answer."
        ),
        note=(
            "Pt 23: adult, breathing. Crews pulled to the next bay before any further "
            "assessment. No identifying information."
        ),
    ),
)


def get(scenario_id: str) -> Scenario:
    for s in SCENARIOS:
        if s.scenario_id == scenario_id:
            return s
    raise KeyError(f"unknown scenario: {scenario_id}")
