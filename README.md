# warden

Discord bot.

## Run

```bash
uv sync
DISCORD_TOKEN=... DATABASE_URL=postgres://... uv run main.py
```

Or via `make install` / `DISCORD_TOKEN=... DATABASE_URL=postgres://... make run`
(same commands, see `Makefile`).

## Checks

```bash
make check   # ruff check + ruff format --check + pytest
```

Same three commands run in CI on every push and PR.

## Documentation

| Doc | What's in it |
| --- | --- |
| [`CONFIGURATION.md`](CONFIGURATION.md) | Environment variables, privileged intents |
| [`ADDING-A-FEATURE.md`](ADDING-A-FEATURE.md) | Feature folder layout and wiring |
| [`ONBOARDING.md`](ONBOARDING.md) | Member/role snapshot feature |
| [`REGISTRATION.md`](REGISTRATION.md) | Manual verification feature — see also [`docs/registration-design.md`](docs/registration-design.md) |
| [`DATABASE.md`](DATABASE.md) | Postgres, goose migrations, schema notes |
| [`DOCKER.md`](DOCKER.md) | Image build and run |
| [`AI-HARNESS.md`](AI-HARNESS.md) | graphify + Serena setup for AI assistants |
