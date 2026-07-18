"""Live end-to-end MCI demo: goldset notes -> Claude extraction -> SALT triage board.

Needs ANTHROPIC_API_KEY. Usage: ``.venv/bin/python -m halo.mci.demo``

Prints per-patient results and the eval that matters: extraction accuracy against
gold observations and the under-triage false-negative count (target 0).
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


def main() -> int:
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
