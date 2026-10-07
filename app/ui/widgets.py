"""Custom UI widgets for AI Story Rewriter (Vietnamese UI)."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal
from app.ui.styles import Styles


STAGE_VI_MAP = {
    "waiting": "CHỜ XỬ LÝ",
    "reading": "ĐANG ĐỌC FILE (PYTHON)",
    "analyzing": "PHÂN TÍCH (PYTHON - 0 TOKEN)",
    "rewriting": "ĐANG VIẾT LẠI & TẠO TITLE (AI)",
    "qc": "KIỂM DUYỆT (PYTHON - 0 TOKEN)",
    "title": "XỬ LÝ TIÊU ĐỀ CTR",
    "building_srt": "CHIA ĐOẠN KỊCH BẢN TTS",
    "validating": "KIỂM TRA ĐẦU RA",
    "saving": "ĐANG LƯU KẾT QUẢ",
    "completed": "HOÀN THÀNH",
    "failed": "THẤT BẠI",
    "paused": "ĐÃ TẠM DỪNG",
}


class StatusBadge(QWidget):
    """Status badge widget."""

    def __init__(self, text: str, status: str = "normal", parent=None):
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
        colors = {
            "normal": Styles.SURFACE_LIGHT,
            "success": Styles.SUCCESS,
            "warning": Styles.WARNING,
            "error": Styles.ERROR,
            "processing": Styles.PRIMARY
        }
        return colors.get(self.status, Styles.SURFACE_LIGHT)

    def _get_text_color(self) -> str:
        return Styles.TEXT_PRIMARY

    def set_status(self, status: str) -> None:
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
        self.text = text
        self.label.setText(text)


class FileListItem(QWidget):
    """List item for file queue."""

    clicked = Signal(str)

    def __init__(self, filename: str, status: str = "waiting", parent=None):
        super().__init__(parent)
        self.filename = filename
        self.status = status

        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("font-weight: 500;")
        layout.addWidget(self.name_label, 1)

        self.status_badge = StatusBadge(self._get_status_text(), self._get_status_type())
        layout.addWidget(self.status_badge)

        self.setStyleSheet("""
            FileListItem:hover {
                background-color: rgba(139, 92, 246, 0.1);
                border-radius: 6px;
            }
        """)

    def _get_status_text(self) -> str:
        return STAGE_VI_MAP.get(self.status, self.status.upper())

    def _get_status_type(self) -> str:
        if self.status == "completed":
            return "success"
        elif self.status == "failed":
            return "error"
        elif self.status in [
            "reading", "analyzing", "rewriting", "qc",
            "title", "building_srt", "validating", "saving"
        ]:
            return "processing"
        else:
            return "normal"

    def update_status(self, status: str) -> None:
        self.status = status
        self.status_badge.set_text(self._get_status_text())
        self.status_badge.set_status(self._get_status_type())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.filename)
        super().mousePressEvent(event)


class ProgressCard(QWidget):
    """Card showing current processing progress in Vietnamese."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.file_label = QLabel("Chưa chọn file nào")
        self.file_label.setProperty("class", "subheading")
        layout.addWidget(self.file_label)

        self.stage_label = QLabel("Trạng thái: Sẵn sàng")
        self.stage_label.setProperty("class", "secondary")
        layout.addWidget(self.stage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("BẮT ĐẦU CHẠY")
        self.start_btn.setProperty("class", "primary")
        self.pause_btn = QPushButton("TẠM DỪNG")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("DỪNG HẲN")
        self.stop_btn.setProperty("class", "danger")
        self.stop_btn.setEnabled(False)

        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

    def update_progress(self, filename: str, stage: str, current: int, total: int) -> None:
        stage_vi = STAGE_VI_MAP.get(stage.lower(), stage.upper())
        self.file_label.setText(f"Đang xử lý ({current}/{total}): {filename}")
        self.stage_label.setText(f"Bước hiện tại: {stage_vi}")

        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            self.progress_bar.setTextVisible(True)

    def set_processing(self, processing: bool) -> None:
        self.start_btn.setEnabled(not processing)
        self.pause_btn.setEnabled(processing)
        self.stop_btn.setEnabled(processing)

    def reset(self) -> None:
        self.file_label.setText("Chưa chọn file nào")
        self.stage_label.setText("Trạng thái: Sẵn sàng")
        self.start_btn.setText("BẮT ĐẦU CHẠY")
        self.progress_bar.setValue(0)
        self.set_processing(False)


class StatsCard(QWidget):
    """Card showing batch statistics in a clean 2x2 grid for the sidebar."""

    def __init__(self, parent=None):
        super().__init__(parent)

        grid = QGridLayout(self)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(8)

        self.total_label = self._create_stat_label("Tổng file", "0")
        self.completed_label = self._create_stat_label("Hoàn thành", "0", "success")
        self.processing_label = self._create_stat_label("Đang chạy", "0", "processing")
        self.failed_label = self._create_stat_label("Bị lỗi", "0", "error")

        grid.addWidget(self.total_label, 0, 0)
        grid.addWidget(self.completed_label, 0, 1)
        grid.addWidget(self.processing_label, 1, 0)
        grid.addWidget(self.failed_label, 1, 1)

    def _create_stat_label(self, title: str, value: str, status: str = "normal") -> QWidget:
        widget = QFrame()
        widget.setStyleSheet(
            f"background-color: {Styles.SURFACE_LIGHT}; border-radius: 6px; padding: 4px;"
        )
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setProperty("class", "heading")
        value_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setProperty("class", "secondary")
        title_label.setStyleSheet("font-size: 9pt;")
        title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(value_label)
        layout.addWidget(title_label)

        return widget

    def update_stats(self, total: int, completed: int, processing: int, failed: int) -> None:
        self.total_label.findChild(QLabel).setText(str(total))
        self.completed_label.findChild(QLabel).setText(str(completed))
        self.processing_label.findChild(QLabel).setText(str(processing))
        self.failed_label.findChild(QLabel).setText(str(failed))


class SectionHeader(QFrame):
    """Section header with title."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)

        label = QLabel(title)
        label.setProperty("class", "subheading")
        layout.addWidget(label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {Styles.BORDER};")
        layout.addWidget(line, 1)
