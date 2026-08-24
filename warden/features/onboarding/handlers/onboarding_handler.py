import logging
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from warden.features.onboarding.services.protocol import OnboardingService

log = logging.getLogger(__name__)


def _human_count(members: Sequence[discord.Member]) -> int:
    return sum(1 for m in members if not m.bot)


class OnboardingHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot, service: OnboardingService) -> None:
        self.bot = bot
        self.service = service

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.debug("onboarding: masuk guild baru", extra={"guild_id": guild.id})
        await guild.chunk()  # runtime join: the roster isn't filled yet
        created = await self.service.snapshot_if_absent(
            guild.members,
            guild.roles,
            guild.channels,
            guild.id,
            triggered_by=None,
        )
        if created:
            count = _human_count(guild.members)
            log.info(
                "onboarding: snapshot guild %d (%d member)",
                guild.id,
                count,
                extra={"guild_id": guild.id, "member_count": count},
            )
        else:
            log.info(
                "onboarding: guild %d sudah punya snapshot, dilewati",
                guild.id,
                extra={"guild_id": guild.id},
            )

    @commands.group(name="onboard", invoke_without_command=True)
    async def onboard(self, ctx: commands.Context) -> None:
        await ctx.send("Subcommand: `existing [--force]`")

    @onboard.command(name="existing")
    @commands.has_guild_permissions(manage_guild=True)
    async def existing(self, ctx: commands.Context, *, flag: str | None = None) -> None:
        if ctx.guild is None:  # used in a DM — nothing to onboard
            await ctx.send("Command ini hanya bisa dipakai di server.")
            return
        if flag not in (None, "--force"):
            await ctx.send("Format: `!onboard existing [--force]`")
            return
        log.debug(
            "onboarding: !onboard existing dipanggil",
            extra={
                "guild_id": ctx.guild.id,
                "triggered_by": ctx.author.id,
                "force": flag == "--force",
            },
        )
        if not ctx.guild.chunked:
            await ctx.guild.chunk()
        created = await self.service.snapshot_if_absent(
            ctx.guild.members,
            ctx.guild.roles,
            ctx.guild.channels,
            ctx.guild.id,
            triggered_by=ctx.author.id,
            force=flag == "--force",
        )
        count = _human_count(ctx.guild.members)
        if not created:
            log.debug(
                "onboarding: snapshot sudah ada, --force tidak dipakai",
                extra={"guild_id": ctx.guild.id},
            )
            await ctx.send(
                "Snapshot sudah ada. Pakai `!onboard existing --force` untuk menimpa."
            )
            return
        log.info(
            "onboarding: snapshot manual %d member (force=%s)",
            count,
            flag == "--force",
            extra={
                "guild_id": ctx.guild.id,
                "triggered_by": ctx.author.id,
                "member_count": count,
                "force": flag == "--force",
            },
        )
        if flag == "--force":
            await ctx.send(f"Snapshot lama ditimpa: {count} member.")
        else:
            await ctx.send(f"Snapshot disimpan: {count} member.")
