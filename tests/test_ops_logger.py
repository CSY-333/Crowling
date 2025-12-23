import logging

from src.ops.logger import setup_logger


def test_setup_logger_creates_console_and_file_handlers(tmp_path):
    logger = setup_logger("run123", logs_dir=str(tmp_path))
    try:
        # Two handlers: console + file
        assert len(logger.handlers) == 2
        levels = sorted(handler.level for handler in logger.handlers)
        assert logging.DEBUG in levels
        assert logging.INFO in levels

        log_files = list(tmp_path.iterdir())
        assert any(f.name.startswith("debug_") and f.suffix == ".log" for f in log_files)
    finally:
        # Clean up handlers so later tests can reconfigure logging
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
