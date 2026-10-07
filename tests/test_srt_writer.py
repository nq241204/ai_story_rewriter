"""Tests for SRT writer."""

import unittest
import tempfile
import os
from app.srt.writer import SRTWriter, SRTConfig
from app.srt.parser import SubtitleEntry


class TestSRTWriter(unittest.TestCase):
    """Test cases for SRT writer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.writer = SRTWriter()
        self.entries = [
            SubtitleEntry(
                index=1,
                start_time="00:00:01,000",
                end_time="00:00:04,000",
                text="John walked into the house."
            ),
            SubtitleEntry(
                index=2,
                start_time="00:00:04,000",
                end_time="00:00:08,000",
                text="He noticed something was wrong."
            )
        ]
    
    def test_write_content(self):
        """Test writing SRT content."""
        content = self.writer.write_content(self.entries)
        
        self.assertIn("1", content)
        self.assertIn("00:00:01,000 --> 00:00:04,000", content)
        self.assertIn("John walked into the house.", content)
        self.assertIn("2", content)
        self.assertIn("00:00:04,000 --> 00:00:08,000", content)
        self.assertIn("He noticed something was wrong.", content)
    
    def test_write_file(self):
        """Test writing to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            self.writer.write_file(self.entries, temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.assertIn("1", content)
            self.assertIn("John walked into the house.", content)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_text_wrapping(self):
        """Test text wrapping."""
        long_text = "This is a very long subtitle that should be wrapped across multiple lines to fit within the character limit."
        wrapped = self.writer._wrap_text(long_text)
        
        lines = wrapped.split('\n')
        for line in lines:
            self.assertLessEqual(len(line), self.writer.config.max_chars_per_line)
    
    def test_map_story_to_timeline(self):
        """Test mapping story to timeline."""
        story = "John walked home. He opened the door. He saw the mess."
        
        new_entries = self.writer.map_story_to_timeline(story, self.entries)
        
        self.assertEqual(len(new_entries), len(self.entries))
        
        # Check timing is preserved
        self.assertEqual(new_entries[0].start_time, self.entries[0].start_time)
        self.assertEqual(new_entries[0].end_time, self.entries[0].end_time)
        
        # Check text is distributed
        total_text = ' '.join(e.text for e in new_entries)
        self.assertTrue(len(total_text) > 0)
    
    def test_split_into_segments(self):
        """Test splitting story into segments."""
        story = "First sentence. Second sentence. Third sentence."
        
        segments = self.writer._split_into_segments(story)
        
        self.assertEqual(len(segments), 3)
        self.assertIn("First sentence", segments[0])
        self.assertIn("Second sentence", segments[1])
        self.assertIn("Third sentence", segments[2])


if __name__ == '__main__':
    unittest.main()
