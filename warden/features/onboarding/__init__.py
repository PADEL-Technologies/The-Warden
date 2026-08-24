"""Onboarding feature. Wiring only — handlers, services, repositories live apart."""

from typing import TYPE_CHECKING

import asyncpg

from warden.features.onboarding.handlers.onboarding_handler import OnboardingHandlers
from warden.features.onboarding.repositories.postgres.onboarding_repository import (
    PostgresOnboardingRepository,
)
from warden.features.onboarding.services.onboarding_service import OnboardingService

if TYPE_CHECKING:
    from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    if not bot.config.onboarding_enabled:
        return
    pool = await asyncpg.create_pool(bot.config.database_url)

    # class name = cog key bot-wide, must stay unique across features
    class OnboardingCog(OnboardingHandlers):
        async def cog_unload(self) -> None:
            await pool.close()

    await bot.add_cog(
        OnboardingCog(bot, OnboardingService(PostgresOnboardingRepository(pool)))
    )
