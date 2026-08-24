from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime


class SnapshotRole(Protocol):
    """The discord.Role subset the service reads."""

    id: int
    name: str
    managed: bool

    def is_default(self) -> bool: ...


class SnapshotMemberSource(Protocol):
    """The discord.Member subset the service reads — test fakes satisfy this."""

    id: int
    bot: bool
    joined_at: datetime | None
    roles: Sequence[SnapshotRole]


class SnapshotChannelSource(Protocol):
    """The discord.abc.GuildChannel subset the service reads."""

    id: int
    name: str
    type: object  # discord.ChannelType enum; str() yields 'text', 'voice', ...


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
        """True if a snapshot was created; False if one exists and not force."""
        ...
