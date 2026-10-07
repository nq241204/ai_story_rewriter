"""Filename utilities for AI Story Rewriter."""

import os
import re
from typing import List, Set


def sanitize_filename(title: str, max_length: int = 200) -> str:
    """
    Sanitize a title to create a safe filename.

    Removes/replaces characters that are invalid in Windows filenames.
    """
    invalid_chars = r'[<>:"/\\|?*\r\n\t]'
    sanitized = re.sub(invalid_chars, '', title)

    # Replace multiple spaces with single underscore
    sanitized = re.sub(r'\s+', '_', sanitized)

    # Remove leading/trailing underscores, dots, and spaces
    sanitized = sanitized.strip('_. ')

    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('_. ')

    return sanitized or "Story"


def natural_sort_key(filename: str) -> list:
    """
    Generate a sort key for pure-Python natural numeric sorting.

    Example: ['001.srt', '002.srt', '010.srt'] instead of ['001.srt', '010.srt', '002.srt']
    """
    def convert(text: str):
        return int(text) if text.isdigit() else text.lower()

    return [convert(c) for c in re.split(r'(\d+)', filename)]


def sort_files_naturally(filenames: List[str]) -> List[str]:
    """Sort a list of filenames using pure-Python natural numeric ordering."""
    return sorted(filenames, key=natural_sort_key)


def extract_file_number(filename: str) -> str:
    """
    Extract the numeric prefix from a filename.

    Example: '001_story.srt' -> '001'
    """
    match = re.match(r'^(\d+)', filename)
    return match.group(1) if match else ''


def generate_output_filename(original_filename: str, title: str, ext: str = ".srt") -> str:
    """
    Generate an output filename from the original filename and generated title.

    Example:
        original_filename: '001.srt'
        title: 'The Mafia Boss Came Home Early'
        output: '001_The_Mafia_Boss_Came_Home_Early.srt' (or .txt)
    """
    prefix = extract_file_number(original_filename)
    safe_title = sanitize_filename(title)

    if not ext.startswith('.'):
        ext = f".{ext}"

    if prefix:
        output = f"{prefix}_{safe_title}{ext}"
    else:
        base_name = os.path.splitext(original_filename)[0]
        safe_base = sanitize_filename(base_name, max_length=50)
        if safe_base and safe_base.lower() != safe_title.lower():
            output = f"{safe_base}_{safe_title}{ext}"
        else:
            output = f"{safe_title}{ext}"

    return output


def get_processed_prefixes(output_dir: str) -> Set[str]:
    """
    Pure-Python scan of output directory to find already processed file prefixes/names.
    Prevents unnecessary AI calls when resuming a batch.
    """
    processed: Set[str] = set()
    if not output_dir or not os.path.exists(output_dir):
        return processed

    try:
        with os.scandir(output_dir) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(('.srt', '.txt')):
                    if entry.stat().st_size > 0:
                        prefix = extract_file_number(entry.name)
                        if prefix:
                            processed.add(prefix)
                        processed.add(os.path.splitext(entry.name)[0].lower())
    except OSError:
        pass

    return processed
