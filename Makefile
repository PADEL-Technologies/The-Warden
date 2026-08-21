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

NAME ?=
migration:
	@if [ -z "$(NAME)" ]; then echo "Usage: make migration NAME=add_left_at"; exit 1; fi
	@touch "migrations/$$(uv run python -c "from datetime import UTC, datetime; print(datetime.now(UTC).strftime('%Y%m%d%H%M%S'))")_$(NAME).sql"
	@ls -t migrations | head -1

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

.PHONY: install run lint format check test migration update-harness install-hooks docker-build docker-run
