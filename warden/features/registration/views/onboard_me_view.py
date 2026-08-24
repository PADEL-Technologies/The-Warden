import contextlib
import logging
from typing import TYPE_CHECKING

import asyncpg
import discord

from warden.features.registration.views.pilih_tipe_view import PilihTipeView
from warden.features.registration.views.threads import (
    THREAD_ARCHIVE_MINUTES,
    get_thread,
    wake,
)

if TYPE_CHECKING:
    from warden.config import Config
    from warden.features.registration.services.protocol import RegistrationService

log = logging.getLogger(__name__)


class OnboardMeView(discord.ui.View):
    def __init__(self, service: RegistrationService, config: Config) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.config = config

    @discord.ui.button(
        label="Onboard Me",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="registration:start",
    )
    async def start(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        # semua balasan ephemeral: #registration-locket publik dan pesan permanennya
        # jangan ketimbun
        await interaction.response.defer(ephemeral=True)
        action, reg = await self.service.start(
            interaction.guild_id, interaction.user.id
        )
        if action == "wait":
            await interaction.followup.send(
                "Formmu sudah masuk. Tunggu verifikasi ya.", ephemeral=True
            )
            return
        if action == "already":
            await interaction.followup.send("Kamu sudah terverifikasi.", ephemeral=True)
            return

        if action == "reuse":
            thread = await get_thread(interaction.guild, reg["thread_id"])
            if thread is not None:
                await wake(thread)
                await thread.add_user(interaction.user)
                await interaction.followup.send(thread.jump_url, ephemeral=True)
                return
            action = "expired_recreate"  # DB bilang hidup, Discord bilang tidak

        if action == "expired_recreate":
            old = await get_thread(interaction.guild, reg["thread_id"])
            if old is not None:
                with contextlib.suppress(discord.HTTPException):
                    await old.delete()

        thread = await self._create_thread(interaction)
        if thread is None:
            return
        try:
            if reg is None:
                await self.service.open_thread(
                    interaction.guild_id, interaction.user.id, thread.id
                )
            else:
                await self.service.reopen_thread(reg["id"], thread.id)
        except asyncpg.UniqueViolationError:
            # dua klik hampir bersamaan; registrations_active yang jadi wasitnya
            log.warning(
                "registration: klik ganda, registrasi barusan sudah dibuat",
                extra={
                    "guild_id": interaction.guild_id,
                    "user_id": interaction.user.id,
                    "thread_id": thread.id,
                },
            )
            with contextlib.suppress(discord.HTTPException):
                await thread.delete()
            await interaction.followup.send(
                "Pendaftaranmu barusan sudah dibuat. Klik sekali lagi.", ephemeral=True
            )
            return
        log.info(
            "registration: thread pendaftaran siap",
            extra={
                "guild_id": interaction.guild_id,
                "user_id": interaction.user.id,
                "thread_id": thread.id,
                "action": action,
            },
        )
        await interaction.followup.send(thread.jump_url, ephemeral=True)

    async def _create_thread(
        self, interaction: discord.Interaction
    ) -> discord.Thread | None:
        # id dari config, bukan interaction.channel: sapuan cleanup memakai channel
        # yang sama, dan keduanya harus menunjuk tempat yang persis sama
        locket = interaction.guild.get_channel(
            self.config.registration_locket_channel_id
        )
        if locket is None:
            log.warning(
                "registration: channel locket tidak ketemu saat membuat thread",
                extra={
                    "channel_id": self.config.registration_locket_channel_id,
                    "guild_id": interaction.guild_id,
                },
            )
            await interaction.followup.send(
                "Channel registrasi belum diset dengan benar. Hubungi admin.",
                ephemeral=True,
            )
            return None
        thread = await locket.create_thread(
            name=f"Registrasi · {interaction.user.name}"[:100],
            type=discord.ChannelType.private_thread,
            invitable=False,  # cuma bot yang boleh menambah orang
            auto_archive_duration=THREAD_ARCHIVE_MINUTES,
            reason="Registrasi",
        )
        await thread.add_user(interaction.user)
        await thread.send(
            f"Halo <@{interaction.user.id}>! Pilih statusmu untuk membuka formnya.",
            view=PilihTipeView(self.service, self.config),
        )
        return thread
