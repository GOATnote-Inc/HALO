# Workflow — who actually does MCI triage, and where HALO sits

Any MCI tool that assumes a physician at the door has misunderstood the event. This document
states the real workflow and maps each HALO surface to the person who owns that step.

## The ground truth

**Door triage is a nursing workflow.** Even the largest trauma centers run a handful of
emergency physicians per shift — often 2–6 — and when 100+ patients present in an hour,
physicians are in the resuscitation bays, not at the door. The published record matches: at
Sunrise Hospital during Route 91, triage at the ambulance bay was run as a rapid sort by a
small team while the physicians staffed treatment stations (Menes et al., *EP Monthly* 2017).

The door sort is performed by triage nurses using rapid protocols they already know:

- **START / "30-2-Can Do"** — the taught mnemonic: respiratory rate under **30**, perfusion
  (radial pulse or capillary refill under **2** seconds), **can do** — follows commands.
  Seconds per patient, numbers over judgments.
- **SALT** — the national all-hazards guideline (Lerner et al. 2008): global sort
  (walk / wave / still), then the individual screen this module implements.

**Physicians own secondary triage.** Re-assessment in the treatment zones, disposition to OR/CT,
and — only there — any resource-based **expectant** designation, typically alongside incident
command. That decision never belongs to the door, and never to software.

## The door reality this module is built for

| Constraint at the door | HALO design answer |
|---|---|
| Seconds per patient, hands busy, gloves on | One free-text/voice-style note ("RR 38, radial present, follows commands") — no forms, no clicks per field |
| Nurses chart numbers, not judgments | Deterministic 30-2-Can-Do derivation: charted RR ≥ 30 fails the breathing screen, and the derivation is reported openly |
| Patients arrive nameless or with garbled names | Quick-registration alias (Epic-style "Trauma, Alpha") gets the triage Observation; identity candidates route to the registration/reunification team, never auto-merged |
| Incomplete assessments under surge | `UNABLE_TO_TRIAGE` with the exact missing fields — a worklist entry, not a guess |
| The chart of a matched patient is enormous | Care-modifier rule table distills hundreds of FHIR resources to the handful of facts that change trauma care now, each with provenance (see docs/INTEGRATION.md on chart bloat) |
| No internet, downtime procedures in effect | The UI is one dependency-free HTML page; runs on hospital intranet |

## Step by step

0. **Charge nurse clears the board first.** Before the first casualty arrives, the battle is
   the department you already have: 23 occupied beds and a wave inbound. HALO reverse-triages
   the existing census (Kelen et al., *Lancet* 2006;368:1984-90) with a deterministic rule
   table — no model call, results in milliseconds: **discharge now** (workup complete, safe),
   **move to chairs** (stable, untethered, vertical care), **expedite admission** (the NSTEMI
   on heparin, the post-tPA stroke, the hypoxemic pneumonia — their beds free when the floor
   pulls them, so escalate the pull), **hold bed** (monitor/O2/infusion tethers, or anything
   undetermined — never move a patient on missing data). On the demo census that yields
   17 beds freed by ED action alone and 4 more on inpatient pull. The comfort-care hospice
   patient routes to a quiet inpatient bed with a goals-of-care check — never to a hallway.
1. **Charge nurse activates the MCI plan.** Zones stand up (red/yellow/green), downtime
   packets and alias registrations are ready.
2. **Triage nurse at the door** — 15-second look, speaks or types one line per patient. HALO
   extracts observations (quotes only, nulls for the undocumented), runs deterministic
   SALT/START, and returns the category, its rationale, and what's missing. The nurse tags the
   patient and moves on; the note and category post to the alias record.
3. **Registration / reunification team** works HALO's identity candidates: partial names,
   agent-corroborated leads ("blood thinner" matched chart clopidogrel), each labeled
   UNCONFIRMED with match reasons. A human merges records through the EHR's normal identity
   governance — software never merges.
4. **Zone teams** see care-modifier flags *conditioned on the candidate match* — head strike +
   chart clopidogrel is an upgrade conversation the nurse can start before the physician ever
   opens the chart.
5. **Physician secondary triage** re-sorts, disposes, and owns any expectant designation
   (`likely_survivable=false` is the only path to EXPECTANT in the entire codebase).
6. **After-action** — every category, derivation, evidence quote, match reason, and agent tool
   call is on the record, timestamped, reconstructable.

## Why this empowers nurses rather than replacing judgment

The algorithm is the one nurses are already taught — SALT/START — executed exactly and
transparently, with the missing-data discipline no human can sustain at patient 60 of 140.
Nothing is hidden: every category shows its rule, every derived answer says it was derived,
every flag cites its chart source. The nurse stays the decision-maker; the module is the
memory and the audit trail. Today this layer is a vendor black box, a paper tag, or one
person who knows the binder; open-sourcing it puts the same capability in every ED that can
run a web page.
