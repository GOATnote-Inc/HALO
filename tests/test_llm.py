"""Unit tests for the Claude seam — all offline (client is stubbed)."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from halo import llm


def _resp(stop_reason: str, text: str | None = None) -> SimpleNamespace:
    blocks = [SimpleNamespace(type="text", text=text)] if text is not None else []
    return SimpleNamespace(stop_reason=stop_reason, content=blocks)


def _patch_client(monkeypatch: pytest.MonkeyPatch, response: SimpleNamespace) -> None:
    def create(**_kwargs: Any) -> SimpleNamespace:
        return response

    fake = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(llm, "client", lambda: fake)


def test_model_name_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HALO_MODEL", raising=False)
    assert llm.model_name() == "claude-opus-4-8"


def test_model_name_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HALO_MODEL", "claude-sonnet-5")
    assert llm.model_name() == "claude-sonnet-5"


def test_generate_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _resp("end_turn", "hello"))
    assert llm.generate("p") == "hello"


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_generate_fails_closed(monkeypatch: pytest.MonkeyPatch, reason: str) -> None:
    _patch_client(monkeypatch, _resp(reason, "partial"))
    with pytest.raises(llm.LLMFailure):
        llm.generate("p")


def test_structured_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _resp("end_turn", json.dumps({"ok": True})))
    assert llm.structured("p", {"type": "object"}) == {"ok": True}


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_structured_fails_closed(monkeypatch: pytest.MonkeyPatch, reason: str) -> None:
    _patch_client(monkeypatch, _resp(reason, "{}"))
    with pytest.raises(llm.LLMFailure):
        llm.structured("p", {"type": "object"})


def test_structured_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _resp("end_turn", json.dumps([1, 2])))
    with pytest.raises(llm.LLMFailure):
        llm.structured("p", {"type": "object"})
