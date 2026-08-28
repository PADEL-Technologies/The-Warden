from warden.features.moderation.services.normalizer import normalize, squeeze


def test_casefold_and_accents():
    assert normalize("JuDoL") == "judol"
    assert normalize("Melocotón") == "melocoton"


def test_leet_is_decoded_not_encoded():
    assert normalize("jud0l") == "judol"
    assert normalize("5l0t g4c0r") == "slot gacor"
    assert normalize("p0rn0") == "porno"


def test_collapses_runs_of_three_but_not_two():
    # Runs of 3+ are evasion; runs of 2 are ordinary Indonesian spelling.
    assert normalize("juuudol") == "judol"
    assert normalize("maaf") == "maaf"
    assert normalize("saat") == "saat"


def test_squeeze_removes_separators():
    assert squeeze(normalize("j u d o l")) == "judol"
    assert squeeze(normalize("j-u-d-o-l")) == "judol"
    assert squeeze(normalize("s.l.o.t g_a_c_o_r")) == "slotgacor"
