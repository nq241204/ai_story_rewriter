"""Main window for AI Story Rewriter."""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QCheckBox, QFileDialog,
    QScrollArea, QFrame, QSplitter, QTextEdit, QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from app.ui.styles import Styles
from app.ui.widgets import (
    FileListItem, ProgressCard, StatsCard, SectionHeader, StatusBadge
)
from app.storage.settings import SettingsManager
from app.storage.history import HistoryManager, HistoryEntry
from app.ai.gemini_client import GeminiClient
from app.ai.ai_service import AIService
from app.pipeline.story_processor import StoryProcessor, ProcessingState
from app.pipeline.batch_processor import BatchProcessor, BatchState
from app.utils.logger import get_logger
from datetime import datetime


class BatchWorker(QThread):
    """Worker thread for batch processing."""
    
    progress_update = Signal(str, str, int, int)  # filename, stage (string), current, total
    log_message = Signal(str)
    finished = Signal()
    
    def __init__(self, batch_processor: BatchProcessor):
        super().__init__()
        self.batch_processor = batch_processor
    
    def run(self):
        """Run batch processing."""
        self.batch_processor.start(
            progress_callback=self.progress_update.emit,
            log_callback=self.log_message.emit
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
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.logger = get_logger()
        self.settings_manager = SettingsManager()
        self.history_manager = HistoryManager()
        
        # Initialize components
        self.gemini_client = None
        self.ai_service = None
        self.story_processor = None
        self.batch_processor = None
        self.batch_worker = None
        
        self.init_ui()
        self.load_settings()
        self.init_ai()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("AI Story Rewriter")
        self.setMinimumSize(1200, 800)
        
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
        left_panel.setFixedWidth(250)
        left_panel.setStyleSheet(f"background-color: {Styles.SURFACE}; border-right: 1px solid {Styles.BORDER};")
        
        layout = QVBoxLayout(left_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("AI STORY\nREWRITER")
        title.setProperty("class", "heading")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; line-height: 1.2;")
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # Stats card
        self.stats_card = StatsCard()
        layout.addWidget(self.stats_card)
        
        layout.addSpacing(20)
        
        # Navigation buttons
        nav_buttons = QVBoxLayout()
        nav_buttons.setSpacing(8)
        
        self.btn_process = QPushButton("Process Files")
        self.btn_process.setProperty("class", "primary")
        self.btn_process.clicked.connect(self.on_process_clicked)
        nav_buttons.addWidget(self.btn_process)
        
        self.btn_queue = QPushButton("Queue")
        self.btn_queue.clicked.connect(lambda: self.center_tabs.setCurrentIndex(0))
        nav_buttons.addWidget(self.btn_queue)
        
        self.btn_history = QPushButton("History")
        self.btn_history.clicked.connect(lambda: self.center_tabs.setCurrentIndex(1))
        nav_buttons.addWidget(self.btn_history)
        
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(lambda: self.center_tabs.setCurrentIndex(2))
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
        
        # Queue tab
        self.create_queue_tab()
        
        # History tab
        self.create_history_tab()
        
        # Settings tab
        self.create_settings_tab()
        
        center_layout.addWidget(self.center_tabs)
        
        parent_layout.addWidget(center_panel, 1)
    
    def create_queue_tab(self):
        """Create queue tab."""
        queue_widget = QWidget()
        queue_layout = QVBoxLayout(queue_widget)
        queue_layout.setSpacing(16)
        
        # Folder selection
        folder_layout = QHBoxLayout()
        
        input_group = QVBoxLayout()
        input_group.addWidget(QLabel("INPUT FOLDER"))
        input_row = QHBoxLayout()
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("Select input folder...")
        self.btn_select_input = QPushButton("Select Folder")
        self.btn_select_input.clicked.connect(self.select_input_folder)
        input_row.addWidget(self.input_path_edit, 1)
        input_row.addWidget(self.btn_select_input)
        input_group.addLayout(input_row)
        folder_layout.addLayout(input_group, 1)
        
        output_group = QVBoxLayout()
        output_group.addWidget(QLabel("OUTPUT FOLDER"))
        output_row = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output folder...")
        self.btn_select_output = QPushButton("Select Folder")
        self.btn_select_output.clicked.connect(self.select_output_folder)
        output_row.addWidget(self.output_path_edit, 1)
        output_row.addWidget(self.btn_select_output)
        output_group.addLayout(output_row)
        folder_layout.addLayout(output_group, 1)
        
        queue_layout.addLayout(folder_layout)
        
        # Scan button
        self.btn_scan = QPushButton("Scan Files")
        self.btn_scan.setProperty("class", "primary")
        self.btn_scan.clicked.connect(self.scan_files)
        queue_layout.addWidget(self.btn_scan)
        
        # Queue list
        queue_layout.addWidget(SectionHeader("QUEUE"))
        
        self.queue_list = QTextEdit()
        self.queue_list.setReadOnly(True)
        self.queue_list.setMaximumHeight(200)
        queue_layout.addWidget(self.queue_list)
        
        # Progress card
        queue_layout.addWidget(SectionHeader("CURRENT STORY"))
        
        self.progress_card = ProgressCard()
        queue_layout.addWidget(self.progress_card)
        
        # Connect buttons
        self.progress_card.start_btn.clicked.connect(self.start_processing)
        self.progress_card.pause_btn.clicked.connect(self.pause_processing)
        self.progress_card.stop_btn.clicked.connect(self.stop_processing)
        
        queue_layout.addStretch()
        
        self.center_tabs.addTab(queue_widget, "Queue")
    
    def create_history_tab(self):
        """Create history tab."""
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setSpacing(16)
        
        history_layout.addWidget(SectionHeader("PROCESSING HISTORY"))
        
        self.history_list = QTextEdit()
        self.history_list.setReadOnly(True)
        history_layout.addWidget(self.history_list)
        
        button_row = QHBoxLayout()
        self.btn_refresh_history = QPushButton("Refresh")
        self.btn_refresh_history.clicked.connect(self.refresh_history)
        self.btn_clear_history = QPushButton("Clear History")
        self.btn_clear_history.setProperty("class", "danger")
        self.btn_clear_history.clicked.connect(self.clear_history)
        button_row.addWidget(self.btn_refresh_history)
        button_row.addWidget(self.btn_clear_history)
        button_row.addStretch()
        history_layout.addLayout(button_row)
        
        self.center_tabs.addTab(history_widget, "History")
    
    def create_settings_tab(self):
        """Create settings tab."""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(16)
        
        # AI Settings
        settings_layout.addWidget(SectionHeader("AI SETTINGS"))
        
        ai_layout = QVBoxLayout()
        
        # Provider
        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Provider:"))
        provider_row.addWidget(QLabel("Google Gemini"))
        provider_row.addStretch()
        ai_layout.addLayout(provider_row)
        
        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-2.5-pro"
        ])
        model_row.addWidget(self.model_combo, 1)
        ai_layout.addLayout(model_row)
        
        # API Key
        api_row = QHBoxLayout()
        api_row.addWidget(QLabel("API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter Gemini API key...")
        api_row.addWidget(self.api_key_edit, 1)
        self.btn_test_api = QPushButton("Test Connection")
        self.btn_test_api.clicked.connect(self.test_api_connection)
        api_row.addWidget(self.btn_test_api)
        ai_layout.addLayout(api_row)
        
        settings_layout.addLayout(ai_layout)
        
        # Processing Options
        settings_layout.addWidget(SectionHeader("PROCESSING OPTIONS"))
        
        options_layout = QVBoxLayout()
        
        self.chk_analyze = QCheckBox("Analyze story")
        self.chk_analyze.setChecked(True)
        options_layout.addWidget(self.chk_analyze)
        
        self.chk_rewrite = QCheckBox("Rewrite story")
        self.chk_rewrite.setChecked(True)
        options_layout.addWidget(self.chk_rewrite)
        
        self.chk_qc = QCheckBox("Logic & continuity QC")
        self.chk_qc.setChecked(True)
        options_layout.addWidget(self.chk_qc)
        
        self.chk_title = QCheckBox("Generate CTR title")
        self.chk_title.setChecked(True)
        options_layout.addWidget(self.chk_title)
        
        self.chk_export = QCheckBox("Export SRT")
        self.chk_export.setChecked(True)
        options_layout.addWidget(self.chk_export)
        
        # Rewrite intensity
        intensity_row = QHBoxLayout()
        intensity_row.addWidget(QLabel("Rewrite intensity:"))
        self.intensity_combo = QComboBox()
        self.intensity_combo.addItems(["Light", "Balanced", "Deep"])
        self.intensity_combo.setCurrentText("Balanced")
        intensity_row.addWidget(self.intensity_combo, 1)
        options_layout.addLayout(intensity_row)
        
        # Max retry
        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("Max retry:"))
        self.retry_edit = QLineEdit("3")
        retry_row.addWidget(self.retry_edit, 1)
        options_layout.addLayout(retry_row)
        
        # API timeout
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("API timeout (s):"))
        self.api_timeout_edit = QLineEdit("60")
        timeout_row.addWidget(self.api_timeout_edit, 1)
        options_layout.addLayout(timeout_row)
        
        # Save failed
        self.chk_save_failed = QCheckBox("Save failed files")
        self.chk_save_failed.setChecked(True)
        options_layout.addWidget(self.chk_save_failed)
        
        settings_layout.addLayout(options_layout)
        
        # Save button
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.btn_save_settings = QPushButton("Save Settings")
        self.btn_save_settings.setProperty("class", "primary")
        self.btn_save_settings.clicked.connect(self.save_settings)
        button_row.addWidget(self.btn_save_settings)
        settings_layout.addLayout(button_row)
        
        settings_layout.addStretch()
        
        self.center_tabs.addTab(settings_widget, "Settings")
    
    def create_right_panel(self, parent_layout):
        """Create right panel."""
        right_panel = QFrame()
        right_panel.setFixedWidth(300)
        right_panel.setStyleSheet(f"background-color: {Styles.SURFACE}; border-left: 1px solid {Styles.BORDER};")
        
        layout = QVBoxLayout(right_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Log section
        layout.addWidget(SectionHeader("LOGS"))
        
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
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)
    
    def init_ai(self):
        """Initialize AI components."""
        api_key = self.settings_manager.get("api_key")
        if api_key:
            self.gemini_client = GeminiClient(api_key)
            self.ai_service = AIService(
                self.gemini_client,
                api_timeout=self.settings_manager.get("api_timeout", 60),
                analysis_timeout=self.settings_manager.get("analysis_timeout", 30),
                qc_timeout=self.settings_manager.get("qc_timeout", 30)
            )
            self.story_processor = StoryProcessor(self.ai_service)
            self.batch_processor = BatchProcessor(self.story_processor)
            self.status_label.setText("Gemini: Connected")
        else:
            self.status_label.setText("Gemini: Not configured")
    
    def load_settings(self):
        """Load settings into UI."""
        settings = self.settings_manager.get_all()
        
        self.api_key_edit.setText(settings.api_key)
        self.model_combo.setCurrentText(settings.model_name)
        self.input_path_edit.setText(settings.input_folder)
        self.output_path_edit.setText(settings.output_folder)
        self.intensity_combo.setCurrentText(settings.rewrite_intensity.capitalize())
        self.retry_edit.setText(str(settings.max_retry))
        self.api_timeout_edit.setText(str(settings.api_timeout))
        self.chk_save_failed.setChecked(settings.save_failed)
    
    def save_settings(self):
        """Save settings from UI."""
        self.settings_manager.update(
            api_key=self.api_key_edit.text(),
            model_name=self.model_combo.currentText(),
            input_folder=self.input_path_edit.text(),
            output_folder=self.output_path_edit.text(),
            rewrite_intensity=self.intensity_combo.currentText().lower(),
            max_retry=int(self.retry_edit.text()) if self.retry_edit.text().isdigit() else 3,
            api_timeout=int(self.api_timeout_edit.text()) if self.api_timeout_edit.text().isdigit() else 60,
            save_failed=self.chk_save_failed.isChecked()
        )
        
        # Reinitialize AI with new settings
        self.init_ai()
        
        self.log_message("Settings saved")
    
    def select_input_folder(self):
        """Select input folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_path_edit.setText(folder)
    
    def select_output_folder(self):
        """Select output folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_path_edit.setText(folder)
    
    def scan_files(self):
        """Scan input folder for SRT files."""
        input_dir = self.input_path_edit.text()
        output_dir = self.output_path_edit.text()
        
        if not input_dir or not output_dir:
            self.log_message("Please select input and output folders")
            return
        
        if not os.path.exists(input_dir):
            self.log_message("Input folder does not exist")
            return
        
        if not self.batch_processor:
            self.init_ai()
        
        count = self.batch_processor.scan_directory(input_dir, output_dir)
        
        # Update queue display
        self.update_queue_display()
        
        # Update stats
        self.update_stats()
        
        self.log_message(f"Found {count} SRT files")
    
    def update_queue_display(self):
        """Update queue list display."""
        statuses = self.batch_processor.get_file_statuses()
        
        text = ""
        for status in statuses:
            status_text = status.status.value.upper()
            text += f"{status.filename} -> {status_text}\n"
        
        self.queue_list.setText(text)
    
    def update_stats(self):
        """Update statistics display."""
        if self.batch_processor:
            current, total, completed, failed = self.batch_processor.get_progress()
            processing = 1 if self.batch_processor.state == BatchState.PROCESSING else 0
            self.stats_card.update_stats(total, completed, processing, failed)
    
    def start_processing(self):
        """Start batch processing."""
        if not self.batch_processor:
            self.init_ai()
        
        if not self.batch_processor or len(self.batch_processor.files) == 0:
            self.log_message("No files to process")
            return
        
        if self.batch_worker and self.batch_worker.isRunning():
            return
        
        # Create worker
        self.batch_worker = BatchWorker(self.batch_processor)
        self.batch_worker.progress_update.connect(self.on_progress_update)
        self.batch_worker.log_message.connect(self.log_message)
        self.batch_worker.finished.connect(self.on_processing_finished)
        
        # Update UI
        self.progress_card.set_processing(True)
        self.btn_scan.setEnabled(False)
        
        # Start
        self.batch_worker.start()
        self.log_message("Processing started")
    
    def pause_processing(self):
        """Pause processing."""
        if self.batch_worker:
            self.batch_worker.pause()
            self.log_message("Processing paused")
    
    def stop_processing(self):
        """Stop processing."""
        if self.batch_worker:
            self.batch_worker.stop()
            self.log_message("Processing stopped")
    
    def on_progress_update(self, filename: str, stage: str, current: int, total: int):
        """Handle progress update."""
        self.progress_card.update_progress(filename, stage, current, total)
        self.update_queue_display()
        self.update_stats()
        self.status_label.setText(f"{current} / {total} - {stage.upper()}")
    
    def on_processing_finished(self):
        """Handle processing finished."""
        self.progress_card.set_processing(False)
        self.progress_card.reset()
        self.btn_scan.setEnabled(True)
        self.update_queue_display()
        self.update_stats()
        self.log_message("Processing completed")
        
        # Save to history
        self.save_batch_to_history()
    
    def save_batch_to_history(self):
        """Save batch results to history."""
        statuses = self.batch_processor.get_file_statuses()
        for status in statuses:
            entry = HistoryEntry(
                original_filename=status.filename,
                output_filename=status.output_filename,
                status=status.status.value,
                start_time=datetime.now().isoformat(),
                finish_time=datetime.now().isoformat(),
                duration_seconds=0.0,
                error_message=status.error_message
            )
            self.history_manager.add_entry(entry)
    
    def test_api_connection(self):
        """Test API connection."""
        api_key = self.api_key_edit.text()
        if not api_key:
            self.log_message("Please enter API key")
            return
        
        try:
            client = GeminiClient(api_key)
            if client.test_connection():
                self.log_message("API connection successful")
                self.status_label.setText("Gemini: Connected")
            else:
                self.log_message("API connection failed")
        except Exception as e:
            self.log_message(f"API test error: {e}")
    
    def refresh_history(self):
        """Refresh history display."""
        entries = self.history_manager.get_recent(50)
        
        text = ""
        for entry in entries:
            status = "DONE" if entry.status == "completed" else "FAILED"
            text += f"{entry.original_filename} -> {status}\n"
            if entry.output_filename:
                text += f"  Output: {entry.output_filename}\n"
            if entry.error_message:
                text += f"  Error: {entry.error_message}\n"
            text += "\n"
        
        self.history_list.setText(text)
    
    def clear_history(self):
        """Clear history."""
        self.history_manager.clear()
        self.refresh_history()
        self.log_message("History cleared")
    
    def log_message(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def on_process_clicked(self):
        """Handle process button click."""
        self.center_tabs.setCurrentIndex(0)
