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
	@goose -dir migrations create -s "$(NAME)" $(ARGS)
	@ls -t migrations | head -1

DB_URL ?= $${DATABASE_URL:?set DATABASE_URL, e.g. from make db}
migrate-up:
	goose -dir migrations postgres "$(DB_URL)" up

migrate-down:
	goose -dir migrations postgres "$(DB_URL)" down

migrate-status:
	goose -dir migrations postgres "$(DB_URL)" status

db:
	docker compose up -d

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

.PHONY: install run lint format check test migration migrate-up migrate-down migrate-status db update-harness install-hooks docker-build docker-run
