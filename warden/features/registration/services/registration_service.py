import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from warden.features.registration.entities.registration import Registration
    from warden.features.registration.repositories.protocol import (
        RegistrationRepository,
    )

log = logging.getLogger(__name__)

# Petunjuk cleanup, bukan gerbang: submit di menit ke-20 dengan thread masih hidup
# tetap diterima. auto_archive_duration Discord cuma menerima 60/1440/4320/10080.
TTL = timedelta(minutes=15)
ANGKATAN_MIN = 2000
NICKNAME_MAX = 32  # batas Discord


def normalize_nim(raw: str | None) -> str | None:
    """Tanpa ini `a1b2 ` dan `A1B2` jadi dua NIM berbeda dan indeks unik bocor."""
    return (raw or "").strip().upper() or None


def validate_angkatan(raw: str, now: datetime | None = None) -> str | None:
    """None = lolos. Selain itu pesan untuk ephemeral."""
    year = (now or datetime.now(UTC)).year
    if not raw.strip().isdigit() or not ANGKATAN_MIN <= int(raw.strip()) <= year:
        return f"Angkatan harus tahun antara {ANGKATAN_MIN} dan {year}."
    return None


def nickname(reg: Registration) -> str:
    """`[D3-TI]Rizky` / `[ALUMNI]Rizky`. Prodi = key mapping env, di-upper()."""
    prefix = "ALUMNI" if reg["type"] == "alumni" else (reg["prodi"] or "").upper()
    # ponytail: dipotong di 32 kalau key prodi-nya kepanjangan — Discord menolak
    # nickname lebih dari itu. Perpendek key-nya kalau potongannya kelihatan.
    return f"[{prefix}]{reg['nama_panggilan']}"[:NICKNAME_MAX]


def role_ids_for(
    reg: Registration,
    *,
    mahasiswa_role_id: int,
    alumni_role_id: int,
    prodi_roles: dict[str, int],
) -> list[int]:
    """KeyError kalau prodinya tidak ada di mapping — approve harus gagal keras,
    bukan diam-diam cuma memberi role mahasiswa."""
    if reg["type"] == "alumni":
        return [alumni_role_id]
    return [mahasiswa_role_id, prodi_roles[reg["prodi"] or ""]]


class RegistrationService:
    def __init__(self, repo: RegistrationRepository, ttl: timedelta = TTL) -> None:
        self._repo = repo
        self._ttl = ttl

    async def start(
        self, guild_id: int, user_id: int, now: datetime | None = None
    ) -> tuple[str, Registration | None]:
        """Satu cabang per baris tabel §State:
        fresh | reuse | expired_recreate | wait | already."""
        reg = await self._repo.active_by_user(guild_id, user_id)
        action = self._action(reg, now or datetime.now(UTC))
        log.debug(
            "registration: start -> %s",
            action,
            extra={
                "guild_id": guild_id,
                "user_id": user_id,
                "action": action,
                "registration_id": reg["id"] if reg else None,
                "state": reg["state"] if reg else None,
            },
        )
        return action, reg

    @staticmethod
    def _action(reg: Registration | None, now: datetime) -> str:
        if reg is None:
            return "fresh"  # belum pernah, atau percobaan terakhirnya ditolak
        if reg["state"] == "pending":
            return "wait"
        if reg["state"] == "approved":
            return "already"
        expires_at = reg["expires_at"]
        if expires_at is None or expires_at <= now or reg["thread_id"] is None:
            return "expired_recreate"
        return "reuse"

    async def open_thread(
        self, guild_id: int, user_id: int, thread_id: int, now: datetime | None = None
    ) -> Registration:
        reg = await self._repo.create_open(
            guild_id, user_id, thread_id, (now or datetime.now(UTC)) + self._ttl
        )
        log.debug(
            "registration: thread dibuka",
            extra={
                "registration_id": reg["id"],
                "guild_id": guild_id,
                "user_id": user_id,
                "thread_id": thread_id,
            },
        )
        return reg

    async def reopen_thread(
        self, registration_id: int, thread_id: int, now: datetime | None = None
    ) -> Registration:
        reg = await self._repo.reopen(
            registration_id, thread_id, (now or datetime.now(UTC)) + self._ttl
        )
        log.debug(
            "registration: thread dibuka ulang",
            extra={"registration_id": registration_id, "thread_id": thread_id},
        )
        return reg

    async def submit(
        self,
        registration_id: int,
        tipe: str,
        nama: str,
        nama_panggilan: str,
        angkatan: str,
        nim: str | None = None,
        prodi: str | None = None,
        linkedin: str | None = None,
    ) -> Registration:
        # DEBUG saja: nama/NIM/prodi/linkedin itu PII, di INFO ke atas cuma ID.
        log.debug(
            "registration: form disubmit",
            extra={
                "registration_id": registration_id,
                "type": tipe,
                "nama": nama,
                "nama_panggilan": nama_panggilan,
                "nim": nim,
                "angkatan": angkatan,
                "prodi": prodi,
                "linkedin": linkedin,
            },
        )
        reg = await self._repo.submit(
            registration_id,
            tipe,
            nama.strip(),
            nama_panggilan.strip(),
            normalize_nim(nim),
            angkatan.strip(),
            prodi,
            (linkedin or "").strip() or None,
        )
        log.info(
            "registration: form masuk, menunggu verifikasi",
            extra={
                "registration_id": reg["id"],
                "guild_id": reg["guild_id"],
                "user_id": reg["user_id"],
                "type": tipe,
            },
        )
        return reg

    async def decide(
        self,
        registration_id: int,
        approve: bool,
        reviewed_by: int,
        reason: str | None = None,
        joined_at: str | None = None,
    ) -> Registration | None:
        """None = sudah diputuskan verifikator lain."""
        # reason itu teks bebas verifikator — PII, jadi DEBUG saja
        log.debug(
            "registration: keputusan masuk",
            extra={
                "registration_id": registration_id,
                "approve": approve,
                "reviewed_by": reviewed_by,
                "reject_reason": reason,
            },
        )
        decided = await self._repo.decide(
            registration_id,
            "approved" if approve else "rejected",
            reviewed_by,
            reason,
            joined_at,
        )
        if decided is None:
            log.warning(
                "registration: keputusan ditolak, sudah tidak pending",
                extra={"registration_id": registration_id, "reviewed_by": reviewed_by},
            )
            return None
        log.info(
            "registration: %s",
            decided["state"],
            extra={
                "registration_id": registration_id,
                "guild_id": decided["guild_id"],
                "user_id": decided["user_id"],
                "state": decided["state"],
                "reviewed_by": reviewed_by,
            },
        )
        return decided

    async def by_thread(self, thread_id: int) -> Registration | None:
        return await self._repo.by_thread(thread_id)

    async def by_report_message(self, message_id: int) -> Registration | None:
        return await self._repo.by_report_message(message_id)

    async def set_report_message(self, registration_id: int, message_id: int) -> None:
        await self._repo.set_report_message(registration_id, message_id)

    async def attempt_count(self, guild_id: int, user_id: int) -> int:
        return await self._repo.attempt_count(guild_id, user_id)

    async def nim_holder(self, guild_id: int, nim: str) -> int | None:
        return await self._repo.nim_holder(guild_id, nim)

    async def clear_thread(self, thread_id: int) -> None:
        await self._repo.clear_thread(thread_id)
