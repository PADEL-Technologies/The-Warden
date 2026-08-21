import aiosqlite
import pytest

from warden.features.onboarding.entities.member_role import MemberRole
from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.repositories.aiosqlite.onboarding_repository import (
    AiosqliteOnboardingRepository,
)


def snap(member_id: int, *role_names: str) -> SnapshotMember:
    return SnapshotMember(
        member_id=member_id,
        joined_at="2026-08-01T10:00:00+00:00",
        roles=[MemberRole(id=i, name=n) for i, n in enumerate(role_names, 1)],
    )


async def test_save_and_has_onboarding(tmp_path):
    repo = AiosqliteOnboardingRepository(tmp_path / "test.db")
    assert not await repo.has_onboarding(5)
    await repo.save(5, 1, [snap(10, "Mod"), snap(20, "Mod", "Admin")])
    assert await repo.has_onboarding(5)
    assert await repo.member_count(5) == 2
    assert not await repo.has_onboarding(6)  # guild lain tidak terpengaruh


async def test_force_replaces_previous_snapshot(tmp_path):
    repo = AiosqliteOnboardingRepository(tmp_path / "test.db")
    await repo.save(5, None, [snap(10, "Mod"), snap(20)])
    await repo.save(5, 1, [snap(30, "Admin")], force=True)
    assert await repo.member_count(5) == 1
    async with aiosqlite.connect(tmp_path / "test.db") as db:
        roles = await db.execute_fetchall(
            "SELECT role_name FROM roles WHERE guild_id = 5 ORDER BY role_name"
        )
        member_roles = await db.execute_fetchall(
            "SELECT m.user_id FROM member_roles mr "
            "JOIN members m ON m.id = mr.member_id WHERE m.guild_id = 5"
        )
        onboarding = await db.execute_fetchall(
            "SELECT triggered_by, member_count FROM onboardings WHERE guild_id = 5"
        )
    assert roles == [("Admin",)]  # role lama ikut terhapus
    assert member_roles == [(30,)]
    assert onboarding == [(1, 1)]


async def test_save_twice_without_force_is_idempotent(tmp_path):
    repo = AiosqliteOnboardingRepository(tmp_path / "test.db")
    await repo.save(5, None, [snap(10, "Mod")])
    await repo.save(5, None, [snap(10, "Mod")])  # INSERT OR IGNORE: tidak error
    assert await repo.member_count(5) == 1


@pytest.mark.parametrize("force", [False, True])
async def test_migrations_applied_fresh_db(tmp_path, force):
    repo = AiosqliteOnboardingRepository(tmp_path / "sub" / "test.db")
    await repo.save(5, None, [snap(10)], force=force)  # mkdir parents + migrasi jalan
    assert await repo.has_onboarding(5)
