import contextlib
import logging
from typing import TYPE_CHECKING

import discord

from warden.features.registration.services.registration_service import validate_angkatan
from warden.features.registration.views.review_card import build_review_embed
from warden.features.registration.views.review_view import ReviewView

if TYPE_CHECKING:
    from warden.config import Config
    from warden.features.registration.entities.registration import Registration
    from warden.features.registration.services.protocol import RegistrationService

log = logging.getLogger(__name__)

# 7 days: once the form is in, the thread must outlast human verification.
PENDING_ARCHIVE_MINUTES = 10080


class RegistrasiModal(discord.ui.Modal):
    """Five components, at Discord's limit. Validation is pushed into built-in
    constraints — a modal cannot answer a modal, so post-submit rejections are
    always costly."""

    def __init__(
        self,
        service: RegistrationService,
        config: Config,
        reg: Registration,
        tipe: str,
        defaults: dict[str, str | None] | None = None,
    ) -> None:
        super().__init__(title=f"Registrasi {tipe.capitalize()}", timeout=None)
        self.service = service
        self.config = config
        self.reg = reg
        self.tipe = tipe
        d = defaults or {}

        self.nama = discord.ui.TextInput(max_length=32, default=d.get("nama"))
        self.panggilan = discord.ui.TextInput(
            max_length=24, default=d.get("nama_panggilan")
        )
        self.angkatan = discord.ui.TextInput(
            min_length=4, max_length=4, placeholder="2021", default=d.get("angkatan")
        )
        if tipe == "mahasiswa":
            self.nim = discord.ui.TextInput(
                min_length=8, max_length=8, default=d.get("nim")
            )
            # closed choice: free typing would let "D3 TI" pass verification
            # but miss the prodi role — silent failure
            self.prodi = discord.ui.Select(
                placeholder="Pilih prodi",
                options=[
                    discord.SelectOption(label=k, value=k, default=k == d.get("prodi"))
                    for k in config.registration_prodi_roles
                ],
            )
            self.linkedin = None
            extra = discord.ui.Label(text="Prodi", component=self.prodi)
        else:
            self.nim = discord.ui.TextInput(
                required=False, max_length=16, default=d.get("nim")
            )
            self.prodi = None
            self.linkedin = discord.ui.TextInput(
                max_length=200, default=d.get("linkedin")
            )
            extra = discord.ui.Label(text="LinkedIn", component=self.linkedin)

        self.add_item(discord.ui.Label(text="Nama", component=self.nama))
        self.add_item(discord.ui.Label(text="Nama Panggilan", component=self.panggilan))
        self.add_item(
            discord.ui.Label(
                text="NIM",
                description=None if tipe == "mahasiswa" else "Boleh dikosongkan.",
                component=self.nim,
            )
        )
        self.add_item(discord.ui.Label(text="Angkatan", component=self.angkatan))
        self.add_item(extra)

    def _prodi_value(self) -> str | None:
        return self.prodi.values[0] if self.prodi and self.prodi.values else None

    def refill(self) -> RegistrasiModal:
        """New modal pre-filled with the old typing — a rejection must not wipe
        the user's input."""
        return RegistrasiModal(
            self.service,
            self.config,
            self.reg,
            self.tipe,
            {
                "nama": self.nama.value,
                "nama_panggilan": self.panggilan.value,
                "nim": self.nim.value,
                "angkatan": self.angkatan.value,
                "prodi": self._prodi_value(),
                "linkedin": self.linkedin.value if self.linkedin else None,
            },
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        error = validate_angkatan(self.angkatan.value)
        if error:
            log.debug(
                "registration: angkatan ditolak validasi",
                extra={
                    "registration_id": self.reg["id"],
                    "user_id": interaction.user.id,
                    "angkatan": self.angkatan.value,
                },
            )
            await interaction.response.send_message(
                error, view=IsiUlangView(self), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        reg = await self.service.submit(
            self.reg["id"],
            self.tipe,
            self.nama.value,
            self.panggilan.value,
            self.angkatan.value,
            nim=self.nim.value,
            prodi=self._prodi_value(),
            linkedin=self.linkedin.value if self.linkedin else None,
        )

        if isinstance(interaction.channel, discord.Thread):
            with contextlib.suppress(discord.HTTPException):
                await interaction.channel.edit(
                    auto_archive_duration=PENDING_ARCHIVE_MINUTES
                )

        embed = build_review_embed(
            reg,
            interaction.user,
            await self.service.attempt_count(reg["guild_id"], reg["user_id"]),
            await self.service.nim_holder(reg["guild_id"], reg["nim"])
            if reg["nim"]
            else None,
        )
        report = interaction.client.get_channel(
            self.config.registration_report_channel_id
        )
        if report is None:
            log.warning(
                "registration: channel review tidak ketemu, kartu tidak terkirim",
                extra={
                    "registration_id": reg["id"],
                    "channel_id": self.config.registration_report_channel_id,
                },
            )
            await interaction.followup.send(
                "Formmu tersimpan, tapi channel review belum diset dengan benar. "
                "Hubungi admin.",
                ephemeral=True,
            )
            return
        message = await report.send(
            embed=embed, view=ReviewView(self.service, self.config)
        )
        await self.service.set_report_message(reg["id"], message.id)
        log.info(
            "registration: kartu review diposting",
            extra={
                "registration_id": reg["id"],
                "user_id": reg["user_id"],
                "message_id": message.id,
                "channel_id": report.id,
            },
        )
        await interaction.followup.send(
            "Formmu sudah masuk. Tunggu verifikasi ya — hasilnya dikirim ke sini.",
            ephemeral=True,
        )


class IsiUlangView(discord.ui.View):
    """Temporary and ephemeral: no need to be persistent, it lives a minute."""

    def __init__(self, modal: RegistrasiModal) -> None:
        super().__init__(timeout=600)
        self.modal = modal

    @discord.ui.button(label="Isi Ulang", style=discord.ButtonStyle.primary)
    async def isi_ulang(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(self.modal.refill())
