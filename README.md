# HALO

[![ci](https://github.com/GOATnote-Inc/HALO/actions/workflows/ci.yml/badge.svg)](https://github.com/GOATnote-Inc/HALO/actions/workflows/ci.yml)

**HALO — High Acuity, Low Occurrence.** An evidence-based EHR module class for the rare,
high-stakes events clinicians can't practice daily; the first module targets Mass Casualty
Incident (MCI) response. Built live at the **Future of Agentic AI in Healthcare** hackathon
(Abridge × Anthropic × Lightspeed), San Francisco, 2026-07-18.

The evidence base (triage science, real-MCI EHR failure modes, ABEM/ACEP standards, prior art)
lives in `docs/RESEARCH.md`. The scaffold gives every terminal the same green baseline: a typed
Python package, a single fail-closed seam for Claude API calls, offline tests, lint, and CI.

## Quickstart

```sh
git clone https://github.com/GOATnote-Inc/HALO.git && cd HALO
make setup          # venv + deps          (or: uv venv && uv pip install -e ".[dev]")
make check          # ruff + pytest — must be green before every push
cp .env.example .env  # then add your ANTHROPIC_API_KEY (never committed)
```

Smoke-test the Claude wiring and the API surface:

```sh
.venv/bin/python -m halo.demo   # one live round-trip (needs ANTHROPIC_API_KEY)
make serve                      # http://127.0.0.1:8000/health
```

## Repo map

| Path | What it is |
|---|---|
| `src/halo/llm.py` | The only place that calls the Claude API. Model knob `HALO_MODEL` (default `claude-opus-4-8`), adaptive thinking, native structured outputs, fail-closed on refusal/truncation. |
| `src/halo/app.py` | FastAPI surface (health check now; demo endpoints as the project takes shape). |
| `src/halo/demo.py` | One-shot live smoke test of the wiring. |
| `tests/` | Offline unit tests — no network, no API key. CI-gated. |
| `CLAUDE.md` | Working charter for coding-agent sessions (also linked as `AGENTS.md`). |
| `STATUS.md` | Live coordination board — multiple terminals share this repo; claim a lane there first. |

## Working agreements

Several agent terminals work in this repo concurrently. The short version (full rules in
[CLAUDE.md](CLAUDE.md)):

- Claim a lane in [STATUS.md](STATUS.md) before writing code; stay inside your lane's files.
- Stage files **by name** (never `git add -A`), `git pull --rebase` + `make check` before every push.
- Synthetic data only. Never read or print `.env` contents.

## Scope & claims

Research demo built in one day. **Synthetic data only — no real patient data.** This is not a
medical device and nothing here is clinical advice; any clinical content requires qualified
professional review before real-world use. Metrics, when reported, include N and method.

## License

[Apache-2.0](LICENSE)
