import gzip
import logging
import logging.handlers
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_DIR = Path(os.getenv("LOG_DIR", "logs")) # configurable log directory, default is "logs"
LOG_FILE = LOG_DIR / "app.log"                #configurable log file name, default is "app.log"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()#finding the log level from environment variable, default is "INFO"

# Rotate when the file reaches this size.
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))  # 10 MB

# Number of rotated files to keep.
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 7))


# ---------------------------------------------------------------------------
# Sensitive data protection
# ---------------------------------------------------------------------------
SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "secret",
    "database_url",
}
def _redact(value: Any) -> Any:
    """
    Recursively remove sensitive values before they reach the logs.
    """

    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact(val)
            for key, val in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]

    return value


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """
    Converts Python LogRecords into structured JSON logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created
        ).astimezone().isoformat()

        log_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Optional contextual fields.
        context_fields = (
            "request_id",
            "case_id",
            "user_id",
            "stage",
            "agent",
            "event",
            "status",
            "duration_ms",
            "error_code",
        )

        for field in context_fields:
            value = getattr(record, field, None)

            if value is not None:
                log_data[field] = value

        # Include exception information when available.
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        log_data = _redact(log_data)

        import json

        return json.dumps(
            log_data,
            ensure_ascii=False,
            default=str,
        )


# ---------------------------------------------------------------------------
# Compressed rotating file handler
# ---------------------------------------------------------------------------

class CompressedRotatingFileHandler(
    logging.handlers.RotatingFileHandler
):
    """
    Rotates logs based on file size and compresses old logs using gzip.
    """

    def doRollover(self) -> None:
        super().doRollover()

        # Compress the newly rotated log.
        rotated_file = Path(f"{self.baseFilename}.1")

        if not rotated_file.exists():
            return

        compressed_file = Path(f"{rotated_file}.gz")

        try:
            with rotated_file.open("rb") as source:
                with gzip.open(compressed_file, "wb") as destination:
                    shutil.copyfileobj(source, destination)

            rotated_file.unlink()

        except OSError:
            # Logging should never crash the application.
            pass


# ---------------------------------------------------------------------------
# Logger configuration
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """
    Configure application-wide structured JSON logging.

    Should be called once when the FastAPI application starts.
    """

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = JSONFormatter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Rotating file handler
    file_handler = CompressedRotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    file_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()

    root_logger.setLevel(LOG_LEVEL)

    # Prevent duplicate handlers if configure_logging()
    # is accidentally called more than once.
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noisy third-party logs.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(LOG_LEVEL)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a logger for a module/service.
    """

    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# FATAL helper
# ---------------------------------------------------------------------------

def fatal(
    logger: logging.Logger,
    message: str,
    **context: Any,
) -> None:
    """
    Log a FATAL-level event.

    Python's logging module calls this level CRITICAL.
    """

    logger.critical(
        message,
        extra=_redact(context),
    )