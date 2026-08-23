from typing import TYPE_CHECKING

import discord

from warden.features.registration.entities.registration import Registration

if TYPE_CHECKING:  # ReviewView yang membuat modal ini — impor balik cuma untuk tipe
    from warden.features.registration.views.review_view import ReviewView


class RejectModal(discord.ui.Modal):
    alasan = discord.ui.TextInput(
        label="Alasan",
        style=discord.TextStyle.paragraph,
        placeholder="Dibaca pendaftar di threadnya.",
        max_length=500,
    )

    def __init__(self, review: ReviewView, reg: Registration) -> None:
        super().__init__(title="Tolak Registrasi")
        self.review = review
        self.reg = reg

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        decided = await self.review.service.decide(
            self.reg["id"],
            approve=False,
            reviewed_by=interaction.user.id,
            reason=str(self.alasan),
        )
        if decided is None:
            await self.review.already_decided(interaction)
            return
        await self.review.finish(
            interaction,
            decided,
            f"registrasimu ditolak.\n> {self.alasan}\n"
            "Kamu boleh mendaftar ulang dari awal lewat tombol **Onboard Me**.",
        )
