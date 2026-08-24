import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    discord_token: str
    onboarding_enabled: bool
    database_url: str
    registration_enabled: bool
    registration_locket_channel_id: int
    registration_report_channel_id: int
    registration_verifier_role_id: int
    registration_mahasiswa_role_id: int
    registration_alumni_role_id: int
    registration_prodi_roles: dict[str, int]
    log_level: str


def _flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def _parse_role_map(raw: str) -> dict[str, int]:
    """`d3-ti:333,d3-tk:444` → `{"d3-ti": 333, "d3-tk": 444}`."""
    return {
        k.strip(): int(v)
        for k, v in (p.split(":", 1) for p in raw.split(",") if p.strip())
    }


def _id(name: str, enabled: bool) -> int:
    """Wajib saat fiturnya hidup: lebih baik gagal di startup daripada diam
    saat orang pertama mengklik."""
    return int(os.environ[name]) if enabled else 0


def load_config() -> Config:
    registration = _flag("REGISTRATION_ENABLED")
    return Config(
        discord_token=os.environ["DISCORD_TOKEN"],
        onboarding_enabled=_flag("ONBOARDING_ENABLED"),
        database_url=os.environ["DATABASE_URL"],
        registration_enabled=registration,
        registration_locket_channel_id=_id(
            "REGISTRATION_LOCKET_CHANNEL_ID", registration
        ),
        registration_report_channel_id=_id(
            "REGISTRATION_REPORT_CHANNEL_ID", registration
        ),
        registration_verifier_role_id=_id(
            "REGISTRATION_VERIFIER_ROLE_ID", registration
        ),
        registration_mahasiswa_role_id=_id(
            "REGISTRATION_MAHASISWA_ROLE_ID", registration
        ),
        registration_alumni_role_id=_id("REGISTRATION_ALUMNI_ROLE_ID", registration),
        registration_prodi_roles=_parse_role_map(
            os.environ["REGISTRATION_PRODI_ROLES"] if registration else ""
        ),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
