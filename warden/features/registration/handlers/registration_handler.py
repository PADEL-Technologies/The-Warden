import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from warden.features.registration.services.registration_service import (
    nickname,
    role_ids_for,
)
from warden.features.registration.views.onboard_me_view import OnboardMeView

if TYPE_CHECKING:
    from warden.features.registration.services.protocol import RegistrationService

log = logging.getLogger(__name__)

LOCKET_TEXT = (
    "Klik **Onboard Me** untuk mulai. Bot akan membuatkan thread pribadi berisi "
    "formnya — isian dan hasilnya cuma kelihatan olehmu dan verifikator."
)


class RegistrationHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot, service: RegistrationService) -> None:
        self.bot = bot
        self.service = service
        self.sweep_archived.start()

    async def cog_unload(self) -> None:
        self.sweep_archived.cancel()

    @commands.group(name="registration", invoke_without_command=True)
    async def registration(self, ctx: commands.Context) -> None:
        await ctx.send("Subcommand: `post`")

    @registration.command(name="post")
    @commands.has_guild_permissions(manage_guild=True)
    async def post(self, ctx: commands.Context) -> None:
        """Permanent locket message. Re-running edits the old message instead of
        posting a second one."""
        locket = self.bot.get_channel(self.bot.config.registration_locket_channel_id)
        if locket is None:
            log.warning(
                "registration: channel locket tidak ketemu",
                extra={
                    "channel_id": self.bot.config.registration_locket_channel_id,
                    "guild_id": ctx.guild.id if ctx.guild else None,
                },
            )
            await ctx.send("`REGISTRATION_LOCKET_CHANNEL_ID` tidak ketemu.")
            return
        embed = discord.Embed(
            title="Registrasi Member",
            description=LOCKET_TEXT,
            color=discord.Color.blurple(),
        )
        view = OnboardMeView(self.service, self.bot.config)
        async for message in locket.history(limit=50):
            if message.author.id == self.bot.user.id and message.components:
                await message.edit(embed=embed, view=view)
                log.info(
                    "registration: pesan locket diperbarui",
                    extra={"message_id": message.id, "channel_id": locket.id},
                )
                await ctx.send(f"Pesan locket diperbarui: {message.jump_url}")
                return
        posted = await locket.send(embed=embed, view=view)
        log.info(
            "registration: pesan locket diposting",
            extra={"message_id": posted.id, "channel_id": locket.id},
        )
        await ctx.send(f"Pesan locket diposting: {posted.jump_url}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Rejoiner who was approved before gets their roles restored here."""
        action, reg = await self.service.start(member.guild.id, member.id)
        if action != "already":
            return
        try:
            role_ids = role_ids_for(
                reg,
                mahasiswa_role_id=self.bot.config.registration_mahasiswa_role_id,
                alumni_role_id=self.bot.config.registration_alumni_role_id,
                prodi_roles=self.bot.config.registration_prodi_roles,
            )
        except KeyError:
            log.warning(
                "registration: prodi %r tidak ada di mapping",
                reg["prodi"],
                extra={
                    "registration_id": reg["id"],
                    "user_id": member.id,
                    "guild_id": member.guild.id,
                },
            )
            return
        try:
            await member.add_roles(
                *[discord.Object(id=r) for r in role_ids],
                reason="Registrasi sudah disetujui sebelumnya",
            )
        except discord.HTTPException as exc:
            log.warning(
                "registration: role gagal dipulihkan setelah join ulang",
                extra={
                    "registration_id": reg["id"],
                    "user_id": member.id,
                    "guild_id": member.guild.id,
                    "role_ids": role_ids,
                    "status": exc.status,
                },
            )
            return
        with contextlib.suppress(discord.HTTPException):
            await member.edit(nick=nickname(reg))
        log.info(
            "registration: role dipulihkan setelah join ulang",
            extra={
                "registration_id": reg["id"],
                "user_id": member.id,
                "guild_id": member.guild.id,
                "role_ids": role_ids,
            },
        )

    @tasks.loop(hours=1)
    async def sweep_archived(self) -> None:
        """Auto-archive is not guaranteed to emit a gateway event, and a thread
        archived while the bot was down never gets one."""
        locket = self.bot.get_channel(self.bot.config.registration_locket_channel_id)
        if locket is None:
            log.warning(
                "registration: sapuan dilewati, channel locket tidak ketemu",
                extra={"channel_id": self.bot.config.registration_locket_channel_id},
            )
            return
        scanned = swept = 0
        # Discord evaluates auto-archive lazily: a thread past its time can stay
        # archived=False until touched, hiding it from archived_threads() below.
        now = discord.utils.utcnow()
        # ponytail: gateway cache instead of Guild.active_threads() (an API
        # call, not a property); fresh enough for an hourly sweep.
        for thread in locket.threads:
            if thread.archive_timestamp and thread.archive_timestamp < now:
                with contextlib.suppress(discord.HTTPException):
                    await thread.edit(archived=True)
        # limit=50 per pass: thread delete is a channel-delete op with a harsh
        # rate limit; the rest waits for the next hour.
        async for thread in locket.archived_threads(private=True, limit=50):
            scanned += 1
            reg = await self.service.by_thread(thread.id)
            if reg is None or reg["state"] == "pending":
                continue  # not ours, or the result still needs a landing spot
            try:
                await thread.delete()
            except discord.HTTPException as exc:
                log.debug(
                    "registration: thread ter-archive gagal dihapus",
                    extra={
                        "thread_id": thread.id,
                        "registration_id": reg["id"],
                        "status": exc.status,
                    },
                )
            else:
                swept += 1
                log.debug(
                    "registration: thread ter-archive dihapus",
                    extra={"thread_id": thread.id, "registration_id": reg["id"]},
                )
            await self.service.clear_thread(thread.id)
        # every hour regardless of outcome: proves the loop is still alive
        log.info(
            "registration: sapuan thread selesai, %d dari %d dihapus",
            swept,
            scanned,
            extra={"scanned": scanned, "swept": swept, "channel_id": locket.id},
        )

    @sweep_archived.before_loop
    async def before_sweep(self) -> None:
        await self.bot.wait_until_ready()
