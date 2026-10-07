"""Filename utilities for AI Story Rewriter."""

import re
from typing import List


def sanitize_filename(title: str, max_length: int = 200) -> str:
    """
    Sanitize a title to create a safe filename.
    
    Removes/replaces characters that are invalid in Windows filenames.
    """
    # Remove invalid characters
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '', title)
    
    # Replace multiple spaces with single underscore
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Remove leading/trailing underscores and spaces
    sanitized = sanitized.strip('_ ')
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('_ ')
    
    return sanitized


def natural_sort_key(filename: str) -> tuple:
    """
    Generate a sort key for natural numeric sorting.
    
    Example: ['001.srt', '002.srt', '010.srt'] instead of ['001.srt', '010.srt', '002.srt']
    """
    def convert(text):
        return int(text) if text.isdigit() else text.lower()
    
    return [convert(c) for c in re.split(r'(\d+)', filename)]


def sort_files_naturally(filenames: List[str]) -> List[str]:
    """Sort a list of filenames using natural numeric ordering."""
    return sorted(filenames, key=natural_sort_key)


def extract_file_number(filename: str) -> str:
    """
    Extract the numeric prefix from a filename.
    
    Example: '001_story.srt' -> '001'
    """
    match = re.match(r'^(\d+)', filename)
    return match.group(1) if match else ''


def generate_output_filename(original_filename: str, title: str) -> str:
    """
    Generate an output filename from the original filename and generated title.
    
    Example:
        original_filename: '001.srt'
        title: 'The Mafia Boss Came Home Early'
        output: '001_The_Mafia_Boss_Came_Home_Early.srt'
    """
    # Extract the numeric prefix
    prefix = extract_file_number(original_filename)
    
    # Sanitize the title
    safe_title = sanitize_filename(title)
    
    # Combine
    if prefix:
        output = f"{prefix}_{safe_title}.srt"
    else:
        output = f"{safe_title}.srt"
    
    return output
