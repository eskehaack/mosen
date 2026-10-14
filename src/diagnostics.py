"""Small, bounded diagnostic log for local support."""

from datetime import datetime
import io
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import zipfile


LOGGER_NAME = "swampmachine"
LOG_DIRECTORY = Path("swamp_logs")
LOG_FILENAME = "swampmachine.log"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 1


_handler: RotatingFileHandler | None = None
_configuration_error: str | None = None


class _KeepAppAndExternalErrors(logging.Filter):
    def filter(self, record):
        return record.name.startswith(LOGGER_NAME) or record.levelno >= logging.ERROR


def configure_logging(
    log_directory=LOG_DIRECTORY,
    *,
    max_bytes=MAX_LOG_BYTES,
):
    """Configure logging once and let the app continue if the disk is unavailable."""
    global _handler, _configuration_error

    if _handler is not None:
        return True

    try:
        directory = Path(log_directory)
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / LOG_FILENAME,
            maxBytes=max_bytes,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.addFilter(_KeepAppAndExternalErrors())
    except Exception as error:
        _configuration_error = f"{type(error).__name__}: {error}"
        return False

    app_logger = logging.getLogger(LOGGER_NAME)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    app_logger.addHandler(handler)
    logging.getLogger().addHandler(handler)

    _handler = handler
    _configuration_error = None
    app_logger.info(
        "diagnostic_logging_started max_bytes=%s backup_count=%s",
        max_bytes,
        BACKUP_COUNT,
    )
    return True


def log_displayed_error(source, message, error=None):
    """Record a visible error without recording callback arguments."""
    logger = logging.getLogger(f"{LOGGER_NAME}.errors")
    error_type = type(error).__name__ if error is not None else "DisplayedError"
    traceback = error.__traceback__ if error is not None else None
    log = logger.error if traceback is not None else logger.warning
    log(
        "displayed_error source=%s type=%s message=%s",
        source,
        error_type,
        message,
        exc_info=(type(error), error, traceback) if traceback is not None else None,
    )


def _log_paths():
    current = Path(_handler.baseFilename)
    return [current] + [
        Path(f"{current}.{index}")
        for index in range(1, _handler.backupCount + 1)
    ]


def get_diagnostics_status():
    if _handler is None:
        error = _configuration_error or "Logging has not been initialized."
        return f"Logging unavailable: {error}", False

    _handler.acquire()
    try:
        _handler.flush()
        paths = [path for path in _log_paths() if path.is_file()]
        size_bytes = sum(path.stat().st_size for path in paths)
        size = (
            f"{size_bytes / (1024 * 1024):.1f} MB"
            if size_bytes >= 1024 * 1024
            else f"{size_bytes / 1024:.1f} KB"
        )
        file_word = "file" if len(paths) == 1 else "files"
        updated = (
            datetime.fromtimestamp(max(path.stat().st_mtime for path in paths)).strftime(
                "%d %b %Y %H:%M"
            )
            if paths
            else "not yet"
        )
        return (
            f"Logging active | {len(paths)} {file_word} | {size} | "
            f"last updated {updated}",
            bool(paths),
        )
    except Exception as error:
        return f"Logging unavailable: {type(error).__name__}: {error}", False
    finally:
        _handler.release()


def build_diagnostics_archive():
    """Return a ZIP snapshot of the current and rotated log files."""
    if _handler is None:
        raise RuntimeError(_configuration_error or "Logging is unavailable.")

    _handler.acquire()
    try:
        _handler.flush()
        paths = [path for path in _log_paths() if path.is_file()]
        if not paths:
            raise RuntimeError("No diagnostic logs are available yet.")

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for path in paths:
                zip_file.writestr(path.name, path.read_bytes())
        return archive.getvalue()
    finally:
        _handler.release()
