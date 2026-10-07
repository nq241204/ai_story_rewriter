"""AI service for AI Story Rewriter (Hybrid Python Pre-Check + Targeted LLM Workflow)."""

import re
from typing import Optional, Dict, Any, List
from app.ai.gemini_client import GeminiClient
from app.ai.prompts import Prompts
from app.pipeline.pre_checker import PythonPreChecker, PreCheckReport, StoryUniquenessGuard
from app.utils.logger import get_logger
from app.utils.text_utils import (
    strip_srt_artifacts,
    parse_unified_ai_output,
    format_tts_paragraphs,
    format_unified_output,
)


class AIService:
    """Service for AI-powered story processing with Hybrid Python+LLM workflow and Cross-Story Uniqueness Guard."""

    def __init__(
        self,
        client: Optional[GeminiClient],
        api_timeout: int = 60,
        analysis_timeout: int = 30,
        qc_timeout: int = 30,
        rewrite_intensity: str = "balanced",
        max_retries: int = 3,
        use_ai_analysis: bool = False,
        use_ai_qc: bool = False,
        workflow_mode: str = "full_ai",  # "full_ai", "hybrid", "python_only"
        story_tags: str = "",
        story_keys: str = "",
    ):
        """
        Initialize AI service.

        workflow_mode:
          - "full_ai": 1-Pass Full Story Rewrite from Plot Skeleton + 0-Token Python Pre/Post-Check (Default).
          - "hybrid": Pure-Python Pre-Check flags specific paragraphs -> LLM only rewrites
                      flagged paragraphs + generates CTR Title (saves 70-95% tokens).
          - "python_only": 0 Tokens! Pure-Python Pre-Check & TTS formatting only,
                           outputs Pre-Check report for human editing.
        """
        self.client = client
        self.prompts = Prompts()
        self.pre_checker = PythonPreChecker()
        self.uniqueness_guard = StoryUniquenessGuard()
        self.logger = get_logger()
        self.api_timeout = api_timeout
        self.analysis_timeout = analysis_timeout
        self.qc_timeout = qc_timeout
        self.rewrite_intensity = (rewrite_intensity or "balanced").lower()
        self.max_retries = max_retries
        self.use_ai_analysis = use_ai_analysis
        self.use_ai_qc = use_ai_qc
        self.workflow_mode = (workflow_mode or "full_ai").lower()
        self.story_tags = (story_tags or "").strip()
        self.story_keys = (story_keys or "").strip()

        # Cached outputs for the current file (isolated per call)
        self._last_source_hash: Optional[int] = None
        self._pending_source_report: Optional[PreCheckReport] = None
        self.last_title: Optional[str] = None
        self.last_tts_script: Optional[str] = None
        self.last_formatted_output: Optional[str] = None
        self.last_precheck_report: Optional[PreCheckReport] = None

    def reset_state(self) -> None:
        """Reset cached single-pass outputs between files (preserves cross-story uniqueness history)."""
        self._last_source_hash = None
        self._pending_source_report = None
        self.last_title = None
        self.last_tts_script = None
        self.last_formatted_output = None
        self.last_precheck_report = None

    def reset_uniqueness_history(self) -> None:
        """Reset cross-story uniqueness registry if starting a completely new project."""
        self.uniqueness_guard.reset()

    # ============================================================
    # STEP 1: PURE PYTHON PRE-CHECK (0 TOKENS)
    # ============================================================

    def run_precheck(self, story: str) -> PreCheckReport:
        """
        Run the pure-Python Pre-Checker (0 tokens, processes millions of words in seconds).
        Detects repetitive words, proper noun typos, long sentences, formatting issues,
        and combines manual Tag/Key inputs with auto-detected genre & hook signals.
        """
        self._last_source_hash = hash(story)
        report = self.pre_checker.analyze_and_prepare(
            story,
            manual_tags=self.story_tags,
            manual_keys=self.story_keys,
        )
        self._pending_source_report = report
        self.last_precheck_report = report
        self.logger.info(
            f"Python Pre-Check: {len(report.paragraphs)} paragraphs "
            f"({len(report.clean_indices)} clean, {len(report.flagged_indices)} flagged, "
            f"~{report.token_savings_estimate_pct}% token savings)"
        )
        return report

    def _python_quality_check(
        self,
        original_story: str,
        rewritten_story: str
    ) -> Dict[str, Any]:
        """
        Pure-Python quality control (0 tokens, <1ms).
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

        if "-->" in rewritten_story:
            issues.append("Output still contains SRT timecodes (-->).")

        return {
            "status": "FAIL" if issues else "PASS",
            "issues": issues
        }

    # ============================================================
    # STEP 2: HYBRID TARGETED LLM POLISH
    # ============================================================

    def _merge_hybrid_paragraphs(
        self,
        original_paragraphs: List[str],
        flagged_indices: List[int],
        ai_script_body: str
    ) -> str:
        """
        Merge AI-rewritten flagged paragraphs [P#i] back into the clean Python paragraphs.
        """
        merged = list(original_paragraphs)

        # Parse [P#index] blocks returned by LLM
        pattern = re.compile(r'\[P#(\d+)\]\s*(.*?)(?=\n\s*\[P#\d+\]|\Z)', re.DOTALL)
        matches = pattern.findall(ai_script_body)

        if matches:
            for idx_str, content in matches:
                idx = int(idx_str)
                cleaned_para = format_tts_paragraphs(content.strip(), sentences_per_paragraph=3)
                if 0 <= idx < len(merged) and cleaned_para:
                    merged[idx] = cleaned_para
            return "\n\n".join(merged)

        # Fallback if LLM returned paragraphs without [P#i] tags in exact count
        returned_paras = [
            p.strip() for p in re.split(r'\n\s*\n', ai_script_body.strip()) if p.strip()
        ]
        if len(returned_paras) == len(flagged_indices):
            for idx, new_p in zip(flagged_indices, returned_paras):
                cleaned_p = re.sub(r'^\[P#\d+\]\s*', '', new_p).strip()
                if cleaned_p:
                    merged[idx] = format_tts_paragraphs(cleaned_p, sentences_per_paragraph=3)
            return "\n\n".join(merged)

        # If LLM rewrote the whole passage coherently
        cleaned_all = re.sub(r'\[P#\d+\]\s*', '', ai_script_body).strip()
        return format_tts_paragraphs(cleaned_all, sentences_per_paragraph=3) or "\n\n".join(merged)

    def rewrite_flagged_paragraphs_only(
        self,
        report: PreCheckReport
    ) -> Optional[str]:
        """
        Hybrid LLM mode: Only sends Python-flagged paragraphs to Gemini for emotional/rhythm polish,
        keeping all clean paragraphs untouched (saving 70%-95% tokens!).
        """
        if not self.client:
            return "\n\n".join(report.paragraphs)

        # Case 1: 0 paragraphs flagged -> 0 rewrite tokens! Only generate CTR title from short excerpt
        if not report.flagged_indices:
            self.logger.info(
                "Hybrid Mode: 0 paragraphs flagged by Python! Skipping story rewrite (100% rewrite tokens saved)."
            )
            full_clean_script = "\n\n".join(report.paragraphs)
            self.last_tts_script = full_clean_script
            self.last_title = self.generate_title(full_clean_script) or "Story"
            self.last_formatted_output = format_unified_output(self.last_title, self.last_tts_script)
            return self.last_tts_script

        # Case 2: Specific paragraphs flagged -> send ONLY flagged paragraphs [P#i] to Gemini
        flagged_blocks_lines = []
        for idx in report.flagged_indices:
            p_issue = report.paragraph_issues[idx]
            flags_str = "; ".join(p_issue.flags)
            flagged_blocks_lines.append(
                f"[P#{idx}] (Flags: {flags_str})\n{p_issue.text}"
            )

        opening_ctx = report.paragraphs[0][:250] if report.paragraphs else ""
        ending_ctx = report.paragraphs[-1][:250] if len(report.paragraphs) > 1 else ""
        chars_str = ", ".join(report.detected_characters) if report.detected_characters else "Main characters"

        prompt = self.prompts.HYBRID_TARGETED_REWRITE.format(
            characters=chars_str,
            opening_context=opening_ctx,
            ending_context=ending_ctx,
            flagged_blocks="\n\n".join(flagged_blocks_lines),
        )

        intensity_hint = self.prompts.INTENSITY_HINTS.get(
            self.rewrite_intensity,
            self.prompts.INTENSITY_HINTS["balanced"]
        )
        system_instruction = f"{self.prompts.HYBRID_SYSTEM}\n\nStyle: {intensity_hint}"

        self.logger.info(
            f"Hybrid Mode: Sending ONLY {len(report.flagged_indices)}/{len(report.paragraphs)} "
            f"flagged paragraphs to Gemini (~{report.token_savings_estimate_pct}% token savings)"
        )

        raw_output = self.client.generate_content(
            prompt,
            system_instruction=system_instruction,
            temperature=0.7,
            max_retries=self.max_retries,
            timeout=self.api_timeout,
        )

        if not raw_output:
            self.logger.warning("Hybrid AI call failed; falling back to Python pre-checked script")
            return None

        title, script_body = parse_unified_ai_output(raw_output)
        merged_script = self._merge_hybrid_paragraphs(
            report.paragraphs,
            report.flagged_indices,
            script_body or raw_output,
        )

        self.last_title = title
        self.last_tts_script = merged_script
        self.last_formatted_output = format_unified_output(
            self.last_title or "Story",
            self.last_tts_script,
        )
        return self.last_tts_script

    # ============================================================
    # PIPELINE METHODS
    # ============================================================

    def analyze_story(self, story: str) -> Optional[str]:
        """
        Step 1 of Hybrid Workflow: Run Pure-Python Pre-Checker (0 tokens, <2ms)
        and generate the Vietnamese Pre-Check Report.
        """
        report = self.run_precheck(story)
        if not self.use_ai_analysis:
            return report.to_vietnamese_summary()

        if not self.client:
            return report.to_vietnamese_summary()

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
        Rewrite story according to configured `workflow_mode`, with strict context isolation
        and cross-story uniqueness enforcement so no two stories ever duplicate content:
          - "python_only": 0 tokens! Returns Python-cleaned TTS paragraphs immediately.
          - "hybrid": Only sends flagged paragraphs to LLM if partial flags exist,
                      or full single-pass with Python pre-check guidance.
          - "full_ai": Full single-pass plot-skeleton rewrite + title generation + uniqueness guard.
        """
        # Guarantee zero state carryover: consume pending source report once, or run fresh precheck
        if self._pending_source_report is not None and self._last_source_hash == hash(original_story):
            report = self._pending_source_report
            self._pending_source_report = None
        else:
            self.reset_state()
            report = self.run_precheck(original_story)
            self._pending_source_report = None

        # Mode 1: Pure Python Pre-Check Only (0 AI Tokens — for human review/editing)
        if self.workflow_mode == "python_only":
            self.logger.info("Python-Only Mode: 0 AI tokens used. Returning pre-checked TTS script.")
            clean_script = "\n\n".join(report.paragraphs)
            clean_script = self.pre_checker.normalize_proper_nouns_in_text(clean_script, report)
            clean_script, active_chars, _, _ = self.uniqueness_guard.prepare_unique_source_and_directive(
                clean_script, report.detected_characters
            )
            auto_title = (
                f"Story ({', '.join(active_chars[:2])})"
                if active_chars
                else f"Story_{self.uniqueness_guard.story_counter}"
            )
            _, uniq_pct, uniq_note = self.uniqueness_guard.verify_and_register(
                auto_title, clean_script, original_story, active_chars
            )
            report.uniqueness_score_pct = uniq_pct
            report.uniqueness_note = uniq_note
            self.last_title = auto_title
            self.last_tts_script = clean_script
            self.last_formatted_output = (
                format_unified_output(self.last_title, self.last_tts_script)
                + "\n"
                + report.to_vietnamese_summary()
            )
            return self.last_tts_script

        if not self.client:
            self.logger.error("GeminiClient is not initialized")
            return None

        # Mode 2: Hybrid Targeted Mode whenever there are clean paragraphs to preserve
        if (
            self.workflow_mode == "hybrid"
            and len(report.paragraphs) >= 1
            and len(report.flagged_indices) < len(report.paragraphs)
        ):
            return self.rewrite_flagged_paragraphs_only(report)

        # Mode 3: Full Single-Pass Story Rewrite from Plot Skeleton (guided by Python Pre-Check & Uniqueness Guard)
        self.logger.info("Starting single-pass story rewrite + CTR title generation (guided by Python Pre-Check)")
        clean_input = "\n\n".join(report.paragraphs)
        if not clean_input:
            return None

        # Fix any character name typos in the source skeleton in pure Python (0 tokens)
        clean_input = self.pre_checker.normalize_proper_nouns_in_text(clean_input, report)

        # Apply Cross-Story Uniqueness Guard (0 tokens): recast names if source SRT is duplicate & rotate hook style
        clean_input, active_chars, uniqueness_directive, was_source_dup = (
            self.uniqueness_guard.prepare_unique_source_and_directive(clean_input, report.detected_characters)
        )
        if was_source_dup:
            self.logger.warning(
                "Source overlap detected with an earlier story! Recasting character names and narrative perspective."
            )

        notes = [
            f"Target story length: maintain or enrich depth (~{max(report.total_words, 120)} words, never summarize).",
            uniqueness_directive,
        ]
        if report.detected_genre_tags:
            notes.append(
                f"Story Genre / Tags (lock onto this exact tone, emotional pacing, and payoff): {', '.join(report.detected_genre_tags)}."
            )
        if report.detected_hook_keys:
            notes.append(
                f"Core Hook Keywords (build the opening hook, dramatic tension, and YouTube CTR title around these elements): {', '.join(report.detected_hook_keys)}."
            )
        if active_chars:
            notes.append(f"Main characters (use these exact names consistently): {', '.join(active_chars)}.")
        if report.flagged_indices:
            flagged_summary = "; ".join(
                f"P#{i+1} ({', '.join(report.paragraph_issues[i].flags)})"
                for i in report.flagged_indices[:5]
            )
            notes.append(f"Fix these source weaknesses during rewrite: {flagged_summary}.")
        precheck_notes = "\n" + " ".join(notes) + "\n"

        intensity_hint = self.prompts.INTENSITY_HINTS.get(
            self.rewrite_intensity,
            self.prompts.INTENSITY_HINTS["balanced"]
        )
        system_instruction = f"{self.prompts.REWRITE_SYSTEM}\n\nStyle: {intensity_hint}"
        prompt = self.prompts.REWRITE_STORY.format(
            story=clean_input,
            precheck_notes=precheck_notes,
        )

        temp = 0.85 if was_source_dup else 0.75
        raw_output = self.client.generate_content(
            prompt,
            system_instruction=system_instruction,
            temperature=temp,
            max_retries=self.max_retries,
            timeout=self.api_timeout
        )

        if not raw_output:
            self.logger.error("Story rewrite failed")
            return None

        title, tts_script = parse_unified_ai_output(raw_output)
        if not tts_script:
            tts_script = format_tts_paragraphs(raw_output, sentences_per_paragraph=3, clean_cliches=True)
        else:
            tts_script = format_tts_paragraphs(tts_script, sentences_per_paragraph=3, clean_cliches=True)

        # Verify output uniqueness against all previous stories in the batch (0 tokens)
        is_unique, uniq_pct, uniq_note = self.uniqueness_guard.verify_and_register(
            title or "Story", tts_script, original_story, active_chars
        )

        self.last_title = title
        self.last_tts_script = tts_script
        self.last_formatted_output = format_unified_output(
            self.last_title or "Story",
            self.last_tts_script
        )
        # Update Pre-Check report on the newly rewritten story (0 tokens)
        post_report = self.pre_checker.analyze_and_prepare(
            self.last_tts_script,
            manual_tags=self.story_tags,
            manual_keys=self.story_keys,
        )
        post_report.uniqueness_score_pct = uniq_pct
        post_report.uniqueness_note = uniq_note
        self.last_precheck_report = post_report

        self.logger.info(
            f"Single-pass rewrite completed (Title: {(self.last_title or 'Pending')[:45]} | Uniqueness: {uniq_pct}%)"
        )
        return self.last_tts_script

    def quality_check(
        self,
        original_story: str,
        rewritten_story: str
    ) -> Optional[Dict[str, Any]]:
        """
        Perform quality control. Uses pure Python by default (0 tokens).
        """
        python_qc = self._python_quality_check(original_story, rewritten_story)
        if python_qc["status"] == "FAIL":
            self.logger.warning(
                f"Python QC detected {len(python_qc['issues'])} issues: {python_qc['issues']}"
            )
            return python_qc

        if not self.use_ai_qc or self.workflow_mode == "python_only" or not self.client:
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
            return result

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

        if len(issues) == 1 and "timecodes" in issues[0].lower():
            cleaned = format_tts_paragraphs(rewritten_story, sentences_per_paragraph=3)
            self.last_tts_script = cleaned
            return cleaned

        if not self.client:
            return rewritten_story

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
        Return the CTR title already extracted in the single-pass/hybrid rewrite (0 extra tokens!),
        or call Gemini with a minimal excerpt only if title was missing.
        """
        if self.last_title:
            self.logger.info(f"Using cached title (0 extra tokens): {self.last_title[:50]}")
            return self.last_title

        parsed_title, _ = parse_unified_ai_output(story)
        if parsed_title:
            self.last_title = parsed_title
            return parsed_title

        if self.workflow_mode == "python_only" or not self.client:
            return "Story"

        self.logger.info("Generating title via AI (short excerpt)")
        excerpt = strip_srt_artifacts(story)[:1500]
        prompt = self.prompts.GENERATE_TITLE.format(story=excerpt)

        title = self.client.generate_content(
            prompt,
            temperature=0.85,
            max_retries=2,
            timeout=20
        )

        if title:
            title = title.strip().splitlines()[0].strip(' "\'*#`')
            self.last_title = title
            self.logger.info(f"Title generated: {title[:50]}")
        else:
            self.logger.error("Title generation failed")

        return title
