"""Story processor for AI Story Rewriter."""

import os
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass
from app.srt.parser import SRTParser, ParsedSRT
from app.srt.writer import SRTWriter
from app.srt.validator import SRTValidator
from app.ai.ai_service import AIService
from app.utils.logger import get_logger
from app.utils.filenames import generate_output_filename


class ProcessingState(Enum):
    """States for story processing."""
    WAITING = "waiting"
    READING = "reading"
    ANALYZING = "analyzing"
    REWRITING = "rewriting"
    QC = "qc"
    TITLE = "title"
    BUILDING_SRT = "building_srt"
    VALIDATING = "validating"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingResult:
    """Result of story processing."""
    filename: str
    status: ProcessingState
    output_filename: Optional[str] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class StoryProcessor:
    """Processor for individual story文件."""
    
    def __init__(
        self,
        ai_service: AIService,
        max_qc_retries: int = 2,
        save_failed: bool = True
    ):
        """
        Initialize story processor.
        
        Args:
            ai_service: AIService instance
            max_qc_retries: Maximum QC correction attempts
            save_failed: Whether to save failed files
        """
        self.ai_service = ai_service
        self.max_qc_retries = max_qc_retries
        self.save_failed = save_failed
        
        self.parser = SRTParser()
        self.writer = SRTWriter()
        self.validator = SRTValidator()
        self.logger = get_logger()
        
        # Story context (reset between files)
        self.original_story: Optional[str] = None
        self.story_analysis: Optional[str] = None
        self.rewritten_story: Optional[str] = None
        self.title: Optional[str] = None
    
    def process_file(
        self,
        input_path: str,
        output_dir: str,
        progress_callback: Optional[Callable[[ProcessingState, str], None]] = None
    ) -> ProcessingResult:
        """
        Process a single SRT file.
        
        Args:
            input_path: Path to input SRT file
            output_dir: Directory for output files
            progress_callback: Optional callback for progress updates
            
        Returns:
            ProcessingResult with outcome
        """
        import time
        start_time = time.time()
        filename = os.path.basename(input_path)
        
        self.logger.info(f"Processing file: {filename}")
        
        try:
            # READ
            if progress_callback:
                progress_callback(ProcessingState.READING, filename)
            
            parsed_srt = self.parser.parse_file(input_path)
            self.original_story = parsed_srt.get_story_text()
            self.logger.info("SRT parsed successfully")
            
            # ANALYZE (optional, non-critical)
            if progress_callback:
                progress_callback(ProcessingState.ANALYZING, filename)
            
            self.story_analysis = self.ai_service.analyze_story(self.original_story)
            
            # REWRITE
            if progress_callback:
                progress_callback(ProcessingState.REWRITING, filename)
            
            self.rewritten_story = self.ai_service.rewrite_story(self.original_story)
            
            if not self.rewritten_story:
                raise Exception("Failed to rewrite story")
            
            # QUALITY CONTROL
            if progress_callback:
                progress_callback(ProcessingState.QC, filename)
            
            qc_result = self.ai_service.quality_check(
                self.original_story,
                self.rewritten_story
            )
            
            if qc_result and qc_result.get("status") == "FAIL":
                issues = qc_result.get("issues", [])
                self.logger.warning(f"QC failed with {len(issues)} issues")
                
                # Attempt corrections
                for attempt in range(self.max_qc_retries):
                    self.logger.info(f"QC correction attempt {attempt + 1}")
                    corrected = self.ai_service.correct_qc_issues(
                        self.rewritten_story,
                        issues
                    )
                    
                    if corrected:
                        self.rewritten_story = corrected
                        # Re-check
                        qc_result = self.ai_service.quality_check(
                            self.original_story,
                            self.rewritten_story
                        )
                        if qc_result and qc_result.get("status") == "PASS":
                            self.logger.info("QC passed after correction")
                            break
                else:
                    self.logger.error("QC still failing after max retries")
                    # Continue anyway with warning
            
            # GENERATE TITLE
            if progress_callback:
                progress_callback(ProcessingState.TITLE, filename)
            
            self.title = self.ai_service.generate_title(self.rewritten_story)
            
            if not self.title:
                self.logger.warning("Title generation failed, using fallback")
                self.title = "Story"
            
            # BUILD SRT
            if progress_callback:
                progress_callback(ProcessingState.BUILDING_SRT, filename)
            
            new_entries = self.writer.map_story_to_timeline(
                self.rewritten_story,
                parsed_srt.entries
            )
            
            # VALIDATE SRT
            if progress_callback:
                progress_callback(ProcessingState.VALIDATING, filename)
            
            is_valid, errors = self.validator.validate_entries(new_entries)
            
            if not is_valid:
                self.logger.warning(f"SRT validation found {len(errors)} issues")
                # Continue anyway
            
            # SAVE
            if progress_callback:
                progress_callback(ProcessingState.SAVING, filename)
            
            output_filename = generate_output_filename(filename, self.title)
            output_path = os.path.join(output_dir, output_filename)
            
            self.writer.write_file(new_entries, output_path)
            self.logger.info(f"Output saved to: {output_filename}")
            
            # Calculate duration
            duration = time.time() - start_time
            
            result = ProcessingResult(
                filename=filename,
                status=ProcessingState.COMPLETED,
                output_filename=output_filename,
                title=self.title,
                duration_seconds=duration
            )
            
        except Exception as e:
            self.logger.error(f"Processing failed for {filename}: {e}")
            duration = time.time() - start_time
            
            result = ProcessingResult(
                filename=filename,
                status=ProcessingState.FAILED,
                error_message=str(e),
                duration_seconds=duration
            )
            
            # Save failed file if enabled
            if self.save_failed:
                try:
                    failed_dir = os.path.join(output_dir, "failed")
                    os.makedirs(failed_dir, exist_ok=True)
                    failed_path = os.path.join(failed_dir, filename)
                    # Copy original to failed folder
                    import shutil
                    shutil.copy2(input_path, failed_path)
                    self.logger.info(f"Failed file saved to: {failed_path}")
                except Exception as save_error:
                    self.logger.error(f"Failed to save failed file: {save_error}")
        
        finally:
            # RESET CONTEXT
            self._reset_context()
            self.logger.info("Story context cleared")
        
        return result
    
    def _reset_context(self) -> None:
        """Reset all story context data."""
        self.original_story = None
        self.story_analysis = None
        self.rewritten_story = None
        self.title = None
