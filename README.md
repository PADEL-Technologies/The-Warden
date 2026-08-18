# warden

Discord bot.

## Run

```bash
uv sync
DISCORD_TOKEN=... uv run main.py
```

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
that keeps the service testable without booting a bot.

## Checks

```bash
uv run ruff check . && uv run ruff format . && uv run pytest
```

Same three commands run in CI on every push and PR.
