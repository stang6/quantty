# core/logging/logger.py
import logging
from pathlib import Path

def get_logger(name: str):
    """
    Returns a logger that writes to:
      log/{name}.log
    And prints to console.
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid adding handlers multiple times (crucial!)
    if logger.handlers:
        return logger

    # Ensure log/ directory exists
    log_dir = Path("log")
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler: log/{name}.log
    file_path = log_dir / f"{name.lower()}.log"
    fh = logging.FileHandler(file_path)
    fh.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

