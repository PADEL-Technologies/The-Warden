from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.services.onboarding_service import OnboardingService
from warden.features.onboarding.services.protocol import (
    SnapshotMemberSource,
    SnapshotRole,
)


class FakeRepo:
    def __init__(self) -> None:
        self.saved: dict[int, list[SnapshotMember]] = {}
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
        force: bool = False,
    ) -> None:
        self.saved[guild_id] = members
        self.force_used = force


@dataclass
class FakeRole(SnapshotRole):
    id: int
    name: str
    default: bool = False

    def is_default(self) -> bool:
        return self.default


@dataclass
class FakeMember(SnapshotMemberSource):
    id: int
    roles: Sequence[SnapshotRole]
    joined_at: datetime | None = field(
        default_factory=lambda: datetime(2026, 8, 1, 10, tzinfo=UTC)
    )


def service() -> tuple[OnboardingService, FakeRepo]:
    repo = FakeRepo()
    return OnboardingService(repo), repo


async def test_skips_when_snapshot_exists():
    svc, repo = service()
    assert await svc.snapshot_if_absent([FakeMember(1, [])], 5, None)
    assert not await svc.snapshot_if_absent([FakeMember(2, [])], 5, None)
    assert len(repo.saved[5]) == 1  # snapshot kedua tidak jalan


async def test_force_overrides_existing():
    svc, repo = service()
    await svc.snapshot_if_absent([FakeMember(1, [])], 5, None)
    assert await svc.snapshot_if_absent([FakeMember(2, [])], 5, None, force=True)
    assert repo.force_used
    assert [m["member_id"] for m in repo.saved[5]] == [2]


async def test_filters_everyone_and_converts_joined_at():
    svc, repo = service()
    everyone = FakeRole(1, "@everyone", default=True)
    mod = FakeRole(2, "Mod")
    await svc.snapshot_if_absent([FakeMember(10, [everyone, mod])], 5, 1)
    snap = repo.saved[5][0]
    assert snap["roles"] == [{"id": 2, "name": "Mod"}]
    assert snap["joined_at"] == "2026-08-01T10:00:00+00:00"


async def test_none_joined_at_survives():
    svc, repo = service()
    await svc.snapshot_if_absent([FakeMember(1, [], joined_at=None)], 5, None)
    assert repo.saved[5][0]["joined_at"] is None
