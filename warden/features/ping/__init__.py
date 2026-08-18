"""Ping feature. Wiring only — handlers and services live in their own folders."""

from discord.ext import commands

from warden.features.ping.handlers.ping_handler import PingHandlers
from warden.features.ping.services.ping_service import PingService


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PingHandlers(bot, PingService()))
