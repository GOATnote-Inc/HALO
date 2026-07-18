"""Legal/compliance agent: audits the live board against regulatory rules.

The second genuine agent in HALO (the first is chart reconciliation). Reviewing
an audit trail against a rule set is open-ended reading — which lines matter,
what pattern violates which rule — so it gets an agent loop. The decision
boundary stays deterministic, twice over:

1. The rules are a fixed, cited list (`RULES`), not model judgment.
2. The agent only *proposes* findings via a final-answer tool; every finding is
   re-verified here — the rule id must exist and the quoted evidence must
   actually appear in the audit log or board state. Fabricated evidence is
   dropped and the drop is reported, never hidden.

Grounding: EMTALA medical screening obligations, IOM/National Academies Crisis
Standards of Care (2012) documentation and accountability requirements, and the
identity-governance posture in docs/GOVERNANCE.md.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import beta_tool

from halo import llm
from halo.mci.board import BOARD

RULES: tuple[dict[str, str], ...] = (
    {
        "rule_id": "R1-EMTALA-MSE",
        "text": "Every arrival receives triage/medical screening before any disposition. "
        "Waiting-room patients routed or discharged without a recorded SALT category "
        "violate this; untriaged patients still waiting are pending, not violations — "
        "flag them as monitor items.",
        "basis": "EMTALA, 42 USC 1395dd — medical screening examination obligation.",
    },
    {
        "rule_id": "R2-EXPECTANT-PHYSICIAN",
        "text": "No expectant designation without an explicit physician decision recorded. "
        "Any expectant categorization or comfort routing must trace to a physician entry.",
        "basis": "IOM Crisis Standards of Care (2012) — accountable human decision-making "
        "for resource-based prioritization.",
    },
    {
        "rule_id": "R3-IDENTITY-MERGE",
        "text": "No chart merge without human confirmation. Identity candidates stay "
        "UNCONFIRMED; software must never write candidate-derived data to a chart.",
        "basis": "docs/GOVERNANCE.md wrong-chart harm posture; HIM identity governance.",
    },
    {
        "rule_id": "R4-AUDIT-TRAIL",
        "text": "Every bed-state transition appears in the activity log with an attributable "
        "entry. Beds that changed state without a log line are violations.",
        "basis": "IOM Crisis Standards of Care (2012) — documentation under crisis operations; "
        "medicolegal reconstructability.",
    },
    {
        "rule_id": "R5-CLASSIFICATION-OVERRIDES",
        "text": "Surge actions refused by classification (e.g., discharging a HOLD bed) must "
        "show the refusal rationale; overrides happen at the bedside, not by click.",
        "basis": "docs/GOVERNANCE.md fail-closed doctrine; ACS-COT under-triage asymmetry.",
    },
)

SYSTEM = """\
You are a compliance reviewer auditing an ED track board during a mass casualty incident.
Work from evidence only: read the rules, the board snapshot, and the audit log via your
tools, then report findings through report_findings — exactly once, at the end.

For each rule, decide: PASS (log/state shows compliance), MONITOR (pending action needed,
e.g. untriaged patients still waiting), or FLAG (evidence of a violation). Every finding
MUST quote evidence verbatim from the audit log lines or the board snapshot — your quotes
are checked against the real log, and fabricated quotes are discarded. Be conservative:
if the evidence is ambiguous, use MONITOR and say what documentation is missing.
"""


def _snapshot() -> dict[str, Any]:
    counts = BOARD.counts()
    return {
        "counts": counts,
        "assessed": BOARD.assessed,
        "waiting": [
            {
                "mrn": a.mrn,
                "name": a.name,
                "category": a.category,
                "destination": a.destination,
            }
            for a in BOARD.arrivals.values()
        ],
        "bays": {b: (BOARD.arrivals[o].mrn if o else None) for b, o in BOARD.bays.items()},
    }


def _log_lines() -> list[str]:
    return [e.text for e in BOARD.events]


def run_compliance_review() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    summary_holder: list[str] = []

    @beta_tool
    def get_rules() -> str:
        """Fetch the compliance rule set (rule_id, requirement text, legal basis).
        Call this first."""
        return json.dumps(list(RULES))

    @beta_tool
    def get_board_snapshot() -> str:
        """Fetch the current board state: counts, waiting-room arrivals with triage
        categories and destinations, and bay occupancy."""
        return json.dumps(_snapshot())

    @beta_tool
    def get_audit_log() -> str:
        """Fetch the full board activity log (every transition, oldest first)."""
        return json.dumps(_log_lines())

    @beta_tool
    def report_findings(findings_json: str, summary: str) -> str:
        """Submit the final review. Call exactly once, at the end.

        Args:
            findings_json: JSON array of objects, one per rule, each with keys:
                rule_id (from get_rules), status ("pass"|"monitor"|"flag"),
                evidence (verbatim quote from the audit log or snapshot),
                recommendation (one sentence).
            summary: Two-sentence overall assessment.
        """
        try:
            findings.extend(json.loads(findings_json))
        except json.JSONDecodeError:
            return "findings_json was not valid JSON — fix and call again"
        summary_holder.append(summary)
        return "recorded"

    _, trail = llm.agent_loop(
        "Audit the board now. Read the rules, snapshot, and log; then report findings.",
        [get_rules, get_board_snapshot, get_audit_log, report_findings],
        system=SYSTEM,
        max_iterations=8,
    )

    # Deterministic verification: rule must exist; evidence must actually appear.
    known_rules = {r["rule_id"] for r in RULES}
    haystack = "\n".join(_log_lines()) + "\n" + json.dumps(_snapshot())
    verified: list[dict[str, Any]] = []
    dropped = 0
    for f in findings:
        evidence = str(f.get("evidence", ""))
        ok_rule = f.get("rule_id") in known_rules
        ok_status = f.get("status") in ("pass", "monitor", "flag")
        # Quote check: substring match after whitespace normalization.
        norm = " ".join(evidence.split())
        ok_evidence = bool(norm) and norm in " ".join(haystack.split())
        if ok_rule and ok_status and ok_evidence:
            verified.append(
                {
                    "rule_id": f["rule_id"],
                    "status": f["status"],
                    "evidence": evidence,
                    "recommendation": str(f.get("recommendation", "")),
                    "basis": next(r["basis"] for r in RULES if r["rule_id"] == f["rule_id"]),
                }
            )
        else:
            dropped += 1

    return {
        "summary": summary_holder[0] if summary_holder else "",
        "findings": verified,
        "dropped_unverified": dropped,  # honesty counter — fabricated evidence never hides
        "rules_total": len(RULES),
        "agent_trail": list(trail),
        "synthetic_only": True,
    }
