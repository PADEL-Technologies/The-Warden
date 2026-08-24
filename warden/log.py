import json
import logging
from datetime import UTC, datetime

# Atribut bawaan LogRecord. Apa pun di luar daftar ini datang dari `extra=` dan
# ikut rata ke top level JSON — itu yang bikin lognya bisa di-query.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Satu baris JSON per record. `message` tetap kalimat manusia, ID-nya ikut
    sebagai field lewat `extra=`."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            # waktu lokal (TZ=Asia/Jakarta di Dockerfile) dengan offset eksplisit,
            # jadi tetap tidak ambigu walau dibaca di zona lain
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            # error yang kita tangkap sendiri dilog tanpa exc_info, jadi traceback
            # di output selalu berarti "tidak ada yang menangani ini"
            payload["exc_type"] = type(record.exc_info[1]).__name__
            payload["exc_message"] = str(record.exc_info[1])
            payload["traceback"] = self.formatException(record.exc_info)
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    # Root dipatok WARNING, LOG_LEVEL hanya dinaikkan untuk warden.*: DEBUG-nya
    # discord.py dan asyncio itu lalu lintas gateway, heartbeat dan loop internal
    # yang menenggelamkan log kita. Error pihak ketiga tetap lolos lewat root.
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)
    logging.getLogger("warden").setLevel(level.upper())
