"""Modern Stoic Pipeline — Logger utility.

Provides a structured logger that writes to a daily rotating log file
and the console. Each module gets its own named logger.
"""

import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_FORMATTER = logging.Formatter(
    "%(asctime)s | %(name)-28s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger writing to both console and a daily log file.

    Purpose:
        Central factory so every module gets consistent formatting without
        duplicate handlers when called multiple times with the same name.

    Args:
        name (str): Logger name, e.g. "script.generator", "video.builder".

    Returns:
        logging.Logger: Configured logger instance.

    Error conditions:
        None — falls back gracefully if log directory is unwritable.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured — avoid duplicate handlers

    logger.setLevel(logging.DEBUG)

    # --- File handler (daily rotation in filename) ---
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"pipeline_{date_str}.log"
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_FORMATTER)
        logger.addHandler(fh)
    except OSError as e:
        print(f"[Logger] WARNING: Cannot write to log file {log_file}: {e}")

    # --- Console handler ---
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(_FORMATTER)
    logger.addHandler(ch)

    # Prevent log records from propagating to the root logger
    logger.propagate = False

    return logger
