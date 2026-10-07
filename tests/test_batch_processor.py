"""Tests for batch processor."""

import os
import shutil
import time
from app.pipeline.batch_processor import BatchProcessor, BatchState, FileStatus
from app.pipeline.story_processor import StoryProcessor, ProcessingState, ProcessingResult
from app.ai.ai_service import AIService
from app.ai.gemini_client import GeminiClient
from app.utils.logger import get_logger


class MockAIService:
    """Mock AI service for testing."""
    
    def __init__(self):
        pass
    
    def rewrite_story(self, story: str) -> str:
        return story + " (rewritten)"
    
    def analyze_story(self, story: str) -> str:
        return "Analysis"
    
    def quality_check(self, original: str, rewritten: str):
        return {"status": "PASS", "issues": []}
    
    def correct_qc_issues(self, rewritten: str, issues: list):
        return rewritten
    
    def generate_title(self, story: str):
        return "Test Title"


def test_batch_processor_initialization():
    """Test batch processor initialization."""
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    assert batch.state == BatchState.IDLE
    assert batch.files == []
    assert batch.file_statuses == []
    assert batch.current_index == 0
    assert not batch._should_stop
    assert not batch._should_pause
    print("[OK] Batch processor initialization test passed")


def test_scan_directory():
    """Test directory scanning."""
    # Create test directory with SRT files
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create test files
    for i in range(1, 6):
        with open(os.path.join(test_dir, f"{i:03d}.srt"), 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:04,000\nTest subtitle\n")
    
    # Create non-SRT file (should be ignored)
    with open(os.path.join(test_dir, "readme.txt"), 'w') as f:
        f.write("This should be ignored")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    count = batch.scan_directory(test_dir, "test_output")
    
    assert count == 5
    assert len(batch.files) == 5
    assert batch.files[0] == "001.srt"
    assert batch.files[1] == "002.srt"
    assert batch.files[4] == "005.srt"
    assert len(batch.file_statuses) == 5
    assert all(s.status == ProcessingState.WAITING for s in batch.file_statuses)
    
    # Cleanup
    for f in os.listdir(test_dir):
        os.remove(os.path.join(test_dir, f))
    os.rmdir(test_dir)
    
    print("[OK] Directory scanning test passed")


def test_natural_sorting():
    """Test natural numeric sorting of files."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create files that would sort incorrectly lexicographically
    filenames = ["001.srt", "010.srt", "002.srt", "020.srt", "003.srt"]
    for filename in filenames:
        with open(os.path.join(test_dir, filename), 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:04,000\nTest\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    batch.scan_directory(test_dir, "test_output")
    
    # Should be sorted naturally: 001, 002, 003, 010, 020
    assert batch.files[0] == "001.srt"
    assert batch.files[1] == "002.srt"
    assert batch.files[2] == "003.srt"
    assert batch.files[3] == "010.srt"
    assert batch.files[4] == "020.srt"
    
    # Cleanup
    for f in os.listdir(test_dir):
        os.remove(os.path.join(test_dir, f))
    os.rmdir(test_dir)
    
    print("[OK] Natural sorting test passed")


def test_file_status_tracking():
    """Test file status tracking during processing."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create test file
    with open(os.path.join(test_dir, "001.srt"), 'w') as f:
        f.write("1\n00:00:01,000 --> 00:00:04,000\nTest story\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    batch.scan_directory(test_dir, output_dir)
    
    # Manually set status to completed (skip actual processing for batch processor test)
    batch.file_statuses[0].status = ProcessingState.COMPLETED
    batch.file_statuses[0].output_filename = "001_Test_Title.srt"
    
    # Check final status
    statuses = batch.get_file_statuses()
    assert len(statuses) == 1
    assert statuses[0].status == ProcessingState.COMPLETED
    assert statuses[0].output_filename is not None
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] File status tracking test passed")


def test_progress_tracking():
    """Test progress tracking."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create multiple test files
    for i in range(1, 4):
        with open(os.path.join(test_dir, f"{i:03d}.srt"), 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:04,000\nTest\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    batch.scan_directory(test_dir, output_dir)
    
    # Initial progress
    current, total, completed, failed = batch.get_progress()
    assert total == 3
    assert completed == 0
    assert failed == 0
    
    # Manually set statuses (skip actual processing)
    for i in range(3):
        batch.file_statuses[i].status = ProcessingState.COMPLETED
    batch.current_index = 3
    
    # Final progress
    current, total, completed, failed = batch.get_progress()
    assert total == 3
    assert completed == 3
    assert failed == 0
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Progress tracking test passed")


def test_pause_resume():
    """Test pause and resume functionality."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create test files
    for i in range(1, 4):
        with open(os.path.join(test_dir, f"{i:03d}.srt"), 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:04,000\nTest\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    batch.scan_directory(test_dir, output_dir)
    
    # Set state to processing
    batch.state = BatchState.PROCESSING
    
    # Pause
    batch.pause()
    assert batch._should_pause == True
    
    # Set state to paused for resume
    batch.state = BatchState.PAUSED
    
    # Resume
    batch.resume()
    assert batch._should_pause == False
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Pause/resume test passed")


def test_stop():
    """Test stop functionality."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create test files
    for i in range(1, 4):
        with open(os.path.join(test_dir, f"{i:03d}.srt"), 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:04,000\nTest\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    batch.scan_directory(test_dir, output_dir)
    
    # Set state to processing
    batch.state = BatchState.PROCESSING
    
    # Stop
    batch.stop()
    assert batch._should_stop == True
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Stop test passed")


def test_reset():
    """Test reset functionality."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create test file
    with open(os.path.join(test_dir, "001.srt"), 'w') as f:
        f.write("1\n00:00:01,000 --> 00:00:04,000\nTest\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    batch.scan_directory(test_dir, output_dir)
    
    # Set to processed state
    batch.state = BatchState.PROCESSING
    batch.file_statuses[0].status = ProcessingState.COMPLETED
    batch.current_index = 1
    batch.state = BatchState.COMPLETED
    
    # Reset
    batch.reset()
    
    assert batch.state == BatchState.IDLE
    assert batch.current_index == 0
    assert all(s.status == ProcessingState.WAITING for s in batch.file_statuses)
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Reset test passed")


def test_can_resume():
    """Test resume capability check."""
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    batch = BatchProcessor(processor)
    
    # Initially cannot resume
    assert not batch.can_resume()
    
    # After pausing, can resume
    batch.state = BatchState.PAUSED
    assert batch.can_resume()
    
    # After processing some files, can resume
    batch.state = BatchState.IDLE
    batch.current_index = 5
    assert batch.can_resume()
    
    print("[OK] Can resume test passed")


if __name__ == "__main__":
    test_batch_processor_initialization()
    test_scan_directory()
    test_natural_sorting()
    test_file_status_tracking()
    test_progress_tracking()
    test_pause_resume()
    test_stop()
    test_reset()
    test_can_resume()
    
    print("\n[SUCCESS] All batch processor tests passed!")
