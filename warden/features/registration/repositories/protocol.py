from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from warden.features.registration.entities.registration import Registration


class RegistrationRepository(Protocol):
    async def active_by_user(self, guild_id: int, user_id: int) -> Registration | None:
        """open/pending/approved. At most one, enforced by registrations_active."""
        ...

    async def create_open(
        self, guild_id: int, user_id: int, thread_id: int, expires_at: datetime
    ) -> Registration: ...

    async def reopen(
        self, registration_id: int, thread_id: int, expires_at: datetime
    ) -> Registration:
        """Reuses an open row whose TTL passed — the new thread is patched onto
        it, so registrations_active never has to argue."""
        ...

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
        """open → pending."""
        ...

    async def by_thread(self, thread_id: int) -> Registration | None: ...
    async def by_report_message(self, message_id: int) -> Registration | None: ...
    async def set_report_message(
        self, registration_id: int, message_id: int
    ) -> None: ...

    async def decide(
        self,
        registration_id: int,
        state: str,
        reviewed_by: int,
        reason: str | None,
        joined_at: str | None = None,
    ) -> Registration | None:
        """None = row is no longer pending; another verifier won the race.
        state='approved' also writes the members row (issue #12); joined_at is
        from Discord, NULL if the user already left."""
        ...

    async def attempt_count(self, guild_id: int, user_id: int) -> int:
        """Includes the in-flight attempt → "Attempt #N" on the card."""
        ...

    async def nim_holder(self, guild_id: int, nim: str) -> int | None:
        """user_id of the approved NIM holder, if any."""
        ...

    async def clear_thread(self, thread_id: int) -> None:
        """Thread deleted in Discord; the row remains as history."""
        ...
