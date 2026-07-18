"""Claude extraction: free-text field/EMS note -> structured SALT observations.

The model reports only what the note documents — every field is nullable and
``null`` means "not documented", which the triage layer treats fail-closed.
The model never assigns a triage category.
"""

from __future__ import annotations

from typing import Any

from halo import llm
from halo.mci.models import Observations

_FIELDS = (
    "breathing",
    "obeys_commands",
    "peripheral_pulse",
    "respiratory_distress",
    "major_hemorrhage_uncontrolled",
    "minor_injuries_only",
    "can_walk",
)

_FIELD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "evidence": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": ["value", "evidence"],
    "additionalProperties": False,
}

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {f: _FIELD_SCHEMA for f in _FIELDS},
    "required": list(_FIELDS),
    "additionalProperties": False,
}

SYSTEM = """\
You extract structured mass-casualty triage observations from a free-text field or EMS note.

Rules — these are safety-critical:
- Report ONLY what the note documents. If a field is not clearly documented, its value is null.
- Never infer, guess, or fill in a plausible value. Null is the correct answer for anything \
not stated or ambiguous.
- Do not assign a triage category or make any clinical judgment; you extract observations only.
- For each non-null value, `evidence` must be a short verbatim quote from the note that \
supports it. If value is null, evidence is null.

Field meanings:
- breathing: patient is breathing (spontaneous respirations documented).
- obeys_commands: follows commands or makes purposeful movements.
- peripheral_pulse: palpable peripheral (e.g. radial) pulse.
- respiratory_distress: labored breathing, severe dyspnea, or respiratory distress documented.
- major_hemorrhage_uncontrolled: major/life-threatening bleeding that is NOT controlled. \
If bleeding is documented as controlled (e.g. tourniquet effective), this is false.
- minor_injuries_only: injuries are documented as minor only.
- can_walk: patient is ambulatory / able to walk.
"""


def extract_observations(note: str) -> tuple[Observations, dict[str, str]]:
    """Return (observations, evidence quotes). Raises ``llm.LLMFailure`` fail-closed."""
    data = llm.structured(
        f"Field note:\n<note>\n{note}\n</note>",
        EXTRACTION_SCHEMA,
        system=SYSTEM,
    )
    values: dict[str, bool | None] = {}
    evidence: dict[str, str] = {}
    for name in _FIELDS:
        entry = data.get(name)
        if not isinstance(entry, dict):
            raise llm.LLMFailure(f"extraction missing field: {name}")
        value = entry.get("value")
        if value is not None and not isinstance(value, bool):
            raise llm.LLMFailure(f"extraction field {name} is not boolean/null")
        values[name] = value
        quote = entry.get("evidence")
        if value is not None and isinstance(quote, str) and quote:
            evidence[name] = quote
    return Observations(**values), evidence
