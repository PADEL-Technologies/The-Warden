from datetime import datetime
from typing import Protocol

from warden.features.registration.entities.registration import Registration


class RegistrationService(Protocol):
    async def start(
        self, guild_id: int, user_id: int, now: datetime | None = None
    ) -> tuple[str, Registration | None]:
        """fresh | reuse | expired_recreate | wait | already, plus barisnya
        kalau ada."""
        ...

    async def open_thread(
        self, guild_id: int, user_id: int, thread_id: int, now: datetime | None = None
    ) -> Registration: ...

    async def reopen_thread(
        self, registration_id: int, thread_id: int, now: datetime | None = None
    ) -> Registration: ...

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
    ) -> Registration: ...

    async def decide(
        self,
        registration_id: int,
        approve: bool,
        reviewed_by: int,
        reason: str | None = None,
    ) -> Registration | None:
        """None = sudah diputuskan verifikator lain."""
        ...

    async def by_thread(self, thread_id: int) -> Registration | None: ...
    async def by_report_message(self, message_id: int) -> Registration | None: ...
    async def set_report_message(
        self, registration_id: int, message_id: int
    ) -> None: ...
    async def attempt_count(self, guild_id: int, user_id: int) -> int: ...
    async def nim_holder(self, guild_id: int, nim: str) -> int | None: ...
    async def clear_thread(self, thread_id: int) -> None: ...
