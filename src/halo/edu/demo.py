"""Readiness & CME demo. Offline by default — no API key needed for any of it.

``python -m halo.edu.demo``                     full offline showcase (corpus, lookup,
                                                dosing, FHIR round-trip, scripted drill,
                                                attestation ledger, card render)
``python -m halo.edu.demo find "query"``        free text -> ranked cards (--llm to route
                                                via Claude, fail-closed)
``python -m halo.edu.demo dose ID --weight 22 --age 6``   computed doses for one module
``python -m halo.edu.demo drill ID --interactive``        timed drill at the terminal;
                                                appends a CME evidence record
``python -m halo.edu.demo cards``               render HTML cards to out/edu/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from halo.edu.attest import append_record, verify_chain
from halo.edu.corpus import get_module, load_corpus, module_version
from halo.edu.dosing import dose_all
from halo.edu.drill import run_drill
from halo.edu.fhir import draft_bundle, patient_context_from_bundle
from halo.edu.lookup import resolve, route_with_claude
from halo.edu.models import DoseStatus, PatientContext
from halo.edu.render import write_cards

OUT_DIR = Path("out/edu")
LEDGER = OUT_DIR / "cme_ledger.jsonl"

SYNTHETIC_CHILD_BUNDLE = {
    "resourceType": "Bundle",
    "type": "collection",
    "synthetic": True,
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "synthetic-child",
                "gender": "female",
                "birthDate": "2020-07-18",
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7"}]},
                "valueQuantity": {"value": 22, "unit": "kg"},
            }
        },
    ],
}

OP_SCRIPTED_ANSWERS = [
    "PPE on everyone, strip and decon outside before they come in",
    "atropine 2 mg IV, double it every 5 minutes until secretions dry",
    "2-PAM 1-2 g IV slowly over 30 minutes, with the atropine",
    "midazolam 10 mg IM",
    "rocuronium — avoid succinylcholine, it lasts hours here",
    "three duodotes, lateral thigh",
    "declare an MCI and call poison control",
]


def _rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _print_doses(module_id: str, ctx: PatientContext) -> None:
    module = get_module(module_id)
    for result in dose_all(module, ctx):
        marker = {"computed": "=", "reference": "~", "refused": "X"}[result.status.value]
        line = result.text if result.status is not DoseStatus.REFUSED else result.reason
        print(f"  [{marker}] {result.med}: {line}")
        for warning in result.warnings:
            print(f"       ! {warning}")


def cmd_showcase() -> int:
    _rule("CORPUS — curated, cited, content-addressed")
    for m in load_corpus():
        drill_n = len(m.drill.decision_points) if m.drill else 0
        print(
            f"  {m.id:22s} {len(m.steps):2d} steps  {len(m.meds)} meds  "
            f"{drill_n} drill pts  [{m.review.status.value}]  {module_version(m.id)}"
        )

    _rule("LOOKUP — free text to the right card, offline")
    for query in (
        "chemical explosion, starting 2pam",
        "breech is crowning and no OB is here",
        "eye is rock hard and proptotic after assault",
    ):
        matches = resolve(query)
        top = matches[0]
        print(f"  {query!r}\n    -> {top.module.id} (score {top.score:g}; {top.why[0]})")

    _rule("DOSING — 22 kg six-year-old, organophosphate module")
    _print_doses("organophosphate", PatientContext(weight_kg=22, age_years=6))
    print("\n  Same module, NO weight/age (fail-closed refusals):")
    _print_doses("organophosphate", PatientContext())

    _rule("EHR SEAM — synthetic FHIR bundle -> context -> doses -> draft docs")
    ctx = patient_context_from_bundle(SYNTHETIC_CHILD_BUNDLE)
    print(f"  extracted: weight={ctx.weight_kg} kg, age={ctx.age_years} y, sex={ctx.sex}")
    module = get_module("organophosphate")
    computed = [d for d in dose_all(module, ctx) if d.status is DoseStatus.COMPUTED]
    bundle = draft_bundle(module, computed, when_iso="2026-07-18T12:00:00Z")
    types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    print(f"  draft outbound bundle: {types} (all tagged synthetic+draft, preliminary)")

    _rule("DRILL — scripted run, deterministic grading")
    result = run_drill(module, OP_SCRIPTED_ANSWERS, trainee="showcase", elapsed_s=222.0)
    for grade in result.grades:
        print(f"  [{'HIT ' if grade.hit else 'MISS'}] {grade.prompt}")
    print(f"  score {result.score:.0%}  critical misses: {len(result.critical_misses)}")
    print(f"  PASSED: {result.passed}  ({result.content_version})")

    missed = ["straight to resus bay 1", *OP_SCRIPTED_ANSWERS[1:]]
    failed = run_drill(module, missed)
    print(
        f"\n  Same run but skipping decon: score {failed.score:.0%} >= threshold, "
        f"yet PASSED: {failed.passed} — critical miss gate ({failed.critical_misses[0][:40]}...)"
    )

    _rule("CME LEDGER — hash-chained evidence records")
    record = append_record(LEDGER, result, trainee="showcase")
    print(f"  appended {record['module_id']} for '{record['trainee']}'")
    print(f"  chain verifies: {verify_chain(LEDGER)} record(s) in {LEDGER}")

    _rule("CARDS — printable 2D reference (open in a browser)")
    for path in write_cards(OUT_DIR):
        print(f"  {path}")
    print("\nAll offline. Optional live paths: find --llm (Claude routing), drill --llm.")
    return 0


def cmd_find(query: str, use_llm: bool) -> int:
    matches = resolve(query)
    if use_llm:
        routed = route_with_claude(query)
        print(f"claude route: {routed or 'none (fail-closed)'}")
    if not matches:
        print("no match — available cards:")
        for m in load_corpus():
            print(f"  {m.id:22s} {m.one_liner}")
        return 1
    for match in matches:
        print(f"{match.score:5.1f}  {match.module.id:22s} {match.module.one_liner}")
        print(f"       why: {'; '.join(match.why)}")
    return 0


def cmd_brief(incident: str) -> int:
    from halo.edu.brief import readiness_brief

    brief = readiness_brief(incident, ledger_path=LEDGER)
    _rule(f"STAFF READINESS — {incident}")
    print(f"  profiles: {', '.join(brief.profiles) or 'none'}")
    print("\n  Set up before the first arrival:")
    for line in brief.prep_now:
        print(f"    [ ] {line}")
    print("\n  Cards this incident may need:")
    stats = {s.module_id: s for s in brief.drill_stats}
    for card in brief.cards:
        stat = stats.get(card.module_id)
        drilled = (
            f"{stat.passes}/{stat.attempts} passed, last {stat.last_when}"
            if stat and stat.attempts
            else "never drilled"
        )
        print(f"    {card.module_id:22s} {drilled}")
        print(f"      why: {card.why}")
    print("\n  Not covered by a HALO card:")
    for gap in brief.gaps:
        print(f"    - {gap}")
    print(f"\n  {brief.ledger_note}")
    return 0


def cmd_dose(module_id: str, weight: float | None, age: float | None) -> int:
    _print_doses(module_id, PatientContext(weight_kg=weight, age_years=age))
    return 0


def cmd_drill(module_id: str, interactive: bool, trainee: str, use_llm: bool) -> int:
    module = get_module(module_id)
    drill = module.drill
    if drill is None:
        print(f"module '{module_id}' has no drill")
        return 1
    if not interactive:
        print("(scripted answers only exist for organophosphate; use --interactive)")
        if module_id != "organophosphate":
            return 1
        result = run_drill(module, OP_SCRIPTED_ANSWERS, trainee=trainee)
    else:
        if not sys.stdin.isatty():
            print("--interactive needs a TTY")
            return 1
        _rule(module.name)
        print(f"\n{drill.stem}\n")
        answers = []
        start = time.monotonic()
        for i, point in enumerate(drill.decision_points, 1):
            print(f"[{i}/{len(drill.decision_points)}] {point.prompt}")
            answers.append(input("> "))
        elapsed = round(time.monotonic() - start, 1)
        result = run_drill(
            module, answers, trainee=trainee, elapsed_s=elapsed, llm_adjudicate=use_llm
        )
        print()
        for grade, point in zip(result.grades, drill.decision_points, strict=True):
            print(f"  [{'HIT ' if grade.hit else 'MISS'}] {point.prompt}")
            if not grade.hit:
                print(f"         ideal: {point.ideal}")
        print(f"\n  time: {elapsed}s")
    print(f"  score {result.score:.0%}, critical misses {len(result.critical_misses)}, ")
    print(f"  PASSED: {result.passed}")
    if interactive:
        record = append_record(LEDGER, result, trainee=trainee)
        print(f"  CME evidence appended to {LEDGER} (record {record['record_hash'][:12]}...)")
    else:
        # Red-team fix: a scripted self-pass must never mint attestation evidence.
        print("  scripted run — no CME record written (interactive runs only)")
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="halo.edu.demo", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")
    p_find = sub.add_parser("find", help="free text -> ranked cards")
    p_find.add_argument("query")
    p_find.add_argument("--llm", action="store_true", help="also route via Claude (needs key)")
    p_dose = sub.add_parser("dose", help="computed doses for one module")
    p_dose.add_argument("module_id")
    p_dose.add_argument("--weight", type=float, default=None, help="kg")
    p_dose.add_argument("--age", type=float, default=None, help="years")
    p_drill = sub.add_parser("drill", help="run a drill; appends a CME record")
    p_drill.add_argument("module_id")
    p_drill.add_argument("--interactive", action="store_true")
    p_drill.add_argument("--trainee", default="anonymous")
    p_drill.add_argument("--llm", action="store_true", help="Claude adjudication of misses")
    p_brief = sub.add_parser("brief", help="incident text -> staff readiness brief")
    p_brief.add_argument("incident")
    sub.add_parser("cards", help="render HTML cards to out/edu/")
    sub.add_parser("json", help="dump corpus summaries as JSON")
    args = parser.parse_args(argv)

    if args.cmd == "find":
        return cmd_find(args.query, args.llm)
    if args.cmd == "dose":
        return cmd_dose(args.module_id, args.weight, args.age)
    if args.cmd == "drill":
        return cmd_drill(args.module_id, args.interactive, args.trainee, args.llm)
    if args.cmd == "brief":
        return cmd_brief(args.incident)
    if args.cmd == "cards":
        for path in write_cards(OUT_DIR):
            print(path)
        return 0
    if args.cmd == "json":
        print(
            json.dumps(
                [asdict(m) for m in load_corpus()],
                indent=2,
                default=str,
            )
        )
        return 0
    return cmd_showcase()


if __name__ == "__main__":
    sys.exit(main())
