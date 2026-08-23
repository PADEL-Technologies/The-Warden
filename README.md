# warden

Discord bot for a campus community. Two features are live:

- **onboarding** — snapshots the member roster and their roles the first time the
  bot joins a guild.
- **registration** — manual member verification: form in a private thread, review
  card for verifiers, roles and nickname on approval.

Plus **ping**, the reference feature that shows the folder layout.

## Run

```bash
uv sync
DISCORD_TOKEN=... DATABASE_URL=postgres://... uv run main.py
```

Or via `make install` / `DISCORD_TOKEN=... DATABASE_URL=postgres://... make run`
(same commands, see `Makefile`).

The bot needs the **Server Members** privileged intent — enable it in the Discord
Developer Portal, it is already requested in `warden/bot.py`.

The app never runs migrations. Apply them as a separate step before starting the
bot — see [Database & migrations](docs/database.md).

## Checks

```bash
make check   # ruff check + ruff format --check + pytest
```

The same three commands run in CI on every push and PR.

## Docker

```bash
make docker-build
make docker-run   # reads DISCORD_TOKEN and friends from .env
```

Multi-stage build (`Dockerfile`): dependencies are installed in a `builder` stage,
the runtime stage copies only the built venv, `warden/` and `main.py` — no `uv`, no
build tools in the final image. Runs headless as a non-root user, timezone pinned
to `Asia/Jakarta`. The image does not carry `migrations/`.

## Docs

- [Configuration](docs/configuration.md) — environment variables, required server permissions
- [Database & migrations](docs/database.md) — Postgres, goose, schema
- [Architecture](docs/architecture.md) — feature layout, adding a feature, AI harness
- [Onboarding feature](docs/onboarding.md)
- [Registration feature](docs/registration.md)

User-facing bot messages are in Indonesian; code, comments in new code, and docs
are in English.
