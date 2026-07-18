"""Live end-to-end MCI demo. Needs ANTHROPIC_API_KEY.

Two modes:

``python -m halo.mci.demo``            goldset eval — extraction accuracy vs gold
                                       observations and the under-triage FN gate (target 0).
``python -m halo.mci.demo --handoff``  three scripted scenarios mirroring published MCI
                                       failure modes (Route 91 / Beirut / Boston patterns):
                                       triage + identity reconciliation + care flags.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from halo.llm import LLMFailure, model_name
from halo.mci import TriageCategory, salt_triage
from halo.mci.extract import extract_observations

GOLDSET_PATH = Path(__file__).parents[3] / "tests" / "fixtures" / "mci_goldset.json"

UNSAFE_FOR_IMMEDIATE = {
    TriageCategory.DELAYED,
    TriageCategory.MINIMAL,
    TriageCategory.EXPECTANT,
    TriageCategory.DEAD,
}


def _rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def run_handoff_scenarios() -> int:
    """Three scripted end-to-end scenarios — the judged demo path."""
    from halo.mci.panel import care_flags
    from halo.mci.reconcile import reconcile
    from halo.mci.scenarios import INCIDENT_DATE, SCENARIOS

    print(f"[model: {model_name()}] {len(SCENARIOS)} synthetic scenarios", file=sys.stderr)
    for i, sc in enumerate(SCENARIOS, 1):
        _rule(f"SCENARIO {i}/{len(SCENARIOS)} — {sc.title}")
        print(f"Pattern:  {sc.pattern}")
        print(f"Expected: {sc.expect}")
        print(f"\nNote: {sc.note}\n")

        try:
            obs, evidence = extract_observations(sc.note)
        except LLMFailure as exc:
            print(f"TRIAGE:   EXTRACTION FAILED CLOSED ({exc}) -> unable_to_triage")
            continue
        result = salt_triage(obs)
        print(f"TRIAGE:   {result.category.value.upper()}")
        print(f"          {result.rationale}")
        for derivation in result.derivations:
            print(f"          derived: {derivation}")
        for name, quote in evidence.items():
            print(f'          {name}: "{quote}"')

        try:
            recon = reconcile(sc.note, on_date=INCIDENT_DATE)
        except LLMFailure as exc:
            print(f"IDENTITY: RECONCILIATION FAILED CLOSED ({exc}) -> unknown patient")
            continue
        print(f"\nIDENTITY: {recon.status} ({recon.method} path) — human must adjudicate")
        for c in recon.candidates:
            n_flags = len(care_flags(c.patient))
            print(f"  candidate: {c.patient.display_name}  match={c.score:.2f}")
            print(f"             {'; '.join(c.reasons)}")
            print(
                f"             anti-bloat: {c.patient.chart_resource_count} chart FHIR "
                f"resources -> {n_flags} care-modifying facts"
            )
            rationale = recon.agent_rationales.get(c.patient.patient_id)
            if rationale:
                print(f"             agent corroboration: {rationale[:220]}")
            for f in care_flags(c.patient):
                print(f"    FLAG[{f.severity}] {f.flag_id}: {f.why}")
                print(f"               provenance: {', '.join(f.provenance)}")
        if recon.trail:
            print("  agent trail:")
            for step in recon.trail:
                print(f"    {step['tool']}({json.dumps(step['input'])[:120]})")
    _rule(
        "All scenarios synthetic. Identity is never confirmed by software; EXPECTANT "
        "requires a human decision."
    )
    return 0


def main() -> int:
    if "--handoff" in sys.argv[1:]:
        return run_handoff_scenarios()
    goldset = json.loads(GOLDSET_PATH.read_text())
    cases: list[dict[str, Any]] = goldset["cases"]
    print(f"[model: {model_name()}] {len(cases)} synthetic cases\n", file=sys.stderr)

    field_hits = field_total = 0
    category_hits = 0
    under_triage: list[str] = []
    escalations: list[str] = []

    for case in cases:
        gold_cat = TriageCategory(case["gold_category"])
        try:
            obs, evidence = extract_observations(case["note"])
        except LLMFailure as exc:
            print(f"{case['id']}: EXTRACTION FAILED CLOSED ({exc}) -> unable_to_triage")
            escalations.append(case["id"])
            if gold_cat is TriageCategory.IMMEDIATE:
                pass  # escalation is safe, not an under-triage
            continue

        for name, gold_value in case["gold_observations"].items():
            field_total += 1
            if asdict(obs).get(name) == gold_value:
                field_hits += 1

        result = salt_triage(obs)
        ok = result.category is gold_cat
        category_hits += ok
        flag = "OK " if ok else "DIFF"
        print(f"{case['id']}: {flag} predicted={result.category.value} gold={gold_cat.value}")
        print(f"         {result.rationale}")
        if result.category is TriageCategory.UNABLE_TO_TRIAGE:
            escalations.append(case["id"])
        if gold_cat is TriageCategory.IMMEDIATE and result.category in UNSAFE_FOR_IMMEDIATE:
            under_triage.append(case["id"])

    n = len(cases)
    print(f"\nExtraction field accuracy: {field_hits}/{field_total}")
    print(f"Category agreement:        {category_hits}/{n}")
    print(f"Escalations (fail-closed): {len(escalations)} {escalations}")
    print(f"UNDER-TRIAGE FNs:          {len(under_triage)} {under_triage}  (target 0)")
    return 1 if under_triage else 0


if __name__ == "__main__":
    raise SystemExit(main())
