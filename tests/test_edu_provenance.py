"""Provenance backbone: optional PMID / OpenEM links on citations."""

from __future__ import annotations

from halo.edu.corpus import load_corpus
from halo.edu.models import Reference
from halo.edu.provenance import pubmed_url, summarize
from halo.edu.render import _reference_html


def test_reference_provenance_fields_default_to_none() -> None:
    r = Reference(label="X", cite="X et al. 2020.")
    assert r.pmid is None
    assert r.openem_id is None


def test_reference_accepts_provenance() -> None:
    r = Reference(label="X", cite="X et al.", pmid="12345678", openem_id="sepsis-adult")
    assert r.pmid == "12345678"
    assert r.openem_id == "sepsis-adult"


def test_existing_content_still_loads() -> None:
    # Regression: adding optional fields must not break the shipped corpus.
    modules = load_corpus()
    assert modules
    assert all(m.references for m in modules)


def test_render_shows_pmid_link_and_openem_tag() -> None:
    html = _reference_html(
        Reference(label="Doe 2024", cite="Doe J. 2024.", pmid="12345678", openem_id="test-crisis")
    )
    assert "pubmed.ncbi.nlm.nih.gov/12345678" in html
    assert "PMID 12345678" in html
    assert "OpenEM: test-crisis" in html


def test_render_omits_provenance_when_absent() -> None:
    html = _reference_html(Reference(label="Doe 2024", cite="Doe J. 2024."))
    assert "PMID" not in html
    assert "OpenEM" not in html


def test_summarize_counts_coverage() -> None:
    refs = (
        Reference(label="a", cite="a", pmid="1", openem_id="x"),
        Reference(label="b", cite="b", openem_id="y"),
        Reference(label="c", cite="c"),
    )
    # Build a minimal stand-in with just the .references attribute the summary reads.
    from types import SimpleNamespace

    summary = summarize(SimpleNamespace(references=refs))  # type: ignore[arg-type]
    assert summary.references_total == 3
    assert summary.with_pmid == 1
    assert summary.with_openem == 2
    assert summary.pmid_coverage == 1 / 3


def test_pubmed_url() -> None:
    assert pubmed_url("999") == "https://pubmed.ncbi.nlm.nih.gov/999/"
