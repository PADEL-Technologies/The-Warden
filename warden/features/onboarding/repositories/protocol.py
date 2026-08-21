from typing import Protocol

from warden.features.onboarding.entities.snapshot_member import SnapshotMember


class OnboardingRepository(Protocol):
    async def has_onboarding(self, guild_id: int) -> bool: ...
    async def member_count(self, guild_id: int) -> int: ...
    async def save(
        self,
        guild_id: int,
        triggered_by: int | None,
        members: list[SnapshotMember],
        force: bool = False,
    ) -> None:
        """force=True: hapus snapshot guild ini dulu, dalam transaksi yang sama."""
        ...
