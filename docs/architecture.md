# Architecture

One feature = one folder under `warden/features/`, laid out like `ping/`:

```
warden/features/greet/
    __init__.py                     wiring: setup(bot) builds the deps and adds the cog
    handlers/greet_handler.py       the Cog — Discord in, Discord out
    services/protocol.py            what the handler depends on
    services/greet_service.py       the implementation
```

The folder is discovered and loaded automatically by `feature_modules()` in
`warden/bot.py` — there is no registry to edit, so two people adding features never
conflict. The only requirement is `setup(bot)` in the feature's `__init__.py`:

```python
# warden/features/greet/__init__.py
from discord.ext import commands

from warden.features.greet.handlers.greet_handler import GreetHandlers
from warden.features.greet.services.greet_service import GreetService


async def setup(bot: commands.Bot) -> None:  # required, or the folder never loads
    await bot.add_cog(GreetHandlers(bot, GreetService()))
```

Handlers take services as constructor arguments, typed against the protocol — that
keeps the service testable without booting a bot.

Features with state add two more layers on the same idea: `repositories/`
(persistence, SQL lives here only) and `entities/` (plain data shapes passed between
layers). Services depend on repository protocols, never on a concrete database.
Registration adds a fifth, `views/`, for the Discord UI components.

A feature that owns a connection pool creates it in `setup(bot)` and closes it in
`cog_unload`. Because the cog class name is the cog key across the whole bot, each
feature subclasses its handler locally to keep that name unique:

```python
class RegistrationCog(RegistrationHandlers):
    async def cog_unload(self) -> None:
        await super().cog_unload()
        await pool.close()
```

Features that can be turned off return early from `setup(bot)` when their flag is
false — nothing is loaded, nothing connects.

## Tests

`warden/tests/` mirrors the source tree. Service tests use fake repositories; the
Postgres repository tests are skipped unless `WARDEN_TEST_DATABASE_URL` is set (see
[Database & migrations](database.md)).

## AI harness

This repo carries a graphify knowledge graph (`graphify-out/`) and Serena project
memories (`.serena/memories/`) for AI coding assistants. `.graphifyignore` keeps the
graph scoped to `warden/` source only — no docs/config noise.

- `make update-harness` — refresh the graph (code-only, no viz) and clear Serena's
  stale symbol cache. Safe to run anytime.
- `make install-hooks` — opt in to two git hooks:
  - `pre-commit` keeps `graphify-out/` out of code commits (unstages it when mixed
    with other paths).
  - `post-commit` does the same refresh automatically after each commit. It only runs
    when the commit touched `*.py`, and always lands the refreshed graph as its own
    separate commit (`chore(graphify): refresh graph`) on top of your code commit —
    all graphify changes, never mixed in.
