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
        """Pesan permanen di locket. Dijalankan lagi = mengedit pesan lama,
        bukan memposting yang kedua."""
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
        """Orang yang lolos lalu keluar-masuk lagi: rolenya menyusul di sini."""
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
        """auto-archive tidak dijamin memancarkan gateway event, dan thread yang
        ter-archive saat bot mati tidak akan pernah dapat event susulan."""
        locket = self.bot.get_channel(self.bot.config.registration_locket_channel_id)
        if locket is None:
            log.warning(
                "registration: sapuan dilewati, channel locket tidak ketemu",
                extra={"channel_id": self.bot.config.registration_locket_channel_id},
            )
            return
        scanned = swept = 0
        # Discord mengevaluasi auto-archive secara malas: thread yang jamnya
        # sudah lewat bisa tetap archived=False kalau tidak disentuh siapa pun,
        # dan itu membuatnya tak terlihat oleh archived_threads() di bawah.
        now = discord.utils.utcnow()
        for thread in await locket.guild.fetch_active_threads():
            if thread.parent_id != locket.id:
                continue
            if thread.archive_timestamp and thread.archive_timestamp < now:
                with contextlib.suppress(discord.HTTPException):
                    await thread.edit(archived=True)
        # limit=50 per pass: delete thread itu operasi channel-delete, rate limitnya
        # galak. Sisanya kebagian jam berikutnya.
        async for thread in locket.archived_threads(private=True, limit=50):
            scanned += 1
            reg = await self.service.by_thread(thread.id)
            if reg is None or reg["state"] == "pending":
                continue  # bukan punya kita, atau hasilnya masih butuh tempat mendarat
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
        # tiap jam apa pun hasilnya: baris ini yang membuktikan loopnya masih hidup
        log.info(
            "registration: sapuan thread selesai, %d dari %d dihapus",
            swept,
            scanned,
            extra={"scanned": scanned, "swept": swept, "channel_id": locket.id},
        )

    @sweep_archived.before_loop
    async def before_sweep(self) -> None:
        await self.bot.wait_until_ready()
