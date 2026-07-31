"""Citation provenance for readiness cards.

HALO's CME engine (deterministic dosing, step-graded drills, physician sign-off)
is the *depth* layer. It is deliberately narrow — four hand-authored procedures.
The breadth and the citations come from OpenEM, the shared EM knowledge corpus
that already feeds ScribeGOAT2 / LostBench / SafeShift / RadSlice. HALO joins
that ecosystem as a downstream consumer, but only as a *sourcing and provenance*
layer: an OpenEM condition can seed a card draft and back its citations, and a
citation can carry a ``pmid`` (independently retrievable) and an ``openem_id``
(traceable to the corpus). None of that is a runtime import — the coupling is by
recorded identifier, honoring the cross-repo "no runtime imports" rule.

This module is the small, honest surface that makes provenance *measurable*: a
card's citation-provenance coverage is a number, not a claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from halo.edu.models import ProcedureModule

PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


@dataclass(frozen=True)
class ProvenanceSummary:
    """Citation-provenance coverage for one card. All counts, no adjectives."""

    references_total: int
    with_pmid: int
    with_openem: int

    @property
    def pmid_coverage(self) -> float:
        """Fraction of citations carrying a retrievable PMID (0.0 if none)."""
        if self.references_total == 0:
            return 0.0
        return self.with_pmid / self.references_total


def summarize(module: ProcedureModule) -> ProvenanceSummary:
    """Count how much of a card's citation set carries provenance links."""
    return ProvenanceSummary(
        references_total=len(module.references),
        with_pmid=sum(1 for r in module.references if r.pmid),
        with_openem=sum(1 for r in module.references if r.openem_id),
    )


def pubmed_url(pmid: str) -> str:
    """Canonical PubMed URL for a PMID."""
    return PUBMED_URL.format(pmid=pmid)
