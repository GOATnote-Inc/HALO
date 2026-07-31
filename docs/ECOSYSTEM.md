# HALO in the GOATnote EM ecosystem

HALO is not a standalone weekend build. It is the newest node in a set of
emergency-medicine artifacts that already share one knowledge layer and one
attestation primitive. This document states, honestly, where each seam is
**wired in code today** and where it is a **documented interface** waiting on a
sprint — so nothing here reads as more finished than it is.

The governing rule (from every repo's charter): **no runtime imports between
these repos.** They interoperate by shared *data formats* and shared
*identifiers*, never by importing each other. Every seam below respects that.

```
            OpenEM corpus  ── breadth: 370 conditions, 631 citations
                  │           (sourcing + provenance, NOT graded content)
                  ▼
   ┌────────────────────────────┐
   │  HALO edu / CME engine      │  depth: step-graded drills, computable
   │  (hand-built, MD-signed)    │  dosing, fail-closed refusal
   └────────────┬───────────────┘
                │ hash-chained CME evidence (identical primitive)
                ▼
            receipts ledger  ── public, Merkle-chained attestation
                ▲
                │ FN=0 safety eval (cardinal metric)
            LostBench / SafeShift
```

## Seam 1 — OpenEM as citation & provenance backbone  *(wired)*

OpenEM supplies breadth and citations; HALO supplies depth. The boundary is
enforced, not aspirational:

- `Reference` now carries optional `pmid` and `openem_id`
  (`src/halo/edu/models.py`). A citation can be independently retrieved (PMID)
  and traced to its OpenEM condition (`openem_id`).
- `halo.edu.provenance.summarize()` makes a card's provenance coverage a
  **number**, not a claim.
- `python -m halo.edu.drafting <openem-condition.md>` seeds a card *draft
  skeleton* from an OpenEM condition: it carries identity + cited provenance and
  **refuses to invent** steps, meds, doses, or drills. The skeleton is
  intentionally not loadable by the corpus validator — a human authors the
  depth and a physician signs it off. This is the explicit answer to "why not
  just import 290 unreviewed OpenEM conditions": because 290 of them are
  agent-compiled and unreviewed, and HALO's whole doctrine is fail-closed and
  physician-in-the-loop.

**Planned:** back-fill `pmid`/`openem_id` on the four shipped cards from their
OpenEM sources; add a provenance-coverage line to the readiness surface.

## Seam 2 — receipts as the attestation ledger  *(wired)*

HALO's CME evidence (`halo.edu.attest`) and the `receipts` project chain records
by the **identical** primitive: `sha256(canonical_json(payload) + prev_hash)`
with `json.dumps(payload, sort_keys=True, separators=(",", ":"))`. Because the
primitive is byte-identical (verified in `tests/test_edu_receipts_export.py`), a
HALO record ingests into the receipts `attestation` table with no transformation
of the payload — its own hash chain survives as auditable content inside the
receipts row.

- `halo.edu.receipts_export.to_receipt_envelope()` produces exactly the envelope
  `receipts.ledger.MerkleLog.append(payload, kind, target_kind, target_id)`
  expects; `target_id` is resolved ledger-side from `target_ref`.

**Planned:** a thin `receipts` ingest adapter (in the receipts repo, not here)
that reads a HALO CME JSONL and appends each record; a one-command demo showing
a HALO drill completion landing in the public ledger.

## Seam 3 — LostBench / SafeShift as the FN=0 eval  *(documented interface)*

HALO's cardinal metric is **unsafe-output false negatives = 0** (see
`CLAUDE.md`). Today that is guarded locally by fail-closed tests: dosing refuses
rather than inventing a number when patient context is missing
(`tests/test_edu_dosing.py`), and routing/grading fall back to deterministic
keyword matching on LLM uncertainty (`tests/test_edu_lookup.py`).

LostBench (CEIS safety grading) is the external harness that would turn that
local guard into a cited, N-and-method safety number over HALO's `halo.llm`
seams — the same corpus-driven safety lift it already reports for other
consumers. This is a **seam, not a claim**: no HALO metric asserts a LostBench
score until the eval is actually run and reported with N and method.

**Planned:** a small refusal/urgency goldset run through LostBench CEIS against
`halo.llm.structured`/`agent_loop`; publish pass^k with N and method.

## What is deliberately *not* here

- No bulk import of unreviewed OpenEM prose into the graded engine.
- No metric asserted without N and method.
- No runtime dependency on OpenEM, receipts, or LostBench.
- HALO remains a research demo, not a medical device; evidence records are for a
  CME/credentialing workflow, not accredited CME credit.
