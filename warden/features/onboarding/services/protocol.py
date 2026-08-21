from collections.abc import Sequence
from datetime import datetime
from typing import Protocol


class SnapshotRole(Protocol):
    """Subset discord.Role yang dibaca service."""

    id: int
    name: str

    def is_default(self) -> bool: ...


class SnapshotMemberSource(Protocol):
    """Subset discord.Member yang dibaca service — fake di test memenuhi ini."""

    id: int
    joined_at: datetime | None
    roles: Sequence[SnapshotRole]


class OnboardingService(Protocol):
    async def snapshot_if_absent(
        self,
        members: Sequence[SnapshotMemberSource],
        guild_id: int,
        triggered_by: int | None,
        force: bool = False,
    ) -> bool:
        """True kalau snapshot dibuat; False kalau sudah ada dan bukan force."""
        ...
