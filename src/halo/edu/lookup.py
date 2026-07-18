"""Free-text -> the right procedure card, in seconds.

Deterministic alias/keyword scoring is the primary path and works offline —
"time to resource" is the preparedness metric this exists for. Claude (via
``halo.llm``) may optionally *route* a messy query, but it only ever selects
from the corpus's ids: it cannot author content, and any failure or
out-of-corpus answer falls back to the deterministic result. No match returns
an empty tuple — the caller shows the full module list, never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from halo.edu.corpus import load_corpus
from halo.edu.models import ProcedureModule

_ALIAS_SUBSTRING = 3.0
_ALIAS_TOKEN = 2.0
_TEXT_TOKEN = 1.0


@dataclass(frozen=True)
class Match:
    module: ProcedureModule
    score: float
    why: tuple[str, ...]


_STOPWORDS = frozenset(
    "and the for with this that are was has had but not now out who how its all any "
    "was were been being have does did can may your from into onto over under "
    "after before during while when where what which there here they them then".split()
)


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.split(r"[^a-z0-9]+", text.lower())
        if (len(t) > 2 or t.isdigit()) and t not in _STOPWORDS
    }


def resolve(query: str, corpus: tuple[ProcedureModule, ...] | None = None) -> tuple[Match, ...]:
    """Rank modules against a free-text query. Deterministic; empty tuple = no match."""
    modules = corpus if corpus is not None else load_corpus()
    q = " ".join(query.lower().split())
    q_tokens = _tokens(q)
    matches = []
    for module in modules:
        score = 0.0
        why: list[str] = []
        for alias in module.aliases:
            if alias in q:
                score += _ALIAS_SUBSTRING
                why.append(f"alias '{alias}'")
            else:
                shared = _tokens(alias) & q_tokens
                if shared:
                    score += _ALIAS_TOKEN * len(shared)
                    why.append(f"alias tokens {sorted(shared)}")
        text_blob = " ".join((module.name, module.one_liner, module.category, *module.indications))
        shared_text = _tokens(text_blob) & q_tokens
        if shared_text:
            score += _TEXT_TOKEN * len(shared_text)
            why.append(f"text tokens {sorted(shared_text)}")
        if score > 0:
            matches.append(Match(module=module, score=score, why=tuple(why)))
    return tuple(sorted(matches, key=lambda m: (-m.score, m.module.id)))


def route_with_claude(query: str) -> str | None:
    """Optional LLM routing for messy phrasing. Returns a corpus id or None.

    Fail-closed: refusal, truncation, API failure, or an id not in the corpus
    all return None — the caller falls back to :func:`resolve` / the full list.
    """
    from halo import llm  # imported here so offline paths never touch the seam

    modules = load_corpus()
    ids = [m.id for m in modules]
    menu = "\n".join(
        f"- {m.id}: {m.one_liner} (aliases: {', '.join(m.aliases[:6])})" for m in modules
    )
    schema = {
        "type": "object",
        "properties": {"module_id": {"type": "string", "enum": [*ids, "none"]}},
        "required": ["module_id"],
        "additionalProperties": False,
    }
    prompt = (
        "A clinician at the bedside typed this into a procedure-card finder:\n"
        f"  {query!r}\n\n"
        "Available cards:\n"
        f"{menu}\n\n"
        'Pick the single best card id, or "none" if no card clearly fits. '
        "Route only — do not answer the clinical question."
    )
    try:
        result = llm.structured(prompt, schema)
    except Exception:
        return None
    module_id = result.get("module_id")
    return module_id if module_id in ids else None
