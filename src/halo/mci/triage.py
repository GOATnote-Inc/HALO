"""Deterministic SALT triage over structured observations.

SALT (Sort, Assess, Lifesaving interventions, Treatment/transport) is the
national all-hazards mass-casualty triage guideline. The individual-assessment
step reduces to:

1. Not breathing (after airway opened)  -> DEAD
2. Breathing — four screening questions:
     obeys commands? peripheral pulse? no respiratory distress?
     major hemorrhage controlled?
   - any "no"  -> IMMEDIATE, unless a human has recorded that the patient is
                  not likely to survive given current resources -> EXPECTANT
   - all "yes" -> minor injuries only? yes -> MINIMAL, otherwise -> DELAYED

Fail-closed policy (the safety contract this module is built around):

- Unknown ``breathing``                 -> UNABLE_TO_TRIAGE
- A known "no" dominates unknowns       -> IMMEDIATE path applies
- All-known answers "yes" but any of the four unknown -> UNABLE_TO_TRIAGE
  (a life threat cannot be ruled out from the record; assess in person now)
- Unknown ``minor_injuries_only`` after four yeses -> DELAYED (over-triage is
  the safe direction; never downgrade on missing data)
- EXPECTANT is never assigned autonomously: it requires an explicit human
  resource decision passed as ``likely_survivable=False``.
"""

from __future__ import annotations

from halo.mci.models import Observations, TriageCategory, TriageResult

# The four SALT screening questions, normalized so True is the "good" answer.
_SCREEN_FIELDS = (
    "obeys_commands",
    "peripheral_pulse",
    "no_respiratory_distress",
    "hemorrhage_controlled",
)


def _screen_answers(obs: Observations) -> dict[str, bool | None]:
    invert = lambda v: None if v is None else not v  # noqa: E731
    return {
        "obeys_commands": obs.obeys_commands,
        "peripheral_pulse": obs.peripheral_pulse,
        "no_respiratory_distress": invert(obs.respiratory_distress),
        "hemorrhage_controlled": invert(obs.major_hemorrhage_uncontrolled),
    }


def salt_triage(obs: Observations, *, likely_survivable: bool | None = None) -> TriageResult:
    """Assign a SALT category. Total function — every input maps to a result.

    ``likely_survivable`` is a human/resource judgment, never extracted from
    the note. Only an explicit ``False`` can produce EXPECTANT.
    """
    if obs.breathing is None:
        return TriageResult(
            TriageCategory.UNABLE_TO_TRIAGE,
            "Breathing status not documented — assess in person immediately.",
            missing_fields=("breathing",),
        )
    if obs.breathing is False:
        return TriageResult(
            TriageCategory.DEAD,
            "Not breathing after airway opening (SALT).",
        )

    answers = _screen_answers(obs)
    failed = [f for f in _SCREEN_FIELDS if answers[f] is False]
    unknown = tuple(f for f in _SCREEN_FIELDS if answers[f] is None)

    if failed:
        # A known life threat dominates any unknowns.
        if likely_survivable is False:
            return TriageResult(
                TriageCategory.EXPECTANT,
                "Life threat present and human resource decision recorded "
                f"survival unlikely (failed: {', '.join(failed)}).",
                missing_fields=unknown,
            )
        return TriageResult(
            TriageCategory.IMMEDIATE,
            f"Failed SALT screen: {', '.join(failed)}.",
            missing_fields=unknown,
        )

    if unknown:
        return TriageResult(
            TriageCategory.UNABLE_TO_TRIAGE,
            "Cannot rule out a life threat — not documented: "
            f"{', '.join(unknown)}. Assess in person immediately.",
            missing_fields=unknown,
        )

    if obs.minor_injuries_only is True:
        return TriageResult(TriageCategory.MINIMAL, "Passed SALT screen; minor injuries only.")
    if obs.minor_injuries_only is False:
        return TriageResult(TriageCategory.DELAYED, "Passed SALT screen; non-minor injuries.")
    return TriageResult(
        TriageCategory.DELAYED,
        "Passed SALT screen; injury extent not documented — defaulting up to "
        "DELAYED (never downgrade on missing data).",
        missing_fields=("minor_injuries_only",),
    )
