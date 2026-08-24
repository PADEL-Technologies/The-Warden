from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from warden.features.onboarding.entities.channel import SnapshotChannel
from warden.features.onboarding.entities.member_role import MemberRole
from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.services.onboarding_service import OnboardingService
from warden.features.onboarding.services.protocol import (
    SnapshotChannelSource,
    SnapshotMemberSource,
    SnapshotRole,
)


class FakeRepo:
    def __init__(self) -> None:
        self.saved: dict[int, list[SnapshotMember]] = {}
        self.roles: dict[int, list[MemberRole]] = {}
        self.channels: dict[int, list[SnapshotChannel]] = {}
        self.force_used = False

    async def has_onboarding(self, guild_id: int) -> bool:
        return guild_id in self.saved

    async def member_count(self, guild_id: int) -> int:
        return len(self.saved.get(guild_id, []))

    async def save(
        self,
        guild_id: int,
        triggered_by: int | None,  # noqa: ARG002 - signature follows OnboardingRepository
        members: list[SnapshotMember],
        roles: list[MemberRole],
        channels: list[SnapshotChannel],
        force: bool = False,
    ) -> None:
        self.saved[guild_id] = members
        self.roles[guild_id] = roles
        self.channels[guild_id] = channels
        self.force_used = force


@dataclass
class FakeRole(SnapshotRole):
    id: int
    name: str
    managed: bool = False
    default: bool = False

    def is_default(self) -> bool:
        return self.default


@dataclass
class FakeMember(SnapshotMemberSource):
    id: int
    roles: Sequence[SnapshotRole]
    bot: bool = False
    joined_at: datetime | None = field(
        default_factory=lambda: datetime(2026, 8, 1, 10, tzinfo=UTC)
    )


@dataclass
class FakeChannel(SnapshotChannelSource):
    id: int
    name: str
    type: object = "text"


def service() -> tuple[OnboardingService, FakeRepo]:
    repo = FakeRepo()
    return OnboardingService(repo), repo


async def test_skips_when_snapshot_exists():
    svc, repo = service()
    assert await svc.snapshot_if_absent([FakeMember(1, [])], [], [], 5, None)
    assert not await svc.snapshot_if_absent([FakeMember(2, [])], [], [], 5, None)
    assert len(repo.saved[5]) == 1  # second snapshot didn't run


async def test_force_overrides_existing():
    svc, repo = service()
    await svc.snapshot_if_absent([FakeMember(1, [])], [], [], 5, None)
    assert await svc.snapshot_if_absent(
        [FakeMember(2, [])], [], [], 5, None, force=True
    )
    assert repo.force_used
    assert [m["member_id"] for m in repo.saved[5]] == [2]


async def test_filters_everyone_and_converts_joined_at():
    svc, repo = service()
    everyone = FakeRole(1, "@everyone", default=True)
    mod = FakeRole(2, "Mod")
    await svc.snapshot_if_absent([FakeMember(10, [everyone, mod])], [mod], [], 5, 1)
    snap = repo.saved[5][0]
    assert snap["roles"] == [{"id": 2, "name": "Mod"}]
    assert snap["joined_at"] == "2026-08-01T10:00:00+00:00"


async def test_none_joined_at_survives():
    svc, repo = service()
    await svc.snapshot_if_absent([FakeMember(1, [], joined_at=None)], [], [], 5, None)
    assert repo.saved[5][0]["joined_at"] is None


async def test_role_without_member_still_in_catalog():
    # issue #7: a 0-member role still lands in the catalog
    svc, repo = service()
    lonely = FakeRole(9, "Kosong")
    await svc.snapshot_if_absent([FakeMember(1, [])], [lonely], [], 5, None)
    assert repo.roles[5] == [{"id": 9, "name": "Kosong"}]


async def test_managed_roles_filtered():
    svc, repo = service()
    bot_role = FakeRole(2, "SomeBot", managed=True)
    human = FakeRole(3, "Human")
    await svc.snapshot_if_absent(
        [FakeMember(1, [bot_role, human])], [bot_role, human], [], 5, None
    )
    assert repo.roles[5] == [{"id": 3, "name": "Human"}]
    assert repo.saved[5][0]["roles"] == [{"id": 3, "name": "Human"}]


async def test_bot_members_excluded():
    svc, repo = service()
    human = FakeMember(1, [])
    bot = FakeMember(2, [], bot=True)
    await svc.snapshot_if_absent([human, bot], [], [], 5, None)
    assert [m["member_id"] for m in repo.saved[5]] == [1]


async def test_channels_snapshotted():
    svc, repo = service()
    channels = [
        FakeChannel(100, "general", "text"),
        FakeChannel(200, "Off Topic", "voice"),
    ]
    await svc.snapshot_if_absent([], [], channels, 5, None)
    assert repo.channels[5] == [
        {"channel_id": 100, "name": "general", "type": "text"},
        {"channel_id": 200, "name": "Off Topic", "type": "voice"},
    ]
