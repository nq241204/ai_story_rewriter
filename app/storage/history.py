"""History storage for AI Story Rewriter."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class HistoryEntry:
    """Entry in processing history."""
    original_filename: str
    output_filename: Optional[str]
    status: str
    start_time: str
    finish_time: str
    duration_seconds: float
    title: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_filename": self.original_filename,
            "output_filename": self.output_filename,
            "status": self.status,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
            "duration_seconds": self.duration_seconds,
            "title": self.title,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoryEntry':
        """Create from dictionary."""
        return cls(**data)


class HistoryManager:
    """Manager for processing history."""
    
    def __init__(self, history_file: str = "history.json"):
        """
        Initialize history manager.
        
        Args:
            history_file: Path to history file
        """
        self.history_file = history_file
        self.history: List[HistoryEntry] = []
        self._load()
    
    def _load(self) -> None:
        """Load history from file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.history = [HistoryEntry.from_dict(entry) for entry in data]
            except Exception as e:
                print(f"Failed to load history: {e}")
                self.history = []
    
    def save(self) -> None:
        """Save history to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([entry.to_dict() for entry in self.history], f, indent=2)
        except Exception as e:
            print(f"Failed to save history: {e}")
    
    def add_entry(self, entry: HistoryEntry) -> None:
        """
        Add a history entry.
        
        Args:
            entry: HistoryEntry to add
        """
        self.history.append(entry)
        self.save()
    
    def get_all(self) -> List[HistoryEntry]:
        """Get all history entries."""
        return self.history
    
    def clear(self) -> None:
        """Clear all history."""
        self.history = []
        self.save()
    
    def get_recent(self, limit: int = 100) -> List[HistoryEntry]:
        """
        Get recent history entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent entries (most recent first)
        """
        return self.history[-limit:][::-1]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics from history.
        
        Returns:
            Dictionary with statistics
        """
        total = len(self.history)
        completed = sum(1 for e in self.history if e.status == "completed")
        failed = sum(1 for e in self.history if e.status == "failed")
        
        avg_duration = 0.0
        if completed > 0:
            total_duration = sum(e.duration_seconds for e in self.history if e.status == "completed")
            avg_duration = total_duration / completed
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "average_duration": avg_duration
        }
