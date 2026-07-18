VENV := .venv
PY := $(VENV)/bin/python

.PHONY: setup test lint fmt typecheck check serve

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -e ".[dev]"
	@echo "OK: $$($(PY) --version) ready. Run 'make check'."

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

fmt:
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

typecheck:
	$(PY) -m mypy

check: lint test

serve:
	$(PY) -m uvicorn halo.app:app --reload --port 8000
