from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from warden.features.moderation.entities.moderation import (
        HitContext,
        Keyword,
        Match,
        RegexRule,
    )


class ModerationRepository(Protocol):
    async def active_keywords(self) -> list[Keyword]:
        """Everything the automaton is built from."""
        ...

    async def active_rules(self) -> list[RegexRule]:
        """Everything the regex pass is built from."""
        ...

    async def add_keywords(
        self, label: str, terms: list[tuple[str, str]], created_by: int
    ) -> list[tuple[str, str, bool]]:
        """`terms` is `(term, normalized)`. Returns `(normalized, term, was_new)`
        per row. `normalized` comes back because it is the conflict key: on
        conflict the stored `term` wins, which may differ in case from what was
        typed, so it is the wrong thing to match results up by."""
        ...

    async def remove_keywords(
        self, label: str, normalized: list[str]
    ) -> list[tuple[str, str]]:
        """Soft: sets `enabled = false`. Returns `(normalized, term)` of the rows
        actually turned off, so the caller can name the ones not found."""
        ...

    async def list_keywords(
        self, label: str | None, include_disabled: bool
    ) -> list[Keyword]: ...

    async def add_rule(
        self, label: str, pattern: str, target: str, note: str | None, created_by: int
    ) -> RegexRule | None:
        """None = a rule with that pattern already exists for that label."""
        ...

    async def remove_rule(self, rule_id: int) -> RegexRule | None:
        """Soft, by id — patterns are painful to retype. None = no such
        enabled rule."""
        ...

    async def list_rules(
        self, label: str | None, include_disabled: bool
    ) -> list[RegexRule]: ...

    async def counts(self) -> dict[str, tuple[int, int]]:
        """`{label: (keywords, rules)}`, enabled only — for `/label list`."""
        ...

    async def record_hit(
        self,
        ctx: HitContext,
        normalized: str,
        enforced: bool,
        matches: list[Match],
    ) -> int:
        """Writes the hit and all its matches in one statement, so a dropped
        connection can never leave a hit with no reasons attached. Returns the
        hit id for the log line."""
        ...
