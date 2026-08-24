"""Only discovered on a live server: a modal over the component limit, and a
non-persistent view — restart the bot and every old button replies "This
interaction failed" with no sign in the UI."""

from warden.config import Config
from warden.features.registration.views.onboard_me_view import OnboardMeView
from warden.features.registration.views.pilih_tipe_view import PilihTipeView
from warden.features.registration.views.registrasi_modal import RegistrasiModal
from warden.features.registration.views.review_view import ReviewView

CONFIG = Config(
    discord_token="t",
    onboarding_enabled=False,
    database_url="postgres://x",
    registration_enabled=True,
    registration_locket_channel_id=1,
    registration_report_channel_id=2,
    registration_verifier_role_id=3,
    registration_mahasiswa_role_id=4,
    registration_alumni_role_id=5,
    registration_prodi_roles={"d3-ti": 333, "d3-tk": 444},
    log_level="INFO",
)
REG = {"id": 1, "guild_id": 5, "user_id": 9, "prodi": None}


def test_semua_view_persistent_dan_custom_id_stabil():
    views = [
        OnboardMeView(None, CONFIG),
        PilihTipeView(None, CONFIG),
        ReviewView(None, CONFIG),
    ]
    assert all(v.is_persistent() for v in views)
    assert [c.custom_id for v in views for c in v.children] == [
        "registration:start",
        "registration:mahasiswa",
        "registration:alumni",
        "registration:approve",
        "registration:reject",
        "registration:join",
    ]


def test_modal_pas_di_batas_lima_komponen():
    for tipe in ("mahasiswa", "alumni"):
        modal = RegistrasiModal(None, CONFIG, REG, tipe)
        assert len(modal.to_components()) == 5


def test_isi_ulang_membawa_ketikan_lama():
    modal = RegistrasiModal(None, CONFIG, REG, "mahasiswa")
    modal.nama._value = "Muhammad Rizky"
    modal.angkatan._value = "20a1"
    assert modal.refill().nama.value == "Muhammad Rizky"
