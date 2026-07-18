"""Render tests — the card must be honest (draft banner, version, disclaimers) and complete."""

from __future__ import annotations

from pathlib import Path

import pytest

from halo.edu import load_corpus
from halo.edu.diagrams import DIAGRAMS, get_diagram
from halo.edu.render import card_html, index_html, write_cards

CORPUS = load_corpus()
IDS = [m.id for m in CORPUS]


@pytest.mark.parametrize("module", CORPUS, ids=IDS)
def test_card_carries_honesty_markers(module: object) -> None:
    html = card_html(module)  # type: ignore[arg-type]
    assert "DRAFT — PENDING PHYSICIAN REVIEW" in html
    assert "not a medical device" in html
    assert "not accredited CME" in html
    assert f"{module.id}@v" in html  # type: ignore[attr-defined]  # content version in footer


@pytest.mark.parametrize("module", CORPUS, ids=IDS)
def test_card_renders_all_content_sections(module: object) -> None:
    html = card_html(module)  # type: ignore[arg-type]
    m = module  # typed as object for parametrize; attributes checked dynamically
    for step in m.steps:  # type: ignore[attr-defined]
        assert step.action[:30] in html or step.action[:30].replace("'", "&#x27;") in html
    for med in m.meds:  # type: ignore[attr-defined]
        assert med.name.split()[0] in html
    assert "Critical" in html  # critical steps are labeled with text, not color alone


def test_canthotomy_card_embeds_diagram() -> None:
    module = next(m for m in CORPUS if m.id == "lateral_canthotomy")
    html = card_html(module)
    assert "INFERIOR CRUS" in html  # the diagram's labeled action line
    assert html.count("<svg") >= 2  # step-flow strip + at least one schematic


def test_all_step_media_ids_resolve() -> None:
    for module in CORPUS:
        for step in module.steps:
            if step.media:
                assert get_diagram(step.media), f"{module.id} step {step.n}: {step.media}"


def test_diagrams_are_labeled_schematics() -> None:
    for name, svg in DIAGRAMS.items():
        assert "Schematic" in svg, name
        assert 'role="img"' in svg, name


def test_index_lists_every_module_and_aliases() -> None:
    html = index_html(CORPUS)
    for module in CORPUS:
        assert f"{module.id}.html" in html
        assert module.aliases[0] in html
    assert "ALL CONTENT DRAFT" in html


def test_write_cards_produces_files(tmp_path: Path) -> None:
    written = write_cards(tmp_path)
    assert {p.name for p in written} == {"index.html", *(f"{i}.html" for i in IDS)}
    for path in written:
        assert path.exists() and path.stat().st_size > 2000
