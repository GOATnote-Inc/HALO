"""Lookup tests — the 'find it in seconds' path. Deterministic core, mocked LLM router."""

from __future__ import annotations

from typing import Any

import pytest

from halo.edu.lookup import resolve, route_with_claude
from halo.llm import LLMFailure


@pytest.mark.parametrize(
    ("query", "expected_first"),
    [
        ("chemical explosion, starting 2pam", "organophosphate"),
        ("pesticide exposure, pinpoint pupils and drooling", "organophosphate"),
        ("breech is crowning and no OB is here", "breech_delivery"),
        ("head entrapment during delivery", "breech_delivery"),
        ("eye is rock hard and proptotic after assault", "lateral_canthotomy"),
        ("retrobulbar hemorrhage vision loss", "lateral_canthotomy"),
        ("pregnant cardiac arrest in triage", "perimortem_cesarean"),
        ("postmortem c section needed", "perimortem_cesarean"),
        ("resuscitative hysterotomy steps", "perimortem_cesarean"),
    ],
)
def test_resolve_top_match(query: str, expected_first: str) -> None:
    matches = resolve(query)
    assert matches, f"no match for {query!r}"
    assert matches[0].module.id == expected_first
    assert matches[0].why  # every score is explainable


def test_resolve_no_match_returns_empty_not_a_guess() -> None:
    assert resolve("quantum flux capacitor maintenance") == ()


def test_resolve_ranks_are_ordered() -> None:
    matches = resolve("2pam for nerve agent after chemical explosion")
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)


class TestClaudeRouter:
    def test_valid_id_passes_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("halo.llm.structured", lambda *a, **k: {"module_id": "organophosphate"})
        assert route_with_claude("the drooling seizing guy from the plant") == "organophosphate"

    def test_none_answer_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("halo.llm.structured", lambda *a, **k: {"module_id": "none"})
        assert route_with_claude("what time is lunch") is None

    def test_out_of_corpus_id_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("halo.llm.structured", lambda *a, **k: {"module_id": "made_up_module"})
        assert route_with_claude("anything") is None

    def test_seam_failure_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a: Any, **k: Any) -> dict[str, Any]:
            raise LLMFailure("fail-closed: stop_reason=refusal")

        monkeypatch.setattr("halo.llm.structured", boom)
        assert route_with_claude("anything") is None
