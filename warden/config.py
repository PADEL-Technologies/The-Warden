import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    discord_token: str
    onboarding_enabled: bool
    database_url: str


def load_config() -> Config:
    return Config(
        discord_token=os.environ["DISCORD_TOKEN"],
        onboarding_enabled=os.environ.get("ONBOARDING_ENABLED", "true").lower()
        in ("1", "true", "yes"),
        database_url=os.environ["DATABASE_URL"],
    )
