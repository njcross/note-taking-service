.PHONY: install run test coverage lint format

install:
	python -m pip install -e ".[dev]"

run:
	uvicorn app.main:app --reload

test:
	python -m pytest

coverage:
	python -m pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format .
