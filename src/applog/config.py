import logging.config
from pathlib import Path

from .context import RequestIdFilter

DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(request_id)s | "
    "%(name)s:%(lineno)d %(funcName)s | %(message)s"
)

# Loggers that are noisy or cause feedback loops. Override via `quiet=`.
DEFAULT_QUIET = {
    "watchfiles": "WARNING",
    "sqlalchemy.engine": "WARNING",
    "uvicorn.access": "WARNING",
}


def setup_logging(
    level: str = "INFO",
    log_dir: str | Path = "logs",
    fmt: str = DEFAULT_FORMAT,
    to_console: bool = True,
    to_file: bool = True,
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
    quiet: dict[str, str] | None = None,
    capture_uvicorn: bool = True,
) -> None:
    """Configure logging once, at app startup. Every module then just does
    `log = logging.getLogger(__name__)`."""
    handlers: dict[str, dict] = {}

    if to_console:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "filters": ["request_id"],
        }

    if to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_opts = {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8",
            "formatter": "detailed",
            "filters": ["request_id"],
        }
        handlers["file"] = {**file_opts, "filename": str(log_path / "app.log")}
        handlers["error_file"] = {
            **file_opts,
            "filename": str(log_path / "errors.log"),
            "level": "ERROR",
        }

    loggers: dict[str, dict] = {
        name: {"level": lvl} for name, lvl in {**DEFAULT_QUIET, **(quiet or {})}.items()
    }
    if capture_uvicorn:  # route uvicorn's logs through our handlers/format
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            loggers.setdefault(name, {}).update({"handlers": [], "propagate": True})

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"request_id": {"()": RequestIdFilter}},
        "formatters": {"detailed": {"format": fmt}},
        "handlers": handlers,
        "root": {"level": level, "handlers": list(handlers)},
        "loggers": loggers,
    })