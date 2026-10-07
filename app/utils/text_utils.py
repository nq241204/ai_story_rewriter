"""Text processing utilities for AI Story Rewriter."""

import re
from typing import List, Tuple, Optional

# Pre-compiled regex patterns for high-speed pure-Python text processing
HTML_TAG_PATTERN = re.compile(r'<[^>]+>|\{\\an\d+\}')
TIMECODE_LINE_PATTERN = re.compile(
    r'^\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}.*$',
    re.MULTILINE
)
INDEX_ONLY_LINE_PATTERN = re.compile(r'^\s*\d+\s*$', re.MULTILINE)
NOISE_BRACKET_PATTERN = re.compile(r'\[(?:music|applause|laughter|silence|sound[^\]]*)\]', re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r'(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bMrs)(?<=[.!?])\s+')

TITLE_MARKER_REGEX = re.compile(
    r'(?:^|\n)\s*[*#`-]*\s*---\s*TITLE\s*---\s*[*#`]*\s*:?\s*',
    re.IGNORECASE
)
SCRIPT_MARKER_REGEX = re.compile(
    r'(?:^|\n)\s*[*#`-]*\s*---\s*TTS_SCRIPT\s*---\s*[*#`]*\s*:?\s*',
    re.IGNORECASE
)


def normalize_line_endings(text: str) -> str:
    """
    Normalize line endings to LF.

    Handles LF, CRLF, and CR line endings.
    """
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    return text


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.

    Simple sentence splitting based on punctuation.
    """
    if not text or not text.strip():
        return []
    sentences = SENTENCE_SPLIT_PATTERN.split(text.strip())
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
    text = re.sub(r' +', ' ', text)
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines)


def strip_srt_artifacts(text: str) -> str:
    """
    Pure-Python removal of all SRT numbers, timecodes, HTML tags, and caption noise.
    Used both before sending text to AI (to save ~40-50% input tokens)
    and after receiving AI output (to guarantee clean TTS script).
    """
    if not text:
        return ""
    text = normalize_line_endings(text)
    text = TIMECODE_LINE_PATTERN.sub('', text)
    text = INDEX_ONLY_LINE_PATTERN.sub('', text)
    text = HTML_TAG_PATTERN.sub('', text)
    text = NOISE_BRACKET_PATTERN.sub('', text)
    return text.strip()


def compress_story_for_ai(lines: List[str]) -> str:
    """
    Deduplicate consecutive rolling subtitle lines and compress whitespace in pure Python.
    Minimizes input tokens sent to Gemini API without losing any story content.
    """
    deduped: List[str] = []
    prev_norm = ""

    for raw_line in lines:
        cleaned = HTML_TAG_PATTERN.sub('', raw_line)
        cleaned = NOISE_BRACKET_PATTERN.sub('', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if not cleaned:
            continue
        norm = cleaned.lower()
        # Skip exact consecutive duplicate caption lines (common in auto-SRT)
        if norm == prev_norm:
            continue
        # If previous line is a prefix of current rolling caption line, replace it
        if prev_norm and norm.startswith(prev_norm) and len(norm) > len(prev_norm):
            deduped[-1] = cleaned
            prev_norm = norm
            continue
        deduped.append(cleaned)
        prev_norm = norm

    return ' '.join(deduped)


def format_tts_paragraphs(text: str, sentences_per_paragraph: int = 3) -> str:
    """
    Format story text into short paragraphs (2-3 sentences per paragraph)
    optimized for Text-to-Speech (TTS) natural reading, with zero timecodes or index numbers.
    """
    cleaned = strip_srt_artifacts(text)
    if not cleaned:
        return ""

    # If AI already structured into good short paragraphs, normalize each paragraph
    raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]

    final_paragraphs: List[str] = []
    for para in raw_paragraphs:
        para_single_line = re.sub(r'\s+', ' ', para).strip()
        sentences = split_into_sentences(para_single_line)
        if len(sentences) <= sentences_per_paragraph:
            final_paragraphs.append(' '.join(sentences))
        else:
            # Split long blocks into chunks of 2-3 sentences for TTS pacing
            for i in range(0, len(sentences), sentences_per_paragraph):
                chunk = sentences[i:i + sentences_per_paragraph]
                if chunk:
                    final_paragraphs.append(' '.join(chunk))

    return '\n\n'.join(final_paragraphs)


def parse_unified_ai_output(raw_text: str) -> Tuple[Optional[str], str]:
    """
    Parse the unified 2-section AI output:
    ---TITLE---
    <Title>
    ---TTS_SCRIPT---
    <TTS Script>

    Returns:
        Tuple of (title_or_none, clean_tts_script)
    """
    if not raw_text or not raw_text.strip():
        return None, ""

    text = normalize_line_endings(raw_text.strip())
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text).strip()

    title: Optional[str] = None
    script_body: str = text

    script_match = SCRIPT_MARKER_REGEX.search(text)
    title_match = TITLE_MARKER_REGEX.search(text)

    if script_match:
        before_script = text[:script_match.start()].strip()
        script_body = text[script_match.end():].strip()

        if title_match and title_match.start() < script_match.start():
            title_raw = text[title_match.end():script_match.start()].strip()
        else:
            title_raw = before_script

        # Take the first non-empty line as title
        title_lines = [line.strip() for line in title_raw.split('\n') if line.strip()]
        if title_lines:
            title = title_lines[0].strip(' "\'*#`')
    elif title_match:
        after_title = text[title_match.end():].strip()
        lines = [line.strip() for line in after_title.split('\n') if line.strip()]
        if lines:
            title = lines[0].strip(' "\'*#`')
            script_body = '\n\n'.join(lines[1:]).strip()

    cleaned_script = format_tts_paragraphs(script_body, sentences_per_paragraph=3)
    return title, cleaned_script


def format_unified_output(title: str, tts_script: str) -> str:
    """
    Format the final output into the 2-part structure shown in the specification:
    ---TITLE--- : Title giật tít CTR YouTube.
    ---TTS_SCRIPT--- : Toàn bộ lời thoại tiếng Anh liền mạch...
    """
    clean_title = (title or "Story").strip().strip('"')
    clean_script = format_tts_paragraphs(tts_script, sentences_per_paragraph=3)
    return f"---TITLE---\n{clean_title}\n\n---TTS_SCRIPT---\n{clean_script}\n"
