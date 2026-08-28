"""The upsert-vs-reactivate distinction and the hit/matches CTE both live in
SQL, so a fake repo proves nothing — this has to hit real Postgres."""

import os
import random

import asyncpg
import pytest

from warden.features.moderation.entities.moderation import HitContext, Match
from warden.features.moderation.repositories.postgres.moderation_repository import (
    PostgresModerationRepository,
)

TEST_DB = os.environ.get("WARDEN_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DB is None, reason="WARDEN_TEST_DATABASE_URL tidak diset"
)

# random guild_id per run: reruns against the same DB never collide, no cleanup
GUILD = random.randrange(2**62)


@pytest.fixture
async def pool():
    pool = await asyncpg.create_pool(TEST_DB)
    yield pool
    await pool.close()


@pytest.fixture
def repo(pool):
    return PostgresModerationRepository(pool)


@pytest.fixture
def label():
    """A label nobody else uses, so keyword rows from other runs stay out of
    the way without a cleanup step."""
    return f"judol{random.randrange(2**40)}"


async def test_add_is_idempotent_and_reports_new_rows(repo, label):
    rows = await repo.add_keywords(label, [("Maxwin", "maxwin")], 1)
    assert rows == [("maxwin", "Maxwin", True)]

    # Same normalized form, different casing: the unique index must catch it.
    rows = await repo.add_keywords(label, [("MAXWIN", "maxwin")], 1)
    assert rows == [("maxwin", "Maxwin", False)]
    assert len(await repo.list_keywords(label, True)) == 1


async def test_remove_then_readd_reactivates_the_same_row(repo, label):
    await repo.add_keywords(label, [("maxwin", "maxwin")], 1)
    assert await repo.remove_keywords(label, ["maxwin"]) == [("maxwin", "maxwin")]
    # Second removal is a no-op: the row is already disabled.
    assert await repo.remove_keywords(label, ["maxwin"]) == []
    assert await repo.list_keywords(label, False) == []

    await repo.add_keywords(label, [("maxwin", "maxwin")], 1)
    active = await repo.list_keywords(label, False)
    assert len(active) == 1
    assert active[0]["enabled"] is True


async def test_record_hit_writes_both_tables_in_one_call(repo, pool):
    ctx = HitContext(
        guild_id=GUILD,
        channel_id=2,
        message_id=random.randrange(2**62),
        author_id=3,
        content="promo maxwin anjing",
        source="edit",
    )
    matches = [
        Match("judol", "keyword", 1, "maxwin"),
        Match("negative", "keyword", 2, "anjing"),
    ]
    hit_id = await repo.record_hit(ctx, "promo maxwin anjing", True, matches)

    async with pool.acquire() as conn:
        hit = await conn.fetchrow("SELECT * FROM moderation_hits WHERE id = $1", hit_id)
        rows = await conn.fetch(
            "SELECT label, rule_kind, matched_term FROM moderation_hit_matches "
            "WHERE hit_id = $1 ORDER BY label",
            hit_id,
        )
    assert hit["source"] == "edit"
    assert hit["enforced"] is True
    assert hit["content"] == "promo maxwin anjing"
    # Multi-label from day one: one message, two rows.
    assert [(r["label"], r["matched_term"]) for r in rows] == [
        ("judol", "maxwin"),
        ("negative", "anjing"),
    ]


async def test_export_shape_is_one_row_per_message(repo, pool):
    """The query docs/moderation.md hands to the fastText phase."""
    ctx = HitContext(
        guild_id=GUILD,
        channel_id=2,
        message_id=random.randrange(2**62),
        author_id=3,
        content="promo maxwin anjing",
        source="create",
    )
    hit_id = await repo.record_hit(
        ctx,
        "promo maxwin anjing",
        True,
        [Match("judol", "keyword", 1, "maxwin"), Match("negative", "regex", 2, "anj")],
    )
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT h.content, array_agg(DISTINCT m.label) AS labels
            FROM moderation_hits h
            JOIN moderation_hit_matches m ON m.hit_id = h.id
            WHERE h.id = $1
            GROUP BY h.id, h.content
            """,
            hit_id,
        )
    assert sorted(row["labels"]) == ["judol", "negative"]
