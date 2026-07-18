"""Single seam for every Claude API call.

All product code calls Claude through this module so the model choice, thinking
config, and failure policy live in one place. Model knob: ``HALO_MODEL``
(default ``claude-opus-4-8``).

Failure policy is fail-closed: a refusal or truncated response raises
``LLMFailure`` instead of returning output that can't be trusted.
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-opus-4-8"


class LLMFailure(RuntimeError):
    """Raised when a response cannot be trusted (refusal, truncation, bad JSON)."""


def model_name() -> str:
    return os.environ.get("HALO_MODEL", DEFAULT_MODEL)


def client() -> anthropic.Anthropic:
    """Reads ANTHROPIC_API_KEY (or an `ant auth login` profile) from the environment."""
    return anthropic.Anthropic()


def _create(prompt: str, system: str | None, max_tokens: int, **extra: Any) -> Any:
    kwargs: dict[str, Any] = {
        "model": model_name(),
        "max_tokens": max_tokens,
        "thinking": {"type": "adaptive"},
        "messages": [{"role": "user", "content": prompt}],
        **extra,
    }
    if system is not None:
        kwargs["system"] = system
    return client().messages.create(**kwargs)


def _text(response: Any) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def generate(prompt: str, *, system: str | None = None, max_tokens: int = 16000) -> str:
    """Freeform text completion."""
    response = _create(prompt, system, max_tokens)
    if response.stop_reason in ("refusal", "max_tokens"):
        raise LLMFailure(f"fail-closed: stop_reason={response.stop_reason}")
    return _text(response)


def agent_loop(
    prompt: str,
    tools: list[Any],
    *,
    system: str | None = None,
    max_tokens: int = 16000,
    max_iterations: int = 8,
) -> tuple[str, list[dict[str, Any]]]:
    """Bounded agentic loop via the SDK tool runner.

    Returns ``(final_text, trail)`` where ``trail`` records every tool call the
    model made (name + input) for transparency. Fail-closed on refusal or
    truncation of the final turn.
    """
    kwargs: dict[str, Any] = {
        "model": model_name(),
        "max_tokens": max_tokens,
        "thinking": {"type": "adaptive"},
        "tools": tools,
        "max_iterations": max_iterations,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        kwargs["system"] = system
    runner = client().beta.messages.tool_runner(**kwargs)
    trail: list[dict[str, Any]] = []
    last = None
    for message in runner:
        last = message
        for block in message.content:
            if block.type == "tool_use":
                trail.append({"tool": block.name, "input": block.input})
    if last is None:
        raise LLMFailure("fail-closed: agent loop produced no message")
    if last.stop_reason in ("refusal", "max_tokens", "pause_turn"):
        raise LLMFailure(f"fail-closed: stop_reason={last.stop_reason}")
    return _text(last), trail


def structured(
    prompt: str,
    schema: dict[str, Any],
    *,
    system: str | None = None,
    max_tokens: int = 16000,
) -> dict[str, Any]:
    """JSON completion constrained to ``schema`` via native structured outputs.

    The schema is not guaranteed on refusal or truncation, so those raise.
    """
    response = _create(
        prompt,
        system,
        max_tokens,
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise LLMFailure(f"fail-closed: stop_reason={response.stop_reason}")
    data = json.loads(_text(response))
    if not isinstance(data, dict):
        raise LLMFailure(f"expected JSON object, got {type(data).__name__}")
    return data
