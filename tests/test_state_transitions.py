"""Tests for state transitions in story processor."""

import os
import shutil
from app.pipeline.story_processor import StoryProcessor, ProcessingState, ProcessingResult
from app.ai.ai_service import AIService
from app.ai.gemini_client import GeminiClient
from app.srt.parser import SRTParser
from app.srt.writer import SRTWriter
from app.srt.validator import SRTValidator


class MockAIService:
    """Mock AI service for testing."""
    
    def __init__(self, should_fail_at=None):
        self.should_fail_at = should_fail_at
        self.call_count = 0
    
    def rewrite_story(self, story: str) -> str:
        self.call_count += 1
        if self.should_fail_at == "rewrite":
            return None
        return story + " (rewritten)"
    
    def analyze_story(self, story: str) -> str:
        self.call_count += 1
        if self.should_fail_at == "analyze":
            return None
        return "Analysis"
    
    def quality_check(self, original: str, rewritten: str):
        self.call_count += 1
        if self.should_fail_at == "qc":
            return None
        return {"status": "PASS", "issues": []}
    
    def correct_qc_issues(self, rewritten: str, issues: list):
        self.call_count += 1
        if self.should_fail_at == "correct":
            return None
        return rewritten
    
    def generate_title(self, story: str):
        self.call_count += 1
        if self.should_fail_at == "title":
            return None
        return "Test Title"


def create_test_srt(filepath: str, content: str = None):
    """Create a test SRT file."""
    if content is None:
        content = """1
00:00:01,000 --> 00:00:04,000
John walked into the house.

2
00:00:04,000 --> 00:00:08,000
He immediately noticed something was wrong.
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def test_state_flow_success():
    """Test complete successful state flow."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file)
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    
    # Track state transitions
    states = []
    def track_state(state, filename):
        states.append(state)
    
    result = processor.process_file(test_file, output_dir, progress_callback=track_state)
    
    # Check state transitions
    expected_states = [
        ProcessingState.READING,
        ProcessingState.ANALYZING,
        ProcessingState.REWRITING,
        ProcessingState.QC,
        ProcessingState.TITLE,
        ProcessingState.BUILDING_SRT,
        ProcessingState.VALIDATING,
        ProcessingState.SAVING
    ]
    
    assert states == expected_states, f"Expected {expected_states}, got {states}"
    assert result.status == ProcessingState.COMPLETED
    assert result.output_filename is not None
    assert result.title == "Test Title"
    
    # Check context was reset
    assert processor.original_story is None
    assert processor.rewritten_story is None
    assert processor.title is None
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Successful state flow test passed")


def test_state_flow_with_qc_failure():
    """Test state flow when QC fails but correction succeeds."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file)
    
    # Mock that fails QC first time
    class QCFailMockAI:
        def __init__(self):
            self.qc_count = 0
        
        def rewrite_story(self, story: str) -> str:
            return story + " (rewritten)"
        
        def analyze_story(self, story: str) -> str:
            return "Analysis"
        
        def quality_check(self, original: str, rewritten: str):
            self.qc_count += 1
            if self.qc_count == 1:
                return {"status": "FAIL", "issues": ["Issue 1", "Issue 2"]}
            return {"status": "PASS", "issues": []}
        
        def correct_qc_issues(self, rewritten: str, issues: list):
            return rewritten + " (corrected)"
        
        def generate_title(self, story: str):
            return "Test Title"
    
    mock_ai = QCFailMockAI()
    processor = StoryProcessor(mock_ai, max_qc_retries=2)
    
    result = processor.process_file(test_file, output_dir)
    
    # Should still complete after correction
    assert result.status == ProcessingState.COMPLETED
    assert mock_ai.qc_count == 2  # First fail, then pass
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] QC failure with correction test passed")


def test_state_flow_with_rewrite_failure():
    """Test state flow when rewrite fails."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file)
    
    mock_ai = MockAIService(should_fail_at="rewrite")
    processor = StoryProcessor(mock_ai)
    
    result = processor.process_file(test_file, output_dir)
    
    # Should fail at rewrite stage
    assert result.status == ProcessingState.FAILED
    assert result.error_message is not None
    assert "Failed to rewrite story" in result.error_message
    
    # Context should still be reset
    assert processor.original_story is None
    assert processor.rewritten_story is None
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Rewrite failure test passed")


def test_state_flow_with_title_failure():
    """Test state flow when title generation fails (non-critical)."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file)
    
    mock_ai = MockAIService(should_fail_at="title")
    processor = StoryProcessor(mock_ai)
    
    result = processor.process_file(test_file, output_dir)
    
    # Should still complete with fallback title
    assert result.status == ProcessingState.COMPLETED
    assert result.title == "Story"  # Fallback title
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Title failure test passed")


def test_context_isolation():
    """Test that context is properly isolated between files."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create two different test files
    test_file1 = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file1, "1\n00:00:01,000 --> 00:00:04,000\nStory A\n")
    
    test_file2 = os.path.join(test_dir, "002.srt")
    create_test_srt(test_file2, "1\n00:00:01,000 --> 00:00:04,000\nStory B\n")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    
    # Process first file
    result1 = processor.process_file(test_file1, output_dir)
    assert result1.status == ProcessingState.COMPLETED
    
    # Verify context is cleared
    assert processor.original_story is None
    assert processor.rewritten_story is None
    assert processor.title is None
    
    # Process second file
    result2 = processor.process_file(test_file2, output_dir)
    assert result2.status == ProcessingState.COMPLETED
    
    # Verify context is cleared again
    assert processor.original_story is None
    assert processor.rewritten_story is None
    assert processor.title is None
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Context isolation test passed")


def test_malformed_srt_handling():
    """Test handling of malformed SRT files."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    # Create malformed SRT
    with open(test_file, 'w') as f:
        f.write("This is not a valid SRT file")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    
    result = processor.process_file(test_file, output_dir)
    
    # Should fail gracefully
    assert result.status == ProcessingState.FAILED
    assert result.error_message is not None
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Malformed SRT handling test passed")


def test_empty_srt_handling():
    """Test handling of empty SRT files."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    # Create empty SRT
    with open(test_file, 'w') as f:
        f.write("")
    
    mock_ai = MockAIService()
    processor = StoryProcessor(mock_ai)
    
    result = processor.process_file(test_file, output_dir)
    
    # Should fail gracefully
    assert result.status == ProcessingState.FAILED
    assert result.error_message is not None
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Empty SRT handling test passed")


def test_save_failed_files():
    """Test that failed files are saved when enabled."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file)
    
    mock_ai = MockAIService(should_fail_at="rewrite")
    processor = StoryProcessor(mock_ai, save_failed=True)
    
    result = processor.process_file(test_file, output_dir)
    
    assert result.status == ProcessingState.FAILED
    
    # Check that failed file was saved
    failed_dir = os.path.join(output_dir, "failed")
    assert os.path.exists(failed_dir)
    assert os.path.exists(os.path.join(failed_dir, "001.srt"))
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] Save failed files test passed")


def test_no_save_failed_files():
    """Test that failed files are not saved when disabled."""
    test_dir = "test_input"
    os.makedirs(test_dir, exist_ok=True)
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "001.srt")
    create_test_srt(test_file)
    
    mock_ai = MockAIService(should_fail_at="rewrite")
    processor = StoryProcessor(mock_ai, save_failed=False)
    
    result = processor.process_file(test_file, output_dir)
    
    assert result.status == ProcessingState.FAILED
    
    # Check that failed folder was not created
    failed_dir = os.path.join(output_dir, "failed")
    assert not os.path.exists(failed_dir)
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    print("[OK] No save failed files test passed")


import unittest


class TestStateTransitions(unittest.TestCase):
    """Unittest wrapper so `python -m unittest discover tests` runs all state transition tests."""

    def test_all_state_transitions(self):
        test_state_flow_success()
        test_state_flow_with_qc_failure()
        test_state_flow_with_rewrite_failure()
        test_state_flow_with_title_failure()
        test_context_isolation()
        test_malformed_srt_handling()
        test_empty_srt_handling()
        test_save_failed_files()
        test_no_save_failed_files()


if __name__ == "__main__":
    test_state_flow_success()
    test_state_flow_with_qc_failure()
    test_state_flow_with_rewrite_failure()
    test_state_flow_with_title_failure()
    test_context_isolation()
    test_malformed_srt_handling()
    test_empty_srt_handling()
    test_save_failed_files()
    test_no_save_failed_files()

    print("\n[SUCCESS] All state transition tests passed!")
