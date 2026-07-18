"""Drill grading engine. Deterministic keyword criteria decide; Claude can only add.

Grading contract:

- The curated ``accept`` groups (OR of ANDs, case-insensitive substring) are
  the grader. They are content, physician-reviewable, and run offline.
- Optional Claude adjudication (``llm_adjudicate=True``) is consulted ONLY for
  answers the keywords missed — it can convert a miss into a hit when the
  trainee used different wording, but it can never take a hit away, and it is
  instructed to grade conservatively. Any seam failure or uncertainty leaves
  the miss in place (no credit on uncertainty).
- ``passed`` requires both the score threshold AND zero critical misses — a
  perfect score on everything else does not excuse pulling on a breech.

Known limit (by design, documented rather than hidden): keyword grading is
self-attestation, not proctoring — pasting a bag of keywords into every prompt
would pass. The CME ledger records the raw answers (``events``) precisely so a
human reviewer can spot that.
"""

from __future__ import annotations

import re

from halo.edu.corpus import module_version
from halo.edu.models import DecisionPoint, DrillResult, ProcedureModule, StepGrade


def _phrase_hits(phrase: str, text: str) -> bool:
    """Left word boundary always; right boundary for digit-final or short phrases.

    Long alpha stems may grow a suffix so "clamp" credits "clamped" and "decon"
    credits "decontamination". But "now" can no longer hide inside "know", "3"
    inside "30 minutes", or "mci" inside "mcintosh" — abbreviations (<= 3
    chars) and numbers match exact words only (red-team fix: raw substring
    matching let wrong answers score critical hits).
    """
    exact = phrase[-1].isdigit() or len(phrase) <= 3
    pattern = r"\b" + re.escape(phrase) + (r"\b" if exact else "")
    return re.search(pattern, text) is not None


def match_answer(accept: tuple[tuple[str, ...], ...], answer: str) -> tuple[str, ...] | None:
    """First accept group whose phrases ALL appear in the answer, else None."""
    normalized = " ".join(answer.lower().split())
    for group in accept:
        if all(_phrase_hits(phrase, normalized) for phrase in group):
            return group
    return None


def _llm_adjudicate(point: DecisionPoint, answer: str) -> bool:
    """Ask Claude whether differently-worded credit is deserved. Fail-closed to False."""
    from halo import llm  # imported here so offline grading never touches the seam

    schema = {
        "type": "object",
        "properties": {"credit": {"type": "boolean"}, "why": {"type": "string"}},
        "required": ["credit", "why"],
        "additionalProperties": False,
    }
    prompt = (
        "You are grading one answer in an emergency-procedure drill.\n\n"
        f"Question: {point.prompt}\n"
        f"Model answer: {point.ideal}\n"
        f"Trainee answer: {answer!r}\n\n"
        "Does the trainee answer clearly demonstrate the same action/knowledge as the "
        "model answer? Grade conservatively: if it is vague, partial, or you are unsure, "
        "credit=false. Wording may differ; substance may not."
    )
    try:
        result = llm.structured(prompt, schema)
    except Exception:
        return False
    return result.get("credit") is True


def grade_point(point: DecisionPoint, answer: str, *, llm_adjudicate: bool = False) -> StepGrade:
    """Grade one decision point. Keyword hit wins; LLM may only upgrade a miss."""
    matched = match_answer(point.accept, answer)
    if matched is not None:
        return StepGrade(
            prompt=point.prompt,
            hit=True,
            critical=point.critical,
            matched_group=matched,
            ideal=point.ideal,
            via="keyword",
        )
    if llm_adjudicate and answer.strip() and _llm_adjudicate(point, answer):
        return StepGrade(
            prompt=point.prompt,
            hit=True,
            critical=point.critical,
            matched_group=None,
            ideal=point.ideal,
            via="llm",
        )
    return StepGrade(
        prompt=point.prompt,
        hit=False,
        critical=point.critical,
        matched_group=None,
        ideal=point.ideal,
        via="keyword",
    )


def run_drill(
    module: ProcedureModule,
    answers: list[str],
    *,
    trainee: str | None = None,
    elapsed_s: float | None = None,
    llm_adjudicate: bool = False,
) -> DrillResult:
    """Grade a full drill run. ``answers`` align 1:1 with the decision points."""
    drill = module.drill
    if drill is None:
        raise ValueError(f"module '{module.id}' has no drill")
    points = drill.decision_points
    if len(answers) != len(points):
        raise ValueError(f"expected {len(points)} answers, got {len(answers)}")

    grades = tuple(
        grade_point(point, answer, llm_adjudicate=llm_adjudicate)
        for point, answer in zip(points, answers, strict=True)
    )
    score = sum(1 for g in grades if g.hit) / len(grades)
    critical_misses = tuple(g.prompt for g in grades if g.critical and not g.hit)
    return DrillResult(
        module_id=module.id,
        content_version=module_version(module.id),
        grades=grades,
        score=round(score, 4),
        critical_misses=critical_misses,
        passed=score >= drill.pass_threshold and not critical_misses,
        elapsed_s=elapsed_s,
        trainee=trainee,
        grades_via="keyword+llm" if any(g.via == "llm" for g in grades) else "keyword",
        events={p.prompt: a for p, a in zip(points, answers, strict=True)},
    )
