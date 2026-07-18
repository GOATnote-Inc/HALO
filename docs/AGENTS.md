# Agents in HALO — inventory and design rationale

HALO follows Anthropic's agent-building doctrine (*Building Effective Agents*): **use the
simplest pattern that works — workflows where the path is known, agents only where the model
must direct its own tool use against open-ended input.** Every Claude call in the system is
listed here, classified honestly, with its guardrails.

## The two genuine agents

### 1. Medical agent — chart reconciliation (`halo/mci/reconcile.py`)

**Problem shape:** a mass-casualty arrival with garbled identity ("last name sounded like
'Masikovich'... takes a blood thinner"). Which panel patient is this? The search space is
open-ended: name variants, phonetic alternatives, demographic narrowing, chart corroboration.
That is agent territory — the model decides which searches to run and when to stop.

**Implementation:** Anthropic SDK **beta tool runner** (`client.beta.messages.tool_runner`),
the recommended loop for custom-tool agents. Tools (3, prescriptive descriptions with
when-to-call triggers):
- `search_patients` — deterministic scorer over the FHIR panel; agent supplies name variants
- `get_patient_chart` — meds/conditions for corroboration ("blood thinner" ↔ clopidogrel)
- `propose_candidates` — final-answer-as-tool: structured proposal, no free-text parsing

**Guardrails (defense in depth):**
- **Latency gate:** the agent runs only when deterministic matching is inconclusive AND a
  real identity lead exists — door-triage seconds are precious
- **Propose, never decide:** every proposed ID is re-verified deterministically; hallucinated
  IDs are discarded; demographic mismatches are discarded; agent-sourced candidates cap at
  "possible"; identity is never "confirmed" by software (a human merges charts)
- **Bounded:** `max_iterations`, fail-closed on refusal/truncation (`halo/llm.py` seam)
- **Transparent:** the full tool-call trail returns in the response and renders in the UI

### 2. Legal agent — compliance review (`halo/mci/compliance.py`)

**Problem shape:** after board actions, audit the activity trail against regulatory
obligations — EMTALA medical-screening requirements, IOM Crisis Standards documentation and
accountability, identity-merge governance. Which log lines matter and what pattern satisfies
or violates which rule is open-ended reading — an agent loop over the evidence.

**Implementation:** same tool-runner seam. Tools (4): `get_rules` (the fixed, cited rule
list — the *rules* are never model judgment), `get_board_snapshot`, `get_audit_log`,
`report_findings` (final-answer-as-tool).

**Guardrails:**
- **Evidence verification:** every finding's quoted evidence is checked verbatim against the
  real audit log and board state; fabricated quotes are dropped and the drop is *counted and
  displayed* (`dropped_unverified`), never hidden
- **Fixed rule set:** the five rules cite their legal bases (EMTALA 42 USC 1395dd, IOM Crisis
  Standards of Care 2012, docs/GOVERNANCE.md postures); the agent classifies pass/monitor/flag
  against them, it does not invent obligations
- **Conservative prompt:** ambiguity → monitor, not flag; bounded iterations; fail-closed

## The workflows (deliberately not agents)

| Call | Pattern | Why not an agent |
|---|---|---|
| SALT observation extraction (`extract.py`) | Single structured-output call, quote-grounded, nulls mandatory | Fixed task; the *decision* is deterministic SALT code |
| Identity cue extraction (`reconcile.py`) | Single structured call | Same — feeds the deterministic scorer first |
| Education query routing (`halo/edu`, T2) | Single structured call, enum-constrained, fail-closed to keyword match | Closed answer space |
| Drill adjudication (`halo/edu`, T2) | Single structured call, no credit on uncertainty | Grading against authored keys |

And the things that must never be model calls are code: SALT categories, surge
classification, routing guards, care-modifier flags, identity scoring, sim state machines.
The pattern throughout: **Claude reads and proposes; deterministic, inspectable code decides.**

## Current-best-practices checklist (as applied)

- Tool runner over hand-rolled loops; final-answer-as-tool over free-text parsing
- Few tools with prescriptive "call this when..." descriptions (ACI design)
- Adaptive thinking on every call; single `halo.llm` seam (model knob, fail-closed policy)
- Agents gated by need (deterministic-first), bounded by `max_iterations`, transparent via
  tool trails rendered in the product
- Every agent output is verified by a deterministic layer before anyone sees it
- No agent may take a consequential action: routing, merging, categorizing, and designating
  are human- or rule-owned

## Where a Managed Agent would slot next

The compliance review is the natural candidate for Anthropic's Managed Agents surface as a
**scheduled deployment** (a recurring after-action audit over the day's board logs), with the
agent config version-pinned and the audit memo delivered via webhook. Out of scope for the
hackathon day; the seam (`halo.llm.agent_loop`) keeps that migration a transport change, not
a redesign.
