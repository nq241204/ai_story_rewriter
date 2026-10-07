"""Batch processor for AI Story Rewriter."""

import os
from enum import Enum
from typing import List, Optional, Callable
from dataclasses import dataclass
from app.pipeline.story_processor import StoryProcessor, ProcessingResult, ProcessingState
from app.utils.logger import get_logger
from app.utils.filenames import (
    sort_files_naturally,
    extract_file_number,
    get_processed_prefixes,
)


class BatchState(Enum):
    """States for batch processing."""
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class FileStatus:
    """Status of a file in the batch."""
    filename: str
    status: ProcessingState
    output_filename: Optional[str] = None
    output_path: Optional[str] = None
    title: Optional[str] = None
    tts_script: Optional[str] = None
    formatted_output: Optional[str] = None
    precheck_report_text: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class BatchProcessor:
    """Processor for batch SRT file processing with pure-Python natural sorting."""

    def __init__(self, story_processor: StoryProcessor, skip_already_processed: bool = False):
        """
        Initialize batch processor.

        Args:
            story_processor: StoryProcessor instance
            skip_already_processed: If True, skip files that already exist in output_dir
        """
        self.story_processor = story_processor
        self.skip_already_processed = skip_already_processed
        self.logger = get_logger()

        self.state = BatchState.IDLE
        self.input_dir: Optional[str] = None
        self.output_dir: Optional[str] = None

        self.files: List[str] = []
        self.file_statuses: List[FileStatus] = []
        self.current_index = 0

        self._should_stop = False
        self._should_pause = False

    def scan_directory(self, input_dir: str, output_dir: str) -> int:
        """
        Scan input directory for SRT files using pure Python (0 AI calls)
        and sort them in natural numeric order (001, 002, ..., 010).

        Args:
            input_dir: Input directory path
            output_dir: Output directory path

        Returns:
            Number of files found
        """
        self.logger.info(f"Scanning directory (pure Python): {input_dir}")

        self.input_dir = input_dir
        self.output_dir = output_dir

        files: List[str] = []
        if os.path.exists(input_dir):
            with os.scandir(input_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    filename = entry.name
                    if filename.startswith('.'):
                        continue
                    if filename.lower().endswith('.srt'):
                        files.append(filename)

        # Pure-Python natural numeric sort (001.srt, 002.srt, 010.srt)
        self.files = sort_files_naturally(files)

        processed_prefixes = (
            get_processed_prefixes(output_dir)
            if self.skip_already_processed
            else set()
        )

        self.file_statuses = []
        for f in self.files:
            prefix = extract_file_number(f)
            base_lower = os.path.splitext(f)[0].lower()
            if self.skip_already_processed and (
                (prefix and prefix in processed_prefixes) or base_lower in processed_prefixes
            ):
                self.file_statuses.append(
                    FileStatus(filename=f, status=ProcessingState.COMPLETED)
                )
            else:
                self.file_statuses.append(
                    FileStatus(filename=f, status=ProcessingState.WAITING)
                )

        self.current_index = 0
        self.state = BatchState.IDLE
        self.logger.info(f"Found {len(self.files)} SRT files (sorted naturally in Python)")

        return len(self.files)

    def get_file_statuses(self) -> List[FileStatus]:
        """Get current status of all files."""
        return self.file_statuses

    def get_progress(self) -> tuple:
        """
        Get batch processing progress.

        Returns:
            Tuple of (current, total, completed, failed)
        """
        total = len(self.file_statuses)
        completed = sum(
            1 for s in self.file_statuses
            if s.status == ProcessingState.COMPLETED
        )
        failed = sum(
            1 for s in self.file_statuses
            if s.status == ProcessingState.FAILED
        )

        return (min(self.current_index + 1, max(1, total)), total, completed, failed)

    def start(
        self,
        progress_callback: Optional[Callable[[str, str, int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        file_completed_callback: Optional[Callable[[FileStatus], None]] = None,
    ) -> None:
        """
        Start batch processing sequentially in natural file order.
        Only calls AI for files that need processing.
        """
        if self.state == BatchState.PROCESSING:
            self.logger.warning("Already processing")
            return

        self.state = BatchState.PROCESSING
        self._should_stop = False
        self._should_pause = False

        self.logger.info("Starting batch processing")
        total_files = len(self.files)

        for i in range(self.current_index, total_files):
            if self._should_stop:
                self.state = BatchState.STOPPED
                self.logger.info("Batch processing stopped")
                break

            if self._should_pause:
                self.state = BatchState.PAUSED
                self.logger.info("Batch processing paused")
                break

            filename = self.files[i]
            status_obj = self.file_statuses[i]

            # Skip files already marked COMPLETED (e.g., when resuming or skip_already_processed)
            if status_obj.status == ProcessingState.COMPLETED:
                if log_callback:
                    log_callback(f"{filename} -> SKIPPED (Already completed)")
                self.current_index = i + 1
                continue

            input_path = os.path.join(self.input_dir, filename)

            # Fast pure-Python pre-check: avoid calling AI if file is empty (0 bytes)
            try:
                if os.path.getsize(input_path) == 0:
                    status_obj.status = ProcessingState.FAILED
                    status_obj.error_message = "Empty SRT file (skipped before AI call)"
                    if log_callback:
                        log_callback(f"{filename} -> FAILED (Empty file, 0 tokens used)")
                    self.current_index = i + 1
                    continue
            except OSError:
                pass

            # Update status to reading
            status_obj.status = ProcessingState.READING

            if progress_callback:
                progress_callback(filename, ProcessingState.READING.value, i + 1, total_files)

            result = self.story_processor.process_file(
                input_path,
                self.output_dir,
                progress_callback=lambda state, fn, idx=i: self._update_progress(
                    idx, state, fn, progress_callback
                )
            )

            # Update status with full result details
            status_obj.status = result.status
            status_obj.output_filename = result.output_filename
            status_obj.output_path = result.output_path
            status_obj.title = result.title
            status_obj.tts_script = result.tts_script
            status_obj.formatted_output = result.formatted_output
            status_obj.precheck_report_text = result.precheck_report_text
            status_obj.error_message = result.error_message
            status_obj.duration_seconds = result.duration_seconds

            if file_completed_callback:
                file_completed_callback(status_obj)

            if log_callback:
                if result.status == ProcessingState.COMPLETED:
                    log_callback(
                        f"{filename} -> DONE ({result.duration_seconds:.1f}s) | {result.output_filename}"
                    )
                else:
                    log_callback(
                        f"{filename} -> FAILED ({result.error_message})"
                    )

            self.current_index = i + 1

        if not self._should_stop and not self._should_pause:
            self.state = BatchState.COMPLETED
            self.logger.info("Batch processing completed")

    def _update_progress(
        self,
        index: int,
        state: ProcessingState,
        filename: str,
        callback: Optional[Callable[[str, str, int, int], None]]
    ) -> None:
        """Update progress during file processing."""
        self.file_statuses[index].status = state
        if callback:
            callback(filename, state.value, index + 1, len(self.files))

    def pause(self) -> None:
        """Pause batch processing."""
        if self.state == BatchState.PROCESSING:
            self._should_pause = True
            self.logger.info("Pause requested")

    def resume(self) -> None:
        """Resume batch processing."""
        if self.state == BatchState.PAUSED:
            self._should_pause = False
            self.logger.info("Resuming")

    def stop(self) -> None:
        """Stop batch processing."""
        if self.state in (BatchState.PROCESSING, BatchState.PAUSED):
            self._should_stop = True
            self.logger.info("Stop requested")

    def reset(self) -> None:
        """Reset batch processor state."""
        self.state = BatchState.IDLE
        self.current_index = 0
        self._should_stop = False
        self._should_pause = False

        for status in self.file_statuses:
            status.status = ProcessingState.WAITING
            status.output_filename = None
            status.output_path = None
            status.title = None
            status.tts_script = None
            status.formatted_output = None
            status.error_message = None
            status.duration_seconds = 0.0

        self.logger.info("Batch processor reset")

    def can_resume(self) -> bool:
        """Check if batch can be resumed."""
        return (
            self.state == BatchState.PAUSED or
            (self.state == BatchState.IDLE and self.current_index > 0)
        )

    def get_completed_files(self) -> List[str]:
        """Get list of completed output filenames."""
        return [
            s.output_filename
            for s in self.file_statuses
            if s.status == ProcessingState.COMPLETED and s.output_filename
        ]
