"""SRT parser for AI Story Rewriter."""

import re
from dataclasses import dataclass
from typing import List, Optional
from app.utils.text_utils import normalize_line_endings


@dataclass
class SubtitleEntry:
    """Represents a single subtitle entry."""
    index: int
    start_time: str  # Format: "00:00:01,000"
    end_time: str    # Format: "00:00:04,000"
    text: str
    
    @property
    def start_ms(self) -> int:
        """Convert start time to milliseconds."""
        return self._time_to_ms(self.start_time)
    
    @property
    def end_ms(self) -> int:
        """Convert end time to milliseconds."""
        return self._time_to_ms(self.end_time)
    
    @staticmethod
    def _time_to_ms(time_str: str) -> int:
        """Convert SRT time string to milliseconds."""
        # Format: "00:00:01,000"
        match = re.match(r'(\d+):(\d+):(\d+),(\d+)', time_str)
        if not match:
            raise ValueError(f"Invalid time format: {time_str}")
        
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600000) + (minutes * 60000) + (seconds * 1000) + milliseconds


@dataclass
class ParsedSRT:
    """Represents a fully parsed SRT file."""
    entries: List[SubtitleEntry]
    full_text: str
    
    def get_story_text(self) -> str:
        """Extract the story text from all subtitle entries."""
        return ' '.join(entry.text.strip() for entry in self.entries)


class SRTParseError(Exception):
    """Exception raised when SRT parsing fails."""
    pass


class SRTParser:
    """Parser for SRT subtitle files."""
    
    TIME_PATTERN = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})')
    INDEX_PATTERN = re.compile(r'^\d+$')
    
    def __init__(self):
        self.entries: List[SubtitleEntry] = []
    
    def parse_file(self, filepath: str) -> ParsedSRT:
        """
        Parse an SRT file.
        
        Args:
            filepath: Path to the SRT file
            
        Returns:
            ParsedSRT object containing all subtitle entries
            
        Raises:
            SRTParseError: If the file cannot be parsed
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(filepath, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception as e:
                raise SRTParseError(f"Failed to read file with encoding: {e}")
        except Exception as e:
            raise SRTParseError(f"Failed to read file: {e}")
        
        return self.parse_content(content)
    
    def parse_content(self, content: str) -> ParsedSRT:
        """
        Parse SRT content from a string.
        
        Args:
            content: SRT content as string
            
        Returns:
            ParsedSRT object
            
        Raises:
            SRTParseError: If content cannot be parsed
        """
        # Normalize line endings
        content = normalize_line_endings(content)
        
        # Split into blocks (separated by blank lines)
        blocks = re.split(r'\n\s*\n', content.strip())
        
        entries = []
        for block in blocks:
            if not block.strip():
                continue
            
            entry = self._parse_block(block)
            if entry:
                entries.append(entry)
        
        if not entries:
            raise SRTParseError("No valid subtitle entries found")
        
        # Validate sequential indices
        for i, entry in enumerate(entries, 1):
            if entry.index != i:
                # Auto-fix indices
                entry.index = i
        
        full_text = ' '.join(entry.text.strip() for entry in entries)
        
        return ParsedSRT(entries=entries, full_text=full_text)
    
    def _parse_block(self, block: str) -> Optional[SubtitleEntry]:
        """
        Parse a single subtitle block.
        
        Block format:
        1
        00:00:01,000 --> 00:00:04,000
        John walked into the house.
        """
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        if len(lines) < 3:
            return None
        
        # Parse index
        index_line = lines[0]
        if not self.INDEX_PATTERN.match(index_line):
            return None
        
        try:
            index = int(index_line)
        except ValueError:
            return None
        
        # Parse time
        time_line = lines[1]
        time_match = self.TIME_PATTERN.match(time_line)
        if not time_match:
            raise SRTParseError(f"Invalid time format in block: {time_line}")
        
        start_time, end_time = time_match.groups()
        
        # Parse text (may span multiple lines)
        text_lines = lines[2:]
        text = ' '.join(text_lines)
        
        if not text:
            raise SRTParseError(f"Empty subtitle text in block {index}")
        
        return SubtitleEntry(
            index=index,
            start_time=start_time,
            end_time=end_time,
            text=text
        )
    
    def validate_timing(self, entry: SubtitleEntry) -> bool:
        """Validate that start time is before end time."""
        return entry.start_ms < entry.end_ms
