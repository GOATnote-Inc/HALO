"""Incident -> staff readiness brief: the seam between MCI surge and readiness/CME.

When the track board declares an MCI ("Factory explosion, 100+ inbound"), the
surge plan answers "where do they go" — this module answers the other half:
"what will these casualties need your hands to do, is the team drilled on it,
and what do you set up before the first arrival."

Same doctrine as everything else in this package:

- Deterministic incident profiles + the corpus decide which cards surface;
  Claude may optionally route messy incident text (fail-closed, opt-in).
- Prep-now lines are derived from card content (first critical step + the
  team-calls lists), never generated.
- Drill readiness comes from the hash-chained CME ledger; a ledger that fails
  verification contributes NOTHING but a loud note.
- The brief names its gaps: casualty types this corpus has no card for are
  listed explicitly — "not covered" beats false confidence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from halo.edu.attest import read_verified
from halo.edu.corpus import get_module, load_corpus
from halo.edu.drill import phrase_hits
from halo.edu.lookup import resolve, route_with_claude
from halo.edu.models import ProcedureModule

DEFAULT_LEDGER = Path("out/edu/cme_ledger.jsonl")


@dataclass(frozen=True)
class DrillStat:
    """Team drill history for one card, from verified ledger records only."""

    module_id: str
    attempts: int
    passes: int
    last_when: str | None
    last_passed: bool | None


@dataclass(frozen=True)
class BriefCard:
    module_id: str
    name: str
    one_liner: str
    why: str  # why this card, for THIS incident — carries the conditionals
    time_target: str


@dataclass(frozen=True)
class ReadinessBrief:
    incident: str
    profiles: tuple[str, ...]
    cards: tuple[BriefCard, ...]
    prep_now: tuple[str, ...]
    gaps: tuple[str, ...]
    drill_stats: tuple[DrillStat, ...]
    ledger_note: str
    routed_by_claude: str | None = None


@dataclass(frozen=True)
class _Profile:
    name: str
    triggers: tuple[str, ...]
    cards: tuple[tuple[str, str], ...]  # (module_id, why-for-this-incident)
    gaps: tuple[str, ...]


_PROFILES: tuple[_Profile, ...] = (
    _Profile(
        name="chemical",
        triggers=(
            "chemical",
            "pesticide",
            "organophosphate",
            "nerve agent",
            "sarin",
            "insecticide",
            "crop duster",
            "gas leak",
            "hazmat",
        ),
        cards=(
            (
                "organophosphate",
                "Cholinergic casualties: decon before the doors, atropine to a dry chest, "
                "2-PAM early — and pharmacy pooling starts now.",
            ),
        ),
        gaps=(
            "Cyanide / carbon monoxide exposure — no HALO card; use your poison-control line",
            "Burn surge — no HALO card",
        ),
    ),
    _Profile(
        name="blast",
        triggers=("explosion", "blast", "bomb", "factory", "industrial", "detonation"),
        cards=(
            (
                "lateral_canthotomy",
                "Blast and facial trauma cause orbital compartment syndrome — proptosis + "
                "falling vision is a bedside decompression, not a CT trip.",
            ),
            (
                "organophosphate",
                "Industrial explosions can release cholinergic agents — miosis + secretions "
                "+ wheeze in casualties means treat as nerve agent/OP until proven otherwise.",
            ),
        ),
        gaps=(
            "Blast lung / primary blast injury — no HALO card",
            "Burn surge — no HALO card",
            "Crush injury / hyperkalemia — no HALO card",
        ),
    ),
    _Profile(
        name="obstetric",
        triggers=("pregnant", "pregnancy", "labor", "obstetric", "maternity"),
        cards=(
            (
                "breech_delivery",
                "Precipitous delivery without OB: hands off the breech, grip only bone.",
            ),
            (
                "perimortem_cesarean",
                "Maternal arrest with fundus at/above the umbilicus: incise by minute 4.",
            ),
        ),
        gaps=("Postpartum hemorrhage — no dedicated HALO card",),
    ),
)

_STANDING_PREP = (
    "Any large event: identify pregnant casualties early — the perimortem-cesarean and "
    "breech cards apply to any of them."
)


def _drill_stats(
    module_ids: tuple[str, ...], ledger_path: Path
) -> tuple[tuple[DrillStat, ...], str]:
    records, note = read_verified(ledger_path)
    stats = []
    for module_id in module_ids:
        mine = [r for r in records if r.get("module_id") == module_id]
        last = mine[-1] if mine else None
        stats.append(
            DrillStat(
                module_id=module_id,
                attempts=len(mine),
                passes=sum(1 for r in mine if r.get("passed") is True),
                last_when=last.get("when") if last else None,
                last_passed=last.get("passed") if last else None,
            )
        )
    return tuple(stats), note


def readiness_brief(
    incident: str,
    *,
    ledger_path: Path | None = None,
    use_llm: bool = False,
) -> ReadinessBrief:
    """Build the staff-readiness half of an MCI declaration. Offline by default."""
    text = " ".join(incident.lower().split())
    corpus_ids = {m.id for m in load_corpus()}

    matched = tuple(p for p in _PROFILES if any(phrase_hits(t, text) for t in p.triggers))
    cards: list[BriefCard] = []
    seen: set[str] = set()

    def _add(module: ProcedureModule, why: str) -> None:
        if module.id in seen:
            return
        seen.add(module.id)
        cards.append(
            BriefCard(
                module_id=module.id,
                name=module.name,
                one_liner=module.one_liner,
                why=why,
                time_target=module.time_target.label,
            )
        )

    for profile in matched:
        for module_id, why in profile.cards:
            _add(get_module(module_id), why)

    # Direct mentions in the incident text (e.g. "2-PAM", "breech") rank next.
    for match in resolve(incident):
        _add(match.module, f"Named in the incident text ({'; '.join(match.why[:1])}).")

    routed = None
    if use_llm and not cards:
        routed = route_with_claude(incident)  # fail-closed: None on any failure
        if routed in corpus_ids:
            _add(get_module(routed), "Claude routed this incident description — verify fit.")

    prep: list[str] = []
    for card in cards:
        module = get_module(card.module_id)
        first = module.steps[0]
        if first.critical:
            prep.append(f"{module.name}: {first.action}")
    for card in cards:
        for call in get_module(card.module_id).team_calls:
            if call not in prep:
                prep.append(call)
    if cards:
        prep.append(_STANDING_PREP)

    gaps = tuple(dict.fromkeys(g for p in matched for g in p.gaps)) or (
        ("No matching readiness card for this incident — full card list at /edu/.",)
        if not cards
        else ()
    )

    ledger = (
        ledger_path
        if ledger_path is not None
        else Path(os.environ.get("HALO_EDU_LEDGER", str(DEFAULT_LEDGER)))
    )
    stats, ledger_note = _drill_stats(tuple(c.module_id for c in cards), ledger)

    return ReadinessBrief(
        incident=incident,
        profiles=tuple(p.name for p in matched),
        cards=tuple(cards),
        prep_now=tuple(prep),
        gaps=gaps,
        drill_stats=stats,
        ledger_note=ledger_note,
        routed_by_claude=routed,
    )
