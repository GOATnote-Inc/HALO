"""Drill engine tests — deterministic grading, the critical-miss gate, fail-closed LLM assist."""

from __future__ import annotations

from typing import Any

import pytest

from halo.edu import get_module
from halo.edu.drill import grade_point, match_answer, run_drill
from halo.llm import LLMFailure

OP = get_module("organophosphate")
BREECH = get_module("breech_delivery")

OP_PERFECT = [
    "Stop — staff into PPE, strip and decon the patient outside before entry",
    "Atropine 2-5 mg IV, doubling every 5 minutes until secretions dry",
    "Pralidoxime 1-2 g IV over 30 minutes, running with the atropine",
    "Midazolam 10 mg IM",
    "Rocuronium 1.2 mg/kg — sux is prolonged here",
    "Three DuoDotes, lateral thigh, rapid succession",
    "Declare an MCI and get poison control on the line",
]


def test_perfect_run_passes() -> None:
    result = run_drill(OP, OP_PERFECT, trainee="test-rn", elapsed_s=180.0)
    assert result.score == 1.0
    assert result.passed is True
    assert result.critical_misses == ()
    assert result.grades_via == "keyword"
    assert result.content_version.startswith("organophosphate@v")


def test_critical_miss_fails_despite_high_score() -> None:
    answers = ["Rush them straight into resus bay 1", *OP_PERFECT[1:]]  # skips decon
    result = run_drill(OP, answers)
    assert result.score >= 0.8  # 6/7 clears the threshold...
    assert result.critical_misses  # ...but the decon miss is critical
    assert result.passed is False


def test_breech_traction_is_a_critical_miss() -> None:
    drill = BREECH.drill
    assert drill is not None
    hands_off = drill.decision_points[1]
    grade = grade_point(hands_off, "I pull gently on the hips to help it along")
    assert grade.hit is False
    assert grade.critical is True


def test_answer_count_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="expected 7 answers"):
        run_drill(OP, ["one answer"])


def test_match_answer_requires_all_phrases_in_group() -> None:
    accept = (("avoid", "succinylcholine"),)
    assert match_answer(accept, "use succinylcholine") is None
    assert match_answer(accept, "AVOID succinylcholine, plasma cholinesterase is gone")


class TestLLMAdjudication:
    ATROPINE_POINT = next(
        p for p in (OP.drill.decision_points if OP.drill else ()) if "First antidote" in p.prompt
    )
    REWORDED = "start the muscarinic blocker and titrate until the lungs are dry"

    def test_reworded_answer_misses_offline(self) -> None:
        grade = grade_point(self.ATROPINE_POINT, self.REWORDED)
        assert grade.hit is False

    def test_llm_can_upgrade_a_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "halo.llm.structured", lambda *a, **k: {"credit": True, "why": "same substance"}
        )
        grade = grade_point(self.ATROPINE_POINT, self.REWORDED, llm_adjudicate=True)
        assert grade.hit is True
        assert grade.via == "llm"

    def test_llm_cannot_downgrade_a_keyword_hit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def never_called(*a: Any, **k: Any) -> dict[str, Any]:
            raise AssertionError("LLM must not be consulted on a keyword hit")

        monkeypatch.setattr("halo.llm.structured", never_called)
        grade = grade_point(self.ATROPINE_POINT, "atropine now", llm_adjudicate=True)
        assert grade.hit is True
        assert grade.via == "keyword"

    def test_llm_uncertainty_stays_a_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "halo.llm.structured", lambda *a, **k: {"credit": False, "why": "vague"}
        )
        grade = grade_point(self.ATROPINE_POINT, self.REWORDED, llm_adjudicate=True)
        assert grade.hit is False

    def test_seam_failure_stays_a_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a: Any, **k: Any) -> dict[str, Any]:
            raise LLMFailure("fail-closed: stop_reason=max_tokens")

        monkeypatch.setattr("halo.llm.structured", boom)
        grade = grade_point(self.ATROPINE_POINT, self.REWORDED, llm_adjudicate=True)
        assert grade.hit is False

    def test_empty_answer_never_reaches_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def never_called(*a: Any, **k: Any) -> dict[str, Any]:
            raise AssertionError("empty answers are graded offline")

        monkeypatch.setattr("halo.llm.structured", never_called)
        grade = grade_point(self.ATROPINE_POINT, "   ", llm_adjudicate=True)
        assert grade.hit is False

    def test_llm_upgrade_marks_run_via(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "halo.llm.structured", lambda *a, **k: {"credit": True, "why": "equivalent"}
        )
        answers = [*OP_PERFECT]
        answers[1] = self.REWORDED
        result = run_drill(OP, answers, llm_adjudicate=True)
        assert result.passed is True
        assert result.grades_via == "keyword+llm"
