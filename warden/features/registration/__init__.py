"""Registration feature. Wiring only — handlers, services, repositories, views
hidup terpisah."""

import asyncpg
from discord.ext import commands

from warden.features.registration.handlers.registration_handler import (
    RegistrationHandlers,
)
from warden.features.registration.repositories.postgres.registration_repository import (
    PostgresRegistrationRepository,
)
from warden.features.registration.services.registration_service import (
    RegistrationService,
)
from warden.features.registration.views.onboard_me_view import OnboardMeView
from warden.features.registration.views.pilih_tipe_view import PilihTipeView
from warden.features.registration.views.review_view import ReviewView


async def setup(bot: commands.Bot) -> None:
    if not bot.config.registration_enabled:
        return  # toggle OFF = cog tidak dimuat
    pool = await asyncpg.create_pool(bot.config.database_url)
    service = RegistrationService(PostgresRegistrationRepository(pool))

    # nama kelas = kunci cog di seluruh bot, jadi harus unik antar feature
    class RegistrationCog(RegistrationHandlers):
        async def cog_unload(self) -> None:
            await super().cog_unload()
            await pool.close()

    await bot.add_cog(RegistrationCog(bot, service))

    # add_view mendaftarkan handler untuk custom_id, bukan untuk satu pesan: sekali di
    # sini menghidupkan kembali semua thread lama dan semua kartu yang belum diputuskan.
    bot.add_view(OnboardMeView(service, bot.config))
    bot.add_view(PilihTipeView(service, bot.config))
    bot.add_view(ReviewView(service, bot.config))
