from typing import TYPE_CHECKING, NamedTuple, TypedDict

if TYPE_CHECKING:
    from datetime import datetime


class Keyword(TypedDict):
    """One `moderation_keywords` row."""

    id: int
    label: str
    term: str  # as typed, for display
    normalized: str  # what the automaton holds
    enabled: bool
    created_by: int | None
    created_at: datetime


class RegexRule(TypedDict):
    """One `moderation_regex_rules` row."""

    id: int
    label: str
    pattern: str
    target: str  # raw | normalized
    note: str | None
    enabled: bool
    created_by: int | None  # NULL = seeded by the migration
    created_at: datetime


class HitContext(NamedTuple):
    """Who said what, where. Bundled so the identity of a message travels as
    one value from the handler down to the INSERT."""

    guild_id: int
    channel_id: int
    message_id: int
    author_id: int
    content: str
    source: str  # create | edit


class Match(NamedTuple):
    """One reason a message was flagged. A message may produce several, across
    several labels — that is what `moderation_hit_matches` stores."""

    label: str
    rule_kind: str  # keyword | regex
    rule_id: int
    matched_term: str
