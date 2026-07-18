# HALO

[![ci](https://github.com/GOATnote-Inc/HALO/actions/workflows/ci.yml/badge.svg)](https://github.com/GOATnote-Inc/HALO/actions/workflows/ci.yml)

**HALO — High Acuity, Low Occurrence.** An open-source, evidence-linked EHR module class for
the rare, high-stakes events clinicians can't practice daily. Module 1: **Mass Casualty
Incident (MCI) triage support** — built live at the *Future of Agentic AI in Healthcare*
hackathon (Abridge × Anthropic × Lightspeed), San Francisco, 2026-07-18.

**Synthetic data only. Research demonstration — not a medical device.** Full medical, legal,
and ethical posture: [docs/GOVERNANCE.md](docs/GOVERNANCE.md).

## The problem

When a mass casualty event hits, the EHR fails in the same ways every time — the published
after-action record is consistent:

- **Las Vegas, Route 91 (2017):** hundreds of penetrating-trauma patients arrived by private
  vehicle with no EMS tag, no identity, no registration; staff fell back to markers and
  improvised labels (Menes et al., *Emergency Physicians Monthly*, 2017).
- **Boston Marathon bombing (2013):** unknown-patient naming, tracking, and documentation were
  the dominant information-system failures at a fully-EHR'd academic center (Landman et al.,
  *Ann Emerg Med* 2015;66(1):51–59).
- **Beirut port explosion (2020):** several hundred casualties in ~two hours at a single
  academic center; identification chaos and paper documentation, per published AUBMC accounts.

Yet in most emergency departments today, MCI triage support is an opaque vendor feature, a
paper form, or one staff member who knows the disaster binder. HALO's position: this layer
should be **open source, inspectable, evidence-linked, and free to every ED on earth**.

## What it does

Three capabilities, one pipeline, every decision fail-closed:

1. **Structured extraction** — Claude turns a free-text field/EMS note (or ambient-style
   transcript) into SALT triage observations. Every value carries a verbatim evidence quote;
   anything not documented is `null`. The model **never assigns a triage category**.
2. **Deterministic SALT triage** — a published national-guideline algorithm (Lerner et al.,
   *Disaster Med Public Health Prep* 2008) maps observations to a category in pure Python.
   Missing critical data → `UNABLE_TO_TRIAGE` (assess in person now). Unknown injury extent
   defaults *up*, never down. `EXPECTANT` requires an explicit human resource decision —
   the algorithm cannot produce it autonomously.
3. **Agentic chart reconciliation** — the Route 91 failure mode is unknown patients. Given
   partial or garbled identity ("last name sounded like *Wilkerson*… takes a blood thinner"),
   deterministic scoring resolves clean cases; when inconclusive, a bounded Claude agent loop
   searches the hospital FHIR panel with name variants, corroborates candidates against chart
   content, and *proposes* — every proposal is re-verified deterministically, demographics
   alone can never rank "strong," and identity is **never "confirmed" by software**. Matched
   candidates surface deterministic care-modifier flags with chart provenance: antithrombotic
   therapy (occult hemorrhage risk), beta-blockade (masked tachycardia), pregnancy, documented
   hospice goals of care.

```
free-text field note ──▶ Claude extraction ──▶ deterministic SALT ──▶ category + rationale
        │                (quotes, nulls)        (published algorithm)   + missing fields
        │
        └──▶ cue extraction ──▶ deterministic match ──┬─ strong ─▶ candidates + care flags
                                    (score, verify)   └─ unclear ─▶ agent loop (search
                                                          variants, corroborate via chart,
                                                          propose) ─▶ re-verify ─▶ candidates
                                                          capped at "possible" + tool trail
```

The agentic design follows Anthropic's building-effective-agents doctrine: the simplest
pattern that works everywhere it works (single structured calls, deterministic code), an
agent loop only where open-ended exploration pays (garbled identity), tools with prescriptive
descriptions, bounded iterations, and a full tool-call trail in every response.

## The safety case

| Failure mode | Behavior |
|---|---|
| Note doesn't document breathing | `UNABLE_TO_TRIAGE` — assess in person immediately |
| Life threat can't be ruled out | `UNABLE_TO_TRIAGE`, never a guess |
| Injury extent unknown after clean screen | Defaults **up** to `DELAYED` — never downgrade on missing data |
| Model refuses / output truncated | `LLMFailure` raised; partials never parsed (`halo.llm`) |
| Resource-based abandonment (`EXPECTANT`) | Only via explicit human `likely_survivable=false` |
| Agent proposes a hallucinated patient ID | Discarded at deterministic re-verification |
| Demographics-only identity match | Capped below "strong" — a name cue is required |
| Any identity match | At most a *candidate*; confirmation is a human act |

**Cardinal metric: under-triage false negatives = 0.** Current results on the synthetic
goldset (N=12 notes, claude-opus-4-8, single run, method in `src/halo/mci/demo.py`):
11/12 category agreement, **0 under-triage FNs**, 78/84 extraction fields correct; the sole
disagreement was safe-direction over-triage. 56 offline tests (including a 3⁷ input-space
totality sweep) gate CI.

## Quickstart

```sh
git clone https://github.com/GOATnote-Inc/HALO.git && cd HALO
make setup          # venv + deps
make check          # ruff + pytest, offline — must be green
cp .env.example .env  # add ANTHROPIC_API_KEY (never committed)
```

Live surfaces (need `ANTHROPIC_API_KEY`):

```sh
.venv/bin/python -m halo.mci.demo            # goldset eval: extraction + triage + FN gate
.venv/bin/python -m halo.mci.demo --handoff  # 3 scripted end-to-end scenarios (see below)
make serve                                    # then open http://127.0.0.1:8000
```

The web UI at `/` is a single dependency-free HTML page (works on a hospital intranet with no
internet): paste or pick a field note, run the handoff, and read the triage banner,
evidence-quoted observations, identity candidates with care flags, and the agent's tool trail.

The three scripted scenarios mirror the published failure modes:

1. **Route 91 pattern** — self-transported, partial identity, head strike; resolves
   deterministically and surfaces the clopidogrel occult-hemorrhage flag.
2. **Beirut pattern** — bystander-reported phonetic name; the agent loop tries variants,
   corroborates "blood thinner" against the chart, and proposes a candidate capped at
   *possible* — including a documented-hospice goals-of-care flag.
3. **Fail-closed showcase** — a sparse note; the system escalates rather than guesses.

## Repo map

| Path | What it is |
|---|---|
| `src/halo/llm.py` | The only Claude seam: model knob (`HALO_MODEL`, default `claude-opus-4-8`), adaptive thinking, structured outputs, bounded agent loop, fail-closed policy. |
| `src/halo/mci/` | Module 1: `extract` (note → observations), `triage` (deterministic SALT), `panel` (FHIR panel, scoring, flag rules), `reconcile` (agentic identity), `scenarios`, `demo`. |
| `src/halo/app.py` | FastAPI: web UI at `/`, `POST /mci/handoff`, `POST /mci/triage/*`. |
| `src/halo/static/` | The dependency-free demo UI. |
| `synthetic-ambient-fhir-25/` | Abridge-provided fully synthetic FHIR R4 panel (25 patients). |
| `tests/` | Offline tests + synthetic goldset — no network, no key. CI-gated. |
| `docs/GOVERNANCE.md` | Medical, legal, and ethical posture; AI risk register; limitations. |
| `CLAUDE.md` / `STATUS.md` | Working charter and live multi-terminal coordination board. |

## Working agreements

Several agent terminals work in this repo concurrently (full rules in [CLAUDE.md](CLAUDE.md)):
claim a lane in [STATUS.md](STATUS.md) first; stage files by name; `git pull --rebase` +
`make check` before every push; synthetic data only; never read or print `.env` contents.

## Scope & claims

Research demo built in one day. **Synthetic data only — no real patient data.** Not a medical
device; no clinical validation; nothing here is clinical advice. A production version would
require the regulatory pathway discussed in [docs/GOVERNANCE.md](docs/GOVERNANCE.md), clinical
validation, and qualified professional review. Metrics, when reported, include N and method.

## License

[Apache-2.0](LICENSE)
