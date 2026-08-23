from datetime import datetime
from typing import TypedDict


class Registration(TypedDict):
    """Satu baris `registrations` — satu percobaan pendaftaran, bukan satu orang."""

    id: int
    guild_id: int
    user_id: int
    type: str | None  # mahasiswa | alumni, NULL selama state=open
    nama: str | None
    nama_panggilan: str | None
    nim: str | None
    angkatan: str | None
    prodi: str | None
    linkedin: str | None
    state: str  # open | pending | approved | rejected
    thread_id: int | None
    report_message_id: int | None
    reject_reason: str | None
    expires_at: datetime | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime
