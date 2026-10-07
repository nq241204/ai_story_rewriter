"""Main entry point for AI Story Rewriter."""

import sys
import os

# Ensure UTF-8 console output on Windows to prevent UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PySide6.QtWidgets import QApplication
from dotenv import load_dotenv
from app.ui.main_window import MainWindow
from app.utils.logger import get_logger


def main():
    """Main application entry point."""
    # Load environment variables
    load_dotenv()

    # Initialize logger
    logger = get_logger()
    logger.info("Starting AI Story Rewriter")

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("AI Story Rewriter")
    app.setOrganizationName("AIStoryRewriter")

    # Create and show main window
    window = MainWindow()
    window.show()

    logger.info("Application started")

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
