import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    import asyncpg

    from warden.features.registration.entities.registration import Registration

log = logging.getLogger(__name__)


def _row(record: asyncpg.Record | None) -> Registration | None:
    return dict(record) if record is not None else None  # type: ignore[return-value]


def _one(record: asyncpg.Record | None, ident: str) -> Registration:
    if record is None:
        # the only explicit failure in this repo; the rest are raw asyncpg errors
        raise LookupError(f"registration not found ({ident})")
    return dict(record)  # type: ignore[return-value]


class PostgresRegistrationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def active_by_user(self, guild_id: int, user_id: int) -> Registration | None:
        async with self._pool.acquire() as conn:
            return _row(
                await conn.fetchrow(
                    "SELECT * FROM registrations "
                    "WHERE guild_id = $1 AND user_id = $2 "
                    "AND state IN ('open', 'pending', 'approved')",
                    guild_id,
                    user_id,
                )
            )

    async def create_open(
        self, guild_id: int, user_id: int, thread_id: int, expires_at: datetime
    ) -> Registration:
        log.debug(
            "registration_repo: create_open",
            extra={"guild_id": guild_id, "user_id": user_id, "thread_id": thread_id},
        )
        async with self._pool.acquire() as conn:
            return _one(
                await conn.fetchrow(
                    "INSERT INTO registrations "
                    "  (guild_id, user_id, state, thread_id, expires_at) "
                    "VALUES ($1, $2, 'open', $3, $4) RETURNING *",
                    guild_id,
                    user_id,
                    thread_id,
                    expires_at,
                ),
                f"user_id={user_id}",
            )

    async def reopen(
        self, registration_id: int, thread_id: int, expires_at: datetime
    ) -> Registration:
        async with self._pool.acquire() as conn:
            return _one(
                await conn.fetchrow(
                    "UPDATE registrations SET thread_id = $2, expires_at = $3 "
                    "WHERE id = $1 RETURNING *",
                    registration_id,
                    thread_id,
                    expires_at,
                ),
                f"id={registration_id}",
            )

    async def submit(
        self,
        registration_id: int,
        tipe: str,
        nama: str,
        nama_panggilan: str,
        nim: str | None,
        angkatan: str,
        prodi: str | None,
        linkedin: str | None,
    ) -> Registration:
        # operation name only, not SQL + params: the statement carries name, NIM,
        # prodi and linkedin all at once
        log.debug(
            "registration_repo: submit", extra={"registration_id": registration_id}
        )
        async with self._pool.acquire() as conn:
            return _one(
                await conn.fetchrow(
                    """
                    UPDATE registrations SET
                        state = 'pending', type = $2, nama = $3, nama_panggilan = $4,
                        nim = $5, angkatan = $6, prodi = $7, linkedin = $8
                    WHERE id = $1
                    RETURNING *
                    """,
                    registration_id,
                    tipe,
                    nama,
                    nama_panggilan,
                    nim,
                    angkatan,
                    prodi,
                    linkedin,
                ),
                f"id={registration_id}",
            )

    async def by_thread(self, thread_id: int) -> Registration | None:
        async with self._pool.acquire() as conn:
            return _row(
                await conn.fetchrow(
                    "SELECT * FROM registrations WHERE thread_id = $1",
                    thread_id,
                )
            )

    async def by_report_message(self, message_id: int) -> Registration | None:
        async with self._pool.acquire() as conn:
            return _row(
                await conn.fetchrow(
                    "SELECT * FROM registrations WHERE report_message_id = $1",
                    message_id,
                )
            )

    async def set_report_message(self, registration_id: int, message_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE registrations SET report_message_id = $2 WHERE id = $1",
                registration_id,
                message_id,
            )

    async def decide(
        self,
        registration_id: int,
        state: str,
        reviewed_by: int,
        reason: str | None,
        joined_at: str | None = None,
    ) -> Registration | None:
        # `AND state = 'pending'` is the only guard against two racing verifiers:
        # approve is an UPDATE, so registrations_active never gets a say.
        #
        # One statement, not two in a transaction: the members row is born from
        # the registrations row that just changed, so "approved but members
        # empty" (issue #12) can't happen even if the connection drops midway.
        # `WHERE state = 'approved'` keeps reject away from members.
        async with self._pool.acquire() as conn:
            return _row(
                await conn.fetchrow(
                    """
                    WITH decided AS (
                        UPDATE registrations SET
                            state = $2, reviewed_by = $3, reviewed_at = now(),
                            reject_reason = $4
                        WHERE id = $1 AND state = 'pending'
                        RETURNING *
                    ), enrolled AS (
                        INSERT INTO members (guild_id, user_id, joined_at)
                        SELECT guild_id, user_id, $5 FROM decided
                        WHERE state = 'approved'
                        ON CONFLICT (guild_id, user_id) DO NOTHING
                    )
                    SELECT * FROM decided
                    """,
                    registration_id,
                    state,
                    reviewed_by,
                    reason,
                    joined_at,
                )
            )

    async def attempt_count(self, guild_id: int, user_id: int) -> int:
        async with self._pool.acquire() as conn:
            return (
                await conn.fetchval(
                    "SELECT COUNT(*) FROM registrations "
                    "WHERE guild_id = $1 AND user_id = $2",
                    guild_id,
                    user_id,
                )
                or 0
            )

    async def nim_holder(self, guild_id: int, nim: str) -> int | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT user_id FROM registrations "
                "WHERE guild_id = $1 AND nim = $2 AND state = 'approved'",
                guild_id,
                nim,
            )

    async def clear_thread(self, thread_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE registrations SET thread_id = NULL WHERE thread_id = $1",
                thread_id,
            )
