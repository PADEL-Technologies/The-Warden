import json
import logging
from datetime import UTC, datetime

# Builtin LogRecord attributes. Anything outside this set comes from `extra=`
# and is flattened to top-level JSON — that's what makes logs queryable.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON line per record. `message` stays human-readable; IDs ride along
    as fields via `extra=`."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            # local time with explicit offset, unambiguous in any timezone
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            # errors we catch ourselves are logged without exc_info, so a
            # traceback here always means "nothing handled this"
            payload["exc_type"] = type(record.exc_info[1]).__name__
            payload["exc_message"] = str(record.exc_info[1])
            payload["traceback"] = self.formatException(record.exc_info)
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    # Root stays WARNING; LOG_LEVEL only raises warden.*: discord.py/asyncio
    # DEBUG traffic is gateway noise that would drown ours. Third-party errors
    # still surface via root.
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)
    logging.getLogger("warden").setLevel(level.upper())
