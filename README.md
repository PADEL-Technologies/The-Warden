# warden

Discord bot.

## Run

```bash
uv sync
DISCORD_TOKEN=... DATABASE_URL=postgres://... uv run main.py
```

Or via `make install` / `DISCORD_TOKEN=... DATABASE_URL=postgres://... make run`
(same commands, see `Makefile`).

## Configuration

All settings come from environment variables (or `.env` for `make docker-run`):

| Variable            | Default           | Purpose                              |
| ------------------- | ----------------- | ------------------------------------ |
| `DISCORD_TOKEN`     | — (required)      | Bot token                            |
| `DATABASE_URL`      | — (required)      | Postgres DSN, e.g. `postgres://user:pass@host:5432/db` |
| `ONBOARDING_ENABLED`| `true`            | Load the onboarding feature at all   |

The bot needs the **Server Members** privileged intent — enable it in the
Discord Developer Portal, it is already requested in `warden/bot.py`.

## Adding a feature

One feature = one folder under `warden/features/`, laid out like `ping/`:

```
warden/features/greet/
    __init__.py                     wiring: setup(bot) builds the deps and adds the cog
    handlers/greet_handler.py       the Cog — Discord in, Discord out
    services/protocol.py            what the handler depends on
    services/greet_service.py       the implementation
```

The folder is discovered and loaded automatically — there is no registry to
edit, so two people adding features never conflict. The only requirement is
`setup(bot)` in the feature's `__init__.py`:

```python
# warden/features/greet/__init__.py
from discord.ext import commands

from warden.features.greet.handlers.greet_handler import GreetHandlers
from warden.features.greet.services.greet_service import GreetService


async def setup(bot: commands.Bot) -> None:  # required, or the folder never loads
    await bot.add_cog(GreetHandlers(bot, GreetService()))
```

Handlers take services as constructor arguments, typed against the protocol —
that keeps the service testable without booting a bot. Onboarding adds two
more layers on the same idea: `repositories/` (persistence, SQL lives here
only) and `entities/` (plain data shapes passed between layers). Services
depend on repository protocols, never on a concrete database.

## Onboarding feature

Snapshots every member and their roles the first time the bot joins a guild
(point-in-time baseline — it is not kept in sync afterwards):

- **Bot joins a new guild** → auto-snapshot, one database transaction.
- **Bot is kicked and re-invited** → existing snapshot is kept, no re-snapshot.
- **`!onboard existing`** (requires *Manage Server*) → snapshot manually, e.g.
  if the feature was disabled when the bot joined.
- **`!onboard existing --force`** → replace the guild's snapshot.

`@everyone` is never stored (everyone has it, it carries no information).

## Database & migrations

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
`go install github.com/pressly/goose/v3/cmd/goose@latest`). The app itself
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

## Checks

```bash
uv run ruff check . && uv run ruff format . && uv run pytest
```

Or `make check`. Same three commands run in CI on every push and PR.

## Docker

```bash
make docker-build
make docker-run   # reads DISCORD_TOKEN from .env
```

Multi-stage build (`Dockerfile`): dependencies are installed in a `builder`
stage, the runtime stage copies only the built venv, `warden/` and `main.py`
— no `uv`, no build tools, no audio/voice libs in the final image. Runs
headless as a non-root user, timezone pinned to `Asia/Jakarta`. The image
does not carry `migrations/` — migrations are applied by a separate process
before the bot starts.

## AI harness

This repo carries a graphify knowledge graph (`graphify-out/`) and Serena
project memories (`.serena/memories/`) for AI coding assistants. `.graphifyignore`
keeps the graph scoped to `warden/` source only — no docs/config noise.

- `make update-harness` — refresh the graph (code-only, no viz) and clear
  Serena's stale symbol cache. Safe to run anytime.
- `make install-hooks` — opt in to a pre-commit hook (`.github/hooks/pre-commit`)
  that does the same refresh automatically before each commit.
