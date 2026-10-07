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
        model_name: str = "gemini-2.5-flash"
    ):
        self.api_key = api_key
        self.model_name = model_name or "gemini-2.5-flash"
        self.logger = get_logger()

        # Fallback models in order of speed & token efficiency
        self.fallback_models = [
            "gemini-2.5-flash",      # Primary fast & cost-efficient model
            "gemini-2.0-flash",      # Fast fallback
            "gemini-2.5-pro",        # High-capability fallback
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
        Determine whether an API error is transient and should be retried on the same model.
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
            "CONNECTION",
        ]

        return any(
            error_code in error_text
            for error_code in retryable_errors
        )

    def _is_model_not_found_error(self, error: Exception) -> bool:
        """
        Determine if the error indicates the model name does not exist or is unsupported,
        so we can immediately switch to the next fallback model without wasting time.
        """
        error_text = str(error).upper()
        return any(
            marker in error_text
            for marker in ("404", "NOT_FOUND", "NOT FOUND", "NOT SUPPORTED")
        )

    def _wait_before_retry(self, attempt: int) -> None:
        """
        Fast exponential backoff with jitter: 1.5s -> 3s -> 6s
        """
        backoff_times = [1.5, 3.0, 6.0]
        base_wait = backoff_times[attempt] if attempt < len(backoff_times) else 6.0
        jitter = random.uniform(0.1, 0.6)
        wait_time = base_wait + jitter

        self.logger.warning(f"Waiting {wait_time:.1f}s before retry...")
        time.sleep(wait_time)

    def _build_models_to_try(self) -> list:
        """Build ordered list of models to try."""
        models_to_try = [self.model_name]
        for model in self.fallback_models:
            if model not in models_to_try:
                models_to_try.append(model)
        return models_to_try

    @staticmethod
    def _build_http_options(timeout: Optional[int]) -> Optional[types.HttpOptions]:
        """Convert timeout in seconds to google-genai HttpOptions (milliseconds)."""
        if timeout and timeout > 0:
            return types.HttpOptions(timeout=int(timeout * 1000))
        return None

    # ============================================================
    # CONNECTION TEST
    # ============================================================

    def test_connection(self) -> bool:
        """
        Test the API connection with minimal token usage.

        Returns:
            True if connection successful, False otherwise.
        """
        for model in self._build_models_to_try():
            try:
                self.logger.info(f"Testing Gemini connection with model: {model}")
                config = types.GenerateContentConfig(
                    max_output_tokens=5,
                    temperature=0.0,
                    http_options=self._build_http_options(15)
                )
                response = self.client.models.generate_content(
                    model=model,
                    contents="OK",
                    config=config
                )

                if response and response.text:
                    if model != self.model_name:
                        self.logger.info(f"Switched active model to available model: {model}")
                        self.model_name = model
                    self.logger.info("Gemini API connection successful")
                    return True

            except Exception as e:
                self.logger.warning(f"Connection test failed on {model}: {e}")
                if self._is_model_not_found_error(e):
                    continue
                return False

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
        Generate text using Gemini API with automatic retry and fallback.
        """
        models_to_try = self._build_models_to_try()

        for model_index, model in enumerate(models_to_try):
            self.logger.info(f"Using Gemini model: {model}")

            for attempt in range(max_retries):
                try:
                    self.logger.info(
                        f"API call attempt {attempt + 1}/{max_retries} using {model}"
                    )

                    config = types.GenerateContentConfig(
                        temperature=temperature,
                        http_options=self._build_http_options(timeout)
                    )

                    if system_instruction:
                        config.system_instruction = system_instruction

                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config
                    )

                    if response and response.text:
                        if model != self.model_name:
                            self.logger.warning(
                                f"Fallback model {model} succeeded. Switching current model."
                            )
                            self.model_name = model

                        return response.text.strip()

                    self.logger.warning("Gemini returned an empty response")
                    return None

                except Exception as e:
                    self.logger.error(
                        f"API call failed (model={model}, attempt={attempt + 1}/{max_retries}): {e}"
                    )

                    # If model does not exist (404), break immediately to try next fallback model
                    if self._is_model_not_found_error(e):
                        self.logger.warning(
                            f"Model {model} not found/supported. Trying next fallback model..."
                        )
                        break

                    # Do not retry non-transient errors (e.g., invalid API key)
                    if not self._is_retryable_error(e):
                        self.logger.error("Error is not retryable. Stopping request.")
                        return None

                    if attempt < max_retries - 1:
                        self._wait_before_retry(attempt)
                    else:
                        self.logger.warning(
                            f"Model {model} failed after {max_retries} attempts."
                        )

            if model_index < len(models_to_try) - 1:
                next_model = models_to_try[model_index + 1]
                self.logger.warning(
                    f"Switching from {model} to fallback model {next_model}"
                )

        self.logger.error("All Gemini models failed.")
        return None

    # ============================================================
    # GENERATE JSON
    # ============================================================

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_retries: int = 3,
        timeout: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Generate JSON using Gemini API.
        """
        models_to_try = self._build_models_to_try()

        for model_index, model in enumerate(models_to_try):
            self.logger.info(f"Generating JSON with model: {model}")

            for attempt in range(max_retries):
                try:
                    self.logger.info(
                        f"JSON API call attempt {attempt + 1}/{max_retries}"
                    )

                    config = types.GenerateContentConfig(
                        temperature=temperature,
                        response_mime_type="application/json",
                        http_options=self._build_http_options(timeout)
                    )

                    if system_instruction:
                        config.system_instruction = system_instruction

                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config
                    )

                    if not response or not response.text:
                        self.logger.warning("Empty JSON response from Gemini")
                        return None

                    response_text = response.text.strip()

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

                    if model != self.model_name:
                        self.logger.warning(
                            f"Fallback model {model} succeeded. Switching current model."
                        )
                        self.model_name = model

                    return result

                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON returned by Gemini: {e}")
                    return None

                except Exception as e:
                    self.logger.error(
                        f"JSON API call failed (model={model}, attempt={attempt + 1}/{max_retries}): {e}"
                    )

                    if self._is_model_not_found_error(e):
                        self.logger.warning(
                            f"Model {model} not found/supported. Trying next fallback model..."
                        )
                        break

                    if not self._is_retryable_error(e):
                        self.logger.error("Error is not retryable.")
                        return None

                    if attempt < max_retries - 1:
                        self._wait_before_retry(attempt)
                    else:
                        self.logger.warning(
                            f"Model {model} failed after {max_retries} JSON attempts."
                        )

            if model_index < len(models_to_try) - 1:
                next_model = models_to_try[model_index + 1]
                self.logger.warning(f"Switching to fallback model: {next_model}")

        self.logger.error("All Gemini models failed for JSON request.")
        return None

    # ============================================================
    # CHANGE MODEL
    # ============================================================

    def set_model(self, model_name: str) -> None:
        """
        Change the model being used.
        """
        self.model_name = model_name
        self.logger.info(f"Gemini model changed to: {self.model_name}")