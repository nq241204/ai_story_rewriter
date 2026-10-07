"""Tests for SRT parser."""

import unittest
import os
import tempfile
from app.srt.parser import SRTParser, SRTParseError, SubtitleEntry


class TestSRTParser(unittest.TestCase):
    """Test cases for SRT parser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = SRTParser()
    
    def test_parse_valid_srt(self):
        """Test parsing a valid SRT file."""
        content = """1
00:00:01,000 --> 00:00:04,000
John walked into the house.

2
00:00:04,000 --> 00:00:08,000
He immediately noticed that something was wrong.
"""
        
        parsed = self.parser.parse_content(content)
        
        self.assertEqual(len(parsed.entries), 2)
        self.assertEqual(parsed.entries[0].index, 1)
        self.assertEqual(parsed.entries[0].text, "John walked into the house.")
        self.assertEqual(parsed.entries[1].index, 2)
        self.assertEqual(parsed.entries[1].text, "He immediately noticed that something was wrong.")
    
    def test_parse_with_crlf(self):
        """Test parsing SRT with CRLF line endings."""
        content = "1\r\n00:00:01,000 --> 00:00:04,000\r\nJohn walked into the house.\r\n\r\n"
        
        parsed = self.parser.parse_content(content)
        
        self.assertEqual(len(parsed.entries), 1)
        self.assertEqual(parsed.entries[0].text, "John walked into the house.")
    
    def test_parse_multiline_subtitle(self):
        """Test parsing subtitle with multiple lines."""
        content = """1
00:00:01,000 --> 00:00:04,000
This is the first line.
This is the second line.
"""
        
        parsed = self.parser.parse_content(content)
        
        self.assertEqual(len(parsed.entries), 1)
        self.assertIn("first line", parsed.entries[0].text)
        self.assertIn("second line", parsed.entries[0].text)
    
    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        with self.assertRaises(SRTParseError):
            self.parser.parse_content("")
    
    def test_parse_malformed_time(self):
        """Test parsing malformed time format."""
        content = """1
00:00:01 --> 00:00:04,000
John walked into the house.
"""
        
        with self.assertRaises(SRTParseError):
            self.parser.parse_content(content)
    
    def test_parse_missing_text(self):
        """Test parsing subtitle with missing text."""
        content = """1
00:00:01,000 --> 00:00:04,000

"""
        
        with self.assertRaises(SRTParseError):
            self.parser.parse_content(content)
    
    def test_time_conversion(self):
        """Test time conversion to milliseconds."""
        entry = SubtitleEntry(
            index=1,
            start_time="00:00:01,500",
            end_time="00:00:02,000",
            text="Test"
        )
        
        self.assertEqual(entry.start_ms, 1500)
        self.assertEqual(entry.end_ms, 2000)
    
    def test_auto_fix_indices(self):
        """Test automatic index fixing."""
        content = """5
00:00:01,000 --> 00:00:04,000
First entry.

3
00:00:04,000 --> 00:00:08,000
Second entry.
"""
        
        parsed = self.parser.parse_content(content)
        
        self.assertEqual(parsed.entries[0].index, 1)
        self.assertEqual(parsed.entries[1].index, 2)
    
    def test_parse_file(self):
        """Test parsing from file."""
        content = """1
00:00:01,000 --> 00:00:04,000
Test subtitle.
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        try:
            parsed = self.parser.parse_file(temp_path)
            self.assertEqual(len(parsed.entries), 1)
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
