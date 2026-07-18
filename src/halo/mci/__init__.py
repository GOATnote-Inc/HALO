"""HALO module 1 — Mass Casualty Incident (MCI) triage support.

Architecture (safety-first split):

- ``extract``  — Claude turns a free-text field/EMS note into structured
  observations. The model **never** assigns a triage category.
- ``triage``   — a deterministic SALT algorithm assigns the category from the
  structured observations. Missing critical data fails closed to
  ``UNABLE_TO_TRIAGE`` (immediate in-person reassessment), never a guess.
- ``EXPECTANT`` is never assigned autonomously — it requires an explicit
  human resource decision (``likely_survivable=False``).

Synthetic data only. Research demo, not a medical device.
"""

from halo.mci.models import Observations, TriageCategory, TriageResult
from halo.mci.triage import salt_triage

__all__ = ["Observations", "TriageCategory", "TriageResult", "salt_triage"]
