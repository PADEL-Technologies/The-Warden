"""Onboarding feature. Wiring only — handlers, services, repositories live apart."""

import asyncpg
from discord.ext import commands

from warden.features.onboarding.handlers.onboarding_handler import OnboardingHandlers
from warden.features.onboarding.repositories.postgres.onboarding_repository import (
    PostgresOnboardingRepository,
)
from warden.features.onboarding.services.onboarding_service import OnboardingService


async def setup(bot: commands.Bot) -> None:
    if not bot.config.onboarding_enabled:
        return  # toggle OFF = cog tidak dimuat
    pool = await asyncpg.create_pool(bot.config.database_url)

    # nama kelas = kunci cog di seluruh bot, jadi harus unik antar feature
    class OnboardingCog(OnboardingHandlers):
        async def cog_unload(self) -> None:
            await pool.close()

    await bot.add_cog(
        OnboardingCog(bot, OnboardingService(PostgresOnboardingRepository(pool)))
    )
