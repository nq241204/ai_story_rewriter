"""Main window for AI Story Rewriter (Vietnamese Hybrid Workflow Interface)."""

import os
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QCheckBox, QFileDialog,
    QFrame, QTextEdit, QTabWidget, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal
from app.ui.styles import Styles
from app.ui.widgets import (
    ProgressCard, StatsCard, SectionHeader, STAGE_VI_MAP
)
from app.storage.settings import SettingsManager
from app.storage.history import HistoryManager, HistoryEntry
from app.ai.gemini_client import GeminiClient
from app.ai.ai_service import AIService
from app.pipeline.pre_checker import PythonPreChecker
from app.pipeline.story_processor import StoryProcessor, ProcessingState
from app.pipeline.batch_processor import BatchProcessor, BatchState, FileStatus
from app.utils.logger import get_logger
from app.utils.text_utils import (
    parse_unified_ai_output,
    format_unified_output,
    format_tts_paragraphs,
)


INTENSITY_UI_TO_KEY = {
    "Nhẹ (Light)": "light",
    "Cân bằng (Balanced)": "balanced",
    "Sâu & Kịch tính (Deep)": "deep",
    "Light": "light",
    "Balanced": "balanced",
    "Deep": "deep",
}

INTENSITY_KEY_TO_UI = {
    "light": "Nhẹ (Light)",
    "balanced": "Cân bằng (Balanced)",
    "deep": "Sâu & Kịch tính (Deep)",
}

WORKFLOW_UI_TO_KEY = {
    "Viết Lại Toàn Bộ Truyện Mới Từ Khung Sườn + Sơ Tuyển Python 0 Token (Khuyên dùng)": "full_ai",
    "Hybrid Tinh Chỉnh Đoạn Lỗi (Python Quét 0 Token + AI Chỉ Sửa Đoạn Gắn Cờ)": "hybrid",
    "Chỉ Sơ Tuyển Python (0 Token — Xuất báo cáo lỗi để người tự sửa)": "python_only",
}

WORKFLOW_KEY_TO_UI = {
    "full_ai": "Viết Lại Toàn Bộ Truyện Mới Từ Khung Sườn + Sơ Tuyển Python 0 Token (Khuyên dùng)",
    "hybrid": "Hybrid Tinh Chỉnh Đoạn Lỗi (Python Quét 0 Token + AI Chỉ Sửa Đoạn Gắn Cờ)",
    "python_only": "Chỉ Sơ Tuyển Python (0 Token — Xuất báo cáo lỗi để người tự sửa)",
}


class BatchWorker(QThread):
    """Worker thread for non-blocking batch processing."""

    progress_update = Signal(str, str, int, int)  # filename, stage (string), current, total
    log_message = Signal(str)
    file_completed = Signal(object)  # FileStatus
    finished = Signal()

    def __init__(self, batch_processor: BatchProcessor):
        super().__init__()
        self.batch_processor = batch_processor

    def run(self):
        """Run batch processing."""
        self.batch_processor.start(
            progress_callback=self.progress_update.emit,
            log_callback=self.log_message.emit,
            file_completed_callback=self.file_completed.emit,
        )
        self.finished.emit()

    def pause(self):
        """Pause processing."""
        self.batch_processor.pause()

    def resume(self):
        """Resume processing."""
        self.batch_processor.resume()

    def stop(self):
        """Stop processing."""
        self.batch_processor.stop()


class MainWindow(QMainWindow):
    """Main application window with full Vietnamese Hybrid Workflow UI."""

    def __init__(self):
        super().__init__()

        self.logger = get_logger()
        self.settings_manager = SettingsManager()
        self.history_manager = HistoryManager()
        self.pre_checker = PythonPreChecker()

        # Initialize components
        self.gemini_client = None
        self.ai_service = None
        self.story_processor = None
        self.batch_processor = None
        self.batch_worker = None
        self._current_preview_status = None

        # Always initialize pure-Python processor so scanning/pre-check works without API key
        self._init_pipeline_components()

        self.init_ui()
        self.load_settings()
        self.init_ai()
        self.refresh_history()

    def _init_pipeline_components(self):
        """Ensure StoryProcessor and BatchProcessor exist for pure-Python scanning & pre-checking."""
        settings = self.settings_manager.get_all()
        if not self.ai_service:
            # Create a 0-token AIService if no client yet so Python-only pre-check always works
            self.ai_service = AIService(
                client=self.gemini_client,
                api_timeout=settings.api_timeout,
                analysis_timeout=settings.analysis_timeout,
                qc_timeout=settings.qc_timeout,
                rewrite_intensity=settings.rewrite_intensity,
                max_retries=settings.max_retry,
                use_ai_analysis=False,
                use_ai_qc=settings.use_ai_qc,
                workflow_mode=settings.workflow_mode,
            )

        if not self.story_processor:
            self.story_processor = StoryProcessor(
                ai_service=self.ai_service,
                save_failed=settings.save_failed,
                export_srt=settings.export_srt,
            )
        else:
            self.story_processor.ai_service = self.ai_service
            self.story_processor.save_failed = settings.save_failed
            self.story_processor.export_srt = settings.export_srt

        if not self.batch_processor:
            self.batch_processor = BatchProcessor(
                self.story_processor,
                skip_already_processed=settings.skip_processed,
            )
        else:
            self.batch_processor.story_processor = self.story_processor
            self.batch_processor.skip_already_processed = settings.skip_processed

    def init_ui(self):
        """Initialize the user interface in Vietnamese."""
        self.setWindowTitle("AI Story Rewriter — Hybrid Workflow (Python Sơ Tuyển 0 Token + AI Tinh Chỉnh)")
        self.setMinimumSize(1280, 840)

        # Apply styles
        self.setStyleSheet(Styles.get_stylesheet())
        self.setPalette(Styles.get_palette())

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create panels
        self.create_left_panel(main_layout)
        self.create_center_panel(main_layout)
        self.create_right_panel(main_layout)

        # Status bar
        self.create_status_bar()

    def create_left_panel(self, parent_layout):
        """Create left sidebar panel."""
        left_panel = QFrame()
        left_panel.setFixedWidth(260)
        left_panel.setStyleSheet(
            f"background-color: {Styles.SURFACE}; border-right: 1px solid {Styles.BORDER};"
        )

        layout = QVBoxLayout(left_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Title
        title = QLabel("AI STORY\nREWRITER")
        title.setProperty("class", "heading")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; line-height: 1.2;")
        layout.addWidget(title)

        subtitle = QLabel("Hybrid Workflow • Python 0 Token + LLM")
        subtitle.setProperty("class", "secondary")
        subtitle.setStyleSheet("font-size: 9pt;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Stats card
        self.stats_card = StatsCard()
        layout.addWidget(self.stats_card)

        layout.addSpacing(8)

        # Navigation buttons
        nav_buttons = QVBoxLayout()
        nav_buttons.setSpacing(8)

        self.btn_process = QPushButton("Hàng Đợi & Xử Lý")
        self.btn_process.setProperty("class", "primary")
        self.btn_process.clicked.connect(lambda: self.center_tabs.setCurrentIndex(0))
        nav_buttons.addWidget(self.btn_process)

        self.btn_editor = QPushButton("Xem & Sửa Kết Quả (Hybrid)")
        self.btn_editor.clicked.connect(lambda: self.center_tabs.setCurrentIndex(1))
        nav_buttons.addWidget(self.btn_editor)

        self.btn_history = QPushButton("Lịch Sử Xử Lý")
        self.btn_history.clicked.connect(lambda: self.center_tabs.setCurrentIndex(2))
        nav_buttons.addWidget(self.btn_history)

        self.btn_settings = QPushButton("Cài Đặt Hệ Thống")
        self.btn_settings.clicked.connect(lambda: self.center_tabs.setCurrentIndex(3))
        nav_buttons.addWidget(self.btn_settings)

        layout.addLayout(nav_buttons)
        layout.addStretch()

        parent_layout.addWidget(left_panel)

    def create_center_panel(self, parent_layout):
        """Create center panel."""
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(20, 20, 20, 20)
        center_layout.setSpacing(16)

        # Tab widget
        self.center_tabs = QTabWidget()
        self.center_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Styles.BORDER};
                border-radius: 8px;
                background-color: {Styles.SURFACE};
            }}
        """)

        # 0: Queue tab
        self.create_queue_tab()

        # 1: Result Viewer & Hybrid Editor tab (Sửa kết quả)
        self.create_result_editor_tab()

        # 2: History tab
        self.create_history_tab()

        # 3: Settings tab
        self.create_settings_tab()

        center_layout.addWidget(self.center_tabs)
        parent_layout.addWidget(center_panel, 1)

    def create_queue_tab(self):
        """Create queue tab in Vietnamese."""
        queue_widget = QWidget()
        queue_layout = QVBoxLayout(queue_widget)
        queue_layout.setSpacing(10)

        # Folder selection
        folder_layout = QHBoxLayout()

        input_group = QVBoxLayout()
        input_group.addWidget(QLabel("THƯ MỤC ĐẦU VÀO (CHỨA FILE .SRT)"))
        input_row = QHBoxLayout()
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("Chọn thư mục chứa các file .srt đầu vào...")
        self.btn_select_input = QPushButton("Chọn Thư Mục")
        self.btn_select_input.clicked.connect(self.select_input_folder)
        input_row.addWidget(self.input_path_edit, 1)
        input_row.addWidget(self.btn_select_input)
        input_group.addLayout(input_row)
        folder_layout.addLayout(input_group, 1)

        output_group = QVBoxLayout()
        output_group.addWidget(QLabel("THƯ MỤC ĐẦU RA (LƯU KẾT QUẢ TTS .TXT)"))
        output_row = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Chọn thư mục lưu file kết quả...")
        self.btn_select_output = QPushButton("Chọn Thư Mục")
        self.btn_select_output.clicked.connect(self.select_output_folder)
        output_row.addWidget(self.output_path_edit, 1)
        output_row.addWidget(self.btn_select_output)
        output_group.addLayout(output_row)
        folder_layout.addLayout(output_group, 1)

        queue_layout.addLayout(folder_layout)

        # Scan button
        self.btn_scan = QPushButton("Quét Thứ Tự File Tự Nhiên (Python Thuần — 0 Tốn Token)")
        self.btn_scan.setProperty("class", "primary")
        self.btn_scan.clicked.connect(self.scan_files)
        queue_layout.addWidget(self.btn_scan)

        # Queue list
        queue_layout.addWidget(SectionHeader("DANH SÁCH HÀNG ĐỢI (THỨ TỰ TỰ NHIÊN 001 → 999)"))

        self.queue_list = QTextEdit()
        self.queue_list.setReadOnly(True)
        self.queue_list.setMaximumHeight(130)
        self.queue_list.setPlaceholderText(
            "Bấm 'Quét Thứ Tự File Tự Nhiên' để tải danh sách file .srt theo đúng thứ tự..."
        )
        queue_layout.addWidget(self.queue_list)

        # Progress card
        queue_layout.addWidget(SectionHeader("TIẾN ĐỘ XỬ LÝ TRUYỆN HIỆN TẠI (HYBRID WORKFLOW)"))

        self.progress_card = ProgressCard()
        queue_layout.addWidget(self.progress_card)

        # Connect buttons
        self.progress_card.start_btn.clicked.connect(self.start_processing)
        self.progress_card.pause_btn.clicked.connect(self.pause_processing)
        self.progress_card.stop_btn.clicked.connect(self.stop_processing)

        # Latest result quick preview right inside Queue tab
        queue_layout.addWidget(SectionHeader("KẾT QUẢ & BÁO CÁO SƠ TUYỂN VỪA TẠO (---TITLE--- & ---TTS_SCRIPT---)"))
        self.quick_result_preview = QTextEdit()
        self.quick_result_preview.setReadOnly(False)
        self.quick_result_preview.setPlaceholderText(
            "---TITLE---\nTitle giật tít CTR YouTube sẽ hiển thị tại đây...\n\n"
            "---TTS_SCRIPT---\nToàn bộ lời thoại tiếng Anh liền mạch, bỏ hoàn toàn số thứ tự và timecode, "
            "chia đoạn văn ngắn (2-3 câu/đoạn) tối ưu cho công cụ Text-to-Speech đọc diễn cảm..."
        )
        queue_layout.addWidget(self.quick_result_preview, 1)

        quick_btn_row = QHBoxLayout()
        self.btn_quick_save = QPushButton("Lưu Sửa Đổi Nhanh")
        self.btn_quick_save.clicked.connect(self.save_quick_preview_edits)
        self.btn_quick_copy_tts = QPushButton("Copy Kịch Bản TTS")
        self.btn_quick_copy_tts.clicked.connect(self.copy_quick_tts_script)
        self.btn_open_full_editor = QPushButton("Mở Trình Sơ Tuyển & Sửa Kết Quả (Hybrid)")
        self.btn_open_full_editor.clicked.connect(lambda: self.center_tabs.setCurrentIndex(1))
        quick_btn_row.addWidget(self.btn_quick_save)
        quick_btn_row.addWidget(self.btn_quick_copy_tts)
        quick_btn_row.addWidget(self.btn_open_full_editor)
        quick_btn_row.addStretch()
        queue_layout.addLayout(quick_btn_row)

        self.center_tabs.addTab(queue_widget, "Hàng Đợi & Xử Lý")

    def create_result_editor_tab(self):
        """Create Hybrid Workflow tab: Python Pre-Check Report + Targeted AI / Human Editor."""
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setSpacing(10)

        editor_layout.addWidget(
            SectionHeader("HYBRID WORKFLOW: BÁO CÁO SƠ TUYỂN PYTHON (0 TOKEN) & CHỈNH SỬA KẾT QUẢ")
        )

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("Chọn file kết quả:"))
        self.result_file_combo = QComboBox()
        self.result_file_combo.currentIndexChanged.connect(self.on_result_file_selected)
        select_row.addWidget(self.result_file_combo, 1)

        self.btn_reload_outputs = QPushButton("Làm Mới Danh Sách")
        self.btn_reload_outputs.clicked.connect(self.load_output_files_into_editor)
        select_row.addWidget(self.btn_reload_outputs)
        editor_layout.addLayout(select_row)

        # Python Pre-Check Report Box (0 Tokens)
        editor_layout.addWidget(
            QLabel("BÁO CÁO SƠ TUYỂN PYTHON THUẦN (0 Token — Phát hiện từ lặp, lỗi tên riêng, đoạn quá dài, lỗi định dạng):")
        )
        self.precheck_report_box = QTextEdit()
        self.precheck_report_box.setReadOnly(True)
        self.precheck_report_box.setMaximumHeight(135)
        self.precheck_report_box.setPlaceholderText(
            "Bấm '1. Quét Sơ Tuyển Python (0 Token)' để kiểm tra từ lặp, lỗi tên riêng, câu quá dài và ước tính % tiết kiệm token..."
        )
        editor_layout.addWidget(self.precheck_report_box)

        # Title editor
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("---TITLE--- (Tiêu đề CTR YouTube):"))
        self.edit_title_input = QLineEdit()
        self.edit_title_input.setPlaceholderText("Nhập hoặc chỉnh sửa Title giật tít CTR YouTube...")
        title_row.addWidget(self.edit_title_input, 1)
        editor_layout.addLayout(title_row)

        # Full unified editor (---TITLE--- + ---TTS_SCRIPT---)
        editor_layout.addWidget(
            QLabel("---TTS_SCRIPT--- (Lời thoại tiếng Anh liền mạch, không timecode, 2-3 câu/đoạn tối ưu cho TTS):")
        )
        self.edit_script_text = QTextEdit()
        self.edit_script_text.setPlaceholderText(
            "Toàn bộ lời thoại tiếng Anh liền mạch, bỏ hoàn toàn số thứ tự và timecode, "
            "chia đoạn văn ngắn (2-3 câu/đoạn) tối ưu cho công cụ Text-to-Speech đọc diễn cảm."
        )
        editor_layout.addWidget(self.edit_script_text, 1)

        action_row1 = QHBoxLayout()
        self.btn_run_precheck = QPushButton("1. Quét Sơ Tuyển Python (0 Token)")
        self.btn_run_precheck.clicked.connect(self.run_python_precheck_on_editor)

        self.btn_hybrid_ai_fix = QPushButton("2. Gọi AI Sửa Riêng Đoạn Gắn Cờ (Hybrid — Ít Token Nhất)")
        self.btn_hybrid_ai_fix.setProperty("class", "primary")
        self.btn_hybrid_ai_fix.clicked.connect(self.run_hybrid_ai_on_editor)

        self.btn_format_paragraphs = QPushButton("3. Chuẩn Hóa 2-3 Câu/Đoạn (Python)")
        self.btn_format_paragraphs.clicked.connect(self.format_current_editor_script)

        action_row1.addWidget(self.btn_run_precheck)
        action_row1.addWidget(self.btn_hybrid_ai_fix)
        action_row1.addWidget(self.btn_format_paragraphs)
        action_row1.addStretch()
        editor_layout.addLayout(action_row1)

        action_row2 = QHBoxLayout()
        self.btn_save_edited_result = QPushButton("Lưu Kết Quả Đã Sửa")
        self.btn_save_edited_result.setProperty("class", "primary")
        self.btn_save_edited_result.clicked.connect(self.save_edited_result_to_disk)

        self.btn_copy_tts_only = QPushButton("Copy Kịch Bản TTS")
        self.btn_copy_tts_only.clicked.connect(self.copy_editor_tts_only)

        self.btn_copy_unified = QPushButton("Copy Toàn Bộ (---TITLE--- + ---TTS_SCRIPT---)")
        self.btn_copy_unified.clicked.connect(self.copy_editor_unified)

        action_row2.addWidget(self.btn_save_edited_result)
        action_row2.addWidget(self.btn_copy_tts_only)
        action_row2.addWidget(self.btn_copy_unified)
        action_row2.addStretch()
        editor_layout.addLayout(action_row2)

        self.center_tabs.addTab(editor_widget, "Xem & Sửa Kết Quả")

    def create_history_tab(self):
        """Create history tab in Vietnamese."""
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setSpacing(16)

        history_layout.addWidget(SectionHeader("LỊCH SỬ XỬ LÝ FILE"))

        self.history_list = QTextEdit()
        self.history_list.setReadOnly(True)
        self.history_list.setPlaceholderText("Chưa có lịch sử xử lý file nào...")
        history_layout.addWidget(self.history_list)

        button_row = QHBoxLayout()
        self.btn_refresh_history = QPushButton("Làm Mới")
        self.btn_refresh_history.clicked.connect(self.refresh_history)
        self.btn_clear_history = QPushButton("Xóa Toàn Bộ Lịch Sử")
        self.btn_clear_history.setProperty("class", "danger")
        self.btn_clear_history.clicked.connect(self.clear_history)
        button_row.addWidget(self.btn_refresh_history)
        button_row.addWidget(self.btn_clear_history)
        button_row.addStretch()
        history_layout.addLayout(button_row)

        self.center_tabs.addTab(history_widget, "Lịch Sử")

    def create_settings_tab(self):
        """Create settings tab in Vietnamese."""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(14)

        # AI Settings
        settings_layout.addWidget(SectionHeader("CẤU HÌNH AI & MÔ HÌNH HYBRID WORKFLOW"))

        ai_layout = QVBoxLayout()

        # Workflow mode selector
        workflow_row = QHBoxLayout()
        workflow_row.addWidget(QLabel("Chế độ vận hành (Workflow):"))
        self.workflow_combo = QComboBox()
        self.workflow_combo.addItems(list(WORKFLOW_UI_TO_KEY.keys()))
        workflow_row.addWidget(self.workflow_combo, 1)
        ai_layout.addLayout(workflow_row)

        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Mô hình AI (Model):"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
        ])
        model_row.addWidget(self.model_combo, 1)
        ai_layout.addLayout(model_row)

        # API Key
        api_row = QHBoxLayout()
        api_row.addWidget(QLabel("Gemini API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Nhập Gemini API Key của bạn tại đây...")
        api_row.addWidget(self.api_key_edit, 1)
        self.btn_test_api = QPushButton("Kiểm Tra Kết Nối")
        self.btn_test_api.clicked.connect(self.test_api_connection)
        api_row.addWidget(self.btn_test_api)
        ai_layout.addLayout(api_row)

        settings_layout.addLayout(ai_layout)

        # Processing Options
        settings_layout.addWidget(SectionHeader("TÙY CHỌN SƠ TUYỂN PYTHON & TIẾT KIỆM TOKEN"))

        options_layout = QVBoxLayout()

        self.chk_skip_processed = QCheckBox(
            "Quét & tự động bỏ qua file đã xử lý bằng Python thuần (Tránh gọi lại AI tốn token)"
        )
        self.chk_skip_processed.setChecked(True)
        options_layout.addWidget(self.chk_skip_processed)

        self.chk_analyze = QCheckBox(
            "Bước 1 — Sơ tuyển (Pre-check) bằng Python thuần (0 Token: Báo cáo từ lặp, tên riêng, đoạn dài, định dạng)"
        )
        self.chk_analyze.setChecked(True)
        options_layout.addWidget(self.chk_analyze)

        self.chk_rewrite = QCheckBox(
            "Bước 2 — AI chỉ tập trung sửa các đoạn bị Python gắn cờ + Tạo Title CTR (Xuất ---TITLE--- & ---TTS_SCRIPT---)"
        )
        self.chk_rewrite.setChecked(True)
        options_layout.addWidget(self.chk_rewrite)

        self.chk_qc = QCheckBox("Kiểm duyệt đầu ra (QC) bằng Python thuần (0 Token — Chỉ gọi AI sửa khi bị lỗi/cắt cụt)")
        self.chk_qc.setChecked(True)
        options_layout.addWidget(self.chk_qc)

        self.chk_ai_qc = QCheckBox("Bắt buộc gọi thêm AI để QC (Tốn thêm token — không khuyến khích)")
        self.chk_ai_qc.setChecked(False)
        options_layout.addWidget(self.chk_ai_qc)

        self.chk_title = QCheckBox("Tạo tiêu đề CTR YouTube tự động")
        self.chk_title.setChecked(True)
        options_layout.addWidget(self.chk_title)

        self.chk_export = QCheckBox("Xuất kèm file phụ đề .SRT (Mặc định tắt để chỉ xuất kịch bản TTS .TXT siêu tốc)")
        self.chk_export.setChecked(False)
        options_layout.addWidget(self.chk_export)

        # Rewrite intensity
        intensity_row = QHBoxLayout()
        intensity_row.addWidget(QLabel("Mức độ trau chuốt cảm xúc:"))
        self.intensity_combo = QComboBox()
        self.intensity_combo.addItems([
            "Nhẹ (Light)",
            "Cân bằng (Balanced)",
            "Sâu & Kịch tính (Deep)",
        ])
        self.intensity_combo.setCurrentText("Cân bằng (Balanced)")
        intensity_row.addWidget(self.intensity_combo, 1)
        options_layout.addLayout(intensity_row)

        # Max retry
        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("Số lần thử lại tối đa khi lỗi mạng:"))
        self.retry_edit = QLineEdit("3")
        retry_row.addWidget(self.retry_edit, 1)
        options_layout.addLayout(retry_row)

        # API timeout
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Thời gian chờ phản hồi AI tối đa (giây):"))
        self.api_timeout_edit = QLineEdit("60")
        timeout_row.addWidget(self.api_timeout_edit, 1)
        options_layout.addLayout(timeout_row)

        # Save failed
        self.chk_save_failed = QCheckBox("Lưu bản sao các file bị lỗi vào thư mục 'failed'")
        self.chk_save_failed.setChecked(True)
        options_layout.addWidget(self.chk_save_failed)

        settings_layout.addLayout(options_layout)

        # Save button
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.btn_save_settings = QPushButton("Lưu Cài Đặt")
        self.btn_save_settings.setProperty("class", "primary")
        self.btn_save_settings.clicked.connect(self.save_settings)
        button_row.addWidget(self.btn_save_settings)
        settings_layout.addLayout(button_row)

        settings_layout.addStretch()
        self.center_tabs.addTab(settings_widget, "Cài Đặt")

    def create_right_panel(self, parent_layout):
        """Create right panel."""
        right_panel = QFrame()
        right_panel.setFixedWidth(310)
        right_panel.setStyleSheet(
            f"background-color: {Styles.SURFACE}; border-left: 1px solid {Styles.BORDER};"
        )

        layout = QVBoxLayout(right_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        layout.addWidget(SectionHeader("NHẬT KÝ HỆ THỐNG (LOGS)"))

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Styles.BACKGROUND};
                border: 1px solid {Styles.BORDER};
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }}
        """)
        layout.addWidget(self.log_text, 1)

        parent_layout.addWidget(right_panel)

    def create_status_bar(self):
        """Create status bar."""
        self.status_label = QLabel("Sẵn sàng")
        self.statusBar().addWidget(self.status_label)

    def init_ai(self):
        """Initialize AI components while keeping pure-Python Hybrid pre-checker always available."""
        settings = self.settings_manager.get_all()
        api_key = settings.api_key or self.api_key_edit.text().strip()

        if api_key:
            try:
                self.gemini_client = GeminiClient(
                    api_key=api_key,
                    model_name=settings.model_name
                )
                self.status_label.setText(
                    f"Hybrid Workflow: Sẵn sàng ({settings.model_name} • Mode: {settings.workflow_mode.upper()})"
                )
            except Exception as e:
                self.logger.error(f"Failed to init Gemini client: {e}")
                self.gemini_client = None
                self.status_label.setText("Gemini: Lỗi khởi tạo kết nối (Sơ tuyển Python vẫn hoạt động)")
        else:
            self.gemini_client = None
            self.status_label.setText("Chế độ Sơ tuyển Python thuần (0 Token) sẵn sàng")

        self.ai_service = AIService(
            self.gemini_client,
            api_timeout=settings.api_timeout,
            analysis_timeout=settings.analysis_timeout,
            qc_timeout=settings.qc_timeout,
            rewrite_intensity=settings.rewrite_intensity,
            max_retries=settings.max_retry,
            use_ai_analysis=False,
            use_ai_qc=settings.use_ai_qc,
            workflow_mode=settings.workflow_mode,
        )
        self._init_pipeline_components()

    def load_settings(self):
        """Load settings into UI."""
        settings = self.settings_manager.get_all()

        self.api_key_edit.setText(settings.api_key)
        self.model_combo.setCurrentText(settings.model_name)
        self.input_path_edit.setText(settings.input_folder)
        self.output_path_edit.setText(settings.output_folder)

        ui_workflow = WORKFLOW_KEY_TO_UI.get(
            settings.workflow_mode.lower(),
            WORKFLOW_KEY_TO_UI["hybrid"]
        )
        self.workflow_combo.setCurrentText(ui_workflow)

        ui_intensity = INTENSITY_KEY_TO_UI.get(
            settings.rewrite_intensity.lower(),
            "Cân bằng (Balanced)"
        )
        self.intensity_combo.setCurrentText(ui_intensity)
        self.retry_edit.setText(str(settings.max_retry))
        self.api_timeout_edit.setText(str(settings.api_timeout))
        self.chk_save_failed.setChecked(settings.save_failed)
        self.chk_export.setChecked(settings.export_srt)
        self.chk_skip_processed.setChecked(settings.skip_processed)
        self.chk_ai_qc.setChecked(settings.use_ai_qc)

    def save_settings(self):
        """Save settings from UI."""
        intensity_key = INTENSITY_UI_TO_KEY.get(
            self.intensity_combo.currentText(),
            "balanced"
        )
        workflow_key = WORKFLOW_UI_TO_KEY.get(
            self.workflow_combo.currentText(),
            "hybrid"
        )
        self.settings_manager.update(
            api_key=self.api_key_edit.text().strip(),
            model_name=self.model_combo.currentText(),
            input_folder=self.input_path_edit.text().strip(),
            output_folder=self.output_path_edit.text().strip(),
            workflow_mode=workflow_key,
            rewrite_intensity=intensity_key,
            max_retry=int(self.retry_edit.text()) if self.retry_edit.text().isdigit() else 3,
            api_timeout=int(self.api_timeout_edit.text()) if self.api_timeout_edit.text().isdigit() else 60,
            save_failed=self.chk_save_failed.isChecked(),
            export_srt=self.chk_export.isChecked(),
            skip_processed=self.chk_skip_processed.isChecked(),
            use_ai_qc=self.chk_ai_qc.isChecked(),
        )

        self.init_ai()
        if self.story_processor:
            self.story_processor.enable_analyze = self.chk_analyze.isChecked()
            self.story_processor.enable_qc = self.chk_qc.isChecked()
            self.story_processor.enable_title = self.chk_title.isChecked()
            self.story_processor.export_srt = self.chk_export.isChecked()

        self.log_message(f"Đã lưu cài đặt hệ thống (Chế độ: {workflow_key.upper()})")

    def select_input_folder(self):
        """Select input folder."""
        folder = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Đầu Vào (.SRT)")
        if folder:
            self.input_path_edit.setText(folder)

    def select_output_folder(self):
        """Select output folder."""
        folder = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Đầu Ra")
        if folder:
            self.output_path_edit.setText(folder)

    def scan_files(self):
        """Scan input folder for SRT files in pure Python without calling AI."""
        input_dir = self.input_path_edit.text().strip()
        output_dir = self.output_path_edit.text().strip()

        if not input_dir or not output_dir:
            self.log_message("Vui lòng chọn đầy đủ thư mục đầu vào và thư mục đầu ra")
            return

        if not os.path.exists(input_dir):
            self.log_message("Thư mục đầu vào không tồn tại")
            return

        self._init_pipeline_components()
        self.batch_processor.skip_already_processed = self.chk_skip_processed.isChecked()

        count = self.batch_processor.scan_directory(input_dir, output_dir)

        self.update_queue_display()
        self.update_stats()
        self.load_output_files_into_editor()

        waiting_count = sum(
            1 for s in self.batch_processor.get_file_statuses()
            if s.status == ProcessingState.WAITING
        )
        skipped_count = count - waiting_count
        if skipped_count > 0:
            self.log_message(
                f"Đã quét {count} file SRT theo thứ tự tự nhiên ({waiting_count} chờ xử lý, {skipped_count} đã hoàn thành trước đó)"
            )
        else:
            self.log_message(f"Đã quét {count} file SRT theo thứ tự tự nhiên (Python thuần — 0 tốn token)")

    def update_queue_display(self):
        """Update queue list display."""
        if not self.batch_processor:
            return
        statuses = self.batch_processor.get_file_statuses()

        lines = []
        for idx, status in enumerate(statuses, 1):
            status_text = STAGE_VI_MAP.get(status.status.value, status.status.value.upper())
            if status.output_filename:
                lines.append(f"[{idx:02d}] {status.filename} -> {status_text} ({status.output_filename})")
            else:
                lines.append(f"[{idx:02d}] {status.filename} -> {status_text}")

        self.queue_list.setPlainText("\n".join(lines))

    def update_stats(self):
        """Update statistics display."""
        if self.batch_processor:
            current, total, completed, failed = self.batch_processor.get_progress()
            processing = 1 if self.batch_processor.state == BatchState.PROCESSING else 0
            self.stats_card.update_stats(total, completed, processing, failed)

    def start_processing(self):
        """Start or resume batch processing."""
        self.save_settings()
        settings = self.settings_manager.get_all()

        # Require API key only if workflow_mode is not python_only
        if settings.workflow_mode != "python_only" and not self.gemini_client:
            self.log_message(
                "Vui lòng nhập Gemini API Key trong tab Cài Đặt (hoặc chọn chế độ 'Chỉ Sơ Tuyển Python 0 Token')"
            )
            self.center_tabs.setCurrentIndex(3)
            return

        if not self.batch_processor or len(self.batch_processor.files) == 0:
            self.log_message("Chưa có file nào trong hàng đợi. Vui lòng bấm 'Quét Thứ Tự File' trước.")
            return

        if self.batch_worker and self.batch_worker.isRunning():
            return

        if self.batch_processor.state == BatchState.PAUSED:
            self.batch_processor.resume()

        self.batch_worker = BatchWorker(self.batch_processor)
        self.batch_worker.progress_update.connect(self.on_progress_update)
        self.batch_worker.log_message.connect(self.log_message)
        self.batch_worker.file_completed.connect(self.on_file_completed)
        self.batch_worker.finished.connect(self.on_processing_finished)

        self.progress_card.start_btn.setText("BẮT ĐẦU CHẠY")
        self.progress_card.set_processing(True)
        self.btn_scan.setEnabled(False)

        self.batch_worker.start()
        self.log_message(f"Bắt đầu xử lý hàng loạt (Chế độ: {settings.workflow_mode.upper()})")

    def pause_processing(self):
        """Pause processing."""
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.pause()
            self.log_message("Đã yêu cầu tạm dừng — sẽ tạm dừng ngay sau khi xong file hiện tại")

    def stop_processing(self):
        """Stop processing."""
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.log_message("Đã yêu cầu dừng hẳn tiến trình")

    def on_progress_update(self, filename: str, stage: str, current: int, total: int):
        """Handle progress update."""
        self.progress_card.update_progress(filename, stage, current, total)
        self.update_queue_display()
        self.update_stats()
        stage_vi = STAGE_VI_MAP.get(stage.lower(), stage.upper())
        self.status_label.setText(f"Tiến độ: {current}/{total} — {stage_vi}")

    def on_file_completed(self, status_obj: FileStatus):
        """Handle individual file completion: show result + Pre-Check report immediately."""
        if status_obj.status == ProcessingState.COMPLETED and status_obj.formatted_output:
            self._current_preview_status = status_obj
            self.quick_result_preview.setPlainText(status_obj.formatted_output)
            if status_obj.precheck_report_text:
                self.precheck_report_box.setPlainText(status_obj.precheck_report_text)
            self.load_output_files_into_editor(select_path=status_obj.output_path)

        if status_obj.status in (ProcessingState.COMPLETED, ProcessingState.FAILED):
            entry = HistoryEntry(
                original_filename=status_obj.filename,
                output_filename=status_obj.output_filename,
                status=status_obj.status.value,
                start_time=datetime.now().isoformat(),
                finish_time=datetime.now().isoformat(),
                duration_seconds=status_obj.duration_seconds,
                title=status_obj.title,
                error_message=status_obj.error_message,
            )
            self.history_manager.add_entry(entry)
            self.refresh_history()

    def on_processing_finished(self):
        """Handle worker thread completion (paused, stopped, or completed)."""
        self.progress_card.set_processing(False)
        self.btn_scan.setEnabled(True)
        self.update_queue_display()
        self.update_stats()

        if self.batch_processor and self.batch_processor.state == BatchState.PAUSED:
            self.progress_card.start_btn.setText("TIẾP TỤC CHẠY")
            self.progress_card.stage_label.setText("Trạng thái: ĐÃ TẠM DỪNG")
            self.status_label.setText("Đã tạm dừng")
            self.log_message("Đã tạm dừng hàng đợi. Bấm 'TIẾP TỤC CHẠY' để chạy tiếp.")
        elif self.batch_processor and self.batch_processor.state == BatchState.STOPPED:
            self.progress_card.reset()
            self.status_label.setText("Đã dừng")
            self.log_message("Đã dừng xử lý hàng đợi.")
        else:
            self.progress_card.reset()
            self.status_label.setText("Hoàn thành toàn bộ")
            self.log_message("Đã hoàn thành xử lý toàn bộ hàng đợi!")

    # ============================================================
    # HYBRID RESULT VIEWER & EDITOR ("SƠ TUYỂN PYTHON & SỬA KẾT QUẢ")
    # ============================================================

    def run_python_precheck_on_editor(self):
        """Run 0-token pure-Python Pre-Check on the current text in the editor."""
        raw_script = self.edit_script_text.toPlainText().strip()
        if not raw_script:
            self.log_message("Chưa có nội dung trong khung kịch bản để chạy Sơ tuyển Python")
            return

        report = self.pre_checker.analyze_and_prepare(raw_script)
        self.precheck_report_box.setPlainText(report.to_vietnamese_summary())
        self.edit_script_text.setPlainText("\n\n".join(report.paragraphs))
        self.log_message(
            f"Sơ tuyển Python (0 Token): {len(report.clean_indices)} đoạn sạch, "
            f"{len(report.flagged_indices)} đoạn gắn cờ (Tiết kiệm ~{report.token_savings_estimate_pct}% token)"
        )

    def run_hybrid_ai_on_editor(self):
        """Use Hybrid AI mode to polish ONLY the paragraphs flagged by Python in the editor."""
        raw_script = self.edit_script_text.toPlainText().strip()
        if not raw_script:
            self.log_message("Chưa có nội dung kịch bản để tinh chỉnh")
            return

        if not self.gemini_client:
            self.save_settings()
        if not self.gemini_client:
            self.log_message("Vui lòng nhập Gemini API Key trong tab Cài Đặt trước khi gọi AI")
            return

        report = self.pre_checker.analyze_and_prepare(raw_script)
        self.precheck_report_box.setPlainText(report.to_vietnamese_summary())

        if not report.flagged_indices:
            self.log_message(
                "Tất cả các đoạn đã đạt chuẩn (0 đoạn bị gắn cờ) — không cần tốn token gọi AI sửa lại!"
            )
            return

        self.log_message(
            f"Đang gửi riêng {len(report.flagged_indices)}/{len(report.paragraphs)} đoạn gắn cờ lên AI..."
        )
        polished_script = self.ai_service.rewrite_flagged_paragraphs_only(report)
        if polished_script:
            self.edit_script_text.setPlainText(polished_script)
            if self.ai_service.last_title and not self.edit_title_input.text().strip():
                self.edit_title_input.setText(self.ai_service.last_title)
            self.log_message(
                f"Đã sửa xong {len(report.flagged_indices)} đoạn gắn cờ bằng AI (Tiết kiệm ~{report.token_savings_estimate_pct}% token)"
            )

    def load_output_files_into_editor(self, select_path: str = None):
        """Scan output folder in pure Python and populate the Result Editor dropdown."""
        output_dir = self.output_path_edit.text().strip()
        if not output_dir or not os.path.exists(output_dir):
            return

        files = []
        try:
            with os.scandir(output_dir) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.lower().endswith('.txt'):
                        files.append(entry.path)
        except OSError:
            return

        files.sort()
        self.result_file_combo.blockSignals(True)
        self.result_file_combo.clear()
        for path in files:
            self.result_file_combo.addItem(os.path.basename(path), path)
        self.result_file_combo.blockSignals(False)

        if select_path:
            idx = self.result_file_combo.findData(select_path)
            if idx >= 0:
                self.result_file_combo.setCurrentIndex(idx)
                self.on_result_file_selected(idx)
        elif files:
            self.on_result_file_selected(self.result_file_combo.currentIndex())

    def on_result_file_selected(self, index: int):
        """Load selected output file into the Title, TTS Script, and Python Pre-Check Report fields."""
        if index < 0:
            return
        filepath = self.result_file_combo.itemData(index)
        if not filepath or not os.path.exists(filepath):
            return

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                raw_content = f.read()
            title, tts_script = parse_unified_ai_output(raw_content)
            script_text = tts_script or raw_content
            self.edit_title_input.setText(title or "")
            self.edit_script_text.setPlainText(script_text)

            # Automatically run 0-token Python Pre-Check report on the loaded script
            report = self.pre_checker.analyze_and_prepare(script_text)
            self.precheck_report_box.setPlainText(report.to_vietnamese_summary())
        except Exception as e:
            self.log_message(f"Không thể đọc file kết quả: {e}")

    def format_current_editor_script(self):
        """Format the TTS script in the editor into 2-3 sentence paragraphs using pure Python."""
        raw_script = self.edit_script_text.toPlainText()
        formatted = format_tts_paragraphs(raw_script, sentences_per_paragraph=3)
        self.edit_script_text.setPlainText(formatted)
        report = self.pre_checker.analyze_and_prepare(formatted)
        self.precheck_report_box.setPlainText(report.to_vietnamese_summary())
        self.log_message("Đã chuẩn hóa kịch bản thành đoạn ngắn 2-3 câu/đoạn cho TTS")

    def save_edited_result_to_disk(self):
        """Save changes made in the Result Editor back to the output file."""
        idx = self.result_file_combo.currentIndex()
        if idx < 0:
            self.log_message("Chưa chọn file kết quả để lưu")
            return

        filepath = self.result_file_combo.itemData(idx)
        if not filepath:
            return

        new_title = self.edit_title_input.text().strip() or "Story"
        new_script = format_tts_paragraphs(self.edit_script_text.toPlainText(), sentences_per_paragraph=3)
        unified_content = format_unified_output(new_title, new_script)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(unified_content)
            self.edit_script_text.setPlainText(new_script)
            self.quick_result_preview.setPlainText(unified_content)
            self.log_message(f"Đã lưu kết quả chỉnh sửa vào: {os.path.basename(filepath)}")
        except Exception as e:
            self.log_message(f"Lỗi khi lưu kết quả: {e}")

    def save_quick_preview_edits(self):
        """Save edits made directly in the Queue tab's quick preview box."""
        raw_text = self.quick_result_preview.toPlainText().strip()
        if not raw_text:
            return

        title, script = parse_unified_ai_output(raw_text)
        unified = format_unified_output(title or "Story", script)
        self.quick_result_preview.setPlainText(unified)

        status_obj = getattr(self, "_current_preview_status", None)
        if status_obj and status_obj.output_path:
            try:
                with open(status_obj.output_path, 'w', encoding='utf-8') as f:
                    f.write(unified)
                self.log_message(f"Đã lưu chỉnh sửa nhanh vào: {status_obj.output_filename}")
                self.load_output_files_into_editor(select_path=status_obj.output_path)
            except Exception as e:
                self.log_message(f"Lỗi lưu chỉnh sửa nhanh: {e}")

    def copy_quick_tts_script(self):
        """Copy only the ---TTS_SCRIPT--- portion from the quick preview to clipboard."""
        _, script = parse_unified_ai_output(self.quick_result_preview.toPlainText())
        if script:
            QApplication.clipboard().setText(script)
            self.log_message("Đã sao chép kịch bản TTS vào bộ nhớ tạm (Clipboard)")

    def copy_editor_tts_only(self):
        """Copy the TTS script from the Result Editor to clipboard."""
        script = self.edit_script_text.toPlainText().strip()
        if script:
            QApplication.clipboard().setText(script)
            self.log_message("Đã sao chép kịch bản TTS vào bộ nhớ tạm (Clipboard)")

    def copy_editor_unified(self):
        """Copy the full ---TITLE--- and ---TTS_SCRIPT--- block to clipboard."""
        title = self.edit_title_input.text().strip() or "Story"
        script = self.edit_script_text.toPlainText().strip()
        unified = format_unified_output(title, script)
        QApplication.clipboard().setText(unified)
        self.log_message("Đã sao chép toàn bộ ---TITLE--- & ---TTS_SCRIPT--- vào Clipboard")

    # ============================================================
    # CONNECTION & HISTORY
    # ============================================================

    def test_api_connection(self):
        """Test API connection."""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            self.log_message("Vui lòng nhập Gemini API Key để kiểm tra")
            return

        model_name = self.model_combo.currentText()
        try:
            client = GeminiClient(api_key, model_name=model_name)
            if client.test_connection():
                self.log_message(f"Kết nối Gemini API thành công ({client.model_name})")
                self.status_label.setText(f"Gemini: Đã kết nối ({client.model_name})")
            else:
                self.log_message("Kết nối Gemini API thất bại — Vui lòng kiểm tra lại API Key")
        except Exception as e:
            self.log_message(f"Lỗi kiểm tra API: {e}")

    def refresh_history(self):
        """Refresh history display."""
        entries = self.history_manager.get_recent(50)

        text = ""
        for entry in entries:
            status = "HOÀN THÀNH" if entry.status == "completed" else "THẤT BẠI"
            text += f"{entry.original_filename} -> {status} ({entry.duration_seconds:.1f}s)\n"
            if entry.title:
                text += f"  Tiêu đề: {entry.title}\n"
            if entry.output_filename:
                text += f"  File xuất: {entry.output_filename}\n"
            if entry.error_message:
                text += f"  Lỗi: {entry.error_message}\n"
            text += "\n"

        self.history_list.setPlainText(text)

    def clear_history(self):
        """Clear history."""
        self.history_manager.clear()
        self.refresh_history()
        self.log_message("Đã xóa toàn bộ lịch sử xử lý")

    def log_message(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def on_process_clicked(self):
        """Handle process button click."""
        self.center_tabs.setCurrentIndex(0)
