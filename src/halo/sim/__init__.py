"""HALO simulation lab — deterministic 2D patient simulations for readiness training.

Cases are data (JSON state machines); the engine is client-side and dumb on
purpose: every branch, vital trajectory, and outcome is authored, reviewable
content — no model in the loop during a simulation. Same doctrine as the rest
of HALO: the clinical logic must be inspectable.
"""

from halo.sim.cases import list_cases, load_case, validate_case

__all__ = ["list_cases", "load_case", "validate_case"]
