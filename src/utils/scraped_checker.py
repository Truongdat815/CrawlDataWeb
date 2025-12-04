#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Helper functions to check if story/chapter already scraped
Optimized: Load all IDs into memory once instead of querying DB multiple times
"""

from src import config
from pymongo import MongoClient
from src.scrapers.base import safe_print


class ScrapedChecker:
    """Check if story/chapter/content already exists in database (optimized with caching)"""
    
    def __init__(self):
        """Initialize MongoDB connection and cache all IDs in memory"""
        try:
            self.client = MongoClient(config.MONGODB_URI)
            self.db = self.client[config.MONGODB_DB_NAME]
            self.is_connected = True
            
            # ✅ CACHE: Load all IDs vào memory một lần
            self.story_ids = set()
            self.chapter_ids = set()
            self.chapter_content_ids = set()
            
            self._load_cache()
        except Exception as e:
            safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
            self.is_connected = False
    
    def _load_cache(self):
        """Load all IDs từ collections vào memory (chỉ 1 lần)"""
        if not self.is_connected:
            return
        
        try:
            # Load story IDs
            stories_collection = self.db["stories"]
            self.story_ids = set(doc["storyId"] for doc in stories_collection.find({}, {"storyId": 1}))
            safe_print(f"   💾 Loaded {len(self.story_ids)} story IDs to cache")
            
            # Load chapter IDs
            chapters_collection = self.db["chapters"]
            self.chapter_ids = set(doc["chapterId"] for doc in chapters_collection.find({}, {"chapterId": 1}))
            safe_print(f"   💾 Loaded {len(self.chapter_ids)} chapter IDs to cache")
            
            # Load chapter content IDs
            chapter_contents_collection = self.db["chapter_contents"]
            self.chapter_content_ids = set(doc["contentId"] for doc in chapter_contents_collection.find({}, {"contentId": 1}))
            safe_print(f"   💾 Loaded {len(self.chapter_content_ids)} chapter content IDs to cache")
        except Exception as e:
            safe_print(f"⚠️ Lỗi load cache: {e}")
    
    def story_exists(self, story_id):
        """Check if story đã được cào (check cache, NOT query DB)
        
        Args:
            story_id: Story ID to check (wp_uuid_v7 format)
        
        Returns:
            True nếu story đã tồn tại, False nếu chưa
        """
        return str(story_id) in self.story_ids
    
    def chapter_exists(self, chapter_id):
        """Check if chapter đã được cào (check cache, NOT query DB)
        
        Args:
            chapter_id: Chapter ID to check
        
        Returns:
            True nếu chapter đã tồn tại, False nếu chưa
        """
        return str(chapter_id) in self.chapter_ids
    
    def chapter_content_exists(self, chapter_id):
        """Check if chapter content đã được cào (check cache, NOT query DB)
        
        Args:
            chapter_id: Chapter ID to check
        
        Returns:
            True nếu chapter content đã tồn tại, False nếu chưa
        """
        content_id = f"{chapter_id}_content"
        return content_id in self.chapter_content_ids
    
    def get_story_status(self, story_id):
        """Get detailed status of story (query DB only once for details)
        
        Returns:
            dict với {exists, chapters_count, comments_count}
        """
        if not self.is_connected:
            return None
        
        # First check cache
        if str(story_id) not in self.story_ids:
            return None
        
        try:
            # Story exists in cache, now get details from DB
            story = self.db["stories"].find_one({"storyId": str(story_id)})
            if not story:
                return None
            
            # Count chapters (query once)
            chapters = list(self.db["chapters"].find(
                {"storyId": str(story_id)}, {"chapterId": 1}
            ))
            chapters_count = len(chapters)
            chapter_ids = [ch["chapterId"] for ch in chapters]
            
            # Count chapter contents (query cache, not DB)
            content_ids = [f"{ch_id}_content" for ch_id in chapter_ids]
            contents_count = sum(1 for cid in content_ids if cid in self.chapter_content_ids)
            
            # Count comments (query once)
            comments_count = self.db["comments"].count_documents(
                {"chapterId": {"$in": chapter_ids}}
            )
            
            return {
                "exists": True,
                "storyName": story.get("storyName"),
                "chapters_count": chapters_count,
                "chapters_with_content": contents_count,
                "comments_count": comments_count,
                "last_updated": story.get("time")
            }
        except Exception as e:
            safe_print(f"⚠️ Lỗi get story status: {e}")
            return None
    
    def close(self):
        """Close MongoDB connection"""
        if self.is_connected:
            self.client.close()


if __name__ == "__main__":
    # Test
    print(f"\n{'='*60}")
    print(f"ScrapedChecker - Optimized with caching")
    print(f"{'='*60}\n")
    
    checker = ScrapedChecker()
    
    # Check story 399709711 (Puck You)
    story_id = "399709711"
    
    print(f"\nCheck Story: {story_id}")
    print(f"{'='*60}")
    
    # First check - hits cache
    if checker.story_exists(story_id):
        print(f"✅ Story exists (from cache)")
    else:
        print(f"❌ Story NOT found")
    
    # Get detailed status - queries DB
    status = checker.get_story_status(story_id)
    if status:
        print(f"\n📊 Story Status:")
        print(f"   - Name: {status['storyName']}")
        print(f"   - Chapters: {status['chapters_count']}")
        print(f"   - Chapter contents: {status['chapters_with_content']}")
        print(f"   - Comments: {status['comments_count']}")
    
    # Check single chapter - hits cache
    chapter_id = "1518948101"
    print(f"\n\nCheck Chapter: {chapter_id}")
    print(f"{'='*60}")
    
    if checker.chapter_exists(chapter_id):
        print(f"✅ Chapter exists (from cache)")
    else:
        print(f"❌ Chapter NOT found")
    
    if checker.chapter_content_exists(chapter_id):
        print(f"✅ Chapter content exists (from cache)")
    else:
        print(f"❌ Chapter content NOT found")
    
    checker.close()

