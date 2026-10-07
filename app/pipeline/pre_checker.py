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

# Patterns that betray AI-generated writing ("dấu vết AI viết")
AI_TRACE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'\b(delve|delved|delving)\b', re.IGNORECASE), "delve"),
    (re.compile(r'\b(tapestry|kaleidoscope|symphony)\b', re.IGNORECASE), "tapestry/symphony"),
    (re.compile(r'\b(palpable|unbeknownst)\b', re.IGNORECASE), "palpable/unbeknownst"),
    (re.compile(r'\btestament to\b', re.IGNORECASE), "testament to"),
    (re.compile(r'\bbeacon of\b', re.IGNORECASE), "beacon of"),
    (re.compile(r'\bwhirlwind of\b', re.IGNORECASE), "whirlwind of"),
    (re.compile(r'\bshivers? down\b', re.IGNORECASE), "shiver down spine"),
    (re.compile(r'\bbreath (?:he|she|they|I) didn\'t know\b', re.IGNORECASE), "breath didn't know holding"),
    (re.compile(r'\blittle did (?:he|she|they|anyone) know\b', re.IGNORECASE), "little did they know"),
    (re.compile(r'\bin the realm of\b', re.IGNORECASE), "in the realm of"),
]


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
    ai_cliche_warnings: List[str] = field(default_factory=list)

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
    uniqueness_score_pct: int = 100
    uniqueness_note: str = "Truyện độc bản 100% (Hoàn toàn riêng biệt)"

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
            f"• Độ độc bản (Chống trùng lặp): {self.uniqueness_score_pct}% — {self.uniqueness_note}",
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
            lines.append("\n✅ Tất cả các đoạn văn đều mượt mà, đúng chuẩn 2-3 câu/đoạn cho TTS, không có dấu vết AI, không lặp từ hay lỗi định dạng!")
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
    5. Detects AI writing clichés ("dấu vết AI") & formatting anomalies.
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

        # 3. Inspect each paragraph for the 5 categories of issues
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

    def normalize_proper_nouns_in_text(self, text: str, report: PreCheckReport) -> str:
        """
        Automatically fix detected proper noun spelling variants in pure Python (0 tokens)
        before sending the plot skeleton to Gemini or exporting in Python-only mode.
        """
        if not report.proper_noun_variants:
            return text
        fixed = text
        for canon, variants in report.proper_noun_variants.items():
            for var in variants:
                fixed = re.sub(rf'\b{re.escape(var)}\b', canon, fixed)
        return fixed

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
        """Check a single paragraph for repetition, proper noun typos, length, AI clichés, and formatting."""
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

        # 4. Check AI Writing Traces ("Dấu vết AI")
        for pattern, label in AI_TRACE_PATTERNS:
            if pattern.search(para):
                issue.ai_cliche_warnings.append(label)
        if issue.ai_cliche_warnings:
            issue.flags.append(f"Dấu vết AI: {', '.join(issue.ai_cliche_warnings)}")

        # 5. Check Formatting & Caption Artifacts
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


@dataclass
class StoryFingerprint:
    """Stores 3-gram shingle fingerprints and metadata of a processed story."""
    title: str
    source_shingles: Set[str]
    output_shingles: Set[str]
    characters: List[str]
    opening_sentence: str


class StoryUniquenessGuard:
    """
    Pure-Python Cross-Story Anti-Duplication & Uniqueness Engine (0 AI Tokens).
    Guarantees every rewritten story is a 100% distinct, standalone story:
    1. Detects if two input SRT files have overlapping/duplicate source text and automatically
       recasts character names, setting, and narrative perspective in Python before calling AI.
    2. Rotates narrative opening hooks & storytelling styles across batch files.
    3. Tracks used titles, character names, and 3-gram content fingerprints so AI never
       repeats titles, character names, or phrasing across stories.
    4. Verifies post-rewrite uniqueness score (%) and triggers a re-spin if similarity is too high.
    """

    FRESH_MALE_NAMES: List[str] = [
        "Arthur", "Caleb", "Nathan", "Victor", "Julian", "Grant", "Miles", "Owen",
        "Warren", "Desmond", "Collin", "Graham", "Trevor", "Preston", "Harrison", "Malcolm",
        "evan", "logan", "carter", "bennett", "spencer", "mitchell", "garrett", "reid"
    ]

    FRESH_FEMALE_NAMES: List[str] = [
        "Evelyn", "Clara", "Hannah", "Rachel", "Diane", "Tessa", "Nora", "Lydia",
        "Sylvia", "Elena", "Valerie", "Miriam", "Audrey", "Celeste", "Naomi", "Vera",
        "claire", "vivian", "elise", "fiona", "camille", "lauren", "helena", "cora"
    ]

    KNOWN_FEMALE_NAMES: Set[str] = {
        "victoria", "sarah", "emily", "jessica", "rachel", "clara", "hannah", "evelyn",
        "lydia", "nora", "tessa", "diane", "elena", "chloe", "grace", "lily", "anna",
        "maria", "lisa", "karen", "susan", "linda", "elizabeth", "emma", "olivia",
        "sophia", "isabella", "mia", "charlotte", "amelia", "harper", "abigail", "ella",
        "madison", "scarlett", "aria", "grace", "zok", "alice", "rose", "martha", "helen",
        "samantha", "ashley", "amanda", "melissa", "nicole", "stephanie", "rebecca",
        "laura", "sharon", "cynthia", "kathleen", "amy", "angela", "brenda", "pamela",
        "natalie", "julia", "amber", "megan", "andrea", "danielle", "brittany", "vanessa"
    }

    NARRATIVE_HOOK_STYLES: List[str] = [
        "Open immediately with a tense, grounded physical action in the middle of the scene (In-Media-Res Action Hook).",
        "Open with a sharp, revealing spoken line or confrontation that immediately establishes the conflict (Dialogue/Confrontation Hook).",
        "Open by contrasting a quiet, ordinary detail of the setting with the sudden arrival of the main conflict (Contrast & Atmosphere Hook).",
        "Open from the protagonist's calm, observant perspective right as everyone else in the room misjudges them (Observant Underdog Hook).",
        "Open with a decisive turning-point moment and build the immediate emotional stakes around why it matters (High-Stakes Moment Hook).",
        "Open with a vivid, realistic workplace or family detail that reveals the unspoken tension between the characters (Grounded Realism Hook).",
    ]

    def __init__(self):
        self.history: List[StoryFingerprint] = []
        self.used_titles: List[str] = []
        self.used_names: Set[str] = set()
        self.story_counter: int = 0

    def reset(self) -> None:
        """Clear all recorded story fingerprints."""
        self.history.clear()
        self.used_titles.clear()
        self.used_names.clear()
        self.story_counter = 0

    @staticmethod
    def extract_shingles(text: str, k: int = 3) -> Set[str]:
        """Extract normalized k-word shingles for fast Jaccard similarity comparison."""
        words = re.findall(r"[a-z]{2,}", (text or "").lower())
        if len(words) < k:
            return set(words)
        return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}

    @staticmethod
    def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """Compute Jaccard overlap between two shingle sets (0.0 to 1.0)."""
        if not set_a or not set_b:
            return 0.0
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union > 0 else 0.0

    def prepare_unique_source_and_directive(
        self,
        clean_source: str,
        detected_chars: List[str],
    ) -> Tuple[str, List[str], str, bool]:
        """
        Inspect incoming source story against all previously processed stories in the session.
        If the input SRT is a duplicate or near-duplicate of a previous input SRT,
        automatically recast character names in Python (0 tokens) and add a mandatory
        setting/perspective transformation directive so the new story is 100% distinct!

        Returns:
            (transformed_source_text, active_character_names, uniqueness_directive_str, was_source_duplicate)
        """
        src_shingles = self.extract_shingles(clean_source, k=3)
        max_src_sim = 0.0
        matched_prev: StoryFingerprint | None = None

        for rec in self.history:
            sim = self.jaccard_similarity(src_shingles, rec.source_shingles)
            if sim > max_src_sim:
                max_src_sim = sim
                matched_prev = rec

        hook_style = self.NARRATIVE_HOOK_STYLES[self.story_counter % len(self.NARRATIVE_HOOK_STYLES)]
        self.story_counter += 1

        active_chars = list(detected_chars)
        transformed_source = clean_source
        was_source_duplicate = max_src_sim >= 0.45

        directive_lines = [f"Narrative Opening Style: {hook_style}"]

        # If source SRT overlaps with a previous file OR shares already-used character names across stories
        need_name_recast = was_source_duplicate or (
            len(active_chars) > 0 and any(c in self.used_names for c in active_chars) and len(self.history) > 0
        )

        if need_name_recast and active_chars:
            avail_male = [
                n.capitalize() for n in self.FRESH_MALE_NAMES
                if n.capitalize() not in self.used_names and n.capitalize() not in active_chars
            ]
            avail_female = [
                n.capitalize() for n in self.FRESH_FEMALE_NAMES
                if n.capitalize() not in self.used_names and n.capitalize() not in active_chars
            ]
            name_map: Dict[str, str] = {}
            new_chars: List[str] = []
            for old_name in active_chars:
                is_female = old_name.lower() in self.KNOWN_FEMALE_NAMES or bool(
                    re.search(rf'\b{re.escape(old_name)}\b[^.!?]{{1,40}}\b(?:she|her|hers|woman|wife|mother|sister|daughter|girl)\b', clean_source, re.IGNORECASE)
                )
                pool = avail_female if is_female else avail_male
                if pool:
                    replacement = pool.pop(0)
                    name_map[old_name] = replacement
                    new_chars.append(replacement)
                else:
                    new_chars.append(old_name)

            for old_n, new_n in name_map.items():
                transformed_source = re.sub(rf'\b{re.escape(old_n)}\b', new_n, transformed_source)
            active_chars = new_chars

        if was_source_duplicate and matched_prev:
            directive_lines.append(
                "CRITICAL UNIQUENESS MANDATE: A previous story had a similar plot outline "
                f"(previous title: '{matched_prev.title}'). You MUST make this a 100% SEPARATE, STANDALONE STORY: "
                "change the specific setting/location, alter the characters' backgrounds and dialogue wording completely, "
                "use a totally different opening scene, and generate a completely different title!"
            )
        elif self.used_titles:
            recent_titles = "; ".join(self.used_titles[-4:])
            avoid_names = ", ".join(list(self.used_names)[-8:])
            directive_lines.append(
                f"Uniqueness Rule: Every story must be 100% distinct. Do NOT reuse phrasing or title patterns from recent titles ({recent_titles})."
            )
            if avoid_names and not active_chars:
                directive_lines.append(
                    f"If inventing character names, pick fresh names and do NOT use: {avoid_names}."
                )

        return transformed_source, active_chars, "\n".join(directive_lines), was_source_duplicate

    def verify_and_register(
        self,
        title: str,
        rewritten_script: str,
        source_text: str,
        characters: List[str],
    ) -> Tuple[bool, int, str]:
        """
        Verify that the newly rewritten story is distinct from all previously generated stories,
        then register its fingerprint in memory.

        Returns:
            (is_unique, uniqueness_score_pct, uniqueness_note_vi)
        """
        out_shingles = self.extract_shingles(rewritten_script, k=3)
        src_shingles = self.extract_shingles(source_text, k=3)
        sentences = split_into_sentences(rewritten_script)
        opening = sentences[0] if sentences else ""

        max_out_sim = 0.0
        max_title_sim = 0.0
        most_similar_title = ""

        for rec in self.history:
            out_sim = self.jaccard_similarity(out_shingles, rec.output_shingles)
            if out_sim > max_out_sim:
                max_out_sim = out_sim
                most_similar_title = rec.title

            if title and rec.title:
                t_sim = SequenceMatcher(None, title.lower(), rec.title.lower()).ratio()
                if t_sim > max_title_sim:
                    max_title_sim = t_sim

        uniqueness_score_pct = max(0, min(100, int(round((1.0 - max_out_sim) * 100))))
        is_unique = (max_out_sim < 0.35) and (max_title_sim < 0.78)

        # Register in history
        self.history.append(
            StoryFingerprint(
                title=title or "Story",
                source_shingles=src_shingles,
                output_shingles=out_shingles,
                characters=list(characters),
                opening_sentence=opening,
            )
        )
        if title:
            self.used_titles.append(title)
        for c in characters:
            self.used_names.add(c)

        if is_unique:
            note_vi = f"Truyện độc bản hoàn toàn riêng biệt (Khác biệt {uniqueness_score_pct}% so với {len(self.history) - 1} truyện trước)"
        else:
            note_vi = (
                f"Cảnh báo trùng lặp ({100 - uniqueness_score_pct}% giống '{most_similar_title[:35]}') — Cần biến đổi góc kể!"
            )

        return is_unique, uniqueness_score_pct, note_vi


