#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Duplicate checker - handles checking if stories/chapters already scraped
Integrates with scraper_engine to skip duplicates
"""

from src.utils.scraped_checker import ScrapedChecker
from src.scrapers.base import safe_print


class DuplicateChecker:
    """Handles duplicate detection and logging during scraping"""
    
    def __init__(self):
        """Initialize checker"""
        self.checker = ScrapedChecker()
        self.skipped_stories = []
        self.skipped_chapters = []
    
    def check_story(self, story_id, story_name=None):
        """Check if story already scraped and log result
        
        Args:
            story_id: Story ID to check (wp_uuid_v7 format)
            story_name: Optional story name for logging
        
        Returns:
            dict with status info or None if not scraped
        """
        story_status = self.checker.get_story_status(story_id)
        
        if story_status:
            # Story already scraped
            safe_print(f"\n⚠️ SKIP: Story '{story_status['storyName']}' đã được cào trước đó!")
            safe_print(f"   - Chapters: {story_status['chapters_count']}")
            safe_print(f"   - Chapter contents: {story_status['chapters_with_content']}")
            safe_print(f"   - Comments: {story_status['comments_count']}")
            safe_print(f"   - Last updated: {story_status['last_updated']}")
            
            self.skipped_stories.append({
                "storyId": story_id,
                "storyName": story_status['storyName'],
                "reason": "already_scraped"
            })
            
            return story_status
        
        return None
    
    def check_chapter(self, chapter_id, chapter_name=None):
        """Check if chapter already scraped and log result
        
        Args:
            chapter_id: Chapter ID to check
            chapter_name: Optional chapter name for logging
        
        Returns:
            True if chapter already scraped, False otherwise
        """
        if self.checker.chapter_exists(chapter_id):
            safe_print(f"      ⚠️ SKIP: Chapter already scraped!")
            
            # Check if content exists
            if self.checker.chapter_content_exists(chapter_id):
                safe_print(f"         ✅ Content exists")
            else:
                safe_print(f"         ⚠️ Content missing")
            
            self.skipped_chapters.append({
                "chapterId": chapter_id,
                "chapterName": chapter_name,
                "reason": "already_scraped",
                "has_content": self.checker.chapter_content_exists(chapter_id)
            })
            
            return True
        
        return False
    
    def get_summary(self):
        """Get summary of skipped items
        
        Returns:
            dict with skip statistics
        """
        return {
            "skipped_stories": len(self.skipped_stories),
            "skipped_chapters": len(self.skipped_chapters),
            "skipped_stories_list": self.skipped_stories,
            "skipped_chapters_list": self.skipped_chapters
        }
    
    def close(self):
        """Close database connection"""
        self.checker.close()
