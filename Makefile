.PHONY: lint format typecheck check test audit security docs docs-serve

lint:
	ruff check . --fix

format:
	ruff format .

typecheck:
	mypy .

check: typecheck lint format

test:
	pytest

audit:
	pip-audit

security:
	bandit -r polytrader/

docs:
	mkdocs build

docs-serve:
	mkdocs serve
