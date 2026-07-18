# STATUS — live coordination board

Every terminal updates this file when claiming or finishing work. Commit it with your changes —
it is the source of truth for who is working where.

## Lanes

| Lane | Owner | Scope (files/dirs) | State | Verify |
|---|---|---|---|---|
| scaffold | T0 | repo root, `src/halo/`, `tests/`, CI | done | `make check` (11 passed) |
| mci-module | T1 | `src/halo/mci/`, `tests/test_mci_*.py`, `tests/fixtures/`, `src/halo/app.py` (add routes only) | done | `make check` (38 passed); live `python -m halo.mci.demo`: 11/12 agreement, 0 under-triage FNs, N=12 synthetic |
| mci-reconcile | T1 | `src/halo/mci/panel.py`, `src/halo/mci/reconcile.py`, `src/halo/llm.py` (agent_loop), `synthetic-ambient-fhir-25/` | done | `make check` (55 passed); live agent path verified (variant search + chart corroboration -> 'possible') |
| demo-surface | T1 | `README.md`, `docs/`, `src/halo/static/`, `src/halo/mci/scenarios.py`, `src/halo/mci/demo.py`, `src/halo/app.py` (UI routes) | done | `make check` (62 passed); `demo --handoff` 3/3 scenarios live; UI verified in Chrome (shell + live autorun screenshots) |
| edu-module | T2 | `src/halo/edu/`, `tests/test_edu_*.py`, `tests/fixtures/edu_*` | active | `make check`; `python -m halo.edu.demo` (offline drill + card render) |
| nurse-workflow | T1 | `src/halo/mci/` (triage/extract/panel/fhir_out), `src/halo/static/`, `docs/WORKFLOW.md`, `docs/INTEGRATION.md`, `README.md`, `tests/test_mci_*`, `tests/test_app.py` | active | `make check`; UI re-verified in Chrome |

Claim a lane: add a row with a short name, your terminal label (T1/T2/…), the exact files or
directories you own, state `active`, and the command that proves your work. Push the claim before
you start. Set state to `done` (with the verify command's result) when you finish.

## Decisions log

- 2026-07-18: Repo created pre-event as the day-of build repo. Name: HALO.
- 2026-07-18: Scope decided — **HALO = High Acuity, Low Occurrence** EHR module class. First
  module: evidence-based Mass Casualty Incident (MCI) support. Deep-research pass (triage science,
  real-MCI EHR failure modes, ABEM/ACEP/JAMA/NEJM evidence base, prior art, defensible demo
  metrics) running; report lands in `docs/RESEARCH.md` and drives the build plan.
- 2026-07-18: MCI module design locked — **extraction/decision split**: Claude extracts SALT
  observations from free-text notes (never assigns a category); a deterministic SALT algorithm
  decides. Fail-closed: missing data -> UNABLE_TO_TRIAGE (or safe-direction over-triage);
  EXPECTANT only via explicit human `likely_survivable=false`. Live e2e on the 12-case synthetic
  goldset (claude-opus-4-8): 11/12 category agreement, 0 under-triage FNs; sole miss is
  safe-direction over-triage.
- 2026-07-18: Module 3 locked — **readiness & CME** (`halo.edu`): just-in-time procedure cards +
  drill engine for HALO procedures a general ED must perform without the specialist (perimortem
  cesarean, imminent breech delivery, lateral canthotomy, organophosphate/2-PAM response). Same
  doctrine as MCI: a curated, versioned corpus and deterministic dosing/grading decide; Claude only
  routes free-text queries to cards and adjudicates drill answers (fail-closed to deterministic
  keyword match; no credit on uncertainty). EHR seams: FHIR bundle -> patient context for
  weight-based dosing; completed drills -> hash-chained CME evidence records (JSONL);
  crisis-session log -> draft FHIR MedicationAdministration/Procedure/Composition. All clinical
  content ships `review.status="draft"` until physician sign-off — rendered on every card.
- 2026-07-18: Module 2 locked — **agentic chart reconciliation** over the Abridge
  synthetic-ambient-fhir-25 panel. Simplest-pattern-first: deterministic cue scoring resolves
  clean identities; the SDK beta tool runner handles garbled ones (name-variant search + chart
  corroboration). Agent proposes, deterministic layer verifies; identity status is never
  "confirmed" (human act); care-modifier flags are a rule table with FHIR provenance. Anti-project
  check: agentic tool use + deterministic clinical guardrails — no dashboard, no RAG, no chatbot.
- 2026-07-18: Judged surface locked — evidence-linked README (Route 91/Boston/Beirut after-action
  citations), docs/GOVERNANCE.md (honest FDA device posture, EMTALA, HIPAA-eligible framing, IOM
  crisis standards, AI risk register), dependency-free web UI at `/` (works offline/intranet),
  and `demo --handoff` (3 scripted scenarios, one source of truth with the UI via
  /mci/scenarios). Mission framing: open-source the MCI layer every ED currently handles with a
  binder, a vendor black box, or one staff member.
