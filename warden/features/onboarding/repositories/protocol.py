from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from warden.features.onboarding.entities.channel import SnapshotChannel
    from warden.features.onboarding.entities.member_role import MemberRole
    from warden.features.onboarding.entities.snapshot_member import SnapshotMember


class OnboardingRepository(Protocol):
    async def has_onboarding(self, guild_id: int) -> bool: ...
    async def member_count(self, guild_id: int) -> int: ...
    async def save(
        self,
        guild_id: int,
        triggered_by: int | None,
        members: list[SnapshotMember],
        roles: list[MemberRole],
        channels: list[SnapshotChannel],
        force: bool = False,
    ) -> None:
        """force=True: hapus snapshot guild ini dulu, dalam transaksi yang sama."""
        ...
