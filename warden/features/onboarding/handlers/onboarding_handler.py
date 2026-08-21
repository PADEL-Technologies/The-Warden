import logging

import discord
from discord.ext import commands

from warden.features.onboarding.services.protocol import OnboardingService

log = logging.getLogger(__name__)


class OnboardingHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot, service: OnboardingService) -> None:
        self.bot = bot
        self.service = service

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await guild.chunk()  # join saat runtime: roster belum terisi
        created = await self.service.snapshot_if_absent(
            guild.members, guild.id, triggered_by=None
        )
        if created:
            count = len(guild.members)
            log.info("onboarding: snapshot guild %d (%d member)", guild.id, count)
        else:
            log.info("onboarding: guild %d sudah punya snapshot, dilewati", guild.id)

    @commands.group(name="onboard", invoke_without_command=True)
    async def onboard(self, ctx: commands.Context) -> None:
        await ctx.send("Subcommand: `existing [--force]`")

    @onboard.command(name="existing")
    @commands.has_guild_permissions(manage_guild=True)
    async def existing(self, ctx: commands.Context, *, flag: str | None = None) -> None:
        if ctx.guild is None:  # dipakai di DM — tidak ada yang bisa di-onboard
            await ctx.send("Command ini hanya bisa dipakai di server.")
            return
        if flag not in (None, "--force"):
            await ctx.send("Format: `!onboard existing [--force]`")
            return
        if not ctx.guild.chunked:
            await ctx.guild.chunk()
        created = await self.service.snapshot_if_absent(
            ctx.guild.members,
            ctx.guild.id,
            triggered_by=ctx.author.id,
            force=flag == "--force",
        )
        if not created:
            await ctx.send(
                "Snapshot sudah ada. Pakai `!onboard existing --force` untuk menimpa."
            )
        elif flag == "--force":
            await ctx.send(f"Snapshot lama ditimpa: {len(ctx.guild.members)} member.")
        else:
            await ctx.send(f"Snapshot disimpan: {len(ctx.guild.members)} member.")
