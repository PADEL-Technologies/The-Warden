from datetime import UTC, datetime, timedelta

from warden.features.registration.entities.registration import Registration
from warden.features.registration.repositories.protocol import RegistrationRepository

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
        if reg is None:
            return "fresh", None  # belum pernah, atau percobaan terakhirnya ditolak
        if reg["state"] == "pending":
            return "wait", reg
        if reg["state"] == "approved":
            return "already", reg
        now = now or datetime.now(UTC)
        expires_at = reg["expires_at"]
        if expires_at is None or expires_at <= now or reg["thread_id"] is None:
            return "expired_recreate", reg
        return "reuse", reg

    async def open_thread(
        self, guild_id: int, user_id: int, thread_id: int, now: datetime | None = None
    ) -> Registration:
        return await self._repo.create_open(
            guild_id, user_id, thread_id, (now or datetime.now(UTC)) + self._ttl
        )

    async def reopen_thread(
        self, registration_id: int, thread_id: int, now: datetime | None = None
    ) -> Registration:
        return await self._repo.reopen(
            registration_id, thread_id, (now or datetime.now(UTC)) + self._ttl
        )

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
        return await self._repo.submit(
            registration_id,
            tipe,
            nama.strip(),
            nama_panggilan.strip(),
            normalize_nim(nim),
            angkatan.strip(),
            prodi,
            (linkedin or "").strip() or None,
        )

    async def decide(
        self,
        registration_id: int,
        approve: bool,
        reviewed_by: int,
        reason: str | None = None,
    ) -> Registration | None:
        """None = sudah diputuskan verifikator lain."""
        return await self._repo.decide(
            registration_id, "approved" if approve else "rejected", reviewed_by, reason
        )

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
