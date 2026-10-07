"""Story processor for AI Story Rewriter."""

import os
import shutil
import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass
from app.srt.parser import SRTParser, ParsedSRT
from app.srt.writer import SRTWriter
from app.srt.validator import SRTValidator
from app.ai.ai_service import AIService
from app.utils.logger import get_logger
from app.utils.filenames import generate_output_filename
from app.utils.text_utils import (
    parse_unified_ai_output,
    format_tts_paragraphs,
    format_unified_output,
)


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
    output_path: Optional[str] = None
    title: Optional[str] = None
    tts_script: Optional[str] = None
    formatted_output: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class StoryProcessor:
    """Processor for individual story files."""

    def __init__(
        self,
        ai_service: AIService,
        max_qc_retries: int = 2,
        save_failed: bool = True,
        export_srt: bool = False,
        enable_analyze: bool = True,
        enable_qc: bool = True,
        enable_title: bool = True,
    ):
        """
        Initialize story processor.

        Args:
            ai_service: AIService instance
            max_qc_retries: Maximum QC correction attempts
            save_failed: Whether to save failed files
            export_srt: If True, also export .srt alongside the TTS .txt output
            enable_analyze: Whether to run analysis step
            enable_qc: Whether to run QC step
            enable_title: Whether to run title step
        """
        self.ai_service = ai_service
        self.max_qc_retries = max_qc_retries
        self.save_failed = save_failed
        self.export_srt = export_srt
        self.enable_analyze = enable_analyze
        self.enable_qc = enable_qc
        self.enable_title = enable_title

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
        start_time = time.time()
        filename = os.path.basename(input_path)

        self.logger.info(f"Processing file: {filename}")

        try:
            # 1. READ & STRIP SRT ARTIFACTS IN PURE PYTHON
            if progress_callback:
                progress_callback(ProcessingState.READING, filename)

            parsed_srt = self.parser.parse_file(input_path)
            self.original_story = parsed_srt.get_story_text()
            if not self.original_story or not self.original_story.strip():
                raise ValueError("SRT file contains no readable text")
            self.logger.info(
                f"SRT parsed in Python ({len(parsed_srt.entries)} blocks, {len(self.original_story.split())} words)"
            )

            # 2. ANALYZE (Pure Python by default - 0 AI tokens)
            if progress_callback:
                progress_callback(ProcessingState.ANALYZING, filename)

            if self.enable_analyze:
                self.story_analysis = self.ai_service.analyze_story(self.original_story)

            # 3. REWRITE (Single-pass AI call returns ---TITLE--- and ---TTS_SCRIPT---)
            if progress_callback:
                progress_callback(ProcessingState.REWRITING, filename)

            raw_rewritten = self.ai_service.rewrite_story(self.original_story)

            if not raw_rewritten:
                raise Exception("Failed to rewrite story")

            # Extract title & clean TTS script if markers are present
            extracted_title, cleaned_script = parse_unified_ai_output(raw_rewritten)
            self.rewritten_story = cleaned_script if cleaned_script else raw_rewritten
            if extracted_title:
                self.title = extracted_title

            # 4. QUALITY CONTROL (Pure Python by default - only calls AI if issues found)
            if progress_callback:
                progress_callback(ProcessingState.QC, filename)

            if self.enable_qc:
                qc_result = self.ai_service.quality_check(
                    self.original_story,
                    self.rewritten_story
                )

                if qc_result and qc_result.get("status") == "FAIL":
                    issues = qc_result.get("issues", [])
                    self.logger.warning(f"QC failed with {len(issues)} issues")

                    for attempt in range(self.max_qc_retries):
                        self.logger.info(f"QC correction attempt {attempt + 1}")
                        corrected = self.ai_service.correct_qc_issues(
                            self.rewritten_story,
                            issues
                        )

                        if corrected:
                            corr_title, corr_script = parse_unified_ai_output(corrected)
                            if corr_title and not self.title:
                                self.title = corr_title
                            self.rewritten_story = corr_script if corr_script else corrected

                            qc_result = self.ai_service.quality_check(
                                self.original_story,
                                self.rewritten_story
                            )
                            if qc_result and qc_result.get("status") == "PASS":
                                self.logger.info("QC passed after correction")
                                break
                    else:
                        self.logger.error("QC still failing after max retries")

            # 5. GENERATE TITLE (Uses cached single-pass title with 0 extra tokens if available)
            if progress_callback:
                progress_callback(ProcessingState.TITLE, filename)

            if self.enable_title:
                if not self.title:
                    self.title = self.ai_service.generate_title(self.rewritten_story)

            if not self.title:
                self.logger.warning("Title generation failed, using fallback")
                self.title = "Story"

            # 6. BUILD TTS OUTPUT (& OPTIONAL SRT)
            if progress_callback:
                progress_callback(ProcessingState.BUILDING_SRT, filename)

            tts_script = format_tts_paragraphs(self.rewritten_story, sentences_per_paragraph=3)
            formatted_output = format_unified_output(self.title, tts_script)

            new_entries = []
            if self.export_srt:
                new_entries = self.writer.map_story_to_timeline(
                    tts_script,
                    parsed_srt.entries
                )

            # 7. VALIDATE OUTPUT
            if progress_callback:
                progress_callback(ProcessingState.VALIDATING, filename)

            if self.export_srt and new_entries:
                is_valid, errors = self.validator.validate_entries(new_entries)
                if not is_valid:
                    self.logger.warning(f"SRT validation found {len(errors)} issues")

            # 8. SAVE RESULT
            if progress_callback:
                progress_callback(ProcessingState.SAVING, filename)

            os.makedirs(output_dir, exist_ok=True)

            # Save the 2-part TTS output (---TITLE--- & ---TTS_SCRIPT---) as .txt
            output_filename = generate_output_filename(filename, self.title, ext=".txt")
            output_path = os.path.join(output_dir, output_filename)
            self.writer.write_tts_file(self.title, tts_script, output_path)
            self.logger.info(f"TTS script saved to: {output_filename}")

            # Optionally also save .srt if requested
            if self.export_srt and new_entries:
                srt_filename = generate_output_filename(filename, self.title, ext=".srt")
                srt_path = os.path.join(output_dir, srt_filename)
                self.writer.write_file(new_entries, srt_path)
                self.logger.info(f"SRT file saved to: {srt_filename}")

            duration = time.time() - start_time

            result = ProcessingResult(
                filename=filename,
                status=ProcessingState.COMPLETED,
                output_filename=output_filename,
                output_path=output_path,
                title=self.title,
                tts_script=tts_script,
                formatted_output=formatted_output,
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

            if self.save_failed:
                try:
                    failed_dir = os.path.join(output_dir, "failed")
                    os.makedirs(failed_dir, exist_ok=True)
                    failed_path = os.path.join(failed_dir, filename)
                    shutil.copy2(input_path, failed_path)
                    self.logger.info(f"Failed file saved to: {failed_path}")
                except Exception as save_error:
                    self.logger.error(f"Failed to save failed file: {save_error}")

        finally:
            self._reset_context()
            self.logger.info("Story context cleared")

        return result

    def _reset_context(self) -> None:
        """Reset all story context data."""
        self.original_story = None
        self.story_analysis = None
        self.rewritten_story = None
        self.title = None
        if hasattr(self.ai_service, "reset_state"):
            self.ai_service.reset_state()
