"""Card drafting from OpenEM: seeds identity + cited provenance, never clinical depth."""

from __future__ import annotations

from pathlib import Path

import pytest

from halo.edu.drafting import draft_from_openem

FIXTURE = Path(__file__).parent / "fixtures" / "openem_condition.md"


@pytest.fixture
def draft() -> dict:
    return draft_from_openem(FIXTURE.read_text())


def test_identity_carried_from_frontmatter(draft: dict) -> None:
    assert draft["id"] == "synthetic-test-crisis"
    assert draft["name"] == "Synthetic Test Crisis"
    assert draft["category"] == "endocrine-metabolic"


def test_references_mapped_with_provenance(draft: dict) -> None:
    refs = draft["references"]
    assert len(refs) == 2
    assert refs[0]["label"] == "Doe 2024"
    assert refs[0]["pmid"] == "12345678"  # parsed from the citation string
    assert all(r["openem_id"] == "synthetic-test-crisis" for r in refs)
    assert refs[1]["pmid"] is None  # no PMID in the second citation


def test_clinical_depth_is_never_fabricated(draft: dict) -> None:
    # The safety boundary: OpenEM breadth must not become graded clinical content.
    for empty in ("steps", "meds", "indications", "contraindications", "success_criteria"):
        assert draft[empty] == [], f"{empty} should be an empty skeleton, not invented"
    assert draft["drill"] is None


def test_marked_draft_and_unauthored(draft: dict) -> None:
    assert draft["_draft"] is True
    assert draft["_source"] == "openem:synthetic-test-crisis"
    assert draft["review"]["status"] == "draft"
    assert draft["review"]["reviewed_by"] is None
    assert draft["review"]["version"] == 0
    assert draft["_todo"], "a skeleton must list what a human still has to author"


def test_rejects_non_openem_text() -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        draft_from_openem("# just a heading, no frontmatter\n")
