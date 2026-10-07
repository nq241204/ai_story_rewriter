"""AI prompts for AI Story Rewriter (Hybrid Workflow & Single-Pass TTS Output)."""


class Prompts:
    """Collection of compact, token-efficient prompts for Gemini API interactions."""

    # System instruction for unified story rewriting + CTR title + TTS script output
    REWRITE_SYSTEM = """You are an expert English-language dramatic storyteller and narrative editor.
The source material is already in English. Rewrite it—do not translate or summarize.
Preserve the core story, major events, relationships, central conflict, major reveal, climax, and ending.
Improve storytelling so it feels natural, emotionally compelling, logically consistent, suspenseful, and human-written.
Strengthen character motivation, cause-and-effect, realistic dialogue, and pacing.
Do not reveal major twists earlier than appropriate. Avoid repetitive AI clichés and meta-commentary.

Xuất kết quả thành 2 phần rõ ràng:
---TITLE--- : Title giật tít CTR YouTube (1 dòng tiếng Anh tự nhiên, tạo tò mò mạnh, kịch tính, không spoil kết, không emoji/hashtag/ngoặc kép).
---TTS_SCRIPT--- : Toàn bộ lời thoại tiếng Anh liền mạch, bỏ hoàn toàn số thứ tự và timecode, chia đoạn văn ngắn (2-3 câu/đoạn) tối ưu cho công cụ Text-to-Speech đọc diễn cảm."""

    # Hybrid Targeted Polish System Prompt (Only fixes Python-flagged paragraphs + generates Title)
    HYBRID_SYSTEM = """You are an expert English dramatic narrative editor working in a Hybrid Python+LLM workflow.
A Python pre-checker has already cleaned the story and flagged ONLY specific paragraphs that have issues (word repetition, proper noun typos, overly long/choppy sentences, or flat pacing).
Your task:
1. Generate ONE high-CTR YouTube title under ---TITLE--- based on the story context.
2. Under ---TTS_SCRIPT---, rewrite ONLY the flagged paragraphs [P#index] to fix their flagged issues and elevate their emotional depth, natural rhythm, and TTS delivery (2-3 sentences per paragraph).
Keep the exact [P#index] tag at the start of each rewritten paragraph so Python can merge them back accurately."""

    # Hybrid Targeted Polish User Prompt
    HYBRID_TARGETED_REWRITE = """STORY CONTEXT:
Characters: {characters}
Opening context: {opening_context}
Ending context: {ending_context}

FLAGGED PARAGRAPHS TO FIX & POLISH:
{flagged_blocks}

Output strictly in this format:
---TITLE---
<1 compelling English YouTube CTR title>

---TTS_SCRIPT---
[P#<index>] <Rewritten paragraph in 2-3 natural, emotionally compelling sentences for TTS>"""

    # Unified single-pass rewrite + title prompt (with optional Python pre-check notes)
    REWRITE_STORY = """Rewrite the following story to make it engaging, natural, emotional, logical, and human-sounding while preserving the core plot and major events.
{precheck_notes}
Format output strictly in 2 parts:
---TITLE---
<1 compelling English YouTube-style CTR title>

---TTS_SCRIPT---
<Full rewritten English story in continuous prose, completely removing all subtitle numbers and timecodes, split into short paragraphs of 2-3 sentences per paragraph optimized for Text-to-Speech>

STORY:
{story}"""

    # Intensity hints (compact to save input tokens)
    INTENSITY_HINTS = {
        "light": "Polish grammar, flow, and emotional delivery lightly while keeping close to original phrasing.",
        "balanced": "Enhance dramatic tension, dialogue naturalness, and emotional pacing while keeping all plot points intact.",
        "deep": "Deeply elevate narrative hooks, sensory details, emotional stakes, and dramatic dialogue while preserving the exact core plot."
    }

    # Optional standalone analysis prompt
    ANALYZE_STORY = """Briefly list main characters, relationships, core conflict, climax, and resolution for continuity:

STORY:
{story}"""

    # Optional AI quality control prompt
    QC_CHECK = """Review the rewritten story against the original. Check plot preservation, character/pronoun consistency, and natural English.

ORIGINAL:
{original_story}

REWRITTEN:
{rewritten_story}

Return JSON:
{{
  "status": "PASS" or "FAIL",
  "issues": ["specific issues if FAIL, else empty"]
}}"""

    # QC correction prompt
    QC_CORRECTION = """Fix these issues in the rewritten story while preserving core plot:
ISSUES:
{issues}

STORY:
{rewritten_story}

Output strictly with ---TITLE--- and ---TTS_SCRIPT--- (2-3 sentences per paragraph, no timecodes)."""

    # Standalone title generation prompt (used when 0 paragraphs are flagged in Hybrid mode!)
    GENERATE_TITLE = """Generate ONE compelling English YouTube CTR title (hook-first, curiosity gap, emotional tension, no spoilers, no emojis/hashtags/quotes):

STORY:
{story}

Return ONLY the title."""
