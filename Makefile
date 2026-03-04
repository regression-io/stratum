.PHONY: setup test lint

setup:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check src tests
