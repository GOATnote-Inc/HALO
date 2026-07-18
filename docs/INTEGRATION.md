# EHR Integration — Epic and FHIR-native incorporation path

HALO is built to slot into the EHR an emergency department already runs, not to replace it.
Everything below describes the integration architecture this repo's interfaces were designed
against; the working demo exercises the same data shapes on synthetic data.

## Integration surfaces (in the order a site would adopt them)

1. **SMART on FHIR app (EHR launch).** The web UI is a single dependency-free HTML page —
   the natural packaging is a SMART on FHIR app launched from the EHR (triage kiosk, tablet
   on the ambulance ramp) with encounter context. Epic, Oracle Health, and MEDITECH all
   support SMART R4 launch; nothing in the UI requires anything beyond a browser.
2. **FHIR R4 reads (already implemented).** The panel layer consumes standard FHIR R4:
   `Patient` (name/gender/birthDate), medication and condition labels, encounter titles —
   the same shapes as US Core `Patient`, `MedicationRequest`, `Condition`, `Encounter`. The
   Abridge synthetic dataset is exactly this format; pointing `panel.py` at a FHIR server's
   query results instead of a JSONL file is an adapter, not a redesign.
3. **FHIR R4 write-back (implemented as a preview).** Every handoff response carries a
   `Bundle` containing one `Observation`: the SALT category (local CodeSystem, mapped to the
   site dictionary at integration), coded components for each documented screen answer with
   verbatim evidence quotes as extensions, LOINC-coded respiratory rate, `status:
   preliminary` (door triage — physician secondary triage supersedes), and
   `dataAbsentReason` naming what was never documented. It targets the
   **unidentified-patient alias record**, mirroring how EDs actually register MCI arrivals.
4. **CDS Hooks for care flags.** The care-modifier rule table (antithrombotic therapy,
   beta-blockade, pregnancy, hospice goals) is shaped like `patient-view` /
   `encounter-start` CDS Hooks cards: short summary, why-it-matters, chart provenance,
   severity. Once a human confirms an identity merge, the same rules fire as cards on the
   real chart — no HALO UI required in the physician's workflow at all.

## The unknown-patient (alias) workflow

EDs register MCI arrivals under quick-registration aliases (Epic-style "Trauma, Alpha" with
a pre-generated MRN from the downtime packet). HALO is built around that reality:

- The triage `Observation` posts to the **alias** record — it is true regardless of identity.
- Identity candidates are a **worklist for the registration/reunification team**, each
  labeled UNCONFIRMED with deterministic match reasons and (when the agent ran) chart
  corroboration. Candidate care flags are deliberately **excluded from the write-back
  bundle**: writing them to the alias would smuggle an unconfirmed identity into the chart.
- Record merge happens through the EHR's existing identity-governance process (HIM review),
  exactly as it does today. Software proposes; humans merge. This is also the safety answer
  to the EHR world's most feared identity failure — the wrong-chart merge.

## Chart bloat — both directions

Chart bloat is the defining failure of EHR documentation: notes assembled by copy-forward
and auto-import until the signal drowns. An MCI tool has to answer for bloat twice:

**Reading.** A matched panel patient can carry an enormous longitudinal record — in this
demo's own synthetic panel, one patient's chart holds **600 FHIR resources**. No zone team
is reading that during a surge. The care-modifier layer is an anti-bloat filter by
construction: a deterministic rule table distills the full record to the few facts that
change trauma care *now* — each with its provenance — and the UI shows the ratio
("600 resources → 4 care-modifying facts"). Nothing is summarized by a model; nothing is
lost silently; the filter is inspectable code.

**Writing.** HALO's write-back is one structured `Observation` with coded components — no
narrative note, no restated history, no copy-forward substrate. The evidence quotes are
extensions on the coded values, not paragraphs. A downstream reader gets exactly what the
door knew, and nothing else. The after-action record accumulates in the event log (which
also captures the agent tool trail), not in the chart.

## Deployment posture

- **Downtime-first:** the UI is one HTML file with zero external requests — it works on an
  intranet segment during the network chaos that accompanies real events.
- **Model seam:** all Claude calls go through `halo.llm` (`HALO_MODEL` knob); a site can pin
  models, route to a gateway, or swap providers in one file.
- **PHI:** this repo is synthetic-only. A production deployment processes PHI and requires
  HIPAA-eligible infrastructure and BAAs across every processor, including the LLM API —
  see docs/GOVERNANCE.md §2 for the full regulatory posture (including why time-critical
  triage CDS should be assumed to be FDA device territory).
