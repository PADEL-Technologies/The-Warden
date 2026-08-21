from warden.features.ping.services.ping_service import PingService


def test_format_latency():
    assert PingService().format_latency(0.0123) == "12 ms"
