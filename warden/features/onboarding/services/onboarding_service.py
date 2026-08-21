from collections.abc import Sequence

from warden.features.onboarding.entities.member_role import MemberRole
from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.repositories.protocol import OnboardingRepository
from warden.features.onboarding.services.protocol import SnapshotMemberSource


class OnboardingService:
    def __init__(self, repo: OnboardingRepository) -> None:
        self._repo = repo

    async def snapshot_if_absent(
        self,
        members: Sequence[SnapshotMemberSource],
        guild_id: int,
        triggered_by: int | None,
        force: bool = False,
    ) -> bool:
        if not force and await self._repo.has_onboarding(guild_id):
            return False
        snapshot = [
            SnapshotMember(
                member_id=m.id,
                joined_at=m.joined_at.isoformat() if m.joined_at else None,
                roles=[
                    MemberRole(id=r.id, name=r.name)
                    for r in m.roles
                    if not r.is_default()
                ],
            )
            for m in members
        ]
        await self._repo.save(guild_id, triggered_by, snapshot, force=force)
        return True
