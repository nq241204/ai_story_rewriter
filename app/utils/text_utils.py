"""Text processing utilities for AI Story Rewriter."""

import re
from typing import List


def normalize_line_endings(text: str) -> str:
    """
    Normalize line endings to LF.
    
    Handles LF, CRLF, and CR line endings.
    """
    # First normalize CRLF to LF
    text = text.replace('\r\n', '\n')
    # Then normalize CR to LF
    text = text.replace('\r', '\n')
    return text


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    
    Simple sentence splitting based on punctuation.
    """
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def estimate_reading_time(text: str, words_per_minute: int = 150) -> float:
    """
    Estimate reading time in minutes.
    """
    word_count = len(text.split())
    return word_count / words_per_minute if words_per_minute > 0 else 0


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def clean_whitespace(text: str) -> str:
    """
    Clean up whitespace in text.
    
    Removes excessive spaces and normalizes line breaks.
    """
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Remove leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split('\n')]
    # Remove empty lines
    lines = [line for line in lines if line]
    return '\n'.join(lines)
