"""SRT and TTS script writer for AI Story Rewriter."""

import re
from typing import List
from dataclasses import dataclass
from app.srt.parser import SubtitleEntry
from app.utils.text_utils import format_unified_output, strip_srt_artifacts


@dataclass
class SRTConfig:
    """Configuration for SRT writing."""
    max_chars_per_line: int = 42
    max_lines_per_subtitle: int = 2
    min_subtitle_duration: int = 1000  # milliseconds
    max_subtitle_duration: int = 7000  # milliseconds


class SRTWriter:
    """Writer for TTS script and SRT subtitle files."""

    def __init__(self, config: SRTConfig = None):
        self.config = config or SRTConfig()

    def write_tts_file(self, title: str, tts_script: str, filepath: str) -> None:
        """
        Write the 2-part output (---TITLE--- and ---TTS_SCRIPT---) to a file.
        """
        content = format_unified_output(title, tts_script)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def write_file(self, entries: List[SubtitleEntry], filepath: str) -> None:
        """
        Write subtitle entries to an SRT file.
        """
        content = self.write_content(entries)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def write_content(self, entries: List[SubtitleEntry]) -> str:
        """
        Generate SRT content from subtitle entries.
        """
        lines = []
        for entry in entries:
            lines.append(str(entry.index))
            lines.append(f"{entry.start_time} --> {entry.end_time}")

            wrapped_text = self._wrap_text(entry.text)
            lines.append(wrapped_text)
            lines.append("")

        return '\n'.join(lines)

    def _wrap_text(self, text: str, truncate_lines: bool = True) -> str:
        """
        Wrap text to fit within character limits.
        """
        if len(text) <= self.config.max_chars_per_line:
            return text

        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            sep = 1 if current_line else 0

            if current_length + word_length + sep <= self.config.max_chars_per_line:
                current_line.append(word)
                current_length += word_length + sep
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length

        if current_line:
            lines.append(' '.join(current_line))

        if truncate_lines and len(lines) > self.config.max_lines_per_subtitle:
            lines = lines[:self.config.max_lines_per_subtitle]

        return '\n'.join(lines)

    def map_story_to_timeline(
        self,
        story_text: str,
        original_entries: List[SubtitleEntry]
    ) -> List[SubtitleEntry]:
        """
        Map rewritten story text to original subtitle timeline proportionally by word count
        so no words at the end of the story are ever lost or truncated.
        """
        if not original_entries:
            return []

        clean_story = strip_srt_artifacts(story_text)
        words = clean_story.split()
        if not words:
            return [
                SubtitleEntry(
                    index=e.index,
                    start_time=e.start_time,
                    end_time=e.end_time,
                    text=e.text
                )
                for e in original_entries
            ]

        total_duration = sum(
            max(100, entry.end_ms - entry.start_ms)
            for entry in original_entries
        )

        new_entries = []
        total_words = len(words)
        word_idx = 0
        elapsed_duration = 0

        for i, entry in enumerate(original_entries):
            entry_duration = max(100, entry.end_ms - entry.start_ms)
            elapsed_duration += entry_duration

            if i == len(original_entries) - 1:
                chunk_words = words[word_idx:]
                word_idx = total_words
            else:
                target_word_idx = round((elapsed_duration / total_duration) * total_words)
                # Ensure at least 1 word if words remain
                if target_word_idx <= word_idx and word_idx < total_words:
                    target_word_idx = word_idx + 1
                chunk_words = words[word_idx:target_word_idx]
                word_idx = target_word_idx

            text = ' '.join(chunk_words) if chunk_words else "..."
            wrapped_text = self._wrap_text(text, truncate_lines=False)

            new_entries.append(
                SubtitleEntry(
                    index=entry.index,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    text=wrapped_text
                )
            )

        return new_entries

    def _split_into_segments(self, text: str) -> List[str]:
        """
        Split text into logical segments for subtitle distribution.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]
