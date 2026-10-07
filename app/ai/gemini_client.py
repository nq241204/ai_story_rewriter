"""Gemini API client for AI Story Rewriter."""

import json
import random
import time
from typing import Optional, Dict, Any

from google import genai
from google.genai import types

from app.utils.logger import get_logger


class GeminiClient:
    """Client for Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.8-flash"
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.logger = get_logger()

        # Fallback models in order of preference
        self.fallback_models = [
            "gemini-3.8-flash",      # Primary
            "gemini-3.7-flash",      # Fallback 1
            "gemini-2.5-pro",        # Fallback 2
        ]

        # Remove duplicate models while preserving order
        self.fallback_models = list(dict.fromkeys(self.fallback_models))

        try:
            self.client = genai.Client(api_key=api_key)

            self.logger.info(
                f"Gemini client initialized with model: {self.model_name}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to initialize Gemini client: {e}"
            )
            raise

    # ============================================================
    # ERROR CLASSIFICATION
    # ============================================================

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine whether an API error should be retried.
        """

        error_text = str(error).upper()

        retryable_errors = [
            "503",
            "UNAVAILABLE",
            "429",
            "RESOURCE_EXHAUSTED",
            "500",
            "502",
            "504",
            "DEADLINE_EXCEEDED",
            "TIMEOUT",
            "INTERNAL",
        ]

        return any(
            error_code in error_text
            for error_code in retryable_errors
        )

    def _wait_before_retry(self, attempt: int) -> None:
        """
        Exponential backoff with jitter: 2s → 4s → 8s (tối ưu)
        """
        # Backoff sequence: 2s, 4s, 8s (ngắn hơn)
        backoff_times = [2, 4, 8]
        
        if attempt < len(backoff_times):
            base_wait = backoff_times[attempt]
        else:
            base_wait = 8  # Cap at 8s
        
        # Add random jitter (0-1s)
        jitter = random.uniform(0, 1)
        
        wait_time = base_wait + jitter
        
        self.logger.warning(
            f"Waiting {wait_time:.1f}s before retry..."
        )
        
        time.sleep(wait_time)

    # ============================================================
    # CONNECTION TEST
    # ============================================================

    def test_connection(self) -> bool:
        """
        Test the API connection.

        Returns:
            True if connection successful, False otherwise.
        """

        try:
            self.logger.info(
                f"Testing Gemini connection with model: "
                f"{self.model_name}"
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents="Reply with exactly: OK"
            )

            if response and response.text:
                self.logger.info(
                    "Gemini API connection successful"
                )
                return True

            self.logger.warning(
                "Gemini API returned an empty response"
            )

            return False

        except Exception as e:
            self.logger.error(
                f"Connection test failed: {e}"
            )

            return False

    # ============================================================
    # GENERATE CONTENT
    # ============================================================

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
        timeout: int = 60
    ) -> Optional[str]:
        """
        Generate text using Gemini API.

        Includes:
        - Retry
        - Exponential backoff
        - 503 handling
        - Automatic model fallback
        - Timeout (default 60s)
        """

        models_to_try = [
            self.model_name
        ]

        for model in self.fallback_models:
            if model not in models_to_try:
                models_to_try.append(model)

        for model_index, model in enumerate(models_to_try):

            self.logger.info(
                f"Using Gemini model: {model}"
            )

            for attempt in range(max_retries):

                try:
                    self.logger.info(
                        f"API call attempt "
                        f"{attempt + 1}/{max_retries} "
                        f"using {model}"
                    )

                    config = types.GenerateContentConfig(
                        temperature=temperature
                    )

                    if system_instruction:
                        config.system_instruction = system_instruction

                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                        timeout=timeout
                    )

                    if response and response.text:

                        # If fallback model succeeded,
                        # remember it for future requests.
                        if model != self.model_name:

                            self.logger.warning(
                                f"Fallback model {model} "
                                f"succeeded. Switching current model."
                            )

                            self.model_name = model

                        return response.text.strip()

                    self.logger.warning(
                        "Gemini returned an empty response"
                    )

                    return None

                except Exception as e:

                    self.logger.error(
                        f"API call failed "
                        f"(model={model}, "
                        f"attempt={attempt + 1}/{max_retries}): {e}"
                    )

                    # Do not retry non-transient errors
                    if not self._is_retryable_error(e):

                        self.logger.error(
                            "Error is not retryable. "
                            "Stopping request."
                        )

                        return None

                    # Retry same model
                    if attempt < max_retries - 1:

                        self._wait_before_retry(attempt)

                    else:

                        self.logger.warning(
                            f"Model {model} failed after "
                            f"{max_retries} attempts."
                        )

            # Try next model
            if model_index < len(models_to_try) - 1:

                next_model = models_to_try[model_index + 1]

                self.logger.warning(
                    f"Switching from {model} "
                    f"to fallback model {next_model}"
                )

        self.logger.error(
            "All Gemini models failed."
        )

        return None

    # ============================================================
    # GENERATE JSON
    # ============================================================

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Generate JSON using Gemini API.
        """

        models_to_try = [
            self.model_name
        ]

        for model in self.fallback_models:
            if model not in models_to_try:
                models_to_try.append(model)

        for model_index, model in enumerate(models_to_try):

            self.logger.info(
                f"Generating JSON with model: {model}"
            )

            for attempt in range(max_retries):

                try:

                    self.logger.info(
                        f"JSON API call attempt "
                        f"{attempt + 1}/{max_retries}"
                    )

                    config = types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json"
                    )

                    if system_instruction:
                        config.system_instruction = system_instruction

                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                        timeout=timeout
                    )

                    if not response or not response.text:

                        self.logger.warning(
                            "Empty JSON response from Gemini"
                        )

                        return None

                    response_text = response.text.strip()

                    # ------------------------------------------------
                    # Parse JSON
                    # ------------------------------------------------

                    try:

                        result = json.loads(response_text)

                    except json.JSONDecodeError:

                        cleaned_text = response_text

                        if cleaned_text.startswith("```json"):
                            cleaned_text = cleaned_text[7:]

                        elif cleaned_text.startswith("```"):
                            cleaned_text = cleaned_text[3:]

                        if cleaned_text.endswith("```"):
                            cleaned_text = cleaned_text[:-3]

                        cleaned_text = cleaned_text.strip()

                        result = json.loads(cleaned_text)

                    # Successful response
                    if model != self.model_name:

                        self.logger.warning(
                            f"Fallback model {model} succeeded. "
                            f"Switching current model."
                        )

                        self.model_name = model

                    return result

                except json.JSONDecodeError as e:

                    self.logger.error(
                        f"Invalid JSON returned by Gemini: {e}"
                    )

                    return None

                except Exception as e:

                    self.logger.error(
                        f"JSON API call failed "
                        f"(model={model}, "
                        f"attempt={attempt + 1}/{max_retries}): {e}"
                    )

                    if not self._is_retryable_error(e):

                        self.logger.error(
                            "Error is not retryable."
                        )

                        return None

                    if attempt < max_retries - 1:

                        self._wait_before_retry(attempt)

                    else:

                        self.logger.warning(
                            f"Model {model} failed after "
                            f"{max_retries} JSON attempts."
                        )

            # Next fallback model
            if model_index < len(models_to_try) - 1:

                next_model = models_to_try[model_index + 1]

                self.logger.warning(
                    f"Switching to fallback model: {next_model}"
                )

        self.logger.error(
            "All Gemini models failed for JSON request."
        )

        return None

    # ============================================================
    # CHANGE MODEL
    # ============================================================

    def set_model(self, model_name: str) -> None:
        """
        Change the model being used.
        """

        self.model_name = model_name

        self.logger.info(
            f"Gemini model changed to: {self.model_name}"
        )