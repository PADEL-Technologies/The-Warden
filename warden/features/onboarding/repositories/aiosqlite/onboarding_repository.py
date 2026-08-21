from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from warden.features.onboarding.entities.snapshot_member import SnapshotMember
from warden.features.onboarding.repositories.aiosqlite.runner import apply_pending


class AiosqliteOnboardingRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await apply_pending(db)  # cek murah: 2 query kecil per koneksi
            yield db

    async def has_onboarding(self, guild_id: int) -> bool:
        async with self._connect() as db:
            rows = await db.execute_fetchall(
                "SELECT 1 FROM onboardings WHERE guild_id = ?", (guild_id,)
            )
            return bool(rows)

    async def member_count(self, guild_id: int) -> int:
        async with self._connect() as db:
            rows = await db.execute_fetchall(
                "SELECT COUNT(*) FROM members WHERE guild_id = ?", (guild_id,)
            )
            return int(rows[0][0])

    async def save(
        self,
        guild_id: int,
        triggered_by: int | None,
        members: list[SnapshotMember],
        force: bool = False,
    ) -> None:
        async with self._connect() as db:
            if force:
                await db.execute(
                    "DELETE FROM member_roles WHERE member_id IN "
                    "(SELECT id FROM members WHERE guild_id = ?)",
                    (guild_id,),
                )
                await db.execute("DELETE FROM members WHERE guild_id = ?", (guild_id,))
                await db.execute("DELETE FROM roles WHERE guild_id = ?", (guild_id,))
                await db.execute(
                    "DELETE FROM onboardings WHERE guild_id = ?", (guild_id,)
                )

            # katalog role guild ini, dedup lewat dict
            role_catalog: dict[int, str] = {}
            for m in members:
                for role in m["roles"]:
                    role_catalog[role["id"]] = role["name"]

            await db.executemany(
                "INSERT OR IGNORE INTO roles "
                "(guild_id, role_id, role_name) VALUES (?, ?, ?)",
                [(guild_id, rid, name) for rid, name in role_catalog.items()],
            )
            await db.executemany(
                "INSERT OR IGNORE INTO members "
                "(guild_id, user_id, joined_at) VALUES (?, ?, ?)",
                [(guild_id, m["member_id"], m["joined_at"]) for m in members],
            )

            roles_map = {
                role_id: id_
                for id_, role_id in await db.execute_fetchall(
                    "SELECT id, role_id FROM roles WHERE guild_id = ?", (guild_id,)
                )
            }
            members_map = {
                user_id: id_
                for id_, user_id in await db.execute_fetchall(
                    "SELECT id, user_id FROM members WHERE guild_id = ?", (guild_id,)
                )
            }
            await db.executemany(
                "INSERT OR IGNORE INTO member_roles (member_id, role_id) VALUES (?, ?)",
                [
                    (members_map[m["member_id"]], roles_map[role["id"]])
                    for m in members
                    for role in m["roles"]
                ],
            )
            await db.execute(
                """
                INSERT INTO onboardings
                    (guild_id, onboarded_at, triggered_by, member_count)
                VALUES (?, datetime('now'), ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    onboarded_at = excluded.onboarded_at,
                    triggered_by = excluded.triggered_by,
                    member_count = excluded.member_count
                """,
                (guild_id, triggered_by, len(members)),
            )
            await db.commit()
