from datetime import UTC, datetime, timedelta

from warden.features.registration.entities.registration import Registration
from warden.features.registration.services.registration_service import (
    RegistrationService,
    nickname,
    normalize_nim,
    validate_angkatan,
)

NOW = datetime(2026, 8, 23, 14, 0, tzinfo=UTC)


class FakeRepo:
    def __init__(self) -> None:
        self.rows: list[Registration] = []
        self._next_id = 1

    def _add(self, **kwargs) -> Registration:
        row: Registration = {
            "id": self._next_id,
            "guild_id": 5,
            "user_id": 1,
            "type": None,
            "nama": None,
            "nama_panggilan": None,
            "nim": None,
            "angkatan": None,
            "prodi": None,
            "linkedin": None,
            "state": "open",
            "thread_id": None,
            "report_message_id": None,
            "reject_reason": None,
            "expires_at": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": NOW,
        } | kwargs
        self._next_id += 1
        self.rows.append(row)
        return row

    def _by_id(self, registration_id: int) -> Registration:
        return next(r for r in self.rows if r["id"] == registration_id)

    async def active_by_user(self, guild_id: int, user_id: int) -> Registration | None:
        return next(
            (
                r
                for r in self.rows
                if r["guild_id"] == guild_id
                and r["user_id"] == user_id
                and r["state"] in ("open", "pending", "approved")
            ),
            None,
        )

    async def create_open(self, guild_id, user_id, thread_id, expires_at):
        return self._add(
            guild_id=guild_id,
            user_id=user_id,
            thread_id=thread_id,
            expires_at=expires_at,
        )

    async def reopen(self, registration_id, thread_id, expires_at):
        row = self._by_id(registration_id)
        row |= {"thread_id": thread_id, "expires_at": expires_at}
        return row

    async def submit(
        self,
        registration_id,
        tipe,
        nama,
        nama_panggilan,
        nim,
        angkatan,
        prodi,
        linkedin,
    ):
        row = self._by_id(registration_id)
        row |= {
            "state": "pending",
            "type": tipe,
            "nama": nama,
            "nama_panggilan": nama_panggilan,
            "nim": nim,
            "angkatan": angkatan,
            "prodi": prodi,
            "linkedin": linkedin,
        }
        return row

    async def by_thread(self, thread_id):
        return next((r for r in self.rows if r["thread_id"] == thread_id), None)

    async def by_report_message(self, message_id):
        return next(
            (r for r in self.rows if r["report_message_id"] == message_id), None
        )

    async def set_report_message(self, registration_id, message_id) -> None:
        self._by_id(registration_id)["report_message_id"] = message_id

    async def decide(self, registration_id, state, reviewed_by, reason):
        row = self._by_id(registration_id)
        if row["state"] != "pending":
            return None  # verifikator lain sudah menang
        row |= {"state": state, "reviewed_by": reviewed_by, "reject_reason": reason}
        return row

    async def attempt_count(self, guild_id, user_id) -> int:
        return sum(
            r["guild_id"] == guild_id and r["user_id"] == user_id for r in self.rows
        )

    async def nim_holder(self, guild_id, nim):
        return next(
            (
                r["user_id"]
                for r in self.rows
                if r["guild_id"] == guild_id
                and r["nim"] == nim
                and r["state"] == "approved"
            ),
            None,
        )

    async def clear_thread(self, thread_id) -> None:
        for r in self.rows:
            if r["thread_id"] == thread_id:
                r["thread_id"] = None


def service() -> tuple[RegistrationService, FakeRepo]:
    repo = FakeRepo()
    return RegistrationService(repo), repo


async def test_start_fresh_when_no_active_row():
    svc, _ = service()
    assert await svc.start(5, 1, NOW) == ("fresh", None)


async def test_start_reuses_live_open_thread():
    svc, repo = service()
    await svc.open_thread(5, 1, thread_id=99, now=NOW)
    action, reg = await svc.start(5, 1, NOW + timedelta(minutes=14))
    assert action == "reuse"
    assert reg["thread_id"] == 99


async def test_start_recreates_when_ttl_lewat():
    svc, _ = service()
    await svc.open_thread(5, 1, thread_id=99, now=NOW)
    action, reg = await svc.start(5, 1, NOW + timedelta(minutes=16))
    assert action == "expired_recreate"
    assert reg["id"] == 1  # baris lama dipakai ulang, bukan baris kedua


async def test_start_recreates_when_thread_sudah_disapu():
    svc, repo = service()
    await svc.open_thread(5, 1, thread_id=99, now=NOW)
    await svc.clear_thread(99)
    action, _ = await svc.start(5, 1, NOW)  # TTL masih hidup, threadnya tidak
    assert action == "expired_recreate"


async def test_start_wait_and_already():
    svc, repo = service()
    reg = await svc.open_thread(5, 1, thread_id=99, now=NOW)
    await svc.submit(reg["id"], "alumni", "Rizky R", "Rizky", "2021", linkedin="x")
    assert (await svc.start(5, 1, NOW))[0] == "wait"
    await svc.decide(reg["id"], approve=True, reviewed_by=7)
    assert (await svc.start(5, 1, NOW))[0] == "already"


async def test_rejected_orang_boleh_daftar_lagi():
    svc, repo = service()
    reg = await svc.open_thread(5, 1, thread_id=99, now=NOW)
    await svc.submit(reg["id"], "alumni", "Rizky R", "Rizky", "2021", linkedin="x")
    await svc.decide(reg["id"], approve=False, reviewed_by=7, reason="foto buram")
    assert await svc.start(5, 1, NOW) == ("fresh", None)
    assert await svc.attempt_count(5, 1) == 1  # percobaan berikutnya jadi ke-2


async def test_decide_kedua_kalah_balapan():
    svc, repo = service()
    reg = await svc.open_thread(5, 1, thread_id=99, now=NOW)
    await svc.submit(reg["id"], "alumni", "Rizky R", "Rizky", "2021", linkedin="x")
    assert await svc.decide(reg["id"], approve=True, reviewed_by=7) is not None
    assert await svc.decide(reg["id"], approve=False, reviewed_by=8) is None
    assert repo.rows[0]["reviewed_by"] == 7  # pemenang tidak ditimpa


async def test_submit_menormalkan_nim():
    svc, repo = service()
    reg = await svc.open_thread(5, 1, thread_id=99, now=NOW)
    await svc.submit(
        reg["id"],
        "mahasiswa",
        " Rizky R ",
        " Rizky ",
        "2021",
        nim=" a1b2c3d4 ",
        prodi="d3-ti",
    )
    assert repo.rows[0]["nim"] == "A1B2C3D4"
    assert repo.rows[0]["nama"] == "Rizky R"


async def test_nim_holder_hanya_lihat_approved():
    svc, repo = service()
    reg = await svc.open_thread(5, 1, thread_id=99, now=NOW)
    await svc.submit(
        reg["id"],
        "mahasiswa",
        "Rizky R",
        "Rizky",
        "2021",
        nim="A1B2C3D4",
        prodi="d3-ti",
    )
    assert await svc.nim_holder(5, "A1B2C3D4") is None  # masih pending
    await svc.decide(reg["id"], approve=True, reviewed_by=7)
    assert await svc.nim_holder(5, "A1B2C3D4") == 1


def test_normalize_nim():
    assert normalize_nim(" a1b2 ") == "A1B2"
    assert normalize_nim("  ") is None  # alumni tanpa NIM tidak bentrok di indeks unik
    assert normalize_nim(None) is None


def test_validate_angkatan():
    assert validate_angkatan("2021", NOW) is None
    assert validate_angkatan("2026", NOW) is None  # tahun berjalan masuk
    assert validate_angkatan("2027", NOW) is not None
    assert validate_angkatan("1999", NOW) is not None
    assert validate_angkatan("20a1", NOW) is not None


def test_nickname():
    base = {"nama_panggilan": "Rizky", "prodi": "d3-ti", "type": "mahasiswa"}
    assert nickname(base) == "[D3-TI]Rizky"
    assert nickname(base | {"type": "alumni", "prodi": None}) == "[ALUMNI]Rizky"
    long = base | {"nama_panggilan": "R" * 24, "prodi": "teknologi-informasi"}
    assert len(nickname(long)) == 32
