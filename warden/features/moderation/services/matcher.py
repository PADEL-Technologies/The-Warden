"""The detection engine: two Aho-Corasick passes over keywords plus one regex
pass. Built once from the database and cached; `ModerationService.reload()`
rebuilds it after every write. One bot instance, so there is no cross-process
cache to invalidate."""

import logging
import re
from typing import TYPE_CHECKING

import ahocorasick

from warden.features.moderation.entities.moderation import Match
from warden.features.moderation.services.normalizer import normalize, squeeze

if TYPE_CHECKING:
    from warden.features.moderation.entities.moderation import Keyword, RegexRule

log = logging.getLogger(__name__)

# Below this squeezed length a keyword is not matched against the squeezed
# text. Short words without word boundaries are exactly what produces
# "analisis" → "anal"; from five characters up, an Indonesian or English word
# is rarely a substring of an innocent one. Raise it if false positives show up
# in moderation_hits — the data is there precisely to answer that.
SQUEEZE_MIN_LEN = 5


def _at_boundary(text: str, start: int, end: int) -> bool:
    """`\\b...\\b` by hand. Cheap because it only runs on actual hits."""
    before = text[start - 1] if start > 0 else ""
    after = text[end + 1] if end + 1 < len(text) else ""
    return not before.isalnum() and not after.isalnum()


class Matcher:
    """Immutable once built. Rebuilt wholesale rather than patched — a rebuild
    is milliseconds and a partially-updated automaton is not worth reasoning
    about."""

    def __init__(self, keywords: list[Keyword], rules: list[RegexRule]) -> None:
        self._word = self._automaton(
            [(k["normalized"], self._value(k)) for k in keywords]
        )
        # The squeezed automaton is keyed on the *squeezed* keyword: the
        # haystack it scans has no separators, so a two-word keyword stored as
        # "slot gacor" could never appear in it.
        squeezed = []
        for k in keywords:
            key = squeeze(k["normalized"])
            if len(key) >= SQUEEZE_MIN_LEN:
                squeezed.append((key, self._value(k)))
        self._squeezed = self._automaton(squeezed)
        self._regexes: list[tuple[RegexRule, re.Pattern[str]]] = []
        for rule in rules:
            try:
                self._regexes.append((rule, re.compile(rule["pattern"])))
            except re.error:
                # Validated on insert, so this means the row predates the check
                # or was written by hand. Skip it; one bad row must not take the
                # whole filter down.
                log.warning(
                    "moderation: pola regex tidak bisa dikompilasi, dilewati",
                    extra={"rule_id": rule["id"], "label": rule["label"]},
                )

    @staticmethod
    def _value(keyword: Keyword) -> tuple[int, str, str]:
        """What a hit carries back: the rule id, its label, and the normalized
        term to record — never the squeezed key, which is unreadable."""
        return (keyword["id"], keyword["label"], keyword["normalized"])

    @staticmethod
    def _automaton(
        entries: list[tuple[str, tuple[int, str, str]]],
    ) -> ahocorasick.Automaton | None:
        """None when empty: `make_automaton()` on an empty trie is not usable."""
        if not entries:
            return None
        auto = ahocorasick.Automaton()
        for key, value in entries:
            auto.add_word(key, value)
        auto.make_automaton()
        return auto

    def scan(self, content: str) -> tuple[str, list[Match]]:
        """Returns the normalized text (stored alongside the hit) and every
        match found. Deduplicated per rule: one rule firing twice in a message
        is still one reason."""
        normalized = normalize(content)
        found: dict[tuple[str, int], Match] = {}

        # Pass A: separators intact, so word boundaries can be checked.
        # Catches "jud0l", "juuudol", "JUDOL".
        if self._word is not None:
            for end, (kid, label, norm) in self._word.iter(normalized):
                start = end - len(norm) + 1
                if _at_boundary(normalized, start, end):
                    found[("keyword", kid)] = Match(label, "keyword", kid, norm)

        # Pass B: separators removed, no boundaries to check. Long keywords
        # only. Catches "j u d o l", "s-l-o-t g-a-c-o-r".
        if self._squeezed is not None:
            for _end, (kid, label, norm) in self._squeezed.iter(squeeze(normalized)):
                found[("keyword", kid)] = Match(label, "keyword", kid, norm)

        for rule, pattern in self._regexes:
            target = normalized if rule["target"] == "normalized" else content
            match = pattern.search(target)
            if match is not None:
                found[("regex", rule["id"])] = Match(
                    rule["label"], "regex", rule["id"], match.group(0)
                )

        return normalized, list(found.values())
