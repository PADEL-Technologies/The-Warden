import logging
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from warden.features.ping.services.protocol import PingService

log = logging.getLogger(__name__)


class PingHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot, service: PingService) -> None:
        self.bot = bot
        self.service = service

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context) -> None:
        log.debug(
            "ping: dipanggil",
            extra={"guild_id": ctx.guild.id if ctx.guild else None},
        )
        await ctx.send(f"Pong! {self.service.format_latency(self.bot.latency)}")
