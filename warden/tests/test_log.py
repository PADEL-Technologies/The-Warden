import json
import logging

from warden.log import JsonFormatter, setup_logging


def _record(**extra):
    record = logging.LogRecord(
        "warden.test", logging.INFO, "f.py", 1, "guild %d siap", (7,), None
    )
    record.__dict__.update(extra)
    return json.loads(JsonFormatter().format(record))


def test_core_fields():
    out = _record()
    assert out["level"] == "INFO"
    assert out["logger"] == "warden.test"
    assert out["message"] == "guild 7 siap"  # %-args tetap diinterpolasi


def test_extra_flattened_to_top_level():
    out = _record(guild_id=7, registration_id=42)
    assert out["guild_id"] == 7
    assert out["registration_id"] == 42


def test_timestamp_carries_explicit_offset():
    ts = _record()["ts"]
    assert ts[10] == "T"
    assert ts[-6] in "+-" or ts.endswith("Z")  # offset tertulis, bukan waktu telanjang


def test_non_serializable_value_does_not_crash():
    # default=str: satu nilai aneh tidak boleh menjatuhkan seluruh baris log
    assert _record(payload=object())["payload"].startswith("<object")


def test_log_level_only_raises_warden_loggers():
    setup_logging("DEBUG")
    assert (
        logging.getLogger("warden.features.ping").getEffectiveLevel() == logging.DEBUG
    )
    # pihak ketiga tetap di root: DEBUG mereka tidak ikut terbuka
    assert logging.getLogger("discord").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("asyncio").getEffectiveLevel() == logging.WARNING
