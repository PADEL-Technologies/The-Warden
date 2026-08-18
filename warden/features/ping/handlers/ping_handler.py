from discord.ext import commands

from warden.features.ping.services.protocol import PingService


class PingHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot, service: PingService) -> None:
        self.bot = bot
        self.service = service

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(f"Pong! {self.service.format_latency(self.bot.latency)}")
