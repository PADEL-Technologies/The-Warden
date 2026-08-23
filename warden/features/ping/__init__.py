"""Ping feature. Wiring only — handlers and services live in their own folders."""

from typing import TYPE_CHECKING

from warden.features.ping.handlers.ping_handler import PingHandlers
from warden.features.ping.services.ping_service import PingService

if TYPE_CHECKING:
    from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PingHandlers(bot, PingService()))
