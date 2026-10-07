"""Settings storage for AI Story Rewriter."""

import json
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class AppSettings:
    """Application settings."""
    api_key: str = ""
    model_name: str = "gemini-3.8-flash"
    input_folder: str = ""
    output_folder: str = ""
    rewrite_intensity: str = "balanced"  # light, balanced, deep
    max_retry: int = 3
    save_failed: bool = True
    max_chars_per_line: int = 42
    max_lines_per_subtitle: int = 2
    theme: str = "dark"
    api_timeout: int = 60  # seconds
    analysis_timeout: int = 30  # seconds
    qc_timeout: int = 30  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppSettings':
        """Create from dictionary."""
        return cls(**data)


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
    
    def _load(self) -> None:
        """Load settings from file."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.settings = AppSettings.from_dict(data)
            except Exception as e:
                print(f"Failed to load settings: {e}")
                # Use defaults
    
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
        
        Args:
            key: Setting key
            value: Setting value
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
        
        Args:
            **kwargs: Key-value pairs to update
        """
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()
