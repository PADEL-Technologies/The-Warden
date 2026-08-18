import asyncio
import contextlib
import pkgutil
import signal

import discord
from discord.ext import commands

import warden.features


def feature_modules() -> list[str]:
    """Every feature package under warden/features/. Adding one = adding a folder."""
    return [
        f"warden.features.{m.name}"
        for m in pkgutil.iter_modules(warden.features.__path__)
        if m.ispkg and not m.name.startswith("_")
    ]


class Warden(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self) -> None:
        for module in feature_modules():
            await self.load_extension(module)

        await self.tree.sync()

        # ponytail: SIGINT is already handled by Bot.run(); SIGTERM is what
        # docker/k8s send and discord.py does not install a handler for it.
        with contextlib.suppress(NotImplementedError):  # Windows
            asyncio.get_running_loop().add_signal_handler(
                signal.SIGTERM, lambda: asyncio.create_task(self.close())
            )
