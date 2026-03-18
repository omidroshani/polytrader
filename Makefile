.PHONY: lint format typecheck check test

lint:
	ruff check . --fix

format:
	ruff format .

typecheck:
	mypy .

check: typecheck lint format

test:
	pytest
