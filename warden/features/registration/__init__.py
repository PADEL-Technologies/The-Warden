"""Registration feature. Wiring only — handlers, services, repositories, views
live apart."""

from typing import TYPE_CHECKING

import asyncpg

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

if TYPE_CHECKING:
    from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    if not bot.config.registration_enabled:
        return
    pool = await asyncpg.create_pool(bot.config.database_url)
    service = RegistrationService(PostgresRegistrationRepository(pool))

    # class name = cog key bot-wide, must stay unique across features
    class RegistrationCog(RegistrationHandlers):
        async def cog_unload(self) -> None:
            await super().cog_unload()
            await pool.close()

    await bot.add_cog(RegistrationCog(bot, service))

    # add_view registers a handler per custom_id, not per message: one call here
    # revives all old threads and undecided cards.
    bot.add_view(OnboardMeView(service, bot.config))
    bot.add_view(PilihTipeView(service, bot.config))
    bot.add_view(ReviewView(service, bot.config))
