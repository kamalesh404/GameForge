.PHONY: install install-dev lint format typecheck test coverage build clean docker-build docker-up

PYTHON ?= python

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m flake8 src tests --max-line-length=100

format:
	$(PYTHON) -m black src tests
	$(PYTHON) -m isort src tests

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

coverage:
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing

build:
	$(PYTHON) -m build

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache htmlcov

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
