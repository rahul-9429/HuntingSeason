import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Any

_LEVELS = {"WARNING": "warn", "CRITICAL": "error"}

_RECORD_FIELDS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "color_message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "message": record.getMessage(),
            "level": _LEVELS.get(record.levelname, record.levelname.lower()),
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "logger": record.name,
        }
        if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, http_version, status_code = record.args
            entry.update(
                client=client,
                method=method,
                path=path,
                http_version=http_version,
                status_code=status_code,
            )
        for key, value in vars(record).items():
            if key not in _RECORD_FIELDS:
                entry.setdefault(key, value)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                },
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {
                name: {"handlers": [], "propagate": True}
                for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
            },
        }
    )
