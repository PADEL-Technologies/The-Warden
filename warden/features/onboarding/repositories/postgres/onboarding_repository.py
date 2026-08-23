from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

    from warden.features.onboarding.entities.snapshot_member import SnapshotMember


class PostgresOnboardingRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def has_onboarding(self, guild_id: int) -> bool:
        async with self._pool.acquire() as conn:
            return (
                await conn.fetchval(
                    "SELECT 1 FROM onboardings WHERE guild_id = $1", guild_id
                )
                is not None
            )

    async def member_count(self, guild_id: int) -> int:
        async with self._pool.acquire() as conn:
            return (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM members WHERE guild_id = $1", guild_id
                )
                or 0
            )

    async def save(
        self,
        guild_id: int,
        triggered_by: int | None,
        members: list[SnapshotMember],
        force: bool = False,
    ) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            if force:
                await conn.execute(
                    "DELETE FROM member_roles WHERE member_id IN "
                    "(SELECT id FROM members WHERE guild_id = $1)",
                    guild_id,
                )
                await conn.execute("DELETE FROM members WHERE guild_id = $1", guild_id)
                await conn.execute("DELETE FROM roles WHERE guild_id = $1", guild_id)
                await conn.execute(
                    "DELETE FROM onboardings WHERE guild_id = $1", guild_id
                )

            # katalog role guild ini, dedup lewat dict
            role_catalog: dict[int, str] = {}
            for m in members:
                for role in m["roles"]:
                    role_catalog[role["id"]] = role["name"]

            await conn.executemany(
                "INSERT INTO roles (guild_id, role_id, role_name) "
                "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                [(guild_id, rid, name) for rid, name in role_catalog.items()],
            )
            await conn.executemany(
                "INSERT INTO members (guild_id, user_id, joined_at) "
                "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                [(guild_id, m["member_id"], m["joined_at"]) for m in members],
            )

            roles_map = {
                role_id: id_
                for id_, role_id in await conn.fetch(
                    "SELECT id, role_id FROM roles WHERE guild_id = $1", guild_id
                )
            }
            members_map = {
                user_id: id_
                for id_, user_id in await conn.fetch(
                    "SELECT id, user_id FROM members WHERE guild_id = $1",
                    guild_id,
                )
            }
            await conn.executemany(
                "INSERT INTO member_roles (member_id, role_id) "
                "VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [
                    (members_map[m["member_id"]], roles_map[role["id"]])
                    for m in members
                    for role in m["roles"]
                ],
            )
            await conn.execute(
                """
                    INSERT INTO onboardings
                        (guild_id, triggered_by, member_count)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id) DO UPDATE SET
                        onboarded_at = now(),
                        triggered_by = excluded.triggered_by,
                        member_count = excluded.member_count
                    """,
                guild_id,
                triggered_by,
                len(members),
            )
