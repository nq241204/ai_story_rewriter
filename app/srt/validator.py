"""SRT validator for AI Story Rewriter."""

from typing import List, Tuple
from app.srt.parser import SubtitleEntry


class ValidationError:
    """Represents a validation error."""
    
    def __init__(self, entry_index: int, message: str):
        self.entry_index = entry_index
        self.message = message
    
    def __str__(self):
        return f"Entry {self.entry_index}: {self.message}"


class SRTValidator:
    """Validator for SRT subtitle files."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
    
    def validate_entries(self, entries: List[SubtitleEntry]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate a list of subtitle entries.
        
        Args:
            entries: List of SubtitleEntry objects
            
        Returns:
            Tuple of (is_valid, list of errors)
        """
        self.errors = []
        
        if not entries:
            self.errors.append(ValidationError(0, "No subtitle entries"))
            return False, self.errors
        
        # Check each entry
        for i, entry in enumerate(entries, 1):
            self._validate_entry(entry, i)
        
        # Check for overlapping timestamps
        self._check_overlaps(entries)
        
        # Check for backwards timestamps
        self._check_backwards(entries)
        
        return len(self.errors) == 0, self.errors
    
    def _validate_entry(self, entry: SubtitleEntry, index: int) -> None:
        """Validate a single subtitle entry."""
        # Check index
        if entry.index != index:
            self.errors.append(
                ValidationError(index, f"Index mismatch: expected {index}, got {entry.index}")
            )
        
        # Check timing
        if entry.start_ms >= entry.end_ms:
            self.errors.append(
                ValidationError(index, f"Start time ({entry.start_time}) >= end time ({entry.end_time})")
            )
        
        # Check for empty text
        if not entry.text or not entry.text.strip():
            self.errors.append(
                ValidationError(index, "Empty subtitle text")
            )
        
        # Check for extremely short duration
        duration = entry.end_ms - entry.start_ms
        if duration < 100:
            self.errors.append(
                ValidationError(index, f"Subtitle duration too short: {duration}ms")
            )
    
    def _check_overlaps(self, entries: List[SubtitleEntry]) -> None:
        """Check for overlapping timestamps between consecutive entries."""
        for i in range(len(entries) - 1):
            current = entries[i]
            next_entry = entries[i + 1]
            
            if current.end_ms > next_entry.start_ms:
                self.errors.append(
                    ValidationError(current.index, 
                        f"Overlaps with next entry (ends at {current.end_time}, next starts at {next_entry.start_time})")
                )
    
    def _check_backwards(self, entries: List[SubtitleEntry]) -> None:
        """Check that timestamps are in chronological order."""
        for i in range(len(entries) - 1):
            current = entries[i]
            next_entry = entries[i + 1]
            
            if current.start_ms >= next_entry.start_ms:
                self.errors.append(
                    ValidationError(next_entry.index,
                        f"Timestamp not chronological (starts at {next_entry.start_time}, previous started at {current.start_time})")
                )
    
    def validate_file_content(self, content: str) -> Tuple[bool, List[ValidationError]]:
        """
        Validate SRT file content string.
        
        Args:
            content: SRT content as string
            
        Returns:
            Tuple of (is_valid, list of errors)
        """
        from app.srt.parser import SRTParser
        
        parser = SRTParser()
        try:
            parsed = parser.parse_content(content)
            return self.validate_entries(parsed.entries)
        except Exception as e:
            self.errors.append(ValidationError(0, f"Parse error: {str(e)}"))
            return False, self.errors
