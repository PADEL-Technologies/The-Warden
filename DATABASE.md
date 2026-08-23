# Database & migrations

PostgreSQL via `asyncpg`. Migrations are managed by
[goose](https://github.com/pressly/goose) — plain SQL files in `migrations/`
with `-- +goose Up` / `-- +goose Down` sections. Migration runs are recorded
in goose's `goose_db_version` table.

Local dev setup:

```bash
make db                # docker compose up -d: postgres:18 on localhost:5432 (warden/warden)
export DATABASE_URL=postgres://warden:warden@localhost:5432/warden
make migrate-up        # apply pending migrations
make migration NAME=add_left_at   # scaffold a new migration (goose create -s)
```

Install the goose binary once
([releases](https://github.com/pressly/goose/releases), or
`make goose-install` which pins `v3.24.3`). The app itself
never runs migrations — apply them as a separate step (or in CI) before
starting the bot.

Tests that need a real database set `WARDEN_TEST_DATABASE_URL` and are
skipped otherwise:

```bash
make db
goose -dir migrations postgres postgres://warden:warden@localhost:5432/warden up
WARDEN_TEST_DATABASE_URL=postgres://warden:warden@localhost:5432/warden uv run pytest
```

The schema has no foreign keys by design — the repository layer owns
referential integrity (e.g. `save(force=True)` deletes junction rows before
parent rows). Table relations:

```
roles.id      <- member_roles.role_id
members.id    <- member_roles.member_id
```
