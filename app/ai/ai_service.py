"""AI service for AI Story Rewriter."""

from typing import Optional, Dict, Any
from app.ai.gemini_client import GeminiClient
from app.ai.prompts import Prompts
from app.utils.logger import get_logger


class AIService:
    """Service for AI-powered story processing."""
    
    def __init__(self, client: GeminiClient, api_timeout: int = 60, analysis_timeout: int = 30, qc_timeout: int = 30):
        """
        Initialize AI service.
        
        Args:
            client: GeminiClient instance
            api_timeout: Timeout for main API calls (seconds)
            analysis_timeout: Timeout for analysis (seconds)
            qc_timeout: Timeout for QC operations (seconds)
        """
        self.client = client
        self.prompts = Prompts()
        self.logger = get_logger()
        self.api_timeout = api_timeout
        self.analysis_timeout = analysis_timeout
        self.qc_timeout = qc_timeout
    
    def rewrite_story(self, original_story: str) -> Optional[str]:
        """
        Rewrite a story using AI.
        
        Args:
            original_story: The original story text
            
        Returns:
            Rewritten story or None if failed
        """
        self.logger.info("Starting story rewrite")
        
        prompt = self.prompts.REWRITE_STORY.format(story=original_story)
        
        rewritten = self.client.generate_content(
            prompt,
            system_instruction=self.prompts.REWRITE_SYSTEM,
            temperature=0.8,
            max_retries=3,
            timeout=self.api_timeout
        )
        
        if rewritten:
            self.logger.info("Story rewrite completed successfully")
        else:
            self.logger.error("Story rewrite failed")
        
        return rewritten
    
    def analyze_story(self, story: str) -> Optional[str]:
        """
        Analyze a story using AI.
        
        Args:
            story: The story text to analyze
            
        Returns:
            Analysis text or None if failed
        """
        self.logger.info("Starting story analysis")
        
        prompt = self.prompts.ANALYZE_STORY.format(story=story)
        
        analysis = self.client.generate_content(
            prompt,
            temperature=0.5,
            max_retries=2,
            timeout=self.analysis_timeout
        )
        
        if analysis:
            self.logger.info("Story analysis completed")
        else:
            self.logger.warning("Story analysis failed (non-critical)")
        
        return analysis
    
    def quality_check(
        self,
        original_story: str,
        rewritten_story: str
    ) -> Optional[Dict[str, Any]]:
        """
        Perform quality control on rewritten story.
        
        Args:
            original_story: The original story
            rewritten_story: The rewritten story
            
        Returns:
            QC result dict with 'status' and 'issues' keys, or None if failed
        """
        self.logger.info("Starting quality control")
        
        prompt = self.prompts.QC_CHECK.format(
            original_story=original_story,
            rewritten_story=rewritten_story
        )
        
        result = self.client.generate_json(
            prompt,
            temperature=0.3,
            max_retries=2,
            timeout=self.qc_timeout
        )
        
        if result:
            status = result.get("status", "FAIL")
            issues = result.get("issues", [])
            
            if status == "PASS":
                self.logger.info("Quality control passed")
            else:
                self.logger.warning(f"Quality control failed with {len(issues)} issues")
                for issue in issues:
                    self.logger.debug(f"  - {issue}")
        else:
            self.logger.error("Quality control failed (API error)")
            return None
        
        return result
    
    def correct_qc_issues(
        self,
        rewritten_story: str,
        issues: list
    ) -> Optional[str]:
        """
        Correct quality control issues.
        
        Args:
            rewritten_story: The rewritten story with issues
            issues: List of QC issues
            
        Returns:
            Corrected story or None if failed
        """
        self.logger.info(f"Correcting {len(issues)} QC issues")
        
        issues_text = "\n".join(f"- {issue}" for issue in issues)
        prompt = self.prompts.QC_CORRECTION.format(
            issues=issues_text,
            rewritten_story=rewritten_story
        )
        
        corrected = self.client.generate_content(
            prompt,
            system_instruction=self.prompts.REWRITE_SYSTEM,
            temperature=0.7,
            max_retries=2,
            timeout=self.qc_timeout
        )
        
        if corrected:
            self.logger.info("QC correction completed")
        else:
            self.logger.error("QC correction failed")
        
        return corrected
    
    def generate_title(self, story: str) -> Optional[str]:
        """
        Generate a CTR title for a story.
        
        Args:
            story: The story text
            
        Returns:
            Generated title or None if failed
        """
        self.logger.info("Generating title")
        
        prompt = self.prompts.GENERATE_TITLE.format(story=story)
        
        title = self.client.generate_content(
            prompt,
            temperature=0.9,  # Higher temperature for creativity
            max_retries=3,
            timeout=30
        )
        
        if title:
            # Clean up the title
            title = title.strip()
            # Remove quotes if present
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            self.logger.info(f"Title generated: {title[:50]}...")
        else:
            self.logger.error("Title generation failed")
        
        return title
