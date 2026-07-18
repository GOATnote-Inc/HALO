# STATUS — live coordination board

Every terminal updates this file when claiming or finishing work. Commit it with your changes —
it is the source of truth for who is working where.

## Lanes

| Lane | Owner | Scope (files/dirs) | State | Verify |
|---|---|---|---|---|
| scaffold | T0 | repo root, `src/halo/`, `tests/`, CI | done | `make check` (11 passed) |

Claim a lane: add a row with a short name, your terminal label (T1/T2/…), the exact files or
directories you own, state `active`, and the command that proves your work. Push the claim before
you start. Set state to `done` (with the verify command's result) when you finish.

## Decisions log

- 2026-07-18: Repo created pre-event as the day-of build repo. Name: HALO. Project scope TBD at
  the event — record it here when decided.
