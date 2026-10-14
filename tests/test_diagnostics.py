import logging
import zipfile
import io

import pytest

from src import diagnostics


@pytest.fixture(autouse=True)
def reset_diagnostics():
    _reset_diagnostics()
    yield
    _reset_diagnostics()


def _reset_diagnostics():
    handler = diagnostics._handler
    if handler is not None:
        app_logger = logging.getLogger(diagnostics.LOGGER_NAME)
        app_logger.removeHandler(handler)
        app_logger.setLevel(logging.NOTSET)
        app_logger.propagate = True
        logging.getLogger().removeHandler(handler)
        handler.close()
    diagnostics._handler = None
    diagnostics._configuration_error = None


def test_reconfiguring_logging_does_not_duplicate_app_messages(tmp_path):
    # Arrange
    assert diagnostics.configure_logging(tmp_path)
    logger = logging.getLogger(f"{diagnostics.LOGGER_NAME}.test")

    # Act
    logger.warning("first marker")
    assert diagnostics.configure_logging(tmp_path)
    logger.warning("second marker")
    external_logger = logging.getLogger("external-library-test")
    previous_level = external_logger.level
    external_logger.setLevel(logging.INFO)
    external_logger.info("routine library chatter")
    external_logger.error("unhandled library failure")
    status_text, download_available = diagnostics.get_diagnostics_status()
    log_text = (tmp_path / diagnostics.LOG_FILENAME).read_text(encoding="utf-8")
    external_logger.setLevel(previous_level)

    # Assert
    assert status_text.startswith("Logging active | 1 file")
    assert download_available is True
    assert log_text.count("first marker") == 1
    assert log_text.count("second marker") == 1
    assert "routine library chatter" not in log_text
    assert "unhandled library failure" in log_text


def test_logging_rotates_and_keeps_only_one_backup(tmp_path):
    # Arrange
    assert diagnostics.MAX_LOG_BYTES == 5 * 1024 * 1024
    assert diagnostics.BACKUP_COUNT == 1
    assert diagnostics.configure_logging(tmp_path, max_bytes=512)
    logger = logging.getLogger(f"{diagnostics.LOGGER_NAME}.test")

    # Act
    for index in range(20):
        logger.error("rotation marker %s %s", index, "x" * 300)
    status_text, download_available = diagnostics.get_diagnostics_status()
    archive_bytes = diagnostics.build_diagnostics_archive()

    # Assert
    assert (tmp_path / diagnostics.LOG_FILENAME).is_file()
    assert (tmp_path / f"{diagnostics.LOG_FILENAME}.1").is_file()
    assert not (tmp_path / f"{diagnostics.LOG_FILENAME}.2").exists()
    assert "2 files" in status_text
    assert download_available is True
    assert sum(path.stat().st_size for path in tmp_path.glob("*.log*")) < 2_048
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert set(archive.namelist()) == {
            diagnostics.LOG_FILENAME,
            f"{diagnostics.LOG_FILENAME}.1",
        }
        assert archive.testzip() is None


def test_displayed_exception_includes_traceback(tmp_path):
    # Arrange
    assert diagnostics.configure_logging(tmp_path)

    # Act
    try:
        raise RuntimeError("diagnostic boom")
    except RuntimeError as error:
        diagnostics.log_displayed_error("test_callback", str(error), error)
    diagnostics.get_diagnostics_status()
    log_text = (tmp_path / diagnostics.LOG_FILENAME).read_text(encoding="utf-8")

    # Assert
    assert "displayed_error source=test_callback" in log_text
    assert "type=RuntimeError message=diagnostic boom" in log_text
    assert "Traceback (most recent call last)" in log_text


def test_unusable_log_directory_does_not_raise(tmp_path):
    # Arrange
    blocked_path = tmp_path / "not-a-directory"
    blocked_path.write_text("occupied", encoding="utf-8")

    # Act
    configured = diagnostics.configure_logging(blocked_path)
    status_text, download_available = diagnostics.get_diagnostics_status()

    # Assert
    assert configured is False
    assert download_available is False
    assert status_text.startswith("Logging unavailable:")
    assert "FileExistsError" in status_text
    with pytest.raises(RuntimeError, match="FileExistsError"):
        diagnostics.build_diagnostics_archive()
