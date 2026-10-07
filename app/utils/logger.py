"""Logging utilities for AI Story Rewriter."""

import logging
import os
import sys
from datetime import datetime
from typing import Optional


class AppLogger:
    """Application logger with file and console handlers."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.logger = logging.getLogger("AIStoryRewriter")
        self.logger.setLevel(logging.DEBUG)

        # Ensure UTF-8 console output on Windows
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)

        # Remove existing handlers
        self.logger.handlers.clear()

        # File handler
        log_file = os.path.join(
            log_dir,
            f"story_rewriter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)


# Global logger instance
_logger: Optional[AppLogger] = None


def get_logger(log_dir: str = "logs") -> AppLogger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        _logger = AppLogger(log_dir)
    return _logger
