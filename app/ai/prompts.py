"""AI prompts for AI Story Rewriter."""

class Prompts:
    """Collection of prompts for Gemini API interactions."""
    
    # System instruction for story rewriting
    REWRITE_SYSTEM = """You are an expert English-language dramatic storyteller and narrative editor.

The source material is already written in English.

Your task is to rewrite it, not translate it.

Preserve the core story, major events, relationships, central conflict, major reveal, climax, and ending.

Improve the storytelling so it feels natural, emotionally compelling, logically consistent, suspenseful, and written by a skilled human.

Strengthen character motivation and cause-and-effect relationships.

Improve dialogue so characters sound like real people.

Improve pacing and scene transitions.

Build curiosity naturally and maintain listener engagement.

Do not summarize the story.

Do not produce commentary about your changes.

Do not explain your writing process.

Do not create a completely different story.

Do not reveal major twists earlier than appropriate.

Do not use repetitive AI-style phrases.

Return only the rewritten story."""
    
    # Rewrite prompt
    REWRITE_STORY = """Rewrite the following story to make it more engaging, natural, emotional, logical, and human-sounding while preserving the core plot and major events.

STORY:
{story}

Rewritten story:"""
    
    # Analysis prompt
    ANALYZE_STORY = """Analyze the following story and provide a structured analysis covering:
- Main characters
- Secondary characters
- Character relationships
- Setting
- Timeline
- Main conflict
- Character motivations
- Important events
- Cause-and-effect relationships
- Emotional stakes
- Suspense points
- Major reveal
- Climax
- Resolution
- Continuity constraints

STORY:
{story}

Analysis:"""
    
    # Quality control prompt
    QC_CHECK = """You are a quality control editor. Review the rewritten story against the original story and analysis.

Check for:
1. Core plot preserved
2. Major events preserved
3. Character identities consistent
4. Relationships consistent
5. Pronouns consistent
6. Timeline consistent
7. Locations consistent
8. Cause and effect logical
9. Motivations believable
10. Climax preserved
11. Ending preserved
12. No accidental contradictions
13. No major unexplained events
14. No excessive repetition
15. Natural English
16. Strong pacing
17. Good emotional progression

ORIGINAL STORY:
{original_story}

REWRITTEN STORY:
{rewritten_story}

Return a JSON response with this exact format:
{{
  "status": "PASS" or "FAIL",
  "issues": ["list of specific issues if status is FAIL, empty list if PASS"]
}}"""
    
    # QC correction prompt
    QC_CORRECTION = """The following rewritten story failed quality control with these issues:

ISSUES:
{issues}

REWRITTEN STORY:
{rewritten_story}

Fix the issues while preserving the story's core elements. Return only the corrected story."""
    
    # Title generation prompt
    GENERATE_TITLE = """Generate exactly ONE compelling YouTube-style title for the following story.

The title must be:
- Hook-first
- Use the strongest curiosity trigger from the story
- Include shocking/emotional event
- Include character or high-stakes situation
- Create a curiosity gap
- Natural English
- Strong curiosity
- Emotional tension
- Accurate to the story
- No dishonest clickbait
- Do not reveal the ending
- Do not reveal the entire twist
- No generic titles
- No excessive capitalization
- No emojis
- No hashtags
- No quotation marks unless genuinely necessary

STORY:
{story}

Return ONLY the title, nothing else."""
