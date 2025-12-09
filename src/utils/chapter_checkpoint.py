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
from src.scrapers import safe_print


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
    """Manager for per-chapter checkpoints across all stories"""
    
    def __init__(self, checkpoint_dir: Optional[str] = None):
        self.checkpoint_dir = checkpoint_dir or os.path.join(config.CHECKPOINT_DIR, "chapters")
        self.checkpoints: Dict[str, ChapterCheckpoint] = {}
        self.lock = threading.Lock()
        self.dirty = False  # Track if changes need to be saved
        
        # Ensure checkpoint directory exists
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        safe_print(f"✅ ChapterCheckpointManager initialized")
        safe_print(f"   📁 Checkpoint dir: {self.checkpoint_dir}")
    
    def _get_checkpoint_file(self, web_story_id: str) -> str:
        """Get checkpoint file path for a story"""
        return os.path.join(self.checkpoint_dir, f"story_{web_story_id}.json")
    
    def load_checkpoint(self, web_story_id: str) -> Optional[ChapterCheckpoint]:
        """Load checkpoint for a story from file"""
        if not config.ENABLE_CHECKPOINTS:
            return None
        
        try:
            filepath = self._get_checkpoint_file(web_story_id)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ckpt = ChapterCheckpoint.from_dict(data)
                    with self.lock:
                        self.checkpoints[web_story_id] = ckpt
                    safe_print(f"✅ Loaded checkpoint for story {web_story_id}")
                    safe_print(f"   ✅ Crawled: {len(ckpt.crawled_chapters)} | ❌ Failed: {len(ckpt.failed_chapters)}")
                    return ckpt
        except Exception as e:
            safe_print(f"⚠️ Failed to load checkpoint for {web_story_id}: {e}")
        
        return None
    
    def save_checkpoint(self, web_story_id: str, ckpt: Optional[ChapterCheckpoint] = None):
        """Save checkpoint for a story to file"""
        if not config.ENABLE_CHECKPOINTS:
            return
        
        try:
            with self.lock:
                checkpoint = ckpt or self.checkpoints.get(web_story_id)
                if not checkpoint:
                    return
                
                filepath = self._get_checkpoint_file(web_story_id)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            safe_print(f"⚠️ Failed to save checkpoint for {web_story_id}: {e}")
    
    def get_or_create_checkpoint(self, web_story_id: str) -> ChapterCheckpoint:
        """Get existing checkpoint or create new one"""
        with self.lock:
            if web_story_id in self.checkpoints:
                return self.checkpoints[web_story_id]
        
        # Try to load from file
        ckpt = self.load_checkpoint(web_story_id)
        if ckpt:
            return ckpt
        
        # Create new checkpoint
        ckpt = ChapterCheckpoint(web_story_id)
        with self.lock:
            self.checkpoints[web_story_id] = ckpt
        return ckpt
    
    def mark_chapter_crawled(self, web_story_id: str, web_chapter_id: str):
        """Mark a chapter as successfully crawled"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            ckpt.crawled_chapters.add(web_chapter_id)
            # Remove from failed if it was retried successfully
            ckpt.failed_chapters.discard(web_chapter_id)
            ckpt.retry_counts.pop(web_chapter_id, None)
    
    def mark_chapter_failed(self, web_story_id: str, web_chapter_id: str):
        """Mark a chapter as permanently failed (after max retries)"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            ckpt.failed_chapters.add(web_chapter_id)
            ckpt.crawled_chapters.discard(web_chapter_id)
    
    def increment_chapter_retry(self, web_story_id: str, web_chapter_id: str) -> int:
        """Increment retry count for a chapter, return new count"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            count = ckpt.retry_counts.get(web_chapter_id, 0) + 1
            ckpt.retry_counts[web_chapter_id] = count
            return count
    
    def get_chapter_retry_count(self, web_story_id: str, web_chapter_id: str) -> int:
        """Get current retry count for a chapter"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            return ckpt.retry_counts.get(web_chapter_id, 0)
    
    def should_retry_chapter(self, web_story_id: str, web_chapter_id: str, max_retries: Optional[int] = None) -> bool:
        """Check if chapter should be retried"""
        max_retries = max_retries or config.MAX_CHAPTER_RETRIES
        current_count = self.get_chapter_retry_count(web_story_id, web_chapter_id)
        return current_count < max_retries
    
    def is_chapter_crawled(self, web_story_id: str, web_chapter_id: str) -> bool:
        """Check if chapter was already successfully crawled"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            return web_chapter_id in ckpt.crawled_chapters
    
    def is_chapter_failed(self, web_story_id: str, web_chapter_id: str) -> bool:
        """Check if chapter permanently failed"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            return web_chapter_id in ckpt.failed_chapters
    
    def get_pending_chapters(self, web_story_id: str, all_chapters: List[str]) -> List[str]:
        """Get list of chapters that need to be crawled"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        ckpt.total_chapters = len(all_chapters)
        
        with self.lock:
            pending = [
                ch for ch in all_chapters
                if ch not in ckpt.crawled_chapters and ch not in ckpt.failed_chapters
            ]
        return pending
    
    def get_retry_chapters(self, web_story_id: str) -> List[str]:
        """Get list of chapters that can be retried"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        max_retries = config.MAX_CHAPTER_RETRIES
        
        with self.lock:
            retry_chapters = []
            for ch_id, retry_count in ckpt.retry_counts.items():
                if retry_count < max_retries and ch_id not in ckpt.crawled_chapters:
                    retry_chapters.append(ch_id)
            return retry_chapters
    
    def get_checkpoint_status(self, web_story_id: str) -> Dict:
        """Get comprehensive status for a story"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            return {
                "web_story_id": web_story_id,
                "total_chapters": ckpt.total_chapters,
                "crawled": len(ckpt.crawled_chapters),
                "failed": len(ckpt.failed_chapters),
                "pending": max(0, ckpt.total_chapters - len(ckpt.crawled_chapters) - len(ckpt.failed_chapters)),
                "status": ckpt.status,
                "crawled_chapters": sorted(list(ckpt.crawled_chapters))[:10],  # First 10 for logging
                "failed_chapters": sorted(list(ckpt.failed_chapters))
            }
    
    def finalize_story(self, web_story_id: str):
        """Finalize checkpoint for story (mark as completed or in-progress)"""
        ckpt = self.get_or_create_checkpoint(web_story_id)
        with self.lock:
            # Nếu đã cào đủ chapter (không thiếu, không fail) thì completed
            if ckpt.total_chapters > 0 and len(ckpt.crawled_chapters) == ckpt.total_chapters and not ckpt.failed_chapters:
                ckpt.status = "completed"
                safe_print(f"✅ Story {web_story_id} completed successfully")
            # Nếu còn thiếu chapter hoặc có chapter fail thì in-progress hoặc partial-fail
            elif ckpt.failed_chapters:
                ckpt.status = "partial-fail"
                safe_print(f"⚠️ Story {web_story_id} completed with {len(ckpt.failed_chapters)} failed chapters")
            else:
                ckpt.status = "in-progress"
                safe_print(f"⏳ Story {web_story_id} still in progress: {len(ckpt.crawled_chapters)}/{ckpt.total_chapters} chapters crawled")
        self.save_checkpoint(web_story_id)
    
    def clear_checkpoint(self, web_story_id: str):
        """Clear checkpoint for a story (e.g., to restart)"""
        try:
            filepath = self._get_checkpoint_file(web_story_id)
            if os.path.exists(filepath):
                os.remove(filepath)
            with self.lock:
                self.checkpoints.pop(web_story_id, None)
            safe_print(f"🗑️ Cleared checkpoint for story {web_story_id}")
        except Exception as e:
            safe_print(f"⚠️ Failed to clear checkpoint: {e}")


# Global instance (lazy-loaded)
_checkpoint_manager: Optional[ChapterCheckpointManager] = None

def get_chapter_checkpoint_manager() -> ChapterCheckpointManager:
    """Get global checkpoint manager instance"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = ChapterCheckpointManager()
    return _checkpoint_manager
