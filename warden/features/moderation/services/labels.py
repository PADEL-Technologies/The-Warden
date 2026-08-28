"""The label taxonomy. Single source of truth for `/label list`, for validating
`/keyword add`, and for the Discord choice lists.

These strings become fastText's `__label__` classes in phase 2, so they are a
frozen constant in code rather than a table: a label that can drift away from
the trained model without a deploy is a silent footgun."""

LABELS: tuple[str, ...] = (
    "neutral",
    "negative",
    "bullying",
    "crypto",
    "judol",
    "porn",
    "sara",
    "scam",
)

# `neutral` is the absence of a hit, not something you register keywords for.
# It stays in LABELS because fastText needs it as a class.
REGISTRABLE_LABELS: tuple[str, ...] = tuple(x for x in LABELS if x != "neutral")

# Deleted on sight. These four are spam/promotion patterns: structured, high
# precision, and with no legitimate reason to be posted. `negative` and
# `bullying` are plain word lists whose context the machine never sees
# ("anjir keren!"), which is where nearly every false positive comes from — so
# they are recorded silently instead.
ENFORCED_LABELS: frozenset[str] = frozenset({"judol", "porn", "scam", "sara"})

# Most severe first: a message hitting several enforced labels is warned about
# once, using the first one found here.
SEVERITY: tuple[str, ...] = ("sara", "porn", "judol", "scam")

WARNINGS: dict[str, str] = {
    "judol": "pesanmu dihapus karena terindikasi promosi judi online.",
    "porn": "pesanmu dihapus karena terindikasi konten pornografi.",
    "scam": "pesanmu dihapus karena terindikasi penipuan atau tautan mencurigakan.",
    "sara": "pesanmu dihapus karena terindikasi ujaran yang menyinggung SARA.",
}


def worst(labels: set[str]) -> str | None:
    """The enforced label to warn about, or None when nothing is enforced."""
    return next((label for label in SEVERITY if label in labels), None)
