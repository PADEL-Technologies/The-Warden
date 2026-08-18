import warden.bot


def test_feature_modules_discovers_ping():
    assert "warden.features.ping" in warden.bot.feature_modules()
