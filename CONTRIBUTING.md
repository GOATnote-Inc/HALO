# Contributing

HALO is a solo-maintained research project; issues and small PRs are welcome.

- Setup: `make setup` (venv + dev deps), then `make check` (ruff + pytest,
  offline) — it must be green before and after your change.
- Stage files by name (never `git add -A`); keep commits focused.
- Synthetic data only. Never commit `.env`, keys, or anything derived from a
  real patient record.
- Fail-closed is the house rule: on model refusal, truncation, bad JSON, or a
  missing final answer, raise `halo.llm.LLMFailure` — never return a partial.
- Type checking is strict on `src` (`.venv/bin/python -m mypy`); keep it clean.
- Metrics claims need N and method (see CLAUDE.md).

Security reports: see [SECURITY.md](SECURITY.md).
