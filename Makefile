.PHONY: install check lint format test migrate run

install:
	uv sync --all-groups

check: lint format test

lint:
	uv run ruff check .
	uv run mypy grantradar apps

format:
	uv run ruff format --check .

test:
	uv run pytest

migrate:
	uv run python manage.py migrate

run:
	uv run python manage.py runserver
