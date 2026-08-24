import os
import random

import asyncpg
import pytest

from warden.features.onboarding.entities.channel import SnapshotChannel
from warden.features.onboarding.entities.member_role import MemberRole
from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.repositories.postgres.onboarding_repository import (
    PostgresOnboardingRepository,
)

TEST_DB = os.environ.get("WARDEN_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DB is None, reason="WARDEN_TEST_DATABASE_URL tidak diset"
)

# random guild_id per test: reruns against the same DB never collide, no cleanup
GUILD = random.randrange(2**62)
OTHER_GUILD = GUILD + 1


@pytest.fixture
async def pool():
    pool = await asyncpg.create_pool(TEST_DB)
    yield pool
    await pool.close()


@pytest.fixture
def repo(pool):
    return PostgresOnboardingRepository(pool)


def snap(member_id: int, *role_names: str) -> SnapshotMember:
    return SnapshotMember(
        member_id=member_id,
        joined_at="2026-08-01T10:00:00+00:00",
        roles=[MemberRole(id=i, name=n) for i, n in enumerate(role_names, 1)],
    )


def chan(channel_id: int, name: str, type_: str = "text") -> SnapshotChannel:
    return SnapshotChannel(channel_id=channel_id, name=name, type=type_)


async def test_save_and_has_onboarding(repo):
    assert not await repo.has_onboarding(GUILD)
    await repo.save(GUILD, 1, [snap(10, "Mod"), snap(20, "Mod", "Admin")], [], [])
    assert await repo.has_onboarding(GUILD)
    assert await repo.member_count(GUILD) == 2
    assert not await repo.has_onboarding(OTHER_GUILD)  # other guilds untouched


async def test_force_replaces_previous_snapshot(repo, pool):
    await repo.save(
        GUILD,
        None,
        [snap(10, "Mod"), snap(20)],
        [MemberRole(id=1, name="Mod")],
        [chan(1, "general")],
    )
    await repo.save(
        GUILD,
        1,
        [snap(30, "Admin")],
        [MemberRole(id=2, name="Admin")],
        [chan(2, "random")],
        force=True,
    )
    assert await repo.member_count(GUILD) == 1
    async with pool.acquire() as conn:
        roles = await conn.fetch(
            "SELECT role_name FROM roles WHERE guild_id = $1 ORDER BY role_name",
            GUILD,
        )
        channels = await conn.fetch(
            "SELECT channel_name FROM channels "
            "WHERE guild_id = $1 ORDER BY channel_name",
            GUILD,
        )
        member_roles = await conn.fetch(
            "SELECT m.user_id FROM member_roles mr "
            "JOIN members m ON m.id = mr.member_id WHERE m.guild_id = $1",
            GUILD,
        )
        onboarding = await conn.fetch(
            "SELECT triggered_by, member_count FROM onboardings WHERE guild_id = $1",
            GUILD,
        )
    assert [r["role_name"] for r in roles] == ["Admin"]  # old roles deleted
    assert [c["channel_name"] for c in channels] == ["random"]  # old channels too
    assert [r["user_id"] for r in member_roles] == [30]
    assert [(r["triggered_by"], r["member_count"]) for r in onboarding] == [(1, 1)]


async def test_save_twice_without_force_is_idempotent(repo):
    await repo.save(GUILD, None, [snap(10, "Mod")], [MemberRole(id=1, name="Mod")], [])
    await repo.save(
        GUILD, None, [snap(10, "Mod")], [MemberRole(id=1, name="Mod")], []
    )  # ON CONFLICT DO NOTHING
    assert await repo.member_count(GUILD) == 1


async def test_role_and_channel_without_member_still_saved(repo, pool):
    # issue #7: role and channel catalogs are not derived from members
    await repo.save(
        GUILD,
        None,
        [snap(10)],
        [MemberRole(id=9, name="Kosong")],
        [chan(500, "lounging", "voice")],
    )
    async with pool.acquire() as conn:
        roles = await conn.fetch(
            "SELECT role_name FROM roles WHERE guild_id = $1", GUILD
        )
        channels = await conn.fetch(
            "SELECT channel_name, channel_type FROM channels WHERE guild_id = $1",
            GUILD,
        )
    assert [r["role_name"] for r in roles] == ["Kosong"]
    assert [(c["channel_name"], c["channel_type"]) for c in channels] == [
        ("lounging", "voice")
    ]
