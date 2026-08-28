import logging
import re
from typing import TYPE_CHECKING, NamedTuple

from warden.features.moderation.services.labels import ENFORCED_LABELS, worst
from warden.features.moderation.services.matcher import Matcher
from warden.features.moderation.services.normalizer import normalize

if TYPE_CHECKING:
    from warden.features.moderation.entities.moderation import (
        HitContext,
        Keyword,
        Match,
        RegexRule,
    )
    from warden.features.moderation.repositories.protocol import ModerationRepository

log = logging.getLogger(__name__)

PATTERN_MAX_LEN = 200


class Verdict(NamedTuple):
    normalized: str
    matches: list[Match]
    labels: set[str]
    enforced: bool
    warning_label: str | None  # which label the public warning speaks about


def parse_terms(raw: str) -> list[str]:
    """Comma-separated input, order preserved, duplicates within the input
    dropped. One code path for a single term and for a hundred — they differ
    only by whether a comma is present."""
    seen: dict[str, None] = {}
    for part in raw.split(","):
        term = part.strip()
        if term:
            seen.setdefault(term, None)
    return list(seen)


def _unbounded_at(pattern: str, i: int) -> bool:
    """Is there a `*`, `+` or `{n,}` at position `i`? `?` and `{n,m}` are
    bounded and cannot blow up."""
    if i >= len(pattern):
        return False
    if pattern[i] in "*+":
        return True
    if pattern[i] == "{":
        end = pattern.find("}", i)
        return end != -1 and pattern[i + 1 : end].endswith(",")
    return False


def _has_unbounded(fragment: str) -> bool:
    """Any unbounded quantifier outside a character class. `[a+]` is a literal
    plus sign, not a repetition."""
    i, in_class = 0, False
    while i < len(fragment):
        char = fragment[i]
        if char == "\\":
            i += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif _unbounded_at(fragment, i):
            return True
        i += 1
    return False


def nested_quantifier(pattern: str) -> bool:
    """`(a+)+`, `(a*)*`, `((a+)+)+` — a repeated group that already repeats
    inside. This is the shape behind essentially every accidental ReDoS.

    Checked statically rather than by timing the pattern against a probe
    string: `re` cannot be interrupted, so a pattern that blows up would leave
    a thread burning a core until the process dies, and would hang shutdown.
    There is no probe length that is safe — `((a+)+)+` is astronomical at
    twenty characters.

    ponytail: misses overlapping alternations like `(a|a)*`, which is the
    other classic shape. Add a subprocess with a hard kill if a real one ever
    gets through — that is the only way to time a pattern safely."""
    stack: list[int] = []
    i, in_class = 0, False
    while i < len(pattern):
        char = pattern[i]
        if char == "\\":
            i += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            stack.append(i)
        elif char == ")" and stack:
            start = stack.pop()
            if _unbounded_at(pattern, i + 1) and _has_unbounded(pattern[start + 1 : i]):
                return True
        i += 1
    return False


def validate_pattern(pattern: str) -> str | None:
    """None = fine. Otherwise a message for the ephemeral reply.

    Three layers, because an admin who accidentally writes `(a+)+$` would
    otherwise hang the bot on every single message from then on."""
    if len(pattern) > PATTERN_MAX_LEN:
        return f"Pola terlalu panjang ({len(pattern)} > {PATTERN_MAX_LEN} karakter)."
    try:
        re.compile(pattern)
    except re.error as exc:
        return f"Pola tidak valid: {exc}"
    if nested_quantifier(pattern):
        return (
            "Pola ditolak: ada kuantifier bersarang seperti `(a+)+` yang bisa "
            "bikin bot hang di setiap pesan (ReDoS). Tulis ulang tanpa "
            "pengulangan di dalam pengulangan."
        )
    return None


class ModerationService:
    def __init__(self, repo: ModerationRepository) -> None:
        self._repo = repo
        self._matcher = Matcher([], [])

    async def reload(self) -> None:
        keywords = await self._repo.active_keywords()
        rules = await self._repo.active_rules()
        self._matcher = Matcher(keywords, rules)
        log.info(
            "moderation: matcher dibangun ulang",
            extra={"keywords": len(keywords), "rules": len(rules)},
        )

    def evaluate(self, content: str) -> Verdict:
        normalized, matches = self._matcher.scan(content)
        labels = {m.label for m in matches}
        warning_label = worst(labels)
        return Verdict(
            normalized=normalized,
            matches=matches,
            labels=labels,
            enforced=bool(labels & ENFORCED_LABELS),
            warning_label=warning_label,
        )

    async def record(self, ctx: HitContext, verdict: Verdict) -> int:
        return await self._repo.record_hit(
            ctx, verdict.normalized, verdict.enforced, verdict.matches
        )

    async def add_keywords(
        self, label: str, raw: str, created_by: int
    ) -> tuple[list[str], list[str], list[str]]:
        terms = parse_terms(raw)
        # Normalizing here, with the very same function the matcher feeds on,
        # is what makes "JUDOL" and "judol" one row instead of two.
        pairs = [(t, normalize(t)) for t in terms]
        pairs = [(t, n) for t, n in pairs if n]
        if not pairs:
            return [], [], []
        # Snapshot of what is currently *enabled*: the upsert cannot tell us
        # whether a conflicting row was disabled beforehand, and that is the
        # only difference between "sudah ada" and "diaktifkan kembali".
        before = {k["normalized"] for k in await self._repo.list_keywords(label, False)}
        rows = await self._repo.add_keywords(label, pairs, created_by)
        await self.reload()
        added = [term for _, term, was_new in rows if was_new]
        already = [t for n, t, new in rows if not new and n in before]
        reactivated = [t for n, t, new in rows if not new and n not in before]
        return added, already, reactivated

    async def remove_keywords(
        self, label: str, raw: str
    ) -> tuple[list[str], list[str]]:
        pairs = [(t, normalize(t)) for t in parse_terms(raw)]
        rows = await self._repo.remove_keywords(label, [n for _, n in pairs if n])
        await self.reload()
        removed_norms = {n for n, _ in rows}
        not_found = [t for t, n in pairs if n not in removed_norms]
        return [term for _, term in rows], not_found

    async def list_keywords(
        self, label: str | None, include_disabled: bool
    ) -> list[Keyword]:
        return await self._repo.list_keywords(label, include_disabled)

    async def add_rule(
        self, label: str, pattern: str, target: str, note: str | None, created_by: int
    ) -> RegexRule | None:
        rule = await self._repo.add_rule(label, pattern, target, note, created_by)
        if rule is not None:
            await self.reload()
        return rule

    async def remove_rule(self, rule_id: int) -> RegexRule | None:
        rule = await self._repo.remove_rule(rule_id)
        if rule is not None:
            await self.reload()
        return rule

    async def list_rules(
        self, label: str | None, include_disabled: bool
    ) -> list[RegexRule]:
        return await self._repo.list_rules(label, include_disabled)

    async def counts(self) -> dict[str, tuple[int, int]]:
        return await self._repo.counts()
