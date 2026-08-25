.PHONY: help setup check format lint type test test-cov pack-validate eval-mini eval-mini-json clean

help:
	@echo "Gatehouse P1 targets"
	@echo "  setup         create venv + install pinned deps"
	@echo "  check         format-check + lint + type + fast tests (CI gate)"
	@echo "  format        apply ruff formatting and import sorting"
	@echo "  lint          ruff check"
	@echo "  type          mypy strict"
	@echo "  test          pytest fast suite"
	@echo "  test-cov      pytest with coverage gate (85 pct)"
	@echo "  pack-validate validate every country pack artifact"
	@echo "  eval-mini     run the offline 30-case mini evaluation"
	@echo "  eval-mini-json write docs/eval-results/mini-metrics.json"

setup:
	py -3.12 -m venv .venv
	.venv/Scripts/python -m pip install --upgrade pip
	.venv/Scripts/python -m pip install -r requirements-lock.txt
	.venv/Scripts/python -m pip install -e . --no-deps

PY := .venv/Scripts/python

format:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

lint:
	$(PY) -m ruff format --check .
	$(PY) -m ruff check .

type:
	$(PY) -m mypy src tests

test:
	$(PY) -m pytest

test-cov:
	$(PY) -m pytest --cov=src/gatehouse --cov-report=term-missing --cov-fail-under=85

check: lint type test

pack-validate:
	$(PY) scripts/validate_packs.py

eval-mini:
	$(PY) -m gatehouse.evaluation.run_mini --pack packs/in/pack.yaml

eval-mini-json:
	$(PY) -m gatehouse.evaluation.run_mini --pack packs/in/pack.yaml --json docs/eval-results/mini-metrics.json

clean:
	$(PY) -B -c "import pathlib, shutil; \
[shutil.rmtree(p) for p in [pathlib.Path('.pytest_cache'), pathlib.Path('.mypy_cache'), pathlib.Path('.ruff_cache')] if p.exists()]; \
print('caches cleared')"
