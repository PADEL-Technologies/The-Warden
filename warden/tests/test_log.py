import json
import logging
import sys

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
    assert out["message"] == "guild 7 siap"  # %-args interpolated


def test_extra_flattened_to_top_level():
    out = _record(guild_id=7, registration_id=42)
    assert out["guild_id"] == 7
    assert out["registration_id"] == 42


def test_timestamp_carries_explicit_offset():
    ts = _record()["ts"]
    assert ts[10] == "T"
    assert ts[-6] in "+-" or ts.endswith("Z")  # explicit offset, not naive time


def test_non_serializable_value_does_not_crash():
    # default=str: one odd value must not sink the whole log line
    assert _record(payload=object())["payload"].startswith("<object")


def test_exception_fields():
    try:
        raise ValueError("gagal")
    except ValueError:
        out = _record(exc_info=sys.exc_info())
    assert out["exc_type"] == "ValueError"
    assert out["exc_message"] == "gagal"
    assert "ValueError: gagal" in out["traceback"]


def test_record_without_exception_has_no_traceback_field():
    assert "traceback" not in _record()


def test_log_level_only_raises_warden_loggers():
    setup_logging("DEBUG")
    assert (
        logging.getLogger("warden.features.ping").getEffectiveLevel() == logging.DEBUG
    )
    # third parties stay at root: their DEBUG stays closed
    assert logging.getLogger("discord").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("asyncio").getEffectiveLevel() == logging.WARNING
