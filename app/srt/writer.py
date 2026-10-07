"""SRT writer for AI Story Rewriter."""

import re
from typing import List
from dataclasses import dataclass
from app.srt.parser import SubtitleEntry


@dataclass
class SRTConfig:
    """Configuration for SRT writing."""
    max_chars_per_line: int = 42
    max_lines_per_subtitle: int = 2
    min_subtitle_duration: int = 1000  # milliseconds
    max_subtitle_duration: int = 7000  # milliseconds


class SRTWriter:
    """Writer for SRT subtitle files."""
    
    def __init__(self, config: SRTConfig = None):
        self.config = config or SRTConfig()
    
    def write_file(self, entries: List[SubtitleEntry], filepath: str) -> None:
        """
        Write subtitle entries to an SRT file.
        
        Args:
            entries: List of SubtitleEntry objects
            filepath: Output file path
        """
        content = self.write_content(entries)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def write_content(self, entries: List[SubtitleEntry]) -> str:
        """
        Generate SRT content from subtitle entries.
        
        Args:
            entries: List of SubtitleEntry objects
            
        Returns:
            SRT formatted string
        """
        lines = []
        for entry in entries:
            lines.append(str(entry.index))
            lines.append(f"{entry.start_time} --> {entry.end_time}")
            
            # Wrap text if needed
            wrapped_text = self._wrap_text(entry.text)
            lines.append(wrapped_text)
            lines.append("")  # Blank line between entries
        
        return '\n'.join(lines)
    
    def _wrap_text(self, text: str) -> str:
        """
        Wrap text to fit within character limits.
        
        Args:
            text: Text to wrap
            
        Returns:
            Wrapped text with newlines
        """
        if len(text) <= self.config.max_chars_per_line:
            return text
        
        # Simple word wrapping
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            if current_length + word_length + 1 <= self.config.max_chars_per_line:
                current_line.append(word)
                current_length += word_length + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Limit to max lines per subtitle
        if len(lines) > self.config.max_lines_per_subtitle:
            lines = lines[:self.config.max_lines_per_subtitle]
        
        return '\n'.join(lines)
    
    def map_story_to_timeline(
        self,
        story_text: str,
        original_entries: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        Map rewritten story text to original subtitle timeline.
        
        This distributes the new story text across the original timing.
        
        Args:
            story_text: The rewritten story text
            original_entries: Original subtitle entries with timing
            
        Returns:
            New subtitle entries with rewritten text and original timing
        """
        if not original_entries:
            return []
        
        # Split story into sentences/segments
        sentences = self._split_into_segments(story_text)
        
        # Calculate total duration
        total_duration = sum(
            entry.end_ms - entry.start_ms
            for entry in original_entries
        )
        
        # Distribute text across timeline
        new_entries = []
        sentence_idx = 0
        current_text = []
        
        for i, entry in enumerate(original_entries):
            # Determine how much text to allocate to this subtitle
            entry_duration = entry.end_ms - entry.start_ms
            entry_ratio = entry_duration / total_duration if total_duration > 0 else 0
            
            # Allocate text proportionally
            target_chars = int(len(story_text) * entry_ratio)
            
            # Build text for this entry
            while sentence_idx < len(sentences) and len(' '.join(current_text)) < target_chars:
                current_text.append(sentences[sentence_idx])
                sentence_idx += 1
            
            if current_text:
                text = ' '.join(current_text)
                # Wrap if needed
                wrapped_text = self._wrap_text(text)
            else:
                # Fallback: use remaining text
                if sentence_idx < len(sentences):
                    wrapped_text = self._wrap_text(sentences[sentence_idx])
                    sentence_idx += 1
                else:
                    wrapped_text = ""
            
            # Create new entry
            new_entry = SubtitleEntry(
                index=entry.index,
                start_time=entry.start_time,
                end_time=entry.end_time,
                text=wrapped_text
            )
            new_entries.append(new_entry)
            
            # Reset for next entry
            current_text = []
        
        # Ensure all text is used
        if sentence_idx < len(sentences):
            remaining_text = ' '.join(sentences[sentence_idx:])
            if new_entries:
                # Add to last entry
                last_entry = new_entries[-1]
                combined_text = last_entry.text + " " + remaining_text
                last_entry.text = self._wrap_text(combined_text)
        
        return new_entries
    
    def _split_into_segments(self, text: str) -> List[str]:
        """
        Split text into logical segments for subtitle distribution.
        
        Args:
            text: Story text
            
        Returns:
            List of text segments
        """
        # Split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]
