from datetime import datetime

import asyncpg

from warden.features.registration.entities.registration import Registration


def _row(record: asyncpg.Record | None) -> Registration | None:
    return dict(record) if record is not None else None  # type: ignore[return-value]


def _one(record: asyncpg.Record | None) -> Registration:
    if record is None:
        raise LookupError("registrasi tidak ditemukan")
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
                )
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
                )
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
                )
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
        self, registration_id: int, state: str, reviewed_by: int, reason: str | None
    ) -> Registration | None:
        # `AND state = 'pending'` adalah satu-satunya penjaga balapan dua verifikator:
        # approve itu UPDATE, jadi registrations_active tidak pernah ikut bicara.
        async with self._pool.acquire() as conn:
            return _row(
                await conn.fetchrow(
                    """
                    UPDATE registrations SET
                        state = $2, reviewed_by = $3, reviewed_at = now(),
                        reject_reason = $4
                    WHERE id = $1 AND state = 'pending'
                    RETURNING *
                    """,
                    registration_id,
                    state,
                    reviewed_by,
                    reason,
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
