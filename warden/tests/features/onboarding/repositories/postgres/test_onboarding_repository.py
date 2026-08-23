import os
import random

import asyncpg
import pytest

from warden.features.onboarding.entities.member_role import MemberRole
from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.repositories.postgres.onboarding_repository import (
    PostgresOnboardingRepository,
)

TEST_DB = os.environ.get("WARDEN_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DB is None, reason="WARDEN_TEST_DATABASE_URL tidak diset"
)

# guild_id acak per test: rerun terhadap DB yang sama tidak bentrok, tanpa cleanup
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


async def test_save_and_has_onboarding(repo):
    assert not await repo.has_onboarding(GUILD)
    await repo.save(GUILD, 1, [snap(10, "Mod"), snap(20, "Mod", "Admin")])
    assert await repo.has_onboarding(GUILD)
    assert await repo.member_count(GUILD) == 2
    assert not await repo.has_onboarding(OTHER_GUILD)  # guild lain tidak terpengaruh


async def test_force_replaces_previous_snapshot(repo, pool):
    await repo.save(GUILD, None, [snap(10, "Mod"), snap(20)])
    await repo.save(GUILD, 1, [snap(30, "Admin")], force=True)
    assert await repo.member_count(GUILD) == 1
    async with pool.acquire() as conn:
        roles = await conn.fetch(
            "SELECT role_name FROM roles WHERE guild_id = $1 ORDER BY role_name",
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
    assert [r["role_name"] for r in roles] == ["Admin"]  # role lama ikut terhapus
    assert [r["user_id"] for r in member_roles] == [30]
    assert [(r["triggered_by"], r["member_count"]) for r in onboarding] == [(1, 1)]


async def test_save_twice_without_force_is_idempotent(repo):
    await repo.save(GUILD, None, [snap(10, "Mod")])
    await repo.save(GUILD, None, [snap(10, "Mod")])  # ON CONFLICT DO NOTHING
    assert await repo.member_count(GUILD) == 1
