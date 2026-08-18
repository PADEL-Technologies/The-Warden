install:
	uv sync

run:
	uv run main.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

test:
	uv run pytest

update-harness:
	uv tool run --from graphifyy graphify extract . --code-only
	find graphify-out -maxdepth 1 -type d -regextype posix-extended -regex '.*/[0-9]{4}-[0-9]{2}-[0-9]{2}' -exec rm -rf {} +
	uv run python -c "import shutil; shutil.rmtree('.serena/cache', ignore_errors=True)"

install-hooks:
	git config core.hooksPath .github/hooks

docker-build:
	docker build -t warden .

docker-run:
	docker run --rm --env-file .env warden

.PHONY: install run lint format check test update-harness install-hooks docker-build docker-run
