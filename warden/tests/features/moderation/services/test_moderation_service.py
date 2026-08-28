import pytest

from warden.features.moderation.entities.moderation import HitContext
from warden.features.moderation.services.moderation_service import (
    ModerationService,
    parse_terms,
    validate_pattern,
)
from warden.features.moderation.services.normalizer import normalize


class FakeRepo:
    def __init__(self) -> None:
        self.keywords: list[dict] = []
        self.rules: list[dict] = []
        self.hits: list[tuple] = []
        self._next_id = 1

    def _row(self, label: str, term: str) -> dict:
        row = {
            "id": self._next_id,
            "label": label,
            "term": term,
            "normalized": normalize(term),
            "enabled": True,
            "created_by": 1,
            "created_at": None,
        }
        self._next_id += 1
        return row

    async def active_keywords(self):
        return [k for k in self.keywords if k["enabled"]]

    async def active_rules(self):
        return [r for r in self.rules if r["enabled"]]

    async def add_keywords(self, label, terms, created_by):
        out = []
        for term, norm in terms:
            existing = next(
                (
                    k
                    for k in self.keywords
                    if k["label"] == label and k["normalized"] == norm
                ),
                None,
            )
            if existing is None:
                row = self._row(label, term)
                row["created_by"] = created_by
                self.keywords.append(row)
                out.append((norm, term, True))
            else:
                existing["enabled"] = True
                out.append((norm, existing["term"], False))
        return out

    async def remove_keywords(self, label, normalized):
        out = []
        for k in self.keywords:
            if k["label"] == label and k["normalized"] in normalized and k["enabled"]:
                k["enabled"] = False
                out.append((k["normalized"], k["term"]))
        return out

    async def list_keywords(self, label, include_disabled):
        return [
            k
            for k in self.keywords
            if (label is None or k["label"] == label)
            and (k["enabled"] or include_disabled)
        ]

    async def add_rule(self, label, pattern, target, note, created_by):
        if any(r["label"] == label and r["pattern"] == pattern for r in self.rules):
            return None
        row = {
            "id": self._next_id,
            "label": label,
            "pattern": pattern,
            "target": target,
            "note": note,
            "enabled": True,
            "created_by": created_by,
            "created_at": None,
        }
        self._next_id += 1
        self.rules.append(row)
        return row

    async def remove_rule(self, rule_id):
        row = next((r for r in self.rules if r["id"] == rule_id and r["enabled"]), None)
        if row is not None:
            row["enabled"] = False
        return row

    async def list_rules(self, label, include_disabled):
        return [
            r
            for r in self.rules
            if (label is None or r["label"] == label)
            and (r["enabled"] or include_disabled)
        ]

    async def counts(self):
        return {}

    async def record_hit(self, ctx, normalized, enforced, matches):
        self.hits.append((ctx, normalized, enforced, matches))
        return len(self.hits)


CTX = HitContext(
    guild_id=5,
    channel_id=6,
    message_id=7,
    author_id=8,
    content="",
    source="create",
)


async def service_with(*terms: tuple[str, str]) -> tuple[ModerationService, FakeRepo]:
    repo = FakeRepo()
    svc = ModerationService(repo)  # type: ignore[arg-type]
    for label, term in terms:
        await svc.add_keywords(label, term, 1)
    return svc, repo


def test_parse_terms_handles_single_and_bulk_the_same_way():
    assert parse_terms("judol") == ["judol"]
    assert parse_terms("judol, slot gacor ,maxwin") == ["judol", "slot gacor", "maxwin"]
    assert parse_terms("judol, judol,  ,") == ["judol"]
    assert parse_terms("  ") == []


async def test_add_is_idempotent_and_reports_each_bucket():
    svc, _ = await service_with()
    added, already, reactivated = await svc.add_keywords("judol", "maxwin, gacor", 1)
    assert (added, already, reactivated) == (["maxwin", "gacor"], [], [])

    added, already, reactivated = await svc.add_keywords("judol", "MAXWIN", 1)
    # Normalized on the way in, so "MAXWIN" is the row that already exists
    # rather than a second one.
    assert (added, already, reactivated) == ([], ["maxwin"], [])


async def test_remove_then_readd_reactivates_rather_than_duplicates():
    svc, repo = await service_with(("judol", "maxwin"))
    removed, not_found = await svc.remove_keywords("judol", "MAXWIN, tidakada")
    assert removed == ["maxwin"]
    assert not_found == ["tidakada"]

    added, already, reactivated = await svc.add_keywords("judol", "maxwin", 1)
    assert (added, already, reactivated) == ([], [], ["maxwin"])
    assert len(repo.keywords) == 1


async def test_enforced_label_is_flagged_but_light_one_is_not():
    svc, _ = await service_with(("judol", "maxwin"), ("negative", "anjing"))

    heavy = svc.evaluate("promo maxwin hari ini")
    assert heavy.enforced is True
    assert heavy.warning_label == "judol"

    light = svc.evaluate("dasar anjing")
    assert light.matches  # still recorded
    assert light.enforced is False
    assert light.warning_label is None


async def test_warning_picks_the_most_severe_label():
    svc, _ = await service_with(("judol", "maxwin"), ("sara", "katarasis"))
    verdict = svc.evaluate("maxwin katarasis")
    assert verdict.labels == {"judol", "sara"}
    assert verdict.warning_label == "sara"


async def test_clean_message_costs_no_database_round_trip():
    svc, repo = await service_with(("judol", "maxwin"))
    assert svc.evaluate("halo semua").matches == []
    assert repo.hits == []


async def test_record_writes_hit_with_every_match():
    svc, repo = await service_with(("judol", "maxwin"), ("negative", "anjing"))
    verdict = svc.evaluate("maxwin anjing")
    hit_id = await svc.record(CTX._replace(content="maxwin anjing"), verdict)
    assert hit_id == 1
    ctx, normalized, enforced, matches = repo.hits[0]
    assert ctx.source == "create"
    assert normalized == "maxwin anjing"
    assert enforced is True
    assert {m.label for m in matches} == {"judol", "negative"}


async def test_rule_add_is_rejected_when_the_pattern_already_exists():
    svc, _ = await service_with()
    assert await svc.add_rule("scam", r"bit\.ly/\S+", "raw", None, 1) is not None
    assert await svc.add_rule("scam", r"bit\.ly/\S+", "raw", None, 1) is None


async def test_removing_a_rule_takes_it_out_of_the_matcher():
    svc, _ = await service_with()
    rule = await svc.add_rule("judol", r"\bmaxwin\b", "normalized", None, 1)
    assert rule is not None
    assert svc.evaluate("promo maxwin").labels == {"judol"}
    await svc.remove_rule(rule["id"])
    assert svc.evaluate("promo maxwin").matches == []


@pytest.mark.parametrize(
    "pattern",
    ["(unclosed", "a" * 201, r"(a+)+$", r"(a*)*$", r"((a+)+)+$", r"(\w+){2,}"],
    ids=["uncompilable", "too_long", "redos", "redos_star", "redos_deep", "redos_open"],
)
def test_bad_patterns_are_rejected(pattern: str):
    assert validate_pattern(pattern) is not None


@pytest.mark.parametrize(
    "pattern",
    [
        r"\b(?:bit\.ly|s\.id)/\S+",
        r"\b(?:wa|whatsapp|hub(?:ungi)?)\W{0,3}(?:0|\+?62)8\d{7,11}\b",
        r"\b[a-z]{3,12}(?:88|99|4d)\b",
        r"[a+]+",  # a character class, not a nested repetition
    ],
)
def test_real_patterns_are_not_false_positives(pattern: str):
    # Every seeded rule has to survive this check, or the migration installs
    # rules that /regex add would refuse.
    assert validate_pattern(pattern) is None
