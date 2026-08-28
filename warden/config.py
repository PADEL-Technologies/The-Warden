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
    moderation_enabled: bool
    moderation_admin_role_ids: list[int]
    moderation_ignored_channel_ids: list[int]
    moderation_warning_delete_after: int
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
    """Required when the feature is on: fail at startup, not silently on first click."""
    return int(os.environ[name]) if enabled else 0


def _id_list(raw: str) -> list[int]:
    """`111,222` → `[111, 222]`. Empty string → empty list."""
    return [int(p.strip()) for p in raw.split(",") if p.strip()]


def load_config() -> Config:
    registration = _flag("REGISTRATION_ENABLED")
    moderation = _flag("MODERATION_ENABLED")
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
        moderation_enabled=moderation,
        # No admin roles = nobody can register a keyword and nobody is exempt
        # from the filter. Fail at startup rather than ship a mute bot.
        moderation_admin_role_ids=_id_list(
            os.environ["MODERATION_ADMIN_ROLE_IDS"] if moderation else ""
        ),
        moderation_ignored_channel_ids=_id_list(
            os.environ.get("MODERATION_IGNORED_CHANNEL_IDS", "")
        ),
        moderation_warning_delete_after=int(
            os.environ.get("MODERATION_WARNING_DELETE_AFTER", "15")
        ),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
