"""Tests for single-pass TTS output (---TITLE--- & ---TTS_SCRIPT---), token optimization, and Vietnamese UI."""

import os
import shutil
import unittest
from app.utils.text_utils import (
    parse_unified_ai_output,
    format_unified_output,
    format_tts_paragraphs,
    compress_story_for_ai,
    strip_srt_artifacts,
)
from app.ai.ai_service import AIService
from app.pipeline.story_processor import StoryProcessor, ProcessingState
from app.pipeline.pre_checker import PythonPreChecker


class DummyGeminiClient:
    """Fake GeminiClient that records the exact number of API calls made."""

    def __init__(self):
        self.api_calls = 0
        self.last_prompt = ""
        self.model_name = "gemini-2.5-flash"

    def generate_content(self, prompt, system_instruction=None, temperature=0.7, max_retries=3, timeout=60):
        self.api_calls += 1
        self.last_prompt = prompt
        if "[P#" in prompt:
            return (
                "---TITLE---\n"
                "She Thought He Was Poor Until The Helicopter Landed\n\n"
                "---FIXED_PARAGRAPHS---\n"
                "[P#1]\n"
                "Marcus stepped forward calmly as the entire hall fell dead silent. "
                "Every guest realized the man they mocked owned the estate."
            )
        return (
            "---TITLE---\n"
            "She Thought He Was Poor Until The Helicopter Landed\n\n"
            "---TTS_SCRIPT---\n"
            "John walked into the grand estate quietly. Nobody in the room bothered to look up at his worn coat. "
            "They assumed he was just another delivery worker.\n\n"
            "Suddenly, the butler rushed forward and bowed deeply. The entire hall went dead silent. "
            "Every single guest realized their terrible mistake."
        )

    def generate_json(self, prompt, system_instruction=None, temperature=0.3, max_retries=3, timeout=60):
        self.api_calls += 1
        return {"status": "PASS", "issues": []}


class TestSinglePassTTS(unittest.TestCase):
    """Test cases for single-pass TTS output, pure-Python token optimizations, Hybrid Workflow, and Vietnamese UI."""

    def test_parse_unified_ai_output(self):
        """Test parsing ---TITLE--- and ---TTS_SCRIPT--- sections."""
        sample = (
            "---TITLE--- : The Billionaire Disguised As A Janitor\n"
            "---TTS_SCRIPT--- :\n"
            "Sentence one is here. Sentence two follows closely. Sentence three ends the first paragraph. "
            "Sentence four starts the second paragraph. Sentence five finishes the thought."
        )
        title, script = parse_unified_ai_output(sample)
        self.assertEqual(title, "The Billionaire Disguised As A Janitor")
        self.assertNotIn("---TITLE---", script)
        self.assertNotIn("---TTS_SCRIPT---", script)
        paragraphs = [p for p in script.split("\n\n") if p.strip()]
        self.assertEqual(len(paragraphs), 2)

    def test_strip_srt_artifacts_and_rolling_dedup(self):
        """Test pure-Python stripping of SRT numbers, timecodes, and rolling duplicate captions."""
        rolling_lines = [
            "<i>John walked into</i>",
            "<i>John walked into the house.</i>",
            "<i>John walked into the house.</i>",
            "[Music] He saw the broken window.",
        ]
        compressed = compress_story_for_ai(rolling_lines)
        self.assertEqual(compressed, "John walked into the house. He saw the broken window.")

        raw_with_timecode = "1\n00:00:01,000 --> 00:00:04,000\nHello world.\n"
        self.assertEqual(strip_srt_artifacts(raw_with_timecode), "Hello world.")

    def test_python_prechecker_flags_issues_zero_tokens(self):
        """Verify pure-Python Pre-Checker detects repetitive words, proper noun variants, AI clichés, and long sentences."""
        checker = PythonPreChecker()
        raw_text = (
            "Marcus entered the grand ballroom quietly. Everyone stared at his old jacket. "
            "Marcus said nothing to the crowd.\n\n"
            "Suddenly Marucs walked toward the stage and suddenly he grabbed the microphone "
            "and suddenly the music stopped while every single rich guest in the massive "
            "chandelier-lit hall wondered why this poor janitor was standing next to the CEO "
            "without anyone stopping him at all"
        )
        report = checker.analyze_and_prepare(raw_text)
        self.assertEqual(report.total_paragraphs, 2)
        # Paragraph 0 is clean, Paragraph 1 has proper noun variant (Marucs vs Marcus), repetition (suddenly), long sentence, and missing period
        self.assertNotIn(0, report.flagged_indices)
        self.assertIn(1, report.flagged_indices)
        self.assertIn("Marcus", report.proper_noun_variants)
        self.assertIn("Marucs", report.proper_noun_variants["Marcus"])
        summary_vi = report.to_vietnamese_summary()
        self.assertIn("BÁO CÁO SƠ TUYỂN PYTHON THUẦN (0 TOKEN)", summary_vi)
        self.assertIn("Đoạn #2", summary_vi)

        # Verify AI cliché detection ("Dấu vết AI")
        ai_text = "Little did he know, a tapestry of emotions and palpable silence filled the room."
        ai_report = checker.analyze_and_prepare(ai_text)
        self.assertIn(0, ai_report.flagged_indices)
        self.assertIn("Dấu vết AI", ai_report.to_vietnamese_summary())

    def test_hybrid_workflow_targeted_ai_and_python_only(self):
        """Verify Hybrid mode only sends flagged paragraphs to AI and Python-only mode uses 0 API calls."""
        dummy_client = DummyGeminiClient()
        ai_service = AIService(
            dummy_client,
            use_ai_analysis=False,
            use_ai_qc=False,
            workflow_mode="hybrid",
        )
        raw_story = (
            "Marcus entered the grand ballroom quietly. Everyone stared at his old jacket. "
            "Marcus said nothing to the crowd.\n\n"
            "Suddenly Marucs walked toward the stage and suddenly he grabbed the microphone "
            "and suddenly the music stopped while every single rich guest in the massive "
            "chandelier-lit hall wondered why this poor janitor was standing next to the CEO "
            "without anyone stopping him at all"
        )
        ai_service.analyze_story(raw_story)
        script = ai_service.rewrite_story(raw_story)
        title = ai_service.generate_title(script)

        self.assertEqual(dummy_client.api_calls, 1)
        # Only [P#1] should be sent in the targeted prompt
        self.assertIn("[P#1]", dummy_client.last_prompt)
        self.assertNotIn("[P#0]", dummy_client.last_prompt)
        self.assertEqual(title, "She Thought He Was Poor Until The Helicopter Landed")
        # Paragraph 0 kept intact + Paragraph 1 replaced with AI polished version
        self.assertIn("Marcus entered the grand ballroom quietly.", script)
        self.assertIn("Marcus stepped forward calmly as the entire hall fell dead silent.", script)

        # Now test python_only mode (0 API calls)
        dummy_client.api_calls = 0
        ai_service.reset_state()
        ai_service.workflow_mode = "python_only"
        ai_service.analyze_story(raw_story)
        script_py = ai_service.rewrite_story(raw_story)
        title_py = ai_service.generate_title(script_py)
        self.assertEqual(dummy_client.api_calls, 0, "Python-only mode must make 0 API calls!")
        self.assertTrue(len(title_py) > 0)
        self.assertTrue(len(script_py) > 0)

    def test_cross_story_uniqueness_guard_and_state_isolation(self):
        """Verify StoryUniquenessGuard recasts duplicate source stories/names and isolates state across stories."""
        dummy_client = DummyGeminiClient()
        ai_service = AIService(dummy_client, use_ai_analysis=False, use_ai_qc=False, workflow_mode="full_ai")

        story_1 = "Marcus entered the luxury dealership in stained overalls. Kevin mocked Marcus in front of everyone."
        story_2_dup = "Marcus entered the luxury dealership in stained overalls. Kevin mocked Marcus in front of everyone."
        story_3_distinct = "Elena opened the small bakery before dawn. David brought the fresh flour sacks inside."

        # Story 1
        ai_service.rewrite_story(story_1)
        prompt_1 = dummy_client.last_prompt
        self.assertIn("Marcus", prompt_1)

        # Story 2 (accidental duplicate source SRT in batch): must automatically recast character names & add CRITICAL UNIQUENESS MANDATE
        ai_service.rewrite_story(story_2_dup)
        prompt_2 = dummy_client.last_prompt
        self.assertIn("CRITICAL UNIQUENESS MANDATE", prompt_2)
        self.assertNotIn("Main characters (use these exact names consistently): Marcus", prompt_2)

        # Story 3 (completely different story called without manual reset_state): must NOT leak Story 1 or 2's text
        ai_service.rewrite_story(story_3_distinct)
        prompt_3 = dummy_client.last_prompt
        self.assertIn("Elena", prompt_3)
        self.assertNotIn("stained overalls", prompt_3)

    def test_single_api_call_per_story(self):
        """Verify that processing an entire story makes AT MOST 1 Gemini API call (or 0 if clean in Hybrid mode)."""
        dummy_client = DummyGeminiClient()
        ai_service = AIService(dummy_client, use_ai_analysis=False, use_ai_qc=False, workflow_mode="full_ai")
        processor = StoryProcessor(ai_service, export_srt=False)

        test_dir = "test_sp_input"
        out_dir = "test_sp_output"
        os.makedirs(test_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        srt_path = os.path.join(test_dir, "001.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(
                "1\n00:00:01,000 --> 00:00:04,000\n"
                "John walked into the house.\n\n"
                "2\n00:00:04,000 --> 00:00:08,000\n"
                "He immediately noticed something was wrong.\n"
            )

        try:
            result = processor.process_file(srt_path, out_dir)
            self.assertEqual(result.status, ProcessingState.COMPLETED)
            self.assertEqual(
                dummy_client.api_calls,
                1,
                f"Expected 1 API call per file in full_ai mode, but made {dummy_client.api_calls}",
            )
            self.assertEqual(result.title, "She Thought He Was Poor Until The Helicopter Landed")
            self.assertTrue(result.output_filename.endswith(".txt"))
            self.assertIn("---TITLE---", result.formatted_output)
            self.assertIn("---TTS_SCRIPT---", result.formatted_output)

            with open(result.output_path, "r", encoding="utf-8") as f:
                saved = f.read()
            self.assertIn("---TITLE---", saved)
            self.assertIn("---TTS_SCRIPT---", saved)
            self.assertNotIn("-->", saved)
        finally:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
            if os.path.exists(out_dir):
                shutil.rmtree(out_dir)

    def test_vietnamese_ui_and_result_editor(self):
        """Verify Vietnamese UI initialization, pure-Python scan, Hybrid Pre-check report, and Result Editor save flow."""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from app.ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        window = MainWindow()

        # Verify Vietnamese tab titles
        tab_titles = [window.center_tabs.tabText(i) for i in range(window.center_tabs.count())]
        self.assertEqual(
            tab_titles,
            ["Hàng Đợi & Xử Lý", "Xem & Sửa Kết Quả", "Lịch Sử", "Cài Đặt"],
        )

        # Test pure-Python scan and Result Editor workflow
        in_dir = "test_ui_in"
        out_dir = "test_ui_out"
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        try:
            for name in ["010.srt", "001.srt", "002.srt"]:
                with open(os.path.join(in_dir, name), "w", encoding="utf-8") as f:
                    f.write("1\n00:00:01,000 --> 00:00:03,000\nHello world.\n")

            sample_out = os.path.join(out_dir, "001_Sample_Title.txt")
            with open(sample_out, "w", encoding="utf-8") as f:
                f.write(format_unified_output("Sample Title", "Line one. Line two."))

            window.input_path_edit.setText(in_dir)
            window.output_path_edit.setText(out_dir)
            window.chk_skip_processed.setChecked(False)
            window.scan_files()

            # Check natural order in queue
            self.assertEqual(window.batch_processor.files, ["001.srt", "002.srt", "010.srt"])

            # Check Result Editor loaded the output file and ran Python Pre-Check automatically
            self.assertEqual(window.edit_title_input.text(), "Sample Title")
            self.assertIn("BÁO CÁO SƠ TUYỂN PYTHON THUẦN (0 TOKEN)", window.precheck_report_box.toPlainText())

            window.edit_title_input.setText("Edited Title For TTS")
            window.edit_script_text.setPlainText("First edited sentence. Second edited sentence.")
            window.save_edited_result_to_disk()

            with open(sample_out, "r", encoding="utf-8") as f:
                updated_content = f.read()
            self.assertIn("Edited Title For TTS", updated_content)
            self.assertIn("First edited sentence. Second edited sentence.", updated_content)
        finally:
            if os.path.exists(in_dir):
                shutil.rmtree(in_dir)
            if os.path.exists(out_dir):
                shutil.rmtree(out_dir)

    def test_manual_story_tags_and_keys_detection(self):
        """Verify manual story tags & keys merge with Python auto-detection and guide AI rewrite prompt."""
        checker = PythonPreChecker()
        sample_text = (
            "The arrogant manager laughed at the old janitor's boots. "
            "Nobody knew the janitor owned the entire corporate building and the board of directors."
        )
        report = checker.analyze_and_prepare(
            sample_text,
            manual_tags="Secret Billionaire, Instant Karma",
            manual_keys="janitor owns the building, arrogant manager fired",
        )
        # Manual tags & keys must appear first in detected lists
        self.assertIn("Secret Billionaire", report.detected_genre_tags)
        self.assertIn("Instant Karma", report.detected_genre_tags)
        self.assertIn("janitor owns the building", report.detected_hook_keys)
        summary_vi = report.to_vietnamese_summary()
        self.assertIn("Thể loại (Tag truyện): Secret Billionaire, Instant Karma", summary_vi)
        self.assertIn("Từ khóa trọng tâm (Key & Hook): janitor owns the building", summary_vi)

        # Verify AIService injects manual tags & keys into Gemini rewrite prompt
        dummy_client = DummyGeminiClient()
        ai_service = AIService(
            dummy_client,
            workflow_mode="full_ai",
            story_tags="Secret Billionaire, Instant Karma",
            story_keys="janitor owns the building, arrogant manager fired",
        )
        ai_service.run_precheck(sample_text)
        ai_service.rewrite_story(sample_text)
        self.assertIn(
            "Story Genre / Tags (lock onto this exact tone, emotional pacing, and payoff): Secret Billionaire, Instant Karma",
            dummy_client.last_prompt,
        )
        self.assertIn(
            "Core Hook Keywords (build the opening hook, dramatic tension, and YouTube CTR title around these elements): janitor owns the building",
            dummy_client.last_prompt,
        )


if __name__ == "__main__":
    unittest.main()


