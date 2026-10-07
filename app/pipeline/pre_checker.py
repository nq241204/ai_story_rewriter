"""Pure-Python Pre-Checker for the Hybrid Workflow (0 Tokens, processes millions of words in seconds)."""

import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Dict, Set, Tuple
from app.utils.text_utils import (
    strip_srt_artifacts,
    split_into_sentences,
    format_tts_paragraphs,
)

# Common English stopwords excluded from repetitive-word detection
STOP_WORDS: Set[str] = {
    "the", "and", "to", "of", "in", "is", "it", "that", "was", "for", "on", "are",
    "with", "as", "be", "at", "one", "have", "this", "from", "or", "had", "by",
    "not", "word", "but", "what", "some", "we", "can", "out", "other", "were",
    "all", "there", "when", "up", "use", "your", "how", "said", "an", "each",
    "she", "which", "do", "their", "time", "if", "will", "way", "about", "many",
    "then", "them", "would", "write", "like", "so", "these", "her", "long", "make",
    "thing", "see", "him", "two", "has", "look", "more", "day", "could", "go",
    "come", "did", "number", "sound", "no", "most", "people", "my", "over", "know",
    "water", "than", "call", "first", "who", "may", "down", "side", "been", "now",
    "find", "any", "new", "work", "part", "take", "get", "place", "made", "live",
    "where", "after", "back", "little", "only", "round", "man", "year", "came",
    "show", "every", "good", "me", "give", "our", "under", "name", "very", "through",
    "just", "form", "sentence", "great", "think", "say", "help", "low", "line",
    "differ", "turn", "cause", "much", "mean", "before", "move", "right", "boy",
    "old", "too", "same", "tell", "does", "set", "three", "want", "air", "well",
    "also", "play", "small", "end", "put", "home", "read", "hand", "port", "large",
    "spell", "add", "even", "land", "here", "must", "big", "high", "such", "follow",
    "act", "why", "ask", "men", "change", "went", "light", "kind", "off", "need",
    "house", "picture", "try", "us", "again", "animal", "point", "mother", "world",
    "near", "build", "self", "earth", "father", "head", "stand", "own", "page",
    "should", "country", "found", "answer", "school", "grow", "study", "still",
    "learn", "plant", "cover", "food", "sun", "four", "between", "state", "keep",
    "eye", "never", "last", "let", "thought", "city", "tree", "cross", "farm",
    "hard", "start", "might", "story", "saw", "far", "sea", "draw", "left", "late",
    "run", "don't", "while", "press", "close", "night", "real", "life", "few",
    "north", "open", "seem", "together", "next", "white", "children", "begin",
    "got", "walk", "example", "ease", "paper", "group", "always", "music", "those",
    "both", "mark", "often", "letter", "until", "mile", "river", "car", "feet",
    "care", "second", "book", "carry", "took", "science", "eat", "room", "friend",
    "began", "idea", "fish", "mountain", "stop", "once", "base", "hear", "horse",
    "cut", "sure", "watch", "color", "face", "wood", "main", "enough", "plain",
    "girl", "usual", "young", "ready", "above", "ever", "red", "list", "though",
    "feel", "talk", "bird", "soon", "body", "dog", "family", "direct", "pose",
    "leave", "song", "measure", "door", "product", "black", "short", "numeral",
    "class", "wind", "question", "happen", "complete", "ship", "area", "half",
    "rock", "order", "fire", "south", "problem", "piece", "told", "knew", "pass",
    "since", "top", "whole", "king", "space", "heard", "best", "hour", "better",
    "true", "during", "hundred", "five", "remember", "step", "early", "hold",
    "west", "ground", "interest", "reach", "fast", "verb", "sing", "listen", "six",
    "table", "travel", "less", "morning", "ten", "simple", "several", "vowel",
    "toward", "war", "lay", "against", "pattern", "slow", "center", "love",
    "person", "money", "serve", "appear", "road", "map", "rain", "rule", "govern",
    "pull", "cold", "notice", "voice", "unit", "power", "town", "fine", "certain",
    "fly", "fall", "lead", "cry", "dark", "machine", "note", "wait", "plan",
    "figure", "star", "box", "noun", "field", "rest", "correct", "able", "pound",
    "done", "beauty", "drive", "stood", "contain", "front", "teach", "week",
    "final", "gave", "green", "oh", "quick", "develop", "ocean", "warm", "free",
    "minute", "strong", "special", "mind", "behind", "clear", "tail", "produce",
    "fact", "street", "inch", "multiply", "nothing", "course", "stay", "wheel",
    "full", "force", "blue", "object", "decide", "surface", "deep", "moon",
    "island", "foot", "system", "busy", "test", "record", "boat", "common", "gold",
    "possible", "plane", "stead", "dry", "wonder", "laugh", "thousand", "ago",
    "ran", "check", "game", "shape", "equate", "hot", "miss", "brought", "heat",
    "snow", "tire", "bring", "yes", "distant", "fill", "east", "paint", "language",
    "among", "he", "his", "they", "you", "i", "into", "into", "didn't", "wasn't",
    "couldn't", "wouldn't", "it's", "that's", "don't", "im", "ive", "youre"
}

NON_NAME_CAPITALIZED: Set[str] = {
    "The", "And", "But", "For", "Nor", "Or", "Yet", "So", "In", "On", "At", "To",
    "From", "By", "With", "About", "Against", "Between", "Into", "Through",
    "During", "Before", "After", "Above", "Below", "He", "She", "They", "We",
    "You", "It", "His", "Her", "Their", "My", "Your", "Our", "This", "That",
    "These", "Those", "What", "When", "Where", "Why", "How", "Who", "Which",
    "Yes", "No", "Not", "One", "Two", "Three", "Then", "There", "Here", "Now",
    "Just", "Mr", "Mrs", "Ms", "Dr", "St", "God", "Okay", "Well", "Oh", "Monday",
    "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January",
    "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "Today", "Tomorrow", "Yesterday", "Suddenly",
    "Finally", "However", "Meanwhile", "Instead", "Because", "Although", "Though",
    "Everyone", "Everybody", "Nobody", "Somebody", "Someone", "Anyone", "Anybody",
    "Everything", "Nothing", "Anything", "Something", "Somewhere", "Nowhere"
}


@dataclass
class ParagraphIssue:
    """Represents pure-Python pre-check flags on a single paragraph."""
    index: int  # 0-based paragraph index
    text: str
    flags: List[str] = field(default_factory=list)
    repetitive_words: List[str] = field(default_factory=list)
    proper_noun_warnings: List[str] = field(default_factory=list)
    length_warnings: List[str] = field(default_factory=list)
    format_warnings: List[str] = field(default_factory=list)

    @property
    def is_flagged(self) -> bool:
        return len(self.flags) > 0


@dataclass
class PreCheckReport:
    """Comprehensive pure-Python pre-check report (0 AI tokens used)."""
    paragraphs: List[str]
    paragraph_issues: List[ParagraphIssue]
    detected_characters: List[str]
    proper_noun_variants: Dict[str, List[str]]
    total_words: int
    total_sentences: int
    flagged_indices: List[int]
    clean_indices: List[int]

    @property
    def total_paragraphs(self) -> int:
        return len(self.paragraphs)

    @property
    def flagged_ratio(self) -> float:
        if not self.paragraphs:
            return 0.0
        return len(self.flagged_indices) / len(self.paragraphs)

    @property
    def token_savings_estimate_pct(self) -> int:
        """Estimated % of tokens saved by only sending flagged paragraphs to LLM."""
        if not self.paragraphs:
            return 100
        clean_ratio = len(self.clean_indices) / len(self.paragraphs)
        # Base savings from stripping timecodes (~40%) + unflagged paragraph savings
        return min(95, max(40, int(40 + clean_ratio * 55)))

    def to_vietnamese_summary(self) -> str:
        """Generate a human-readable Vietnamese Pre-Check Report for the UI."""
        lines = [
            "=== BÁO CÁO SƠ TUYỂN PYTHON THUẦN (0 TOKEN) ===",
            f"• Tổng số từ: {self.total_words} từ | Tổng số câu: {self.total_sentences} câu | Số đoạn TTS: {len(self.paragraphs)} đoạn",
            f"• Đoạn đạt chuẩn (Giữ nguyên - 0 tốn token): {len(self.clean_indices)}/{len(self.paragraphs)} đoạn",
            f"• Đoạn gắn cờ cần trau chuốt: {len(self.flagged_indices)}/{len(self.paragraphs)} đoạn (Ước tính tiết kiệm ~{self.token_savings_estimate_pct}% token)",
            f"• Tên riêng / Nhân vật phát hiện: {', '.join(self.detected_characters) if self.detected_characters else 'Không phát hiện tên riêng rõ ràng'}",
        ]

        if self.proper_noun_variants:
            variant_strs = [
                f"{canon} (nghi ngờ biến thể/sai chính tả: {', '.join(vars_)})"
                for canon, vars_ in self.proper_noun_variants.items()
            ]
            lines.append(f"• [CẢNH BÁO TÊN RIÊNG]: {'; '.join(variant_strs)}")

        if not self.flagged_indices:
            lines.append("\n✅ Tất cả các đoạn văn đều mượt mà, đúng chuẩn 2-3 câu/đoạn cho TTS, không có lỗi lặp từ hay định dạng!")
        else:
            lines.append("\n--- CHI TIẾT CÁC ĐOẠN BỊ GẮN CỜ CẢNH BÁO ---")
            for idx in self.flagged_indices:
                p_issue = self.paragraph_issues[idx]
                reasons = " | ".join(p_issue.flags)
                preview = p_issue.text[:90] + ("..." if len(p_issue.text) > 90 else "")
                lines.append(f"[Đoạn #{idx + 1}] ⚠️ {reasons}\n   ↳ \"{preview}\"")

        return "\n".join(lines)


class PythonPreChecker:
    """
    Pure-Python Pre-Check Engine for the Hybrid Workflow.
    Processes story text in milliseconds with 0 AI tokens:
    1. Cleans formatting & splits into 2-3 sentence TTS paragraphs.
    2. Detects repetitive words/sentence starters.
    3. Detects proper nouns (character names) and fuzzy spelling inconsistencies.
    4. Detects overly long sentences (>35 words) or choppy caption fragments.
    5. Detects formatting anomalies (ALL CAPS, missing punctuation, broken symbols).
    """

    def __init__(
        self,
        max_sentence_words: int = 35,
        min_paragraph_words: int = 8,
        repetition_threshold: int = 3,
    ):
        self.max_sentence_words = max_sentence_words
        self.min_paragraph_words = min_paragraph_words
        self.repetition_threshold = repetition_threshold

    def analyze_and_prepare(self, raw_text: str) -> PreCheckReport:
        """
        Run full pure-Python pre-check on raw SRT/story text.
        """
        # 1. Strip SRT artifacts and format into initial 2-3 sentence TTS paragraphs
        clean_text = format_tts_paragraphs(raw_text, sentences_per_paragraph=3)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', clean_text) if p.strip()]

        all_words = clean_text.split()
        all_sentences = split_into_sentences(clean_text)

        # 2. Extract character names & check for inconsistent proper noun spelling
        detected_chars, noun_variants, suspect_to_canonical = self._detect_proper_nouns_and_typos(clean_text)

        # 3. Inspect each paragraph for the 4 categories of issues
        paragraph_issues: List[ParagraphIssue] = []
        flagged_indices: List[int] = []
        clean_indices: List[int] = []

        for idx, para in enumerate(paragraphs):
            issue = self._check_paragraph(idx, para, suspect_to_canonical, detected_chars)
            paragraph_issues.append(issue)
            if issue.is_flagged:
                flagged_indices.append(idx)
            else:
                clean_indices.append(idx)

        return PreCheckReport(
            paragraphs=paragraphs,
            paragraph_issues=paragraph_issues,
            detected_characters=detected_chars,
            proper_noun_variants=noun_variants,
            total_words=len(all_words),
            total_sentences=len(all_sentences),
            flagged_indices=flagged_indices,
            clean_indices=clean_indices,
        )

    def _detect_proper_nouns_and_typos(
        self, text: str
    ) -> Tuple[List[str], Dict[str, List[str]], Dict[str, str]]:
        """
        Find capitalized proper nouns and detect fuzzy spelling variants
        (e.g., 'Marcus' vs 'Marucs', 'Arthur' vs 'Artur', 'Julian' vs 'Jullian').
        """
        cap_words = re.findall(r'\b([A-Z][a-z]{2,15})\b', text)
        counts = Counter(
            w for w in cap_words
            if w not in NON_NAME_CAPITALIZED and w.lower() not in STOP_WORDS
        )

        if not counts:
            return [], {}, {}

        # Sort by frequency descending
        sorted_nouns = [name for name, _ in counts.most_common(15)]
        canonical_names: List[str] = []
        variants_map: Dict[str, List[str]] = {}
        suspect_to_canonical: Dict[str, str] = {}

        for candidate in sorted_nouns:
            matched_canon = None
            for canon in canonical_names:
                ratio = SequenceMatcher(None, candidate.lower(), canon.lower()).ratio()
                if 0.75 <= ratio < 1.0:
                    matched_canon = canon
                    break

            if matched_canon:
                variants_map.setdefault(matched_canon, []).append(candidate)
                suspect_to_canonical[candidate] = matched_canon
            else:
                if counts[candidate] >= 1 and len(canonical_names) < 8:
                    canonical_names.append(candidate)

        # Also check if any canonical name appears lowercase by mistake in the text
        all_lower_tokens = set(re.findall(r'\b[a-z]{3,15}\b', text))
        for canon in canonical_names:
            if counts[canon] >= 2 and canon.lower() in all_lower_tokens:
                if canon.lower() not in STOP_WORDS:
                    variants_map.setdefault(canon, []).append(canon.lower())
                    suspect_to_canonical[canon.lower()] = canon

        return canonical_names, variants_map, suspect_to_canonical

    def _check_paragraph(
        self,
        index: int,
        para: str,
        suspect_to_canonical: Dict[str, str],
        detected_chars: List[str],
    ) -> ParagraphIssue:
        """Check a single paragraph for repetition, proper noun typos, length, and formatting."""
        issue = ParagraphIssue(index=index, text=para)
        words_raw = re.findall(r"\b[A-Za-z']+\b", para)
        words_lower = [w.lower() for w in words_raw]
        sentences = split_into_sentences(para)

        # 1. Check Repetitive Words & Repetitive Sentence Starters
        content_words = [
            w for w in words_lower
            if len(w) >= 4 and w not in STOP_WORDS
        ]
        word_counts = Counter(content_words)
        repeated = [w for w, c in word_counts.items() if c >= self.repetition_threshold]

        # Check consecutive sentences starting with the exact same word
        if len(sentences) >= 3:
            starters = []
            for s in sentences:
                first_match = re.match(r'^["\']?([A-Za-z]+)', s.strip())
                if first_match:
                    starters.append(first_match.group(1).lower())
            starter_counts = Counter(starters)
            for st, cnt in starter_counts.items():
                if cnt >= 3 and st not in repeated:
                    repeated.append(f"mở đầu câu lặp '{st}' ({cnt} lần)")

        if repeated:
            issue.repetitive_words = repeated
            issue.flags.append(f"Từ lặp: {', '.join(repeated[:3])}")

        # 2. Check Proper Noun Typos / Inconsistencies
        for token in words_raw:
            if token in suspect_to_canonical:
                canon = suspect_to_canonical[token]
                warn = f"'{token}' -> '{canon}'"
                if warn not in issue.proper_noun_warnings:
                    issue.proper_noun_warnings.append(warn)

        if issue.proper_noun_warnings:
            issue.flags.append(f"Lỗi tên riêng: {', '.join(issue.proper_noun_warnings)}")

        # 3. Check Sentence & Paragraph Length / Pacing
        for s in sentences:
            s_words = s.split()
            if len(s_words) > self.max_sentence_words:
                issue.length_warnings.append(f"Câu quá dài ({len(s_words)} từ > {self.max_sentence_words} từ)")
                break

        if len(words_raw) < self.min_paragraph_words and len(sentences) <= 1:
            issue.length_warnings.append(f"Đoạn quá cụt/rời rạc ({len(words_raw)} từ)")

        if issue.length_warnings:
            issue.flags.append(", ".join(issue.length_warnings))

        # 4. Check Formatting & Caption Artifacts
        if not re.search(r'[.!?]["\']?$', para.strip()):
            issue.format_warnings.append("Thiếu dấu kết câu")

        # Check ALL CAPS words (more than 2 all-caps words of length >= 4)
        all_caps = [w for w in words_raw if len(w) >= 4 and w.isupper()]
        if len(all_caps) >= 2:
            issue.format_warnings.append(f"Chữ IN HOA toàn bộ ({', '.join(all_caps[:2])})")

        if ".." in para and "..." not in para:
            issue.format_warnings.append("Dấu chấm câu lỗi (..)")

        if issue.format_warnings:
            issue.flags.append(f"Định dạng: {', '.join(issue.format_warnings)}")

        return issue
