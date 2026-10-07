"""Settings storage for AI Story Rewriter."""

import json
import os
from typing import Dict, Any
from dataclasses import dataclass, asdict, fields


@dataclass
class AppSettings:
    """Application settings."""
    api_key: str = ""
    model_name: str = "gemini-3.5-flash-lite"
    input_folder: str = ""
    output_folder: str = ""
    workflow_mode: str = "full_ai"  # "full_ai", "hybrid", "python_only"
    rewrite_intensity: str = "balanced"  # light, balanced, deep
    max_retry: int = 3
    save_failed: bool = True
    max_chars_per_line: int = 42
    max_lines_per_subtitle: int = 2
    theme: str = "dark"
    api_timeout: int = 60  # seconds
    analysis_timeout: int = 30  # seconds
    qc_timeout: int = 30  # seconds
    export_srt: bool = False  # False = export clean TTS .txt only (faster, 50% less tokens)
    skip_processed: bool = True  # Skip already completed files in output folder
    use_ai_qc: bool = False  # False = pure Python QC (0 extra AI tokens)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppSettings':
        """Create from dictionary, ignoring unknown keys and migrating retired model names."""
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}

        # Migrate retired 2.x / 1.5 model names to active fast model
        model = filtered.get("model_name", "gemini-3.5-flash-lite")
        if model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-pro", "gemini-1.5-flash"):
            filtered["model_name"] = "gemini-3.5-flash-lite"

        return cls(**filtered)


class SettingsManager:
    """Manager for application settings."""

    def __init__(self, settings_file: str = "settings.json"):
        """
        Initialize settings manager.

        Args:
            settings_file: Path to settings file
        """
        self.settings_file = settings_file
        self.settings = AppSettings()
        self._load()

        # Fallback to GEMINI_API_KEY environment variable if api_key in settings is empty
        if not self.settings.api_key:
            env_key = os.getenv("GEMINI_API_KEY", "").strip()
            if env_key and env_key != "your_api_key_here":
                self.settings.api_key = env_key

    def _load(self) -> None:
        """Load settings from file."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.settings = AppSettings.from_dict(data)
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def save(self) -> None:
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return getattr(self.settings, key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.
        """
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
            self.save()
        else:
            raise ValueError(f"Unknown setting: {key}")

    def get_all(self) -> AppSettings:
        """Get all settings."""
        return self.settings

    def update(self, **kwargs) -> None:
        """
        Update multiple settings.
        """
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()
