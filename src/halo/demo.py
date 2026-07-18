"""Smoke-test the Claude wiring (needs ANTHROPIC_API_KEY in the environment).

Usage: .venv/bin/python -m halo.demo "your prompt"
"""

from __future__ import annotations

import sys

from halo.llm import generate, model_name


def main() -> int:
    prompt = " ".join(sys.argv[1:]) or "Reply with exactly: HALO scaffold OK"
    print(f"[model: {model_name()}]", file=sys.stderr)
    print(generate(prompt, max_tokens=1000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
