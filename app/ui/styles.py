"""UI styles for AI Story Rewriter."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QFont


class Styles:
    """Style definitions for the application."""
    
    # Colors
    BACKGROUND = "#1e1e2e"
    SURFACE = "#252535"
    SURFACE_LIGHT = "#2d2d3d"
    PRIMARY = "#8b5cf6"  # Purple
    PRIMARY_DARK = "#7c3aed"
    SECONDARY = "#3b82f6"  # Blue
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"
    TEXT_PRIMARY = "#f1f5f9"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_DISABLED = "#64748b"
    BORDER = "#3d3d4d"
    
    # Fonts
    FONT_FAMILY = "Segoe UI, Arial, sans-serif"
    FONT_SIZE_NORMAL = 11
    FONT_SIZE_SMALL = 9
    FONT_SIZE_LARGE = 13
    FONT_SIZE_TITLE = 16
    
    @staticmethod
    def get_stylesheet() -> str:
        """Get the main application stylesheet."""
        return f"""
            QMainWindow {{
                background-color: {Styles.BACKGROUND};
            }}
            
            QWidget {{
                background-color: {Styles.BACKGROUND};
                color: {Styles.TEXT_PRIMARY};
                font-family: {Styles.FONT_FAMILY};
                font-size: {Styles.FONT_SIZE_NORMAL}pt;
            }}
            
            QPushButton {{
                background-color: {Styles.SURFACE};
                color: {Styles.TEXT_PRIMARY};
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            
            QPushButton:hover {{
                background-color: {Styles.SURFACE_LIGHT};
                border-color: {Styles.PRIMARY};
            }}
            
            QPushButton:pressed {{
                background-color: {Styles.PRIMARY_DARK};
            }}
            
            QPushButton:disabled {{
                background-color: {Styles.SURFACE};
                color: {Styles.TEXT_DISABLED};
                border-color: {Styles.BORDER};
            }}
            
            QPushButton.primary {{
                background-color: {Styles.PRIMARY};
                border: none;
            }}
            
            QPushButton.primary:hover {{
                background-color: {Styles.PRIMARY_DARK};
            }}
            
            QPushButton.success {{
                background-color: {Styles.SUCCESS};
                border: none;
            }}
            
            QPushButton.warning {{
                background-color: {Styles.WARNING};
                border: none;
            }}
            
            QPushButton.danger {{
                background-color: {Styles.ERROR};
                border: none;
            }}
            
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {Styles.SURFACE};
                color: {Styles.TEXT_PRIMARY};
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                padding: 8px;
                selection-background-color: {Styles.PRIMARY};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border-color: {Styles.PRIMARY};
            }}
            
            QComboBox {{
                background-color: {Styles.SURFACE};
                color: {Styles.TEXT_PRIMARY};
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
            
            QComboBox:hover {{
                border-color: {Styles.PRIMARY};
            }}
            
            QComboBox::drop-down {{
                border: none;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {Styles.TEXT_SECONDARY};
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {Styles.SURFACE};
                border: 1px solid {Styles.BORDER};
                selection-background-color: {Styles.PRIMARY};
                color: {Styles.TEXT_PRIMARY};
            }}
            
            QListWidget {{
                background-color: {Styles.SURFACE};
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                outline: none;
            }}
            
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {Styles.BORDER};
            }}
            
            QListWidget::item:selected {{
                background-color: {Styles.PRIMARY};
            }}
            
            QListWidget::item:hover {{
                background-color: {Styles.SURFACE_LIGHT};
            }}
            
            QScrollBar:vertical {{
                background-color: {Styles.SURFACE};
                width: 10px;
                border-radius: 5px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {Styles.TEXT_DISABLED};
                border-radius: 5px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {Styles.TEXT_SECONDARY};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QProgressBar {{
                background-color: {Styles.SURFACE};
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                text-align: center;
                color: {Styles.TEXT_PRIMARY};
            }}
            
            QProgressBar::chunk {{
                background-color: {Styles.PRIMARY};
                border-radius: 5px;
            }}
            
            QLabel {{
                color: {Styles.TEXT_PRIMARY};
            }}
            
            QLabel.heading {{
                font-size: {Styles.FONT_SIZE_TITLE}pt;
                font-weight: bold;
                color: {Styles.TEXT_PRIMARY};
            }}
            
            QLabel.subheading {{
                font-size: {Styles.FONT_SIZE_LARGE}pt;
                font-weight: 600;
                color: {Styles.TEXT_PRIMARY};
            }}
            
            QLabel.secondary {{
                color: {Styles.TEXT_SECONDARY};
            }}
            
            QGroupBox {{
                background-color: {Styles.SURFACE};
                border: 1px solid {Styles.BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 600;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            
            QCheckBox {{
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {Styles.BORDER};
                border-radius: 4px;
                background-color: {Styles.SURFACE};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {Styles.PRIMARY};
                border-color: {Styles.PRIMARY};
            }}
            
            QCheckBox::indicator:hover {{
                border-color: {Styles.PRIMARY};
            }}
            
            QSlider::groove:horizontal {{
                height: 6px;
                background-color: {Styles.SURFACE};
                border-radius: 3px;
            }}
            
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                background-color: {Styles.PRIMARY};
                border-radius: 8px;
                margin: -5px 0;
            }}
            
            QSlider::handle:horizontal:hover {{
                background-color: {Styles.PRIMARY_DARK};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                background-color: {Styles.SURFACE};
            }}
            
            QTabBar::tab {{
                background-color: {Styles.SURFACE};
                color: {Styles.TEXT_SECONDARY};
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {Styles.SURFACE_LIGHT};
                color: {Styles.TEXT_PRIMARY};
                border-bottom: 2px solid {Styles.PRIMARY};
            }}
            
            QTabBar::tab:hover {{
                background-color: {Styles.SURFACE_LIGHT};
            }}
        """
    
    @staticmethod
    def get_palette():
        """Get application color palette."""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(Styles.BACKGROUND))
        palette.setColor(QPalette.WindowText, QColor(Styles.TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(Styles.SURFACE))
        palette.setColor(QPalette.AlternateBase, QColor(Styles.SURFACE_LIGHT))
        palette.setColor(QPalette.Text, QColor(Styles.TEXT_PRIMARY))
        palette.setColor(QPalette.Button, QColor(Styles.SURFACE))
        palette.setColor(QPalette.ButtonText, QColor(Styles.TEXT_PRIMARY))
        palette.setColor(QPalette.Highlight, QColor(Styles.PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(Styles.TEXT_PRIMARY))
        return palette
