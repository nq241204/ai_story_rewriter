"""Gemini API client for AI Story Rewriter."""

import json
import random
import time
import warnings
from typing import Optional, Dict, Any

# Suppress google-genai AFC info warnings
warnings.filterwarnings("ignore")

from google import genai
from google.genai import types

from app.utils.logger import get_logger


class GeminiClient:
    """Client for Google Gemini API with instant 503/404 model failover."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash-lite"
    ):
        self.api_key = api_key
        self.model_name = model_name or "gemini-3.5-flash-lite"
        self.logger = get_logger()

        # Verified active models ordered by availability, speed (~1s), and token efficiency
        self.fallback_models = [
            "gemini-3.5-flash-lite",      # ~1.1s response, 100% availability & lowest token cost
            "gemini-flash-lite-latest",   # ~1.0s response, 100% availability
            "gemini-3.8-flash",           # Latest 3.8 Flash
            "gemini-3.7-flash",           # 3.7 Flash
            "gemini-3.6-flash",           # 3.6 Flash
        ]

        # Remove duplicate models while preserving order
        self.fallback_models = list(dict.fromkeys(self.fallback_models))

        try:
            # Disable SDK's internal 5x tenacity retry so our fast model failover is immediate
            default_http = self._build_http_options(60)
            self.client = genai.Client(api_key=api_key, http_options=default_http)
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
        Determine whether an API error is transient.
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

    def _should_switch_model_immediately(self, error: Exception) -> bool:
        """
        Determine if we should immediately switch to the next fallback model
        instead of waiting and retrying the same overloaded/unavailable model.
        """
        error_text = str(error).upper()
        immediate_switch_markers = (
            "404",
            "NOT_FOUND",
            "NOT FOUND",
            "NOT SUPPORTED",
            "NO LONGER AVAILABLE",
            "503",
            "UNAVAILABLE",
            "HIGH DEMAND",
            "429",
            "RESOURCE_EXHAUSTED",
            "504",
            "DEADLINE_EXCEEDED",
        )
        return any(marker in error_text for marker in immediate_switch_markers)

    def _wait_before_retry(self, attempt: int) -> None:
        """
        Fast exponential backoff with jitter: 1.0s -> 2.0s -> 4.0s
        """
        backoff_times = [1.0, 2.0, 4.0]
        base_wait = backoff_times[attempt] if attempt < len(backoff_times) else 4.0
        jitter = random.uniform(0.1, 0.4)
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
    def _build_http_options(timeout: Optional[int]) -> types.HttpOptions:
        """
        Convert timeout in seconds to google-genai HttpOptions (milliseconds).
        Enforces minimum 15s (15000ms) required by Gemini API deadline rules,
        and sets attempts=1 to prevent SDK internal 45s tenacity hangs on 503.
        """
        safe_seconds = max(15, int(timeout or 60))
        return types.HttpOptions(
            timeout=safe_seconds * 1000,
            retry_options=types.HttpRetryOptions(attempts=1)
        )

    # ============================================================
    # CONNECTION TEST
    # ============================================================

    def test_connection(self) -> bool:
        """
        Test the API connection with fast automatic model failover.

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
                    contents="Reply OK",
                    config=config
                )

                if response and response.text:
                    if model != self.model_name:
                        self.logger.info(
                            f"Model {self.model_name} busy/unavailable -> switched to fast model: {model}"
                        )
                        self.model_name = model
                    self.logger.info(f"Gemini API connection successful ({self.model_name})")
                    return True

            except Exception as e:
                self.logger.warning(f"Connection test failed on {model}: {e}")
                if self._should_switch_model_immediately(e):
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
        Generate text using Gemini API with instant model failover on 503/404.
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
                                f"Fallback model {model} succeeded. Switching active model to {model}."
                            )
                            self.model_name = model

                        return response.text.strip()

                    self.logger.warning("Gemini returned an empty response")
                    return None

                except Exception as e:
                    self.logger.error(
                        f"API call failed (model={model}, attempt={attempt + 1}/{max_retries}): {e}"
                    )

                    # If model is overloaded (503) or not found (404) and we have fallback models,
                    # switch immediately without wasting time retrying the overloaded model!
                    if self._should_switch_model_immediately(e) and model_index < len(models_to_try) - 1:
                        self.logger.warning(
                            f"Model {model} returned 503/404/429. Failing over immediately to next model..."
                        )
                        break

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
        Generate JSON using Gemini API with instant model failover.
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
                            f"Fallback model {model} succeeded. Switching active model to {model}."
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

                    if self._should_switch_model_immediately(e) and model_index < len(models_to_try) - 1:
                        self.logger.warning(
                            f"Model {model} busy/unavailable. Switching immediately to next model..."
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