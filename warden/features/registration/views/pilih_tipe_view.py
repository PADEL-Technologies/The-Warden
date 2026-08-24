import logging
from typing import TYPE_CHECKING

import discord

from warden.features.registration.views.registrasi_modal import RegistrasiModal

if TYPE_CHECKING:
    from warden.config import Config
    from warden.features.registration.services.protocol import RegistrationService

log = logging.getLogger(__name__)


class PilihTipeView(discord.ui.View):
    """Lives inside the applicant's thread. Verifiers get in via Join Thread,
    so the owner must still be checked."""

    def __init__(self, service: RegistrationService, config: Config) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.config = config

    async def _open(self, interaction: discord.Interaction, tipe: str) -> None:
        reg = await self.service.by_thread(interaction.channel_id)
        if reg is None or reg["state"] != "open":
            await interaction.response.send_message(
                "Form ini sudah tidak aktif. Klik **Onboard Me** lagi di "
                "#registration-locket.",
                ephemeral=True,
            )
            return
        if reg["user_id"] != interaction.user.id:
            log.warning(
                "registration: form orang lain dibuka",
                extra={
                    "registration_id": reg["id"],
                    "owner_id": reg["user_id"],
                    "user_id": interaction.user.id,
                    "thread_id": interaction.channel_id,
                },
            )
            await interaction.response.send_message(
                "Ini form pendaftaran orang lain.", ephemeral=True
            )
            return
        log.debug(
            "registration: modal dibuka",
            extra={
                "registration_id": reg["id"],
                "user_id": interaction.user.id,
                "type": tipe,
            },
        )
        await interaction.response.send_modal(
            RegistrasiModal(self.service, self.config, reg, tipe)
        )

    @discord.ui.button(
        label="Mahasiswa",
        style=discord.ButtonStyle.primary,
        custom_id="registration:mahasiswa",
    )
    async def mahasiswa(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._open(interaction, "mahasiswa")

    @discord.ui.button(
        label="Alumni",
        style=discord.ButtonStyle.secondary,
        custom_id="registration:alumni",
    )
    async def alumni(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._open(interaction, "alumni")
