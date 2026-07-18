"""HALO module 3 — readiness & CME for High Acuity, Low Occurrence procedures.

The problem: the procedures most likely to kill when fumbled (perimortem
cesarean, imminent breech, lateral canthotomy, nerve-agent response) are
exactly the ones a general ED performs least. This module makes the resource
*findable in seconds* and *drillable in minutes*, so the moment of need is not
the first encounter.

Architecture (same doctrine as the MCI module):

- ``corpus``  — curated, versioned, cited clinical content (data, not model
  output). Strict fail-closed validation at load; ``review.status`` stays
  ``draft`` until a physician signs off, and drafts are labeled on every card.
- ``dosing``  — deterministic dose arithmetic from patient context. Missing
  weight/age -> ``REFUSED`` with a reason, never a guessed number.
- ``lookup``  — alias/keyword resolution from free text to the right card;
  Claude may *route* a messy query (via ``halo.llm``) but never authors
  clinical content. No match -> the full module list, never a guess.
- ``drill``   — scripted scenario grading. Deterministic keyword criteria
  decide; optional Claude adjudication can only *add* credit for wording the
  keywords missed, and grades fail closed to "miss" on any LLM failure.
- ``attest``  — hash-chained CME evidence records (JSONL, tamper-evident).
- ``fhir``    — EHR seams: FHIR bundle -> patient context for dosing;
  drill/session results -> draft FHIR resources. Synthetic data only.

Research demo, not a medical device. Not accredited CME — the records are
evidence suitable for a CME/credentialing process, pending physician review.
"""

from halo.edu.corpus import get_module, load_corpus, module_version
from halo.edu.models import (
    DoseResult,
    DoseStatus,
    DrillResult,
    Med,
    PatientContext,
    ProcedureModule,
    ReviewStatus,
)

__all__ = [
    "DoseResult",
    "DoseStatus",
    "DrillResult",
    "Med",
    "PatientContext",
    "ProcedureModule",
    "ReviewStatus",
    "get_module",
    "load_corpus",
    "module_version",
]
