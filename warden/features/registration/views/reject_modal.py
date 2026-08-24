import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:  # ReviewView builds this modal — import is for types only
    from warden.features.registration.entities.registration import Registration
    from warden.features.registration.views.review_view import ReviewView

log = logging.getLogger(__name__)


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
        log.debug(
            "registration: modal tolak disubmit",
            extra={
                "registration_id": self.reg["id"],
                "reviewed_by": interaction.user.id,
            },
        )
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
