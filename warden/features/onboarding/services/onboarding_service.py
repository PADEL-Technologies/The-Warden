import logging
from typing import TYPE_CHECKING

from warden.features.onboarding.entities.channel import SnapshotChannel
from warden.features.onboarding.entities.member_role import MemberRole
from warden.features.onboarding.entities.snapshot_member import SnapshotMember

if TYPE_CHECKING:
    from collections.abc import Sequence

    from warden.features.onboarding.repositories.protocol import OnboardingRepository
    from warden.features.onboarding.services.protocol import (
        SnapshotChannelSource,
        SnapshotMemberSource,
        SnapshotRole,
    )

log = logging.getLogger(__name__)


def _keep_role(role: SnapshotRole) -> bool:
    # @everyone is held by everyone; managed = bot/integration roles (Boosters
    # included) — neither is human-managed, both uninformative.
    return not role.is_default() and not role.managed


class OnboardingService:
    def __init__(self, repo: OnboardingRepository) -> None:
        self._repo = repo

    async def snapshot_if_absent(
        self,
        members: Sequence[SnapshotMemberSource],
        roles: Sequence[SnapshotRole],
        channels: Sequence[SnapshotChannelSource],
        guild_id: int,
        triggered_by: int | None,
        force: bool = False,
    ) -> bool:
        if not force and await self._repo.has_onboarding(guild_id):
            log.debug(
                "onboarding: guild sudah punya snapshot", extra={"guild_id": guild_id}
            )
            return False
        snapshot = [
            SnapshotMember(
                member_id=m.id,
                joined_at=m.joined_at.isoformat() if m.joined_at else None,
                roles=[
                    MemberRole(id=r.id, name=r.name) for r in m.roles if _keep_role(r)
                ],
            )
            for m in members
            if not m.bot
        ]
        role_catalog = [
            MemberRole(id=r.id, name=r.name) for r in roles if _keep_role(r)
        ]
        channel_snapshot = [
            SnapshotChannel(channel_id=c.id, name=c.name, type=str(c.type))
            for c in channels
        ]
        await self._repo.save(
            guild_id,
            triggered_by,
            snapshot,
            role_catalog,
            channel_snapshot,
            force=force,
        )
        return True
