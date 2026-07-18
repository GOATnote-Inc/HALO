"""Chart reconciliation: partial identity in a field note -> panel candidates.

Doctrine (Anthropic "building effective agents"): simplest pattern first, agent
only where open-ended exploration pays.

1. A single structured call extracts identity cues from the note.
2. Deterministic scoring (``panel.match_candidates``) runs on those cues.
3. Only if that is inconclusive does an **agent loop** run: Claude searches the
   panel with name variants and corroborates via chart content, then proposes
   candidates through a ``propose_candidates`` tool (final-answer-as-tool).

Safety boundary: the agent only ever *proposes*. Every proposed ID is
re-verified against the panel; gender mismatches are discarded; the returned
status is at most ``possible`` for agent-sourced candidates and is never
"confirmed" — identity confirmation is a human act.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from anthropic import beta_tool

from halo import llm
from halo.mci.panel import (
    Candidate,
    IdentityCues,
    PanelPatient,
    load_panel,
    match_candidates,
    score_candidate,
)

CUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "family_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "given_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "gender": {"anyOf": [{"type": "string", "enum": ["male", "female"]}, {"type": "null"}]},
        "approximate_age": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["family_name", "given_name", "gender", "approximate_age"],
    "additionalProperties": False,
}

CUE_SYSTEM = """\
You extract patient-identity cues from a mass-casualty field note. Report only what the note
documents; null for anything absent or ambiguous. Partial or uncertain name fragments ARE
worth reporting verbatim (e.g. "Wilk-something" -> family_name "Wilk"). Do not guess values
that are not grounded in the note. Extraction only — no clinical judgment.
"""

AGENT_SYSTEM = """\
You reconcile a mass-casualty patient against a hospital panel. The field note contains
partial or garbled identity information. Search the panel for plausible matches — try name
variants, phonetic alternatives, and truncations; narrow by gender and approximate age when
documented. Corroborate promising candidates against their chart (e.g. the note says "on a
blood thinner" and the chart lists clopidogrel).

Rules:
- Call search_patients whenever you have any name fragment; try multiple variants if the
  first search is weak.
- Call get_patient_chart before proposing a candidate, and cite the corroborating chart
  content in your rationale.
- Finish by calling propose_candidates exactly once with 0-3 candidates. Propose only
  patients you actually retrieved. If nothing is plausible, propose an empty list.
- You are proposing leads for a human to adjudicate, not confirming identity.
"""


@dataclass(frozen=True)
class Proposal:
    patient_id: str
    rationale: str


@dataclass(frozen=True)
class Reconciliation:
    status: str  # "strong_candidate" | "possible" | "no_match"
    method: str  # "deterministic" | "agent"
    cues: IdentityCues
    candidates: tuple[Candidate, ...]
    agent_rationales: dict[str, str]
    trail: tuple[dict[str, Any], ...]


def extract_cues(note: str) -> IdentityCues:
    data = llm.structured(f"Field note:\n<note>\n{note}\n</note>", CUE_SCHEMA, system=CUE_SYSTEM)
    age = data.get("approximate_age")
    return IdentityCues(
        family_name=data.get("family_name") or None,
        given_name=data.get("given_name") or None,
        gender=data.get("gender") or None,
        approximate_age=age if isinstance(age, int) else None,
    )


def _make_tools(
    panel: tuple[PanelPatient, ...], on_date: str, proposals: list[Proposal]
) -> list[Any]:
    @beta_tool
    def search_patients(
        family_name: str = "",
        given_name: str = "",
        gender: str = "",
        approximate_age: int = -1,
    ) -> str:
        """Search the hospital panel for patients matching identity cues.

        Call this whenever you have any name fragment, even a partial or misheard
        one; call it again with variants if results are weak. Returns the top
        deterministic matches with scores in [0,1].

        Args:
            family_name: Family-name fragment or variant ("" to omit).
            given_name: Given-name fragment or variant ("" to omit).
            gender: "male" or "female" ("" to omit).
            approximate_age: Estimated age in years (-1 to omit).
        """
        cues = IdentityCues(
            family_name=family_name or None,
            given_name=given_name or None,
            gender=gender or None,
            approximate_age=approximate_age if approximate_age >= 0 else None,
        )
        ranked = sorted(
            (score_candidate(p, cues, on_date=on_date) for p in panel),
            key=lambda c: c.score,
            reverse=True,
        )[:5]
        return json.dumps(
            [
                {
                    "patient_id": c.patient.patient_id,
                    "name": c.patient.display_name,
                    "gender": c.patient.gender,
                    "age": c.patient.age_on(on_date),
                    "score": round(c.score, 2),
                }
                for c in ranked
                if c.score > 0
            ]
        )

    @beta_tool
    def get_patient_chart(patient_id: str) -> str:
        """Fetch a panel patient's chart summary (demographics, active medications,
        active conditions). Call this before proposing a candidate so your rationale
        can cite corroborating chart content.

        Args:
            patient_id: The patient_id returned by search_patients.
        """
        for p in panel:
            if p.patient_id == patient_id:
                return json.dumps(
                    {
                        "patient_id": p.patient_id,
                        "name": p.display_name,
                        "gender": p.gender,
                        "age": p.age_on(on_date),
                        "medications": list(p.medication_labels),
                        "conditions": list(p.condition_labels),
                    }
                )
        return json.dumps({"error": f"unknown patient_id {patient_id}"})

    @beta_tool
    def propose_candidates(candidate_patient_ids: list[str], rationale: str) -> str:
        """Submit your final candidate proposal. Call exactly once, at the end.

        Args:
            candidate_patient_ids: 0-3 patient_ids you retrieved and corroborated,
                strongest first. Empty list if no plausible match exists.
            rationale: One short paragraph citing the note cues and chart content
                that support (or rule out) each candidate.
        """
        for pid in candidate_patient_ids[:3]:
            proposals.append(Proposal(patient_id=pid, rationale=rationale))
        return "recorded"

    return [search_patients, get_patient_chart, propose_candidates]


def reconcile(
    note: str,
    *,
    on_date: str,
    panel: tuple[PanelPatient, ...] | None = None,
) -> Reconciliation:
    panel = panel or load_panel()
    cues = extract_cues(note)
    status, candidates = match_candidates(cues, on_date=on_date, panel=panel)
    if status == "strong_candidate":
        return Reconciliation(status, "deterministic", cues, candidates, {}, ())
    # The agent loop costs tens of seconds — at the door that budget is precious.
    # Chase identity only when there's something to chase: a name fragment, or at
    # least a gender+age pair worth a demographic shortlist.
    has_lead = (
        cues.family_name is not None
        or cues.given_name is not None
        or (cues.gender is not None and cues.approximate_age is not None)
    )
    if not has_lead:
        return Reconciliation(status, "deterministic", cues, candidates, {}, ())

    proposals: list[Proposal] = []
    tools = _make_tools(panel, on_date, proposals)
    _, trail = llm.agent_loop(
        f"Reconcile this patient against the panel.\n<note>\n{note}\n</note>\n"
        f"Cues already extracted: {json.dumps(cues.__dict__)}",
        tools,
        system=AGENT_SYSTEM,
    )

    # Re-verify: proposals must be real panel patients and not demographic mismatches.
    by_id = {p.patient_id: p for p in panel}
    rationales: dict[str, str] = {}
    verified: list[Candidate] = []
    seen = {c.patient.patient_id for c in candidates}
    for prop in proposals:
        patient = by_id.get(prop.patient_id)
        if patient is None:
            continue  # hallucinated ID — discard
        if cues.gender is not None and patient.gender != cues.gender:
            continue  # demographic mismatch — discard
        rationales[patient.patient_id] = prop.rationale
        if patient.patient_id not in seen:
            seen.add(patient.patient_id)
            verified.append(score_candidate(patient, cues, on_date=on_date))

    merged = tuple(sorted([*candidates, *verified], key=lambda c: c.score, reverse=True))
    # Agent-sourced candidates never upgrade status past "possible".
    final_status = "possible" if merged else "no_match"
    return Reconciliation(final_status, "agent", cues, merged, rationales, tuple(trail))
