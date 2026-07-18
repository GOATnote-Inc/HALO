"""Simulation case loader + structural validation.

A case must be a closed, total state machine before it ships: every ``goto``
names a real state, every ``next.decision`` names a real decision, every
outcome referenced is defined, and both a survival and a death path exist —
a training sim with unreachable endings teaches nothing.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CASES_DIR = Path(__file__).parent / "cases"

_VITAL_KEYS = {"hr", "sbp", "dbp", "spo2", "rr"}
_CME_AUDIENCES = ("physician", "nursing", "ems")
_KNOWN_DIAGRAMS = {"io_humerus", "io_tibia", "canthotomy", "breech_grip", "pmcd_timeline"}
_KNOWN_WOUNDS = {"none", "abdomen", "eye"}
_EDU_MODULES = {"breech_delivery", "lateral_canthotomy", "organophosphate", "perimortem_cesarean"}


def list_cases() -> list[dict[str, Any]]:
    out = []
    for path in sorted(CASES_DIR.glob("*.json")):
        case = load_case(path.stem)
        out.append(
            {
                "id": case["id"],
                "title": case["title"],
                "briefing": case["briefing"],
                "synthetic": case["synthetic"],
                "draft": case["draft"],
            }
        )
    return out


@lru_cache(maxsize=16)
def load_case(case_id: str) -> dict[str, Any]:
    path = CASES_DIR / f"{case_id}.json"
    if not path.is_file() or path.parent != CASES_DIR:
        raise KeyError(f"unknown case: {case_id}")
    case: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    validate_case(case)
    return case


def validate_case(case: dict[str, Any]) -> None:
    required = (
        "id",
        "title",
        "briefing",
        "states",
        "start",
        "decisions",
        "outcomes",
        "references",
        "cme",
    )
    for key in required:
        if key not in case:
            raise ValueError(f"case missing required key: {key}")
    if case.get("synthetic") is not True or case.get("draft") is not True:
        raise ValueError("cases must be marked synthetic and draft")

    # Evidence: at least one real citation, each with the text and what it supports.
    refs = case["references"]
    if not isinstance(refs, list) or not refs:
        raise ValueError("references must be a non-empty list")
    for ref in refs:
        if not ref.get("citation") or not ref.get("note"):
            raise ValueError("each reference needs citation and note")

    # CME/CE framing: objectives for every role — physician, nursing, and EMS/tech.
    cme = case["cme"]
    if tuple(cme.get("audiences", ())) != _CME_AUDIENCES:
        raise ValueError(f"cme.audiences must be exactly {list(_CME_AUDIENCES)}")
    objectives = cme.get("objectives", {})
    for role in _CME_AUDIENCES:
        if not objectives.get(role):
            raise ValueError(f"cme.objectives missing role: {role}")
    if not cme.get("note"):
        raise ValueError("cme.note required (draft / not-accredited statement)")

    if case.get("edu_module") is not None and case["edu_module"] not in _EDU_MODULES:
        raise ValueError(f"edu_module must be one of {sorted(_EDU_MODULES)} or null")
    wound = (case.get("sprite") or {}).get("wound", "none")
    if wound not in _KNOWN_WOUNDS:
        raise ValueError(f"sprite.wound must be one of {sorted(_KNOWN_WOUNDS)}")

    states: dict[str, Any] = case["states"]
    decisions: dict[str, Any] = case["decisions"]
    outcomes: dict[str, Any] = case["outcomes"]

    def check_state(name: str, where: str) -> None:
        if name not in states:
            raise ValueError(f"{where}: unknown state {name!r}")

    def check_decision(name: str, where: str) -> None:
        if name not in decisions:
            raise ValueError(f"{where}: unknown decision {name!r}")

    def check_outcome(name: str, where: str) -> None:
        if name not in outcomes:
            raise ValueError(f"{where}: unknown outcome {name!r}")

    check_state(case["start"]["state"], "start")
    check_decision(case["start"]["decision"], "start")

    reachable_outcomes: set[str] = set()
    for sname, state in states.items():
        missing = _VITAL_KEYS - set(state.get("vitals", {}))
        if missing:
            raise ValueError(f"state {sname}: missing vitals {sorted(missing)}")
        resolve = state.get("resolve")
        if resolve:
            if "outcome" in resolve:
                check_outcome(resolve["outcome"], f"state {sname}")
                reachable_outcomes.add(resolve["outcome"])
            if "goto" in resolve:
                check_state(resolve["goto"], f"state {sname}")
            if "outcome" not in resolve and "goto" not in resolve:
                raise ValueError(f"state {sname}: resolve needs outcome or goto")

    for dname, decision in decisions.items():
        if not decision.get("options"):
            raise ValueError(f"decision {dname}: no options")
        diagrams = decision.get("diagram")
        if diagrams is not None:
            names = [diagrams] if isinstance(diagrams, str) else list(diagrams)
            unknown = set(names) - _KNOWN_DIAGRAMS
            if unknown:
                raise ValueError(f"decision {dname}: unknown diagram(s) {sorted(unknown)}")
        for opt in decision["options"]:
            for key in ("id", "label", "goto", "log"):
                if key not in opt:
                    raise ValueError(f"decision {dname}: option missing {key}")
            check_state(opt["goto"], f"decision {dname} option {opt['id']}")
            nxt = opt.get("next")
            if nxt:
                check_decision(nxt["decision"], f"decision {dname} option {opt['id']}")

    for oname, outcome in outcomes.items():
        for key in ("label", "tone", "debrief", "teaching"):
            if key not in outcome:
                raise ValueError(f"outcome {oname}: missing {key}")

    tones = {o["tone"] for o in outcomes.values()}
    if "good" not in tones or "bad" not in tones:
        raise ValueError("case must define at least one good and one bad outcome")
    # Every outcome must be reachable via some state resolve.
    unreachable = set(outcomes) - reachable_outcomes
    if unreachable:
        raise ValueError(f"outcomes never reached by any state resolve: {sorted(unreachable)}")
