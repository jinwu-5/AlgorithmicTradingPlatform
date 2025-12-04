"""Logging helper."""
import logging
from typing import Optional


def setup_logging(level: int = logging.INFO, log_file: str = "trading_bot.log") -> logging.Logger:
    """Configure global logging once and return the root trading bot logger."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return logging.getLogger("trading_bot")

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    return logging.getLogger("trading_bot")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Convenience wrapper for module-level loggers."""
    return logging.getLogger(name or "trading_bot")
