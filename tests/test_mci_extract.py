"""Extraction seam tests — offline (Claude stubbed). Live eval: ``python -m halo.mci.demo``."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from halo import llm
from halo.mci.extract import EXTRACTION_SCHEMA, extract_observations


def _stub(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], stop: str = "end_turn") -> None:
    response = SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )

    def create(**_kwargs: Any) -> SimpleNamespace:
        return response

    fake = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(llm, "client", lambda: fake)


def _payload(**overrides: Any) -> dict[str, Any]:
    fields = EXTRACTION_SCHEMA["required"]
    base: dict[str, Any] = {f: {"value": None, "evidence": None} for f in fields}
    base.update(overrides)
    return base


def test_schema_is_strict() -> None:
    assert EXTRACTION_SCHEMA["additionalProperties"] is False
    for prop in EXTRACTION_SCHEMA["properties"].values():
        assert prop["additionalProperties"] is False


def test_extracts_values_and_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(
        monkeypatch,
        _payload(
            breathing={"value": True, "evidence": "breathing comfortably"},
            peripheral_pulse={"value": True, "evidence": "radial pulse strong"},
        ),
    )
    obs, evidence = extract_observations("note")
    assert obs.breathing is True
    assert obs.peripheral_pulse is True
    assert obs.obeys_commands is None
    assert evidence == {
        "breathing": "breathing comfortably",
        "peripheral_pulse": "radial pulse strong",
    }


def test_undocumented_fields_stay_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _payload())
    obs, evidence = extract_observations("note")
    assert obs == type(obs)()  # all-None observations
    assert evidence == {}


def test_refusal_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _payload(), stop="refusal")
    with pytest.raises(llm.LLMFailure):
        extract_observations("note")


def test_non_boolean_value_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _payload(breathing={"value": "yes", "evidence": "x"}))
    with pytest.raises(llm.LLMFailure):
        extract_observations("note")


def test_respiratory_rate_extracted_as_int(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _payload(respiratory_rate={"value": 38, "evidence": "RR 38"}))
    obs, evidence = extract_observations("note")
    assert obs.respiratory_rate == 38
    assert evidence["respiratory_rate"] == "RR 38"


def test_non_integer_rate_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, _payload(respiratory_rate={"value": "38", "evidence": "RR 38"}))
    with pytest.raises(llm.LLMFailure):
        extract_observations("note")


def test_boolean_rate_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    # bool is an int subclass in Python — must still be rejected for an integer field.
    _stub(monkeypatch, _payload(respiratory_rate={"value": True, "evidence": "x"}))
    with pytest.raises(llm.LLMFailure):
        extract_observations("note")


def test_missing_field_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    del payload["breathing"]
    _stub(monkeypatch, payload)
    with pytest.raises(llm.LLMFailure):
        extract_observations("note")
