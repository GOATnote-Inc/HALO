# HALO — session charter

Day-of build repo for the Future of Agentic AI in Healthcare hackathon (Abridge × Anthropic ×
Lightspeed, SF, 2026-07-18). Public repo — judges and engineers from both companies may read
anything committed here at any time.

## Start of session — do this first

1. Read `STATUS.md`. Claim a lane (add/edit a row, commit + push it) **before** writing code.
2. `make setup` once per machine. `make check` must be green before every push.

## Commands

- `make setup` — venv + deps
- `make check` — ruff + pytest (the CI gate, run it before pushing)
- `make fmt` / `make typecheck` — format; mypy (advisory, not CI-blocking)
- `make serve` — FastAPI on :8000
- `.venv/bin/python -m halo.demo "prompt"` — live Claude smoke test

## Multi-terminal protocol

Several Claude Code sessions share this repo. To keep git history clean:

- **One terminal = one lane.** Scope is a set of files/dirs, recorded in `STATUS.md`. Do not edit
  files outside your lane; if you must, coordinate via a note in `STATUS.md` first.
- **Commit small, commit often.** Stage files **by name** — never `git add -A` or `git add .`.
- **Before every push:** `git pull --rebase origin main`, re-run `make check`, then push.
- If a rebase conflicts in files outside your lane, stop — don't resolve someone else's work.
- Shared files (`STATUS.md`, `README.md`, `pyproject.toml`) get one-line focused commits so
  rebases stay trivial.

## Hard rules

- **Never read `.env` or print secret values.** Verify presence only:
  `awk -F= '/^ANTHROPIC_API_KEY=/ {print $1, "len:", length($2)}' .env`
- **Synthetic data only.** No real patient data, ever. Mark every fixture `"synthetic": true`.
- **Claims discipline** (public, judged repo): no metrics without N and method; say
  "HIPAA-eligible", never "HIPAA compliant"; research demo, not a medical device.
- **Evals before features** where feasible: a small goldset with a failing-closed test beats an
  untested feature. Unsafe-output false negatives are the cardinal metric — target 0.

## Claude API

- Every product call goes through `halo.llm` — never construct an Anthropic client elsewhere.
- Model knob: `HALO_MODEL`, default `claude-opus-4-8`. Adaptive thinking stays on.
- Structured output via `halo.llm.structured()` (native `output_config` json_schema).
  `stop_reason` of `refusal` or `max_tokens` means the schema is not guaranteed — the seam raises
  `LLMFailure`; treat it as failure, never parse the partial.
