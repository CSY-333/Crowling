import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(run_id: str, logs_dir: str = "logs") -> logging.Logger:
    """
    Configures the root logger:
    - Console: INFO level
    - File: DEBUG level (logs/debug_{timestamp}.log)
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers to avoid duplicates during re-runs or tests
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 1. Console Handler (INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (DEBUG)
    log_path = Path(logs_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_id}.log"
    file_handler = logging.FileHandler(log_path / filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger