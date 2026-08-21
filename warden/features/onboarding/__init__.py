"""Onboarding feature. Wiring only — handlers, services, repositories live apart."""

from discord.ext import commands

from warden.features.onboarding.handlers.onboarding_handler import OnboardingHandlers
from warden.features.onboarding.repositories.aiosqlite.onboarding_repository import (
    AiosqliteOnboardingRepository,
)
from warden.features.onboarding.services.onboarding_service import OnboardingService


async def setup(bot: commands.Bot) -> None:
    if not bot.config.onboarding_enabled:
        return  # toggle OFF = cog tidak dimuat
    repo = AiosqliteOnboardingRepository(bot.config.db_path)
    await bot.add_cog(OnboardingHandlers(bot, OnboardingService(repo)))
