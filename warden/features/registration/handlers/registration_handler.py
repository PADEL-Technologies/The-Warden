import contextlib
import logging

import discord
from discord.ext import commands, tasks

from warden.features.registration.services.protocol import RegistrationService
from warden.features.registration.services.registration_service import (
    nickname,
    role_ids_for,
)
from warden.features.registration.views.onboard_me_view import OnboardMeView

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
                await ctx.send(f"Pesan locket diperbarui: {message.jump_url}")
                return
        posted = await locket.send(embed=embed, view=view)
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
            log.warning("registration: prodi %r tidak ada di mapping", reg["prodi"])
            return
        with contextlib.suppress(discord.HTTPException):
            await member.add_roles(
                *[discord.Object(id=r) for r in role_ids],
                reason="Registrasi sudah disetujui sebelumnya",
            )
            await member.edit(nick=nickname(reg))

    @tasks.loop(hours=1)
    async def sweep_archived(self) -> None:
        """auto-archive tidak dijamin memancarkan gateway event, dan thread yang
        ter-archive saat bot mati tidak akan pernah dapat event susulan."""
        locket = self.bot.get_channel(self.bot.config.registration_locket_channel_id)
        if locket is None:
            return
        # limit=50 per pass: delete thread itu operasi channel-delete, rate limitnya
        # galak. Sisanya kebagian jam berikutnya.
        async for thread in locket.archived_threads(private=True, limit=50):
            reg = await self.service.by_thread(thread.id)
            if reg is None or reg["state"] == "pending":
                continue  # bukan punya kita, atau hasilnya masih butuh tempat mendarat
            with contextlib.suppress(discord.HTTPException):
                await thread.delete()
            await self.service.clear_thread(thread.id)

    @sweep_archived.before_loop
    async def before_sweep(self) -> None:
        await self.bot.wait_until_ready()
