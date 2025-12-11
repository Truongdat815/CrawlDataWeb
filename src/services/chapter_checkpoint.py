# -*- coding: utf-8 -*-
"""
Per-Chapter Checkpoint Manager
✅ Track progress per story → per chapter instead of per story
- Supports resuming failed chapter crawls
- Tracks crawled vs failed chapters
- Minimal I/O overhead (batch updates)
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Set, Optional
from src import config
from ..scrapers import safe_print

class ChapterCheckpoint:
    """Per-chapter checkpoint for a single story"""
    def __init__(self, web_story_id: str):
        self.web_story_id = web_story_id
        self.status = "in-progress"  # in-progress, completed, partial-fail
        self.crawled_chapters: Set[str] = set()  # webChapterId
        self.failed_chapters: Set[str] = set()   # webChapterId that failed after max retries
        self.retry_counts: Dict[str, int] = {}   # webChapterId -> retry count
        self.timestamp = datetime.now().isoformat()
        self.total_chapters = 0
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "web_story_id": self.web_story_id,
            "status": self.status,
            "crawled_chapters": sorted(list(self.crawled_chapters)),
            "failed_chapters": sorted(list(self.failed_chapters)),
            "retry_counts": self.retry_counts,
            "total_chapters": self.total_chapters,
            "timestamp": self.timestamp,
            "progress": {
                "crawled": len(self.crawled_chapters),
                "failed": len(self.failed_chapters),
                "pending": max(0, self.total_chapters - len(self.crawled_chapters) - len(self.failed_chapters))
            }
        }
    @staticmethod
    def from_dict(data: Dict) -> 'ChapterCheckpoint':
        """Create from JSON dict"""
        ckpt = ChapterCheckpoint(data.get("web_story_id", ""))
        ckpt.status = data.get("status", "in-progress")
        ckpt.crawled_chapters = set(data.get("crawled_chapters", []))
        ckpt.failed_chapters = set(data.get("failed_chapters", []))
        ckpt.retry_counts = data.get("retry_counts", {})
        ckpt.total_chapters = data.get("total_chapters", 0)
        ckpt.timestamp = data.get("timestamp", datetime.now().isoformat())
        return ckpt

class ChapterCheckpointManager:
    """Manages checkpoints for all stories"""
    def __init__(self):
        self.checkpoints = []  # Danh sách các checkpoint, có thể cập nhật lại cho phù hợp

    def export_chapter_checkpoint(self, output_path: str = "data/chapter_checkpoint.json"):
        """Export all chapter checkpoints to a JSON file"""
        try:
            # Nếu self.checkpoints là list các ChapterCheckpoint
            data = [ckpt.to_dict() for ckpt in self.checkpoints]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            safe_print(f"✅ Exported chapter checkpoint summary to {output_path}")
        except Exception as e:
            safe_print(f"❌ Failed to export chapter checkpoint: {e}")

_checkpoint_manager = None

def get_chapter_checkpoint_manager() -> ChapterCheckpointManager:
    """Get global checkpoint manager instance"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = ChapterCheckpointManager()
    return _checkpoint_manager