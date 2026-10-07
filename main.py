"""Main entry point for AI Story Rewriter."""

import sys
import os
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
