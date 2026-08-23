import discord

from warden.config import Config
from warden.features.registration.services.protocol import RegistrationService
from warden.features.registration.views.registrasi_modal import RegistrasiModal


class PilihTipeView(discord.ui.View):
    """Hidup di dalam thread pendaftar. Verifikator ikut masuk lewat Join Thread,
    jadi pemiliknya tetap harus diperiksa."""

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
            await interaction.response.send_message(
                "Ini form pendaftaran orang lain.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            RegistrasiModal(self.service, self.config, reg, tipe)
        )

    @discord.ui.button(
        label="Mahasiswa",
        style=discord.ButtonStyle.primary,
        custom_id="registration:mahasiswa",
    )
    async def mahasiswa(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._open(interaction, "mahasiswa")

    @discord.ui.button(
        label="Alumni",
        style=discord.ButtonStyle.secondary,
        custom_id="registration:alumni",
    )
    async def alumni(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._open(interaction, "alumni")
