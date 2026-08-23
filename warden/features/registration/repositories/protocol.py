from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from warden.features.registration.entities.registration import Registration


class RegistrationRepository(Protocol):
    async def active_by_user(self, guild_id: int, user_id: int) -> Registration | None:
        """state open/pending/approved. Maksimal satu, dijaga registrations_active."""
        ...

    async def create_open(
        self, guild_id: int, user_id: int, thread_id: int, expires_at: datetime
    ) -> Registration: ...

    async def reopen(
        self, registration_id: int, thread_id: int, expires_at: datetime
    ) -> Registration:
        """Baris open yang TTL-nya lewat dipakai ulang — thread barunya ditambal
        ke sini, jadi registrations_active tidak perlu ikut berdebat."""
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
        """None = barisnya sudah bukan pending; verifikator lain menang balapan.
        state='approved' sekalian menulis barisnya ke members (issue #12);
        joined_at dari Discord, NULL kalau orangnya sudah keluar server."""
        ...

    async def attempt_count(self, guild_id: int, user_id: int) -> int:
        """Termasuk percobaan yang sedang berjalan → "Percobaan ke-N" di kartu."""
        ...

    async def nim_holder(self, guild_id: int, nim: str) -> int | None:
        """user_id pemilik NIM yang sudah approved, kalau ada."""
        ...

    async def clear_thread(self, thread_id: int) -> None:
        """Thread sudah dihapus di Discord; barisnya tetap ada sebagai riwayat."""
        ...
