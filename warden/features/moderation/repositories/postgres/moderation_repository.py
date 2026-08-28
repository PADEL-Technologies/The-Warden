import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

    from warden.features.moderation.entities.moderation import (
        HitContext,
        Keyword,
        Match,
        RegexRule,
    )

log = logging.getLogger(__name__)


class PostgresModerationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def active_keywords(self) -> list[Keyword]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM moderation_keywords WHERE enabled ORDER BY id"
            )
        return [dict(r) for r in rows]  # type: ignore[misc]

    async def active_rules(self) -> list[RegexRule]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM moderation_regex_rules WHERE enabled ORDER BY id"
            )
        return [dict(r) for r in rows]  # type: ignore[misc]

    async def add_keywords(
        self, label: str, terms: list[tuple[str, str]], created_by: int
    ) -> list[tuple[str, str, bool]]:
        # Terms are logged at DEBUG only: a bulk add carries the whole word
        # list, and that list is what the filter is.
        log.debug(
            "moderation_repo: add_keywords",
            extra={"label": label, "count": len(terms)},
        )
        # `xmax = 0` is the standard way to tell an INSERT apart from the
        # UPDATE branch of ON CONFLICT — the alternative is a SELECT first,
        # which races against a second admin running the same command.
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                INSERT INTO moderation_keywords (label, term, normalized, created_by)
                SELECT $1, t.term, t.normalized, $4
                FROM unnest($2::text[], $3::text[]) AS t(term, normalized)
                ON CONFLICT (label, normalized)
                DO UPDATE SET enabled = true
                RETURNING normalized, term, (xmax = 0) AS was_new
                """,
                label,
                [t for t, _ in terms],
                [n for _, n in terms],
                created_by,
            )
        return [(r["normalized"], r["term"], r["was_new"]) for r in rows]

    async def remove_keywords(
        self, label: str, normalized: list[str]
    ) -> list[tuple[str, str]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "UPDATE moderation_keywords SET enabled = false "
                "WHERE label = $1 AND normalized = ANY($2::text[]) AND enabled "
                "RETURNING normalized, term",
                label,
                normalized,
            )
        return [(r["normalized"], r["term"]) for r in rows]

    async def list_keywords(
        self, label: str | None, include_disabled: bool
    ) -> list[Keyword]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM moderation_keywords "
                "WHERE ($1::text IS NULL OR label = $1) "
                "AND (enabled OR $2) ORDER BY label, term",
                label,
                include_disabled,
            )
        return [dict(r) for r in rows]  # type: ignore[misc]

    async def add_rule(
        self, label: str, pattern: str, target: str, note: str | None, created_by: int
    ) -> RegexRule | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO moderation_regex_rules
                    (label, pattern, target, note, created_by)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (label, pattern) DO NOTHING
                RETURNING *
                """,
                label,
                pattern,
                target,
                note,
                created_by,
            )
        return dict(row) if row is not None else None  # type: ignore[return-value]

    async def remove_rule(self, rule_id: int) -> RegexRule | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE moderation_regex_rules SET enabled = false "
                "WHERE id = $1 AND enabled RETURNING *",
                rule_id,
            )
        return dict(row) if row is not None else None  # type: ignore[return-value]

    async def list_rules(
        self, label: str | None, include_disabled: bool
    ) -> list[RegexRule]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM moderation_regex_rules "
                "WHERE ($1::text IS NULL OR label = $1) "
                "AND (enabled OR $2) ORDER BY label, id",
                label,
                include_disabled,
            )
        return [dict(r) for r in rows]  # type: ignore[misc]

    async def counts(self) -> dict[str, tuple[int, int]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT label,
                       count(*) FILTER (WHERE kind = 'keyword') AS keywords,
                       count(*) FILTER (WHERE kind = 'regex')   AS rules
                FROM (
                    SELECT label, 'keyword' AS kind FROM moderation_keywords
                    WHERE enabled
                    UNION ALL
                    SELECT label, 'regex' FROM moderation_regex_rules WHERE enabled
                ) x
                GROUP BY label
                """
            )
        return {r["label"]: (r["keywords"], r["rules"]) for r in rows}

    async def record_hit(
        self,
        ctx: HitContext,
        normalized: str,
        enforced: bool,
        matches: list[Match],
    ) -> int:
        # One statement, not two in a transaction: the matches are derived from
        # the hit that was just written, so "hit with no reason attached" cannot
        # happen even if the connection drops midway. Same shape as
        # registration_repository.decide().
        #
        # No params logged: `content` is the member's message.
        log.debug(
            "moderation_repo: record_hit",
            extra={"message_id": ctx.message_id, "matches": len(matches)},
        )
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                """
                WITH h AS (
                    INSERT INTO moderation_hits
                        (guild_id, channel_id, message_id, author_id,
                         content, normalized, source, enforced)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                ), m AS (
                    INSERT INTO moderation_hit_matches
                        (hit_id, label, rule_kind, rule_id, matched_term)
                    SELECT h.id, t.label, t.kind, t.rule_id, t.term
                    FROM h, unnest($9::text[], $10::text[], $11::bigint[], $12::text[])
                             AS t(label, kind, rule_id, term)
                )
                SELECT id FROM h
                """,
                ctx.guild_id,
                ctx.channel_id,
                ctx.message_id,
                ctx.author_id,
                ctx.content,
                normalized,
                ctx.source,
                enforced,
                [m.label for m in matches],
                [m.rule_kind for m in matches],
                [m.rule_id for m in matches],
                [m.matched_term for m in matches],
            )
