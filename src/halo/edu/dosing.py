"""Deterministic dose arithmetic from patient context. No LLM anywhere in this path.

Fail-closed contract (the point of this module):

- Weight-based med, no weight            -> REFUSED, reason names the missing datum
- Adult-vs-peds unresolvable (no age or
  weight)                                -> REFUSED — a population is never assumed
- Population resolves to peds but the
  med has no pediatric spec              -> REFUSED — adult numbers are never scaled down ad hoc
- Curated text with no computable fields -> REFERENCE (verbatim curated line, no arithmetic)
- Computed doses respect ``max_amount`` (warning when capped) and ``round_to``
  (half-up — never banker's rounding for a drug dose)

A documented allergy that appears in the med's name or cautions is surfaced as
a warning, never silently dropped and never an automatic block — that call
belongs to the clinician.
"""

from __future__ import annotations

import math

from halo.edu.models import DoseResult, DoseSpec, DoseStatus, Med, PatientContext, ProcedureModule

PEDS_AGE_CUTOFF_YEARS = 14.0
PEDS_WEIGHT_CUTOFF_KG = 40.0


def _round_half_up(value: float, step: float) -> float:
    return round(math.floor(value / step + 0.5) * step, 10)


def _fmt(value: float) -> str:
    return f"{value:g}"


def _pick_population(
    med: Med, ctx: PatientContext
) -> tuple[DoseSpec, str, tuple[str, ...]] | DoseResult:
    """Choose adult vs peds spec, or return a REFUSED result if that's not safe."""
    warnings: tuple[str, ...] = ()
    if ctx.age_years is not None:
        population = "peds" if ctx.age_years < PEDS_AGE_CUTOFF_YEARS else "adult"
    elif ctx.weight_kg is not None:
        population = "peds" if ctx.weight_kg < PEDS_WEIGHT_CUTOFF_KG else "adult"
        warnings = (
            f"age unknown — {population} spec chosen by weight "
            f"({_fmt(ctx.weight_kg)} kg vs {_fmt(PEDS_WEIGHT_CUTOFF_KG)} kg cutoff); verify",
        )
    else:
        return DoseResult(
            status=DoseStatus.REFUSED,
            med=med.name,
            route=med.route,
            text=_spec_texts(med),
            reason="age or weight required to select adult vs pediatric dosing",
        )
    spec = med.peds if population == "peds" else med.adult
    if spec is None:
        return DoseResult(
            status=DoseStatus.REFUSED,
            med=med.name,
            route=med.route,
            text=_spec_texts(med),
            reason=f"no {'pediatric' if population == 'peds' else 'adult'} dosing spec in this "
            "module — verify with pharmacy/poison control",
        )
    return spec, population, warnings


def _spec_texts(med: Med) -> str:
    parts = []
    if med.adult is not None:
        parts.append(f"adult: {med.adult.text}")
    if med.peds is not None:
        parts.append(f"peds: {med.peds.text}")
    return "; ".join(parts)


def _allergy_warnings(med: Med, ctx: PatientContext) -> tuple[str, ...]:
    haystack = " ".join((med.name, *med.cautions)).lower()
    return tuple(
        f"documented allergy '{allergy}' — verify against {med.name} before giving"
        for allergy in ctx.allergies
        if allergy.lower() in haystack
    )


def dose(med: Med, ctx: PatientContext) -> DoseResult:
    """Dose one med for one patient. Total function — every input maps to a result."""
    picked = _pick_population(med, ctx)
    if isinstance(picked, DoseResult):
        return picked
    spec, population, warnings = picked
    warnings += _allergy_warnings(med, ctx)

    if spec.per_kg is not None:
        if ctx.weight_kg is None:
            return DoseResult(
                status=DoseStatus.REFUSED,
                med=med.name,
                route=med.route,
                text=spec.text,
                reason=f"weight required: {population} dose is {_fmt(spec.per_kg)} {spec.unit}/kg",
                warnings=warnings,
            )
        amount = spec.per_kg * ctx.weight_kg
        if spec.max_amount is not None and amount > spec.max_amount:
            amount = spec.max_amount
            warnings += (f"capped at max {_fmt(spec.max_amount)} {spec.unit}",)
        if spec.round_to is not None:
            amount = _round_half_up(amount, spec.round_to)
        return DoseResult(
            status=DoseStatus.COMPUTED,
            med=med.name,
            route=med.route,
            text=f"{_fmt(amount)} {spec.unit} {med.route} "
            f"({_fmt(spec.per_kg)} {spec.unit}/kg x {_fmt(ctx.weight_kg)} kg) — {spec.text}",
            warnings=warnings,
        )

    if spec.fixed is not None:
        return DoseResult(
            status=DoseStatus.COMPUTED,
            med=med.name,
            route=med.route,
            text=f"{_fmt(spec.fixed)} {spec.unit} {med.route} — {spec.text}",
            warnings=warnings,
        )

    return DoseResult(
        status=DoseStatus.REFERENCE,
        med=med.name,
        route=med.route,
        text=f"{spec.text} ({med.route})",
        warnings=warnings,
    )


def dose_all(module: ProcedureModule, ctx: PatientContext) -> tuple[DoseResult, ...]:
    """Dose every med in a module for one patient, in content order."""
    return tuple(dose(med, ctx) for med in module.meds)
