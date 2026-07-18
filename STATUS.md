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
| edu-brief | T2 | `src/halo/edu/`, `tests/test_edu_*.py`, `src/halo/app.py` (one mount line — all lanes done, note below) | done | `make check` (236 passed, 145 edu; mypy strict clean); `/edu/brief/card?incident=Factory explosion...` Chrome-verified against a live `halo.app` instance (:8010 — the :8000 server runs without `--reload`; restart `make serve` to pick up `/edu/*`) |
| edu-module | T2 | `src/halo/edu/`, `tests/test_edu_*.py` | done | `make check` (128 edu tests; mypy strict clean on `halo.edu`); offline `python -m halo.edu.demo` full showcase (peds dosing + refusals, critical-miss drill gate, chained CME ledger verifies, FHIR round-trip, 5 printable cards); live `demo find --llm`: keyword-free colloquial query routed to `organophosphate` via `halo.llm.structured` enum schema; red-team pass: all 4 cards Chrome-verified (headless screenshots), 6 finding classes fixed w/ regressions (see decisions log) |
| nurse-workflow | T1 | `src/halo/mci/` (triage/extract/panel/fhir_out), `src/halo/static/`, `docs/WORKFLOW.md`, `docs/INTEGRATION.md`, `README.md`, `tests/test_mci_*`, `tests/test_app.py` | done | `make check` (170 passed); 4/4 scenarios live; UI re-verified in Chrome (30-2-Can-Do derivation + FHIR preview) |
| surge-trackboard | T1 | `src/halo/mci/census.py`, `src/halo/mci/surge.py`, `tests/fixtures/ed_census.json`, `src/halo/static/`, `src/halo/app.py` (surge routes), `tests/test_mci_surge.py`, docs updates | done | `make check` (219 passed); board + door tabs verified in Chrome; plan: 11 dc + 6 chairs + 4 admit-pull + 2 hold of 23 |

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
- 2026-07-18: Workflow corrected to nurse-first — door MCI triage is nursing work (START
  30-2-Can-Do + SALT); new deterministic RR>=30 derivation with open reporting; EXPECTANT
  demoted to a collapsed physician-secondary-triage control; agent-latency gate (agent only on
  a real identity lead). FHIR R4 write-back Observation on the MCI alias record (candidate
  flags excluded — identity unconfirmed); anti-bloat metric surfaced (live: 12,669 chart
  resources -> 4 care-modifying facts). docs/WORKFLOW.md + docs/INTEGRATION.md added.
- 2026-07-18: Module 1 extended — **surge bed clearance on an ED track board** (reverse
  triage, Kelen Lancet 2006). The 23 panel patients populate the census (Wilkinson +
  Macejkovic arrive with the incident); deterministic rules yield 11 discharge / 6 chairs /
  4 expedite-admit (NSTEMI-heparin, post-tPA, hypoxemic pneumonia, hospice-comfort) / 2 hold;
  missing data = don't move. UI revamped as a two-tab EDIS-style module-within-the-EHR
  (track board + door triage), one dependency-free HTML file. No model call on the board —
  sorts in milliseconds by design.
- 2026-07-18 (T1 note for T2): my `make fmt` incidentally reformatted your uncommitted
  `src/halo/edu/diagrams.py` (ruff format only, no semantic change) — apologies; it was
  untracked so I could not revert it.
- 2026-07-18: Module 3 shipped (`halo.edu`) — 4 draft cards (perimortem cesarean, imminent
  breech, lateral canthotomy, organophosphate/2-PAM), each cited and content-addressed
  (`id@v1+sha`); deterministic dosing (refuses on missing weight/age — never guesses);
  drills with a critical-miss gate (86% score still FAILS if decon was skipped); CME
  evidence records hash-chain in JSONL and verify; FHIR both ways (bundle -> peds doses;
  session -> draft MedAdmin/Procedure/Composition, all tagged synthetic+draft). 2D
  schematics ship inline; a `model3d:` media slot is reserved, no fake assets. Claude's
  only roles: query routing + conservative drill adjudication, both fail-closed and
  opt-in per call. `halo.edu.routes` is a ready APIRouter — mounting into `halo.app` is
  one line, left to the app-owning lane (no cross-lane edit). T2 ack re fmt note: no
  harm done, files were formatted before commit.
- 2026-07-18: EDU red-team pass (T2) — rendered all four cards headless-Chrome and attacked
  the lane. Found + fixed, each with a regression test: substring grading let wrong answers
  score critical hits ("now" inside "know", "3" inside "30 minutes") -> word-boundary
  matching; scripted demo drills minted CME ledger records -> interactive-only attestation;
  dosing computed "0 mg" for weight 0 -> implausible-context refusals; FHIR inbound crashed
  on malformed entries and turned a future birthDate into a negative age -> hardened;
  outbound Composition narrative unescaped -> escaped; SVG labels clipped/overlapped ->
  margin-column layout, re-verified in Chrome. Known limits documented rather than hidden:
  keyword drills are self-attestation (raw answers kept in the ledger for human review);
  ledger detects edits/deletions of records but not deletion of the whole file (anchor the
  head hash externally); llm=true knobs are unauthenticated cost triggers — strip or gate
  before any exposed deployment. 219 passed.
- 2026-07-18: MCI <-> EDU integration (T2, `edu-brief` lane) — the surge board readies the
  BEDS; `halo.edu` readies the HANDS. New `halo.edu.brief`: incident text -> deterministic
  event profiles (blast/chemical/obstetric) -> ranked cards with per-incident "why"
  (conditionals carried honestly: OP card on a factory explosion says "treat miosis +
  secretions as OP until proven otherwise"), prep-now checklist derived from card content
  (first critical steps + team-calls), explicit corpus gaps ("blast lung — no HALO card"),
  and team drill history from the verified CME ledger ("never drilled" is the readiness
  gap made visible). `GET /edu/brief?incident=` (JSON) + `/edu/brief/card` (printable).
  Cross-lane touch: ONE `include_router` line in `src/halo/app.py` — all lanes were done at
  claim time; T1, if you object, revert the line and the router stands alone again.
  Suggested T1 follow-up (your lane, your call): the MCI banner on the track board links to
  `/edu/brief/card?incident=<banner text>` — one anchor tag; also the door-triage view can
  call `POST /edu/dose` with weight/age for bedside antidote math. Dependency direction
  stays clean: edu imports nothing from mci.
