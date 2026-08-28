"""Moderation feature. Wiring only — handlers, services, repositories, views
live apart."""

from typing import TYPE_CHECKING

import asyncpg

from warden.features.moderation.handlers.moderation_commands import ModerationCommands
from warden.features.moderation.handlers.moderation_handler import ModerationHandlers
from warden.features.moderation.repositories.postgres.moderation_repository import (
    PostgresModerationRepository,
)
from warden.features.moderation.services.moderation_service import ModerationService

if TYPE_CHECKING:
    from warden.bot import Warden


async def setup(bot: Warden) -> None:
    if not bot.config.moderation_enabled:
        return
    pool = await asyncpg.create_pool(bot.config.database_url)
    service = ModerationService(PostgresModerationRepository(pool))
    # Build the automaton once here rather than lazily on the first message:
    # a broken rule in the database should surface at startup.
    await service.reload()

    # class name = cog key bot-wide, must stay unique across features
    class ModerationCog(ModerationHandlers):
        async def cog_unload(self) -> None:
            await pool.close()

    await bot.add_cog(ModerationCog(bot, service))
    await bot.add_cog(ModerationCommands(bot, service))
