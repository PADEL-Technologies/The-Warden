from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from warden.features.moderation.entities.moderation import (
        HitContext,
        Keyword,
        RegexRule,
    )
    from warden.features.moderation.services.moderation_service import Verdict


class ModerationService(Protocol):
    async def reload(self) -> None:
        """Rebuild the matcher from the database. Called at startup and after
        every command that writes."""
        ...

    def evaluate(self, content: str) -> Verdict:
        """Pure, no I/O — the hot path runs this on every message and only
        touches the database when something matched."""
        ...

    async def record(self, ctx: HitContext, verdict: Verdict) -> int: ...

    async def add_keywords(
        self, label: str, raw: str, created_by: int
    ) -> tuple[list[str], list[str], list[str]]:
        """`raw` is the comma-separated input. Returns
        `(added, already_there, reactivated)`."""
        ...

    async def remove_keywords(
        self, label: str, raw: str
    ) -> tuple[list[str], list[str]]:
        """Returns `(removed, not_found)`."""
        ...

    async def list_keywords(
        self, label: str | None, include_disabled: bool
    ) -> list[Keyword]: ...

    async def add_rule(
        self, label: str, pattern: str, target: str, note: str | None, created_by: int
    ) -> RegexRule | None: ...

    async def remove_rule(self, rule_id: int) -> RegexRule | None: ...

    async def list_rules(
        self, label: str | None, include_disabled: bool
    ) -> list[RegexRule]: ...

    async def counts(self) -> dict[str, tuple[int, int]]: ...
