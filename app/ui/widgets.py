"""Custom UI widgets for AI Story Rewriter."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QListWidget, QListWidgetItem, QFrame
)
from PySide6.QtCore import Qt, Signal
from app.ui.styles import Styles


class StatusBadge(QWidget):
    """Status badge widget."""
    
    def __init__(self, text: str, status: str = "normal", parent=None):
        """
        Initialize status badge.
        
        Args:
            text: Badge text
            status: Status type (normal, success, warning, error)
            parent: Parent widget
        """
        super().__init__(parent)
        self.text = text
        self.status = status
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        self.label = QLabel(text)
        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: {self._get_bg_color()};
                color: {self._get_text_color()};
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: 600;
                font-size: 9pt;
            }}
        """)
        
        layout.addWidget(self.label)
    
    def _get_bg_color(self) -> str:
        """Get background color based on status."""
        colors = {
            "normal": Styles.SURFACE_LIGHT,
            "success": Styles.SUCCESS,
            "warning": Styles.WARNING,
            "error": Styles.ERROR,
            "processing": Styles.PRIMARY
        }
        return colors.get(self.status, Styles.SURFACE_LIGHT)
    
    def _get_text_color(self) -> str:
        """Get text color based on status."""
        return Styles.TEXT_PRIMARY
    
    def set_status(self, status: str) -> None:
        """Update status."""
        self.status = status
        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: {self._get_bg_color()};
                color: {self._get_text_color()};
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: 600;
                font-size: 9pt;
            }}
        """)
    
    def set_text(self, text: str) -> None:
        """Update text."""
        self.text = text
        self.label.setText(text)


class FileListItem(QWidget):
    """List item for file queue."""
    
    clicked = Signal(str)
    
    def __init__(self, filename: str, status: str = "waiting", parent=None):
        """
        Initialize file list item.
        
        Args:
            filename: File name
            status: Processing status
            parent: Parent widget
        """
        super().__init__(parent)
        self.filename = filename
        self.status = status
        
        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        
        # Filename
        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("font-weight: 500;")
        layout.addWidget(self.name_label, 1)
        
        # Status badge
        self.status_badge = StatusBadge(self._get_status_text(), self._get_status_type())
        layout.addWidget(self.status_badge)
        
        # Update background on hover
        self.setStyleSheet("""
            FileListItem:hover {{
                background-color: rgba(139, 92, 246, 0.1);
                border-radius: 6px;
            }}
        """)
    
    def _get_status_text(self) -> str:
        """Get status display text."""
        status_map = {
            "waiting": "WAITING",
            "reading": "READING",
            "analyzing": "ANALYZING",
            "rewriting": "REWRITING",
            "qc": "QC",
            "title": "TITLE",
            "building_srt": "BUILDING",
            "validating": "VALIDATING",
            "saving": "SAVING",
            "completed": "DONE",
            "failed": "FAILED"
        }
        return status_map.get(self.status, self.status.upper())
    
    def _get_status_type(self) -> str:
        """Get status type for badge styling."""
        if self.status == "completed":
            return "success"
        elif self.status == "failed":
            return "error"
        elif self.status in ["reading", "analyzing", "rewriting", "qc", "title", "building_srt", "validating", "saving"]:
            return "processing"
        else:
            return "normal"
    
    def update_status(self, status: str) -> None:
        """Update processing status."""
        self.status = status
        self.status_badge.set_text(self._get_status_text())
        self.status_badge.set_status(self._get_status_type())
    
    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.filename)
        super().mousePressEvent(event)


class ProgressCard(QWidget):
    """Card showing current processing progress."""
    
    def __init__(self, parent=None):
        """Initialize progress card."""
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Current file label
        self.file_label = QLabel("No file selected")
        self.file_label.setProperty("class", "subheading")
        layout.addWidget(self.file_label)
        
        # Stage label
        self.stage_label = QLabel("Ready")
        self.stage_label.setProperty("class", "secondary")
        layout.addWidget(self.stage_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("START")
        self.start_btn.setProperty("class", "primary")
        self.pause_btn = QPushButton("PAUSE")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setProperty("class", "danger")
        self.stop_btn.setEnabled(False)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
    
    def update_progress(self, filename: str, stage: str, current: int, total: int) -> None:
        """Update progress display."""
        self.file_label.setText(f"File: {filename}")
        self.stage_label.setText(f"Stage: {stage.upper()}")
        
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            self.progress_bar.setTextVisible(True)
    
    def set_processing(self, processing: bool) -> None:
        """Set processing state."""
        self.start_btn.setEnabled(not processing)
        self.pause_btn.setEnabled(processing)
        self.stop_btn.setEnabled(processing)
    
    def reset(self) -> None:
        """Reset progress card."""
        self.file_label.setText("No file selected")
        self.stage_label.setText("Ready")
        self.progress_bar.setValue(0)
        self.set_processing(False)


class StatsCard(QWidget):
    """Card showing batch statistics."""
    
    def __init__(self, parent=None):
        """Initialize stats card."""
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setSpacing(20)
        
        # Total files
        self.total_label = self._create_stat_label("Total", "0")
        layout.addWidget(self.total_label)
        
        # Completed
        self.completed_label = self._create_stat_label("Completed", "0", "success")
        layout.addWidget(self.completed_label)
        
        # Processing
        self.processing_label = self._create_stat_label("Processing", "0", "processing")
        layout.addWidget(self.processing_label)
        
        # Failed
        self.failed_label = self._create_stat_label("Failed", "0", "error")
        layout.addWidget(self.failed_label)
    
    def _create_stat_label(self, title: str, value: str, status: str = "normal") -> QWidget:
        """Create a stat label widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(4)
        
        value_label = QLabel(value)
        value_label.setProperty("class", "heading")
        value_label.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setProperty("class", "secondary")
        title_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        
        return widget
    
    def update_stats(self, total: int, completed: int, processing: int, failed: int) -> None:
        """Update statistics."""
        self.total_label.findChild(QLabel).setText(str(total))
        self.completed_label.findChild(QLabel).setText(str(completed))
        self.processing_label.findChild(QLabel).setText(str(processing))
        self.failed_label.findChild(QLabel).setText(str(failed))


class SectionHeader(QFrame):
    """Section header with title."""
    
    def __init__(self, title: str, parent=None):
        """
        Initialize section header.
        
        Args:
            title: Section title
            parent: Parent widget
        """
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        
        label = QLabel(title)
        label.setProperty("class", "subheading")
        layout.addWidget(label)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {Styles.BORDER};")
        layout.addWidget(line, 1)
