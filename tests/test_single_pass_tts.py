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


class DummyGeminiClient:
    """Fake GeminiClient that records the exact number of API calls made."""

    def __init__(self):
        self.api_calls = 0
        self.model_name = "gemini-2.5-flash"

    def generate_content(self, prompt, system_instruction=None, temperature=0.7, max_retries=3, timeout=60):
        self.api_calls += 1
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
    """Test cases for single-pass TTS output, pure-Python token optimizations, and Vietnamese UI."""

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

    def test_single_api_call_per_story(self):
        """Verify that processing an entire story makes ONLY 1 Gemini API call (saving 75%+ tokens)."""
        dummy_client = DummyGeminiClient()
        ai_service = AIService(dummy_client, use_ai_analysis=False, use_ai_qc=False)
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
                f"Expected exactly 1 API call per file, but made {dummy_client.api_calls}",
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
        """Verify Vietnamese UI initialization, pure-Python scan, and Result Editor save flow."""
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

            # Check Result Editor loaded the output file and can save edits
            self.assertEqual(window.edit_title_input.text(), "Sample Title")
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


if __name__ == "__main__":
    unittest.main()
