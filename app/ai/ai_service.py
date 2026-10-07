"""AI service for AI Story Rewriter (Token-Optimized Single-Pass Pipeline)."""

import re
from collections import Counter
from typing import Optional, Dict, Any, List
from app.ai.gemini_client import GeminiClient
from app.ai.prompts import Prompts
from app.utils.logger import get_logger
from app.utils.text_utils import (
    strip_srt_artifacts,
    parse_unified_ai_output,
    format_tts_paragraphs,
    format_unified_output,
    split_into_sentences,
    estimate_reading_time,
)


class AIService:
    """Service for AI-powered story processing with minimal token usage."""

    def __init__(
        self,
        client: GeminiClient,
        api_timeout: int = 60,
        analysis_timeout: int = 30,
        qc_timeout: int = 30,
        rewrite_intensity: str = "balanced",
        max_retries: int = 3,
        use_ai_analysis: bool = False,
        use_ai_qc: bool = False,
    ):
        """
        Initialize AI service.

        By default, `use_ai_analysis=False` and `use_ai_qc=False` so analysis and QC
        are performed in pure Python (0 extra tokens), and Title + TTS Script are
        generated in a single Gemini API call.
        """
        self.client = client
        self.prompts = Prompts()
        self.logger = get_logger()
        self.api_timeout = api_timeout
        self.analysis_timeout = analysis_timeout
        self.qc_timeout = qc_timeout
        self.rewrite_intensity = (rewrite_intensity or "balanced").lower()
        self.max_retries = max_retries
        self.use_ai_analysis = use_ai_analysis
        self.use_ai_qc = use_ai_qc

        # Cached single-pass outputs for the current file
        self.last_title: Optional[str] = None
        self.last_tts_script: Optional[str] = None
        self.last_formatted_output: Optional[str] = None

    def reset_state(self) -> None:
        """Reset cached single-pass outputs between files."""
        self.last_title = None
        self.last_tts_script = None
        self.last_formatted_output = None

    # ============================================================
    # PURE PYTHON ANALYSIS & QC (0 AI TOKENS)
    # ============================================================

    def _python_analyze_story(self, story: str) -> str:
        """
        Fast pure-Python story analysis (0 tokens, <1ms).
        Extracts word count, sentence count, reading duration, and character names.
        """
        clean_text = strip_srt_artifacts(story)
        words = clean_text.split()
        sentences = split_into_sentences(clean_text)
        reading_mins = estimate_reading_time(clean_text)

        # Find probable character names (capitalized words not at start of sentence)
        stop_words = {
            "The", "And", "But", "For", "Nor", "Or", "Yet", "So", "In", "On",
            "At", "To", "From", "By", "With", "About", "Against", "Between",
            "Into", "Through", "During", "Before", "After", "Above", "Below",
            "He", "She", "They", "We", "You", "It", "His", "Her", "Their",
            "My", "Your", "Our", "This", "That", "These", "Those", "What",
            "When", "Where", "Why", "How", "Who", "Which", "Yes", "No", "Not",
            "One", "Two", "Three", "Then", "There", "Here", "Now", "Just",
            "Mr", "Mrs", "Ms", "Dr", "St", "God", "Okay", "Well", "Oh"
        }
        capitalized = re.findall(r'(?<=[a-z]\s)([A-Z][a-z]{2,15})\b', clean_text)
        char_counts = Counter(w for w in capitalized if w not in stop_words)
        top_chars = [name for name, _ in char_counts.most_common(6)]

        analysis_summary = (
            f"Words: {len(words)} | Sentences: {len(sentences)} | "
            f"Est. TTS: {reading_mins:.1f} min | "
            f"Detected Characters: {', '.join(top_chars) if top_chars else 'N/A'}"
        )
        return analysis_summary

    def _python_quality_check(
        self,
        original_story: str,
        rewritten_story: str
    ) -> Dict[str, Any]:
        """
        Pure-Python quality control (0 tokens, <1ms).
        Only flags FAIL if the AI output is genuinely broken, truncated, or empty.
        """
        issues: List[str] = []

        if not rewritten_story or not rewritten_story.strip():
            return {"status": "FAIL", "issues": ["Rewritten story is empty."]}

        orig_words = strip_srt_artifacts(original_story).split()
        rew_words = strip_srt_artifacts(rewritten_story).split()

        if len(rew_words) < 3:
            issues.append("Rewritten story is too short or incomplete.")
        elif len(orig_words) >= 40 and len(rew_words) < len(orig_words) * 0.25:
            issues.append(
                f"Rewritten story was severely truncated ({len(rew_words)} words vs {len(orig_words)} original words)."
            )

        # Check for raw SRT timecodes
        if "-->" in rewritten_story:
            issues.append("Output still contains SRT timecodes (-->).")

        return {
            "status": "FAIL" if issues else "PASS",
            "issues": issues
        }

    # ============================================================
    # PIPELINE METHODS
    # ============================================================

    def analyze_story(self, story: str) -> Optional[str]:
        """
        Analyze a story. Uses pure Python by default to save 100% of analysis tokens.
        """
        if not self.use_ai_analysis:
            analysis = self._python_analyze_story(story)
            self.logger.info(f"Python story analysis: {analysis}")
            return analysis

        self.logger.info("Starting AI story analysis")
        prompt = self.prompts.ANALYZE_STORY.format(story=strip_srt_artifacts(story))
        return self.client.generate_content(
            prompt,
            temperature=0.4,
            max_retries=2,
            timeout=self.analysis_timeout
        )

    def rewrite_story(self, original_story: str) -> Optional[str]:
        """
        Single-pass AI call: Rewrites the story into 2-3 sentence TTS paragraphs
        AND generates the CTR YouTube title in one request (---TITLE--- & ---TTS_SCRIPT---).
        """
        self.reset_state()
        self.logger.info("Starting single-pass story rewrite + CTR title generation")

        clean_input = strip_srt_artifacts(original_story)
        if not clean_input:
            self.logger.error("Input story is empty after stripping SRT artifacts")
            return None

        intensity_hint = self.prompts.INTENSITY_HINTS.get(
            self.rewrite_intensity,
            self.prompts.INTENSITY_HINTS["balanced"]
        )
        system_instruction = f"{self.prompts.REWRITE_SYSTEM}\n\nStyle: {intensity_hint}"
        prompt = self.prompts.REWRITE_STORY.format(story=clean_input)

        raw_output = self.client.generate_content(
            prompt,
            system_instruction=system_instruction,
            temperature=0.75,
            max_retries=self.max_retries,
            timeout=self.api_timeout
        )

        if not raw_output:
            self.logger.error("Story rewrite failed")
            return None

        title, tts_script = parse_unified_ai_output(raw_output)
        if not tts_script:
            tts_script = format_tts_paragraphs(raw_output, sentences_per_paragraph=3)

        self.last_title = title
        self.last_tts_script = tts_script
        self.last_formatted_output = format_unified_output(
            self.last_title or "Story",
            self.last_tts_script
        )

        self.logger.info(
            f"Single-pass rewrite completed (Title: {(self.last_title or 'Pending')[:45]})"
        )
        return self.last_tts_script

    def quality_check(
        self,
        original_story: str,
        rewritten_story: str
    ) -> Optional[Dict[str, Any]]:
        """
        Perform quality control. Uses pure Python by default (0 tokens),
        only calling AI if Python QC fails or `use_ai_qc` is explicitly enabled.
        """
        python_qc = self._python_quality_check(original_story, rewritten_story)
        if python_qc["status"] == "FAIL":
            self.logger.warning(
                f"Python QC detected {len(python_qc['issues'])} issues: {python_qc['issues']}"
            )
            return python_qc

        if not self.use_ai_qc:
            self.logger.info("Quality control passed (pure Python check, 0 tokens used)")
            return python_qc

        self.logger.info("Starting AI quality control")
        prompt = self.prompts.QC_CHECK.format(
            original_story=strip_srt_artifacts(original_story),
            rewritten_story=rewritten_story
        )

        result = self.client.generate_json(
            prompt,
            temperature=0.2,
            max_retries=2,
            timeout=self.qc_timeout
        )

        if result:
            status = result.get("status", "FAIL")
            issues = result.get("issues", [])
            if status == "PASS":
                self.logger.info("AI quality control passed")
            else:
                self.logger.warning(f"AI quality control failed with {len(issues)} issues")
            return result

        self.logger.warning("AI QC call failed; falling back to Python QC PASS")
        return python_qc

    def correct_qc_issues(
        self,
        rewritten_story: str,
        issues: list
    ) -> Optional[str]:
        """
        Correct quality control issues (only called when QC actually fails).
        """
        self.logger.info(f"Correcting {len(issues)} QC issues")

        # Fast path: if only issue is SRT timecodes, strip them in pure Python (0 tokens!)
        if len(issues) == 1 and "timecodes" in issues[0].lower():
            cleaned = format_tts_paragraphs(rewritten_story, sentences_per_paragraph=3)
            self.last_tts_script = cleaned
            return cleaned

        issues_text = "\n".join(f"- {issue}" for issue in issues)
        prompt = self.prompts.QC_CORRECTION.format(
            issues=issues_text,
            rewritten_story=rewritten_story
        )

        corrected_raw = self.client.generate_content(
            prompt,
            system_instruction=self.prompts.REWRITE_SYSTEM,
            temperature=0.6,
            max_retries=2,
            timeout=self.qc_timeout
        )

        if not corrected_raw:
            self.logger.error("QC correction failed")
            return None

        title, corrected_script = parse_unified_ai_output(corrected_raw)
        if title and not self.last_title:
            self.last_title = title
        if corrected_script:
            self.last_tts_script = corrected_script
            self.last_formatted_output = format_unified_output(
                self.last_title or "Story",
                self.last_tts_script
            )
            return corrected_script

        return format_tts_paragraphs(corrected_raw, sentences_per_paragraph=3)

    def generate_title(self, story: str) -> Optional[str]:
        """
        Return the CTR title already extracted in the single-pass rewrite (0 extra tokens!),
        or call Gemini as a fallback only if title was missing.
        """
        if self.last_title:
            self.logger.info(f"Using single-pass title (0 extra tokens): {self.last_title[:50]}")
            return self.last_title

        # Check if story itself contains ---TITLE---
        parsed_title, _ = parse_unified_ai_output(story)
        if parsed_title:
            self.last_title = parsed_title
            return parsed_title

        self.logger.info("Generating fallback title via AI")
        # Send only first ~2500 chars to save tokens on fallback title generation
        excerpt = strip_srt_artifacts(story)[:2500]
        prompt = self.prompts.GENERATE_TITLE.format(story=excerpt)

        title = self.client.generate_content(
            prompt,
            temperature=0.85,
            max_retries=2,
            timeout=25
        )

        if title:
            title = title.strip().splitlines()[0].strip(' "\'*#`')
            self.last_title = title
            self.logger.info(f"Fallback title generated: {title[:50]}")
        else:
            self.logger.error("Title generation failed")

        return title
