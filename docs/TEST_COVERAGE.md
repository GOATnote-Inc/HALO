# Test coverage analysis

Method: full offline suite under `pytest-cov` (branch mode) on a fresh `make setup`,
2026-07-30. N = 275 tests over 2,140 statements. Result: **80% line / 77% branch**.
Numbers below are per-module branch coverage from that run.

Re-verified 2026-07-31 after the ecosystem + lint merges (N = 291 tests over 2,232
statements): 80% line / 78% combined, `halo/llm.py` still 57% — every gap and priority
below stands unchanged. The new `edu/provenance.py` (90%), `edu/drafting.py` (83%), and
`edu/receipts_export.py` (100%) arrived tested and are not on the gap list.

## What is already strong

The deterministic clinical core carries the safety weight, and it is the best-tested
code in the repo: `mci/triage.py`, `mci/surge.py`, `edu/lookup.py`, `edu/routes.py`,
and the `mci/extract.py` schema mapping at 100%; `edu/dosing.py` 98%; `edu/drill.py`
and `edu/attest.py` 96%. The goldset test asserts zero under-triage on the
deterministic SALT layer, and `test_mci_reconcile.py` exercises the safety boundary
directly (hallucinated-ID and gender-mismatch discards).

## Gaps, in priority order

### 1. `halo/llm.py` — the seam itself (57%, worst-tested module)

- `agent_loop()` has **zero tests**, yet `mci.reconcile` and `mci.compliance` ride on
  it. Unverified: fail-closed on `pause_turn`/`refusal`/`max_tokens`, `LLMFailure` on
  an empty runner, tool-call trail recording. All testable offline with a stub runner
  (same pattern `test_llm.py` uses for `generate`).
- **Confirmed latent bug** (reproduced offline): `structured()` on malformed or empty
  JSON raises raw `json.JSONDecodeError`, not `LLMFailure` — contradicting the
  `LLMFailure` docstring ("refusal, truncation, bad JSON"). App routes catch only
  `LLMFailure`, so this path surfaces as an unhandled 500 instead of the intended
  fail-closed 502. Fix: wrap `json.loads` and raise `LLMFailure`; add regressions for
  malformed JSON and for a response with no text blocks.

### 2. LLM-backed HTTP routes — no tests at all

`/mci/handoff` (the flagship demo endpoint), `/mci/triage/note`, and
`/mci/compliance` are never exercised, even with stubs. Untested: the handoff
response contract the UI depends on (candidates, `care_flags_if_matched`,
`edu_links`, FHIR bundle) and the `LLMFailure` → 502 mapping. Add per route: one
happy-path test with the LLM-backed functions monkeypatched, one stubbed-failure
test asserting 502. Also cover the `BoardError` → HTTP branches on `/mci/waiting/*`.

### 3. Content-validator rejection branches (`edu/corpus.py` 80%, `sim/cases.py` 80%)

The validators are the only gate on clinical content ("the corpus decides"), but
nearly every `raise ValueError` branch is dead in tests — sim: missing keys,
synthetic/draft flags, missing vitals, unknown `goto`/outcome, unreachable outcomes;
corpus: dose both `per_kg` and `fixed`, per-kg dose without `max_amount`, empty
accept groups, bad `pass_threshold`, no critical step, <2 references, id≠filename,
duplicate ids. Add parametrized mutation tests: copy a valid module/case, break one
field, assert the specific error. Protects the hand-edited-JSON workflow.

### 4. Agent tool bodies (`mci/reconcile.py` 81%, `mci/compliance.py` 90%)

Tests stub `agent_loop` and only call `propose_candidates`/`report_findings`, so the
`@beta_tool` closures the model actually executes are uncovered: `search_patients`
(ranking, top-5 cap, score>0 filter), `get_patient_chart` (found + unknown id),
compliance's three read tools, and the malformed-JSON retry in `report_findings`.
Notably, no test drives an agent proposal that is *new* (absent from the
deterministic shortlist) through scoring into the merged result — the agent's
value-add path (reconcile.py:230-232) never executes. All deterministic; test via
`tool.call({...})` or a fake loop that searches before proposing. `extract_cues`
normalization also needs one stubbed-`structured` test.

### 5. Codify the live goldset eval; decide demo coverage policy

`demo.py`, `mci/demo.py`, `edu/demo.py` are 304 statements at 0% and most of the
headline shortfall. The extraction-side under-triage gate (cardinal metric, target
0) lives only in `python -m halo.mci.demo` — printed, eyeballed. Add a `live` pytest
marker (auto-skip without `ANTHROPIC_API_KEY`, excluded from CI) that runs the
goldset through `extract_observations` and *asserts* 0 under-triage FNs and the
agreement count. Then exclude `*/demo.py` from coverage with a documented rationale;
remaining product code sits near 93% line.

### Smaller items

- `mci/scenarios.py` `get()` (62%): untested lookup + `KeyError`.
- `mci/census.py` fail-closed guards (missing `synthetic` flag, unknown panel
  patient): tmp-fixture tests via `HALO_CENSUS_PATH` (mind the `lru_cache`).
- `mci/board.py` (85%): "already departed" 409, reassess no-op, undo edge branches,
  waiting-fixture synthetic guard.
- CI has no coverage gate: add `pytest-cov` to dev extras and `--cov-fail-under`
  (start 80, ratchet) so the number cannot silently regress.
- Static HTML/JS is Chrome-verified manually only — accepted risk for now; the API
  contract tests are the cheap guard.
