"""Readiness-brief tests — the MCI->EDU seam. All offline; ledger via tmp_path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from halo.edu import get_module
from halo.edu.attest import append_record
from halo.edu.brief import readiness_brief
from halo.edu.drill import run_drill
from halo.edu.render import brief_html
from halo.llm import LLMFailure
from tests.test_edu_drill import OP_PERFECT

FACTORY = "Factory explosion, 2.1 mi — EMS estimates 100+ inbound"
EMPTY_LEDGER = Path("/nonexistent/ledger.jsonl")


def test_factory_explosion_matches_blast_profile() -> None:
    brief = readiness_brief(FACTORY, ledger_path=EMPTY_LEDGER)
    assert brief.profiles == ("blast",)
    ids = [c.module_id for c in brief.cards]
    assert ids[0] == "lateral_canthotomy"  # ocular blast trauma is the sure category
    assert "organophosphate" in ids  # chemical release is conditional — the why says so
    op_card = next(c for c in brief.cards if c.module_id == "organophosphate")
    assert "until proven otherwise" in op_card.why


def test_factory_explosion_prep_and_gaps() -> None:
    brief = readiness_brief(FACTORY, ledger_path=EMPTY_LEDGER)
    assert any("decon FIRST" in line for line in brief.prep_now)
    assert any("pregnant" in line.lower() for line in brief.prep_now)  # standing line
    joined = " ".join(brief.gaps).lower()
    for gap in ("blast lung", "burn", "crush"):
        assert gap in joined  # the brief names what the corpus does NOT cover


def test_chemical_incident_routes_to_op() -> None:
    brief = readiness_brief("crop duster pesticide spill, 6 exposed", ledger_path=EMPTY_LEDGER)
    assert "chemical" in brief.profiles
    assert brief.cards[0].module_id == "organophosphate"


def test_obstetric_incident() -> None:
    brief = readiness_brief(
        "pregnant patient in active labor at the door", ledger_path=EMPTY_LEDGER
    )
    assert brief.profiles == ("obstetric",)
    assert {c.module_id for c in brief.cards} == {"breech_delivery", "perimortem_cesarean"}


def test_direct_mention_surfaces_card_without_profile() -> None:
    brief = readiness_brief("need the 2pam dosing", ledger_path=EMPTY_LEDGER)
    assert brief.profiles == ()
    assert brief.cards and brief.cards[0].module_id == "organophosphate"


def test_no_match_is_honest() -> None:
    brief = readiness_brief("meteor shower of kittens", ledger_path=EMPTY_LEDGER)
    assert brief.cards == ()
    assert brief.prep_now == ()
    assert any("No matching readiness card" in g for g in brief.gaps)


class TestLedgerIntegration:
    def _ledger_with_op_pass(self, tmp_path: Path) -> Path:
        ledger = tmp_path / "cme.jsonl"
        result = run_drill(get_module("organophosphate"), OP_PERFECT, trainee="rn-a")
        append_record(ledger, result, trainee="rn-a", when_iso="2026-07-18T20:00:00+00:00")
        return ledger

    def test_drill_stats_from_verified_ledger(self, tmp_path: Path) -> None:
        ledger = self._ledger_with_op_pass(tmp_path)
        brief = readiness_brief(FACTORY, ledger_path=ledger)
        stats = {s.module_id: s for s in brief.drill_stats}
        assert stats["organophosphate"].attempts == 1
        assert stats["organophosphate"].passes == 1
        assert stats["organophosphate"].last_when == "2026-07-18T20:00:00+00:00"
        assert stats["lateral_canthotomy"].attempts == 0  # never drilled shows as a gap
        assert "verified" in brief.ledger_note

    def test_tampered_ledger_contributes_nothing_but_a_loud_note(self, tmp_path: Path) -> None:
        ledger = self._ledger_with_op_pass(tmp_path)
        doctored = ledger.read_text().replace('"passed":true', '"passed":false', 1)
        assert doctored != ledger.read_text()
        ledger.write_text(doctored)
        brief = readiness_brief(FACTORY, ledger_path=ledger)
        assert "FAILED VERIFICATION" in brief.ledger_note
        assert all(s.attempts == 0 for s in brief.drill_stats)


class TestClaudeRoutingOptIn:
    def test_llm_can_route_when_nothing_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("halo.llm.structured", lambda *a, **k: {"module_id": "organophosphate"})
        brief = readiness_brief(
            "workers down at the malathion silo", ledger_path=EMPTY_LEDGER, use_llm=True
        )
        assert brief.routed_by_claude == "organophosphate"
        assert any("verify fit" in c.why for c in brief.cards)

    def test_llm_failure_leaves_brief_offline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a: Any, **k: Any) -> dict[str, Any]:
            raise LLMFailure("fail-closed")

        monkeypatch.setattr("halo.llm.structured", boom)
        brief = readiness_brief("meteor shower of kittens", ledger_path=EMPTY_LEDGER, use_llm=True)
        assert brief.routed_by_claude is None
        assert brief.cards == ()


def test_brief_html_is_escaped_and_honest() -> None:
    brief = readiness_brief("factory explosion <script>alert(1)</script>", ledger_path=EMPTY_LEDGER)
    html = brief_html(brief)
    assert "<script>alert" not in html
    assert "never drilled" in html
    assert "DRAFT" in html
    assert "Not covered by a HALO card" in html
    assert 'href="/"' in html  # links back to the track board
