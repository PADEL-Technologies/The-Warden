"""Text canonicalisation, run before any matching.

The direction here is *decode*: `jud0l` → `judol`, not the other way round.
Keywords go through the exact same functions at insert time, so what the
automaton holds and what it is fed always agree."""

import re
import unicodedata

# Only unambiguous shapes. `6`→`g` and `2`→`z` are left out on purpose: they
# collide with ordinary Indonesian shorthand ("jam 6", "orang 2").
LEET = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "|": "l",
        "!": "i",
    }
)

# Runs of 3+, not 2+: "juuudol" collapses to "judol" while "maaf", "saat" and
# "keeper" survive untouched.
_RUNS = re.compile(r"(.)\1{2,}")
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Casefold, strip accents, decode leet, collapse repeated characters.
    Separators are kept, so word boundaries still exist afterwards."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _RUNS.sub(r"\1", stripped.casefold().translate(LEET))


def squeeze(normalized: str) -> str:
    """Everything that is not a letter or digit removed, so `j u d o l` and
    `j-u-d-o-l` become `judol`. Word boundaries are gone here by design —
    that is why only long keywords are matched against this (see matcher.py)."""
    return _SEPARATORS.sub("", normalized)
