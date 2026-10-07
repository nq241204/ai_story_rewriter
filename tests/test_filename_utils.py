"""Tests for filename utilities."""

import unittest
from app.utils.filenames import (
    sanitize_filename,
    natural_sort_key,
    sort_files_naturally,
    extract_file_number,
    generate_output_filename
)


class TestFilenameUtils(unittest.TestCase):
    """Test cases for filename utilities."""
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test invalid characters
        self.assertEqual(
            sanitize_filename("Test/File:Name*"),
            "TestFileName"
        )
        
        # Test spaces to underscores
        self.assertEqual(
            sanitize_filename("Test File Name"),
            "Test_File_Name"
        )
        
        # Test length limit
        long_name = "A" * 250
        sanitized = sanitize_filename(long_name, max_length=100)
        self.assertLessEqual(len(sanitized), 100)
    
    def test_natural_sort_key(self):
        """Test natural sort key generation."""
        key1 = natural_sort_key("001.srt")
        key2 = natural_sort_key("002.srt")
        key3 = natural_sort_key("010.srt")
        
        self.assertLess(key1, key2)
        self.assertLess(key2, key3)
    
    def test_sort_files_naturally(self):
        """Test natural file sorting."""
        files = ["010.srt", "002.srt", "001.srt", "100.srt"]
        sorted_files = sort_files_naturally(files)
        
        self.assertEqual(sorted_files, ["001.srt", "002.srt", "010.srt", "100.srt"])
    
    def test_extract_file_number(self):
        """Test extracting file number."""
        self.assertEqual(extract_file_number("001.srt"), "001")
        self.assertEqual(extract_file_number("010_story.srt"), "010")
        self.assertEqual(extract_file_number("story.srt"), "")
    
    def test_generate_output_filename(self):
        """Test output filename generation."""
        result = generate_output_filename(
            "001.srt",
            "The Mafia Boss Came Home Early"
        )
        
        self.assertIn("001", result)
        self.assertIn("The_Mafia_Boss_Came_Home_Early", result)
        self.assertTrue(result.endswith(".srt"))


if __name__ == '__main__':
    unittest.main()
