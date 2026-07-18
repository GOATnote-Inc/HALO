# STATUS — live coordination board

Every terminal updates this file when claiming or finishing work. Commit it with your changes —
it is the source of truth for who is working where.

## Lanes

| Lane | Owner | Scope (files/dirs) | State | Verify |
|---|---|---|---|---|
| scaffold | T0 | repo root, `src/halo/`, `tests/`, CI | done | `make check` (11 passed) |
| mci-module | T1 | `src/halo/mci/`, `tests/test_mci_*.py`, `tests/fixtures/`, `src/halo/app.py` (add routes only) | done | `make check` (38 passed); live `python -m halo.mci.demo`: 11/12 agreement, 0 under-triage FNs, N=12 synthetic |

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
