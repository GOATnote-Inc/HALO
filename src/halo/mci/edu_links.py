"""Just-in-time education links: clinical text -> readiness card (halo.edu).

Deterministic keyword rules — when a note or board entry indicates a
high-acuity low-occurrence procedure, the UI surfaces a small "?" affordance
linking staff to the matching CME/readiness card. The rules only *suggest a
card*; they never alter triage or surge decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CARD_URL = "/edu/modules/{module_id}/card"

_RULES: tuple[tuple[str, str, str], ...] = (
    # (module_id, human title, trigger regex over free text)
    (
        "lateral_canthotomy",
        "Lateral canthotomy",
        r"canthotomy|retrobulbar|propto|orbital compartment|rock-hard orbit|tense orbit",
    ),
    (
        "organophosphate",
        "Organophosphate poisoning",
        r"organophosphate|nerve agent|pesticide|pinpoint pupils|sludge symptoms"
        r"|excessive secretions|drooling|fasciculat",
    ),
    (
        "perimortem_cesarean",
        "Perimortem cesarean",
        r"perimortem|resuscitative hysterotomy|maternal (arrest|code)|pregnan\w* .*arrest",
    ),
    (
        "breech_delivery",
        "Imminent breech delivery",
        r"breech",
    ),
)


@dataclass(frozen=True)
class EduLink:
    module_id: str
    title: str
    matched: str  # the text fragment that triggered the link
    url: str


def edu_links(text: str) -> tuple[EduLink, ...]:
    """Scan free text and return matching readiness cards (each module once)."""
    links: list[EduLink] = []
    for module_id, title, pattern in _RULES:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            links.append(
                EduLink(
                    module_id=module_id,
                    title=title,
                    matched=m.group(0),
                    url=CARD_URL.format(module_id=module_id),
                )
            )
    return tuple(links)
