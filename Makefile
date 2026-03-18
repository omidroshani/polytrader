.PHONY: lint format typecheck check test audit security

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
