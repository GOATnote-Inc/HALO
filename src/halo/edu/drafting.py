"""Seed a HALO card *draft skeleton* from an OpenEM condition.

The recommendation this implements is deliberate about the boundary: OpenEM is a
breadth corpus (370 conditions, prose recognition/management), and 290 of those
are agent-compiled and unreviewed. HALO's engine is depth — step-graded drills
and computable dosing that a physician signs off on. So this tool moves exactly
what is safe to move automatically — identity, category, and *citations with
provenance* — and refuses to invent the clinical payload.

What it emits:
- id / name / category / one_liner, from the OpenEM frontmatter
- references, mapped from OpenEM ``sources`` with an ``openem_id`` provenance
  link (and a ``pmid`` when the citation string carries one)
- review.status = "draft" with an author string that names the provenance and
  says, in words, that the clinical content is not authored

What it refuses to emit: steps, meds, doses, drills. Those stay empty with a
``_todo`` checklist. The skeleton is intentionally NOT loadable by the corpus
validator — a human authors the depth, then a physician reviews it. That is the
whole point: the CME engine's depth is hand-built and physician-signed.
"""

from __future__ import annotations

import re
import sys
from typing import Any

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_REF_LINE = re.compile(r'^\s*ref:\s*"?(.+?)"?\s*$')
_SCALAR = re.compile(r"^(id|condition|category|esi):\s*(.+?)\s*$")
_PMID = re.compile(r"PMID[:\s]*(\d+)", re.IGNORECASE)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Raises if no frontmatter is present."""
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValueError("no YAML frontmatter found — not an OpenEM condition file")
    return match.group(1), text[match.end() :]


def _label_for(cite: str) -> str:
    """Derive a short display label ("Surname Year") from a citation string."""
    surname = cite.split(",", 1)[0].split()[0] if cite.split() else "Source"
    year = _YEAR.search(cite)
    return f"{surname} {year.group(0)}" if year else surname[:40]


def _parse(frontmatter: str) -> tuple[dict[str, str], list[str]]:
    """Minimal, defensive parse: the scalars we need plus every ``ref:`` string.

    Deliberately not a general YAML parser — it reads only the OpenEM fields
    this tool consumes and ignores everything else, so a corpus schema change
    elsewhere cannot silently corrupt a draft.
    """
    scalars: dict[str, str] = {}
    refs: list[str] = []
    for line in frontmatter.splitlines():
        scalar = _SCALAR.match(line)
        if scalar:
            scalars[scalar.group(1)] = scalar.group(2).strip().strip('"')
            continue
        ref = _REF_LINE.match(line)
        if ref:
            refs.append(ref.group(1).strip())
    return scalars, refs


def draft_from_openem(text: str) -> dict[str, Any]:
    """Build a HALO card draft skeleton from OpenEM condition markdown.

    Populates identity + citations (with provenance); leaves the clinical
    payload empty with a ``_todo`` list. The result is a scaffold for a human
    author, not a loadable module.
    """
    frontmatter, _body = _split_frontmatter(text)
    scalars, ref_strings = _parse(frontmatter)
    openem_id = scalars.get("id", "unknown")
    name = scalars.get("condition", openem_id.replace("-", " ").title())
    esi = scalars.get("esi")
    one_liner = f"[DRAFT] {name}" + (f" — OpenEM ESI {esi}" if esi else "")

    references = []
    for cite in ref_strings:
        pmid_match = _PMID.search(cite)
        references.append(
            {
                "label": _label_for(cite),
                "cite": cite,
                "pmid": pmid_match.group(1) if pmid_match else None,
                "openem_id": openem_id,
            }
        )

    return {
        "id": openem_id,
        "name": name,
        "category": scalars.get("category", "uncategorized"),
        "one_liner": one_liner,
        "aliases": [],
        "indications": [],
        "contraindications": [],
        "time_target": {"label": "TODO", "minutes": None},
        "team_calls": [],
        "equipment": [],
        "steps": [],
        "meds": [],
        "pitfalls": [],
        "success_criteria": [],
        "aftercare": [],
        "references": references,
        "review": {
            "status": "draft",
            "author": f"OpenEM draft ({openem_id}) — clinical content NOT authored; needs a human",
            "date": "TODO",
            "version": 0,
            "reviewed_by": None,
        },
        "drill": None,
        "_draft": True,
        "_source": f"openem:{openem_id}",
        "_todo": [
            "author steps (mark the critical ones, add accept phrase groups)",
            "author meds with computable adult/peds DoseSpec",
            "author indications, contraindications, pitfalls, success_criteria, aftercare",
            "author a synthetic drill with a critical decision point",
            "set time_target, version, date; obtain physician sign-off (review.status)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m halo.edu.drafting <path-to-openem-condition.md>``."""
    import json
    from pathlib import Path

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m halo.edu.drafting <openem-condition.md>", file=sys.stderr)
        return 2
    draft = draft_from_openem(Path(args[0]).read_text())
    print(json.dumps(draft, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
