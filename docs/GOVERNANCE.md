# Governance — medical, legal, and ethical posture

HALO's MCI module makes safety-relevant suggestions in a clinical context, so its design has to
answer to three landscapes at once: the medical evidence, the regulatory/legal environment, and
the ethics of algorithmic triage. This document states our posture plainly and maps each concern
to a concrete engineering decision in this repository. Nothing here is legal advice; a production
deployment requires qualified regulatory, legal, and clinical review.

## 1. Why this problem — the published evidence

Mass casualty incidents break the parts of the EHR everyone assumes will work. The pattern
repeats across published after-action accounts:

- **Las Vegas, Route 91 Harvest festival shooting (2017).** The widely cited account of the
  Sunrise Hospital response (Menes, Tintinalli, Plaster — *Emergency Physicians Monthly*, 2017)
  describes hundreds of penetrating-trauma patients, most arriving by private vehicle and
  rideshare with no EMS triage tag, no identity, and no registration — staff resorted to
  markers and improvised labels because formal registration could not keep pace. Identity and
  tracking, not clinical skill, were the bottleneck.
- **Boston Marathon bombing (2013).** Landman et al., *Annals of Emergency Medicine* 2015
  (66(1):51–59), document one ED's information-systems experience: unknown-patient naming,
  patient tracking, and documentation under surge were dominant failure modes — in a modern,
  fully-EHR'd academic center.
- **Beirut port explosion (2020).** Published accounts from the American University of Beirut
  Medical Center describe several hundred casualties arriving within roughly two hours,
  identification chaos, families searching for the missing, and documentation reduced to paper —
  one of the largest single-hospital surges in modern history.
- **Triage science.** SALT is the national all-hazards mass-casualty triage guideline (Lerner
  et al., *Disaster Med Public Health Prep* 2008;2(S1):S25–S34, and the Model Uniform Core
  Criteria, Lerner et al. 2011;5(2):129–137). ASPR TRACIE's *Mass Casualty Trauma Triage:
  Paradigms and Pitfalls* (2019) catalogs how triage systems fail in practice; the ACS Committee
  on Trauma's field-triage doctrine treats **under-triage as the harm to minimize** and accepts
  substantial over-triage as its price.

Today, most emergency departments handle this with an opaque vendor feature, a paper form, or
one staff member who "knows the disaster plan." HALO's premise is that this layer should be
open-source, evidence-linked, and inspectable by any physician, anywhere.

## 2. Regulatory posture

**This is a research demonstration, not a medical device, and it is not deployed for clinical
use.** We state that honestly rather than engineering around it:

- **FDA.** Under the FDA's *Clinical Decision Support Software* guidance (September 2022),
  software that supports **time-critical** decisions — and triage is the canonical example —
  generally does not qualify for the non-device CDS carve-out, because a clinician cannot
  practically review the basis for each recommendation in the moment. A production version of
  this module should therefore be assumed to be **device territory (SaMD)** requiring the
  appropriate regulatory pathway. We do not claim an exemption. What we *do* adopt from the CDS
  guidance is its transparency principle: every output carries the verbatim evidence quote,
  rule, or chart provenance that produced it, so the basis is independently reviewable.
- **EMTALA.** In a real deployment, MCI triage occurs inside EMTALA obligations. This module
  supports prioritization; it does not perform or replace the medical screening examination,
  and nothing in it gates whether a patient is seen.
- **HIPAA.** This repository contains **synthetic data only** (every fixture and the Abridge
  panel are marked synthetic). A real deployment would handle PHI and requires HIPAA-eligible
  infrastructure, a BAA covering every processor (including the LLM API), minimum-necessary
  access to matched charts, and audit logging. We say "HIPAA-eligible," never "HIPAA
  compliant" — compliance is a property of a deployment, not of code.
- **Crisis standards of care.** The IOM/National Academies *Crisis Standards of Care* framework
  (2012) is explicit that resource-based prioritization decisions carry ethical and legal weight
  and belong to accountable humans and institutions. That is why `EXPECTANT` cannot be produced
  by this software autonomously (see §4).

## 3. Liability and the audit trail

Decision-support liability turns on two questions: *was the clinician meaningfully in the loop*
and *can you reconstruct what the system told them*. Both are engineering requirements here:

- **Human-in-the-loop by construction.** Triage categories come from a deterministic, published
  algorithm (SALT) over extracted observations; identity is never "confirmed" by software;
  `EXPECTANT` requires an explicit human decision; `UNABLE_TO_TRIAGE` demands in-person
  assessment rather than guessing.
- **Reconstructable record.** Every handoff response carries the extracted observations with
  verbatim evidence quotes, the deterministic rule rationale, the identity-match reasons and
  scores, the chart provenance behind every care flag, and the complete agent tool-call trail.
  In an after-action review — or a courtroom — the system's exact contribution at each moment
  is inspectable. Opaque triage (paper, memory, or a black-box vendor feature) offers none of
  this.

## 4. Ethics

- **Under-triage is the cardinal harm.** Missing a salvageable critical patient is the error
  the system is built to avoid; the eval gate is **zero under-triage false negatives**, and
  every missing-data path resolves upward (over-triage) or to escalation, never downward. This
  mirrors the ACS-COT asymmetry between under- and over-triage.
- **Expectant is a human act.** Declaring a patient expectant is a distributive-justice
  decision — allocating care away from someone to save others. Ethically that decision requires
  human judgment and human accountability; the algorithm will output `EXPECTANT` only when a
  human has explicitly recorded that resource judgment (`likely_survivable=false`), and never
  infers it.
- **Wrong-chart harm and identity.** Merging the wrong chart can be as dangerous as no chart
  (wrong allergies, wrong anticoagulation status). Identity status is therefore capped at
  *candidate* strength: demographics alone can never rank "strong," agent-proposed matches cap
  at "possible," and confirmation is reserved for humans.
- **Equity in name matching.** String-similarity matching degrades on transliterated,
  hyphenated, or culturally unfamiliar names — a known bias vector documented as a limitation
  (see §5). The mitigation direction is phonetic/variant search (the agent layer) plus human
  adjudication, never higher automation.
- **Automation bias.** Clinicians over-trust confident software. Counters built in: every
  category shows its rule and its missing fields; every flag shows its chart provenance; the
  UI labels candidates "UNCONFIRMED"; escalation states are visually louder than answers.
- **Privacy under chaos.** Chart context surfaced during an MCI is limited to care-modifying
  facts (medications, conditions, goals of care) — minimum necessary, not the full record.
- **Open source as equity.** Well-resourced trauma centers rehearse MCIs; small and rural EDs
  get a binder. Publishing this layer under Apache-2.0, with its evidence and its evals, is
  itself the ethical position: the standard of care in a disaster should not depend on a
  hospital's software budget.

## 5. AI-specific risk register

| Risk | Mitigation in this repo |
|---|---|
| Model hallucination (invented observations) | Extraction is quote-grounded (verbatim `evidence` per field); nulls are the mandated answer for anything not documented |
| Model hallucination (invented patients) | Agent proposals are re-verified against the panel; unknown IDs discarded |
| Model refusal / truncation | Fail-closed seam raises `LLMFailure`; no partial output is ever parsed (`src/halo/llm.py`) |
| Model assigns clinical judgment | It can't — categories and flags are deterministic code over structured fields; the model only extracts and searches |
| Demographic false confidence | Gender/age-only cues capped below "strong"; gender mismatch zeroes a candidate |
| Name-similarity bias | Documented limitation; agent variant-search partially mitigates; human adjudication required |
| Automation bias | Rationale, provenance, and missing-field lists on every output; UNCONFIRMED labeling |
| Silent scope creep to real data | Every fixture and dataset marked `synthetic: true`; goldset test asserts it |

## 6. Known limitations

Research demo built in one day, on synthetic data, with a 25-patient panel and a 12-case
triage goldset. No clinical validation, no IRB, no prospective evaluation, no claim of
generalization. Extraction accuracy and identity matching are measured only against the
synthetic goldset (N and method reported wherever metrics appear). Name matching has known
bias modes (§4). The SALT implementation covers the individual-assessment step, not the full
incident-command workflow. None of this is clinical advice.
