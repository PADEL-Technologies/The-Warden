from warden.features.moderation.services.matcher import Matcher
from warden.features.moderation.services.normalizer import normalize


def kw(id_: int, label: str, term: str):
    return {
        "id": id_,
        "label": label,
        "term": term,
        "normalized": normalize(term),
        "enabled": True,
        "created_by": None,
        "created_at": None,
    }


def rule(id_: int, label: str, pattern: str, target: str = "raw"):
    return {
        "id": id_,
        "label": label,
        "pattern": pattern,
        "target": target,
        "note": None,
        "enabled": True,
        "created_by": None,
        "created_at": None,
    }


def labels(matcher: Matcher, text: str) -> set[str]:
    _, matches = matcher.scan(text)
    return {m.label for m in matches}


def test_empty_matcher_matches_nothing():
    normalized, matches = Matcher([], []).scan("apa saja")
    assert normalized == "apa saja"
    assert matches == []


def test_word_boundary_stops_scunthorpe():
    matcher = Matcher([kw(1, "porn", "anal"), kw(2, "negative", "las")], [])
    # Both are substrings of ordinary Indonesian words. Neither may fire.
    assert labels(matcher, "analisis data kelas pagi") == set()
    assert labels(matcher, "kata anal itu vulgar") == {"porn"}


def test_leet_and_repeats_hit_through_normalization():
    matcher = Matcher([kw(1, "judol", "judol")], [])
    assert labels(matcher, "main JuD0L terus") == {"judol"}
    assert labels(matcher, "main juuudol terus") == {"judol"}


def test_spaced_out_evasion_needs_the_squeeze_pass():
    matcher = Matcher([kw(1, "judol", "slot gacor")], [])
    # The squeezed automaton has to be keyed on the squeezed keyword too, or a
    # two-word term can never appear in a haystack that has no separators.
    assert labels(matcher, "s l o t g a c o r hari ini") == {"judol"}


def test_five_letter_keyword_is_still_squeezed():
    matcher = Matcher([kw(1, "judol", "judol")], [])
    assert labels(matcher, "main j u d o l terus") == {"judol"}
    assert labels(matcher, "main j-u-d-0-l terus") == {"judol"}


def test_short_keywords_stay_out_of_the_squeeze_pass():
    # "anal" is 4 chars, below SQUEEZE_MIN_LEN, so the boundary-free pass must
    # not see it — otherwise "analisis" comes back as a hit.
    matcher = Matcher([kw(1, "porn", "anal")], [])
    assert labels(matcher, "analisis") == set()


def test_one_message_can_carry_several_labels():
    matcher = Matcher(
        [kw(1, "negative", "anjing")],
        [rule(2, "judol", r"\brtp\s*\d{2,3}\s*%")],
    )
    assert labels(matcher, "anjing rtp 98% gacor") == {"negative", "judol"}


def test_regex_target_picks_which_text_it_sees():
    raw_only = Matcher([], [rule(1, "scam", r"bit\.ly/\S+", "raw")])
    assert labels(raw_only, "cek bit.ly/abc123") == {"scam"}
    # Normalized text has separators intact but leet decoded, so a pattern
    # written against raw URLs would not survive being pointed at it.
    normalized_only = Matcher([], [rule(1, "judol", r"\bgacor\b", "normalized")])
    assert labels(normalized_only, "G4C0R banget") == {"judol"}


def test_one_rule_firing_twice_is_still_one_match():
    matcher = Matcher([kw(1, "negative", "anjing")], [])
    _, matches = matcher.scan("anjing anjing anjing")
    assert len(matches) == 1


def test_uncompilable_rule_is_skipped_not_fatal():
    matcher = Matcher([kw(1, "negative", "anjing")], [rule(2, "scam", "(unclosed")])
    assert labels(matcher, "dasar anjing") == {"negative"}
