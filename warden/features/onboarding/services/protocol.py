from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime


class SnapshotRole(Protocol):
    """Subset discord.Role yang dibaca service."""

    id: int
    name: str
    managed: bool

    def is_default(self) -> bool: ...


class SnapshotMemberSource(Protocol):
    """Subset discord.Member yang dibaca service — fake di test memenuhi ini."""

    id: int
    bot: bool
    joined_at: datetime | None
    roles: Sequence[SnapshotRole]


class SnapshotChannelSource(Protocol):
    """Subset discord.abc.GuildChannel yang dibaca service."""

    id: int
    name: str
    type: object  # discord.ChannelType enum; str() menghasilkan 'text', 'voice', ...


class OnboardingService(Protocol):
    async def snapshot_if_absent(
        self,
        members: Sequence[SnapshotMemberSource],
        roles: Sequence[SnapshotRole],
        channels: Sequence[SnapshotChannelSource],
        guild_id: int,
        triggered_by: int | None,
        force: bool = False,
    ) -> bool:
        """True kalau snapshot dibuat; False kalau sudah ada dan bukan force."""
        ...
