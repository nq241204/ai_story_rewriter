"""Batch processor for AI Story Rewriter."""

import os
from enum import Enum
from typing import List, Optional, Callable
from dataclasses import dataclass
from app.pipeline.story_processor import StoryProcessor, ProcessingResult, ProcessingState
from app.utils.logger import get_logger
from app.utils.filenames import sort_files_naturally


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
    error_message: Optional[str] = None


class BatchProcessor:
    """Processor for batch SRT file processing."""
    
    def __init__(self, story_processor: StoryProcessor):
        """
        Initialize batch processor.
        
        Args:
            story_processor: StoryProcessor instance
        """
        self.story_processor = story_processor
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
        Scan input directory for SRT files.
        
        Args:
            input_dir: Input directory path
            output_dir: Output directory path
            
        Returns:
            Number of files found
        """
        self.logger.info(f"Scanning directory: {input_dir}")
        
        self.input_dir = input_dir
        self.output_dir = output_dir
        
        # Get all .srt files
        files = []
        for filename in os.listdir(input_dir):
            if filename.lower().endswith('.srt'):
                # Skip hidden files
                if not filename.startswith('.'):
                    files.append(filename)
        
        # Sort naturally
        self.files = sort_files_naturally(files)
        
        # Initialize statuses
        self.file_statuses = [
            FileStatus(filename=f, status=ProcessingState.WAITING)
            for f in self.files
        ]
        
        self.current_index = 0
        self.logger.info(f"Found {len(self.files)} SRT files")
        
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
        
        return (self.current_index + 1, total, completed, failed)
    
    def start(
        self,
        progress_callback: Optional[Callable[[str, str, int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Start batch processing.
        
        Args:
            progress_callback: Callback for progress updates (filename, state_string, current, total)
            log_callback: Callback for log messages
        """
        if self.state == BatchState.PROCESSING:
            self.logger.warning("Already processing")
            return
        
        self.state = BatchState.PROCESSING
        self._should_stop = False
        self._should_pause = False
        
        self.logger.info("Starting batch processing")
        
        for i in range(self.current_index, len(self.files)):
            if self._should_stop:
                self.state = BatchState.STOPPED
                self.logger.info("Batch processing stopped")
                break
            
            if self._should_pause:
                self.state = BatchState.PAUSED
                self.logger.info("Batch processing paused")
                break
            
            filename = self.files[i]
            input_path = os.path.join(self.input_dir, filename)
            
            # Update status to processing
            self.file_statuses[i].status = ProcessingState.READING
            
            # Callback
            if progress_callback:
                progress_callback(filename, ProcessingState.READING.value, i + 1, len(self.files))
            
            # Process file
            result = self.story_processor.process_file(
                input_path,
                self.output_dir,
                progress_callback=lambda state, fn: self._update_progress(
                    i, state, fn, progress_callback
                )
            )
            
            # Update status
            self.file_statuses[i].status = result.status
            self.file_statuses[i].output_filename = result.output_filename
            self.file_statuses[i].error_message = result.error_message
            
            # Log callback
            if log_callback:
                status_text = "DONE" if result.status == ProcessingState.COMPLETED else "FAILED"
                log_callback(f"{filename} -> {status_text}")
            
            self.current_index = i + 1
        
        if not self._should_stop and not self._should_pause:
            self.state = BatchState.COMPLETED
            self.logger.info("Batch processing completed")
    
    def _update_progress(
        self,
        index: int,
        state: ProcessingState,
        filename: str,
        callback: Callable[[str, str, int, int], None]
    ) -> None:
        """Update progress during file processing."""
        self.file_statuses[index].status = state
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
            # Will continue in the start() loop
    
    def stop(self) -> None:
        """Stop batch processing."""
        if self.state == BatchState.PROCESSING or self.state == BatchState.PAUSED:
            self._should_stop = True
            self.logger.info("Stop requested")
    
    def reset(self) -> None:
        """Reset batch processor state."""
        self.state = BatchState.IDLE
        self.current_index = 0
        self._should_stop = False
        self._should_pause = False
        
        # Reset all file statuses
        for status in self.file_statuses:
            status.status = ProcessingState.WAITING
            status.output_filename = None
            status.error_message = None
        
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
