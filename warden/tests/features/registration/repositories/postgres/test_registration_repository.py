"""Issue #12: approve must write to members. The logic lives in SQL, so a fake
repo proves nothing — this has to hit real Postgres."""

import os
import random
from datetime import UTC, datetime

import asyncpg
import pytest

from warden.features.registration.repositories.postgres.registration_repository import (
    PostgresRegistrationRepository,
)

TEST_DB = os.environ.get("WARDEN_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DB is None, reason="WARDEN_TEST_DATABASE_URL tidak diset"
)

# random guild_id per test: reruns against the same DB never collide, no cleanup
GUILD = random.randrange(2**62)
EXPIRES = datetime(2026, 8, 23, 14, 0, tzinfo=UTC)
JOINED_AT = "2026-08-01T10:00:00+00:00"


@pytest.fixture
async def pool():
    pool = await asyncpg.create_pool(TEST_DB)
    yield pool
    await pool.close()


@pytest.fixture
def repo(pool):
    return PostgresRegistrationRepository(pool)


async def pending(repo, user_id: int, nim: str):
    """create_open → submit, the only legal path to state=pending."""
    reg = await repo.create_open(GUILD, user_id, user_id, EXPIRES)
    return await repo.submit(
        reg["id"], "mahasiswa", "Nama Lengkap", "Nama", nim, "2021", "d3-ti", None
    )


async def members_of(pool, user_id: int) -> list[tuple[int, str | None]]:
    rows = await pool.fetch(
        "SELECT user_id, joined_at FROM members WHERE guild_id = $1 AND user_id = $2",
        GUILD,
        user_id,
    )
    return [(r["user_id"], r["joined_at"]) for r in rows]


async def test_approve_inserts_member(repo, pool):
    reg = await pending(repo, 10, "A0000010")
    decided = await repo.decide(reg["id"], "approved", 99, None, JOINED_AT)
    assert decided["state"] == "approved"
    assert await members_of(pool, 10) == [(10, JOINED_AT)]


async def test_reject_does_not_insert_member(repo, pool):
    reg = await pending(repo, 20, "A0000020")
    decided = await repo.decide(reg["id"], "rejected", 99, "foto buram")
    assert decided["state"] == "rejected"
    assert await members_of(pool, 20) == []


async def test_approve_keeps_existing_member_row(repo, pool):
    # already captured by the onboarding snapshot: ON CONFLICT DO NOTHING, not an error
    await pool.execute(
        "INSERT INTO members (guild_id, user_id, joined_at) VALUES ($1, $2, $3)",
        GUILD,
        30,
        JOINED_AT,
    )
    reg = await pending(repo, 30, "A0000030")
    assert await repo.decide(reg["id"], "approved", 99, None, None) is not None
    assert await members_of(pool, 30) == [(30, JOINED_AT)]  # not overwritten with NULL


async def test_second_approve_loses_and_changes_nothing(repo, pool):
    reg = await pending(repo, 40, "A0000040")
    assert await repo.decide(reg["id"], "approved", 99, None, JOINED_AT) is not None
    assert (
        await repo.decide(reg["id"], "approved", 98, None, "2026-09-09T00:00:00")
        is None
    )
    assert await members_of(pool, 40) == [(40, JOINED_AT)]
