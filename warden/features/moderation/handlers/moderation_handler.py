import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from warden.features.moderation.entities.moderation import HitContext
from warden.features.moderation.services.labels import WARNINGS

if TYPE_CHECKING:
    from warden.features.moderation.services.protocol import ModerationService

log = logging.getLogger(__name__)


class ModerationHandlers(commands.Cog):
    def __init__(self, bot: commands.Bot, service: ModerationService) -> None:
        self.bot = bot
        self.service = service

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._inspect(message, "create")

    @commands.Cog.listener()
    async def on_message_edit(
        self, _before: discord.Message, after: discord.Message
    ) -> None:
        """Post something clean, then edit it into something else — the cheapest
        way around any filter, and free to close since it is the same code."""
        await self._inspect(after, "edit")

    def _skip(self, message: discord.Message) -> bool:
        if message.author.bot or not message.content:
            return True
        if message.channel.id in self.bot.config.moderation_ignored_channel_ids:
            return True
        # Admins are exempt: they are the ones who register the keywords, and a
        # mod quoting a judol link while discussing a case should not trip the
        # filter they maintain.
        admin_roles = set(self.bot.config.moderation_admin_role_ids)
        return isinstance(message.author, discord.Member) and any(
            role.id in admin_roles for role in message.author.roles
        )

    async def _inspect(self, message: discord.Message, source: str) -> None:
        guild = message.guild  # DMs are never filtered
        if guild is None or self._skip(message):
            return
        verdict = self.service.evaluate(message.content)
        if not verdict.matches:
            return  # the common case: no database round-trip at all

        # Record before deleting. If delete() fails — missing permission, or the
        # message is already gone — the hit is still in the corpus.
        hit_id = await self.service.record(
            HitContext(
                guild_id=guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                author_id=message.author.id,
                content=message.content,
                source=source,
            ),
            verdict,
        )
        log.info(
            "moderation: pesan terindikasi",
            extra={
                "hit_id": hit_id,
                "guild_id": guild.id,
                "channel_id": message.channel.id,
                "message_id": message.id,
                "author_id": message.author.id,
                "labels": sorted(verdict.labels),
                "enforced": verdict.enforced,
                "source": source,
            },
        )
        if verdict.warning_label is None:
            return
        await self._enforce(message, verdict.warning_label, hit_id)

    async def _enforce(self, message: discord.Message, label: str, hit_id: int) -> None:
        try:
            await message.delete()
        except discord.HTTPException as exc:
            log.warning(
                "moderation: pesan gagal dihapus",
                extra={"hit_id": hit_id, "status": exc.status},
            )
            return
        try:
            await message.channel.send(
                f"{message.author.mention} {WARNINGS[label]}",
                # Not a permanent public record: a false positive should not
                # sit in the channel shaming someone for weeks. The lasting
                # trace is the moderation_hits row.
                delete_after=self.bot.config.moderation_warning_delete_after,
            )
        except discord.HTTPException as exc:
            log.warning(
                "moderation: peringatan gagal dikirim",
                extra={"hit_id": hit_id, "status": exc.status},
            )
