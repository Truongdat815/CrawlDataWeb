"""
Chapter scraper module - handles chapter content and metadata storage for Wattpad.
Schema:
- chapterId: unique chapter ID
- storyId: parent story ID
- chapterName: chapter title
- voted: vote count
- views: view count
- order: chapter index/order
- publishedTime: publish date
- lastUpdated: last update date
- chapterUrl: URL to chapter
- commentCount: number of comments
- wordCount: word count
- rating: chapter rating
- pages: number of pages
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config
from src.utils.validation import validate_against_schema
from src.schemas.chapter_schema import CHAPTER_SCHEMA


class ChapterScraper(BaseScraper):
    """Scraper for chapter content and metadata (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"chapters": "chapters"})
    
    @staticmethod
    def map_prefetched_to_chapter(prefetched_data, story_id):
        """
        Map window.prefetched data to new chapter schema with validation
        
        Args:
            prefetched_data: dict from window.prefetched (data field)
            story_id: ID of parent story
        
        Returns:
            dict formatted according to new chapter schema, or None if invalid
        """
        try:
            mapped = {
                "chapterId": str(prefetched_data.get("id")),
                "webChapterId": None,                # Wattpad doesn't have separate web ID
                "order": prefetched_data.get("order", 0),
                "chapterName": prefetched_data.get("title"),
                "chapterUrl": prefetched_data.get("url"),
                "publishedTime": prefetched_data.get("createDate"),
                "storyId": str(story_id),
                "voted": prefetched_data.get("voteCount", 0),
                "views": prefetched_data.get("readCount", 0),
                "totalComments": prefetched_data.get("commentCount", 0),
            }
            
            # ✅ Validate before return
            validated = validate_against_schema(mapped, CHAPTER_SCHEMA, strict=False)
            return validated
        except Exception as e:
            safe_print(f"⚠️  Chapter validation failed: {e}")
            return None
    
    @staticmethod
    def extract_chapters_from_prefetched(prefetched_data, story_id):
        """
        Trích xuất chapters từ prefetched data
        
        Args:
            prefetched_data: window.prefetched object
            story_id: Story ID
        
        Returns:
            List of chapter data (limited by MAX_CHAPTERS_PER_STORY)
        """
        chapters = []
        
        try:
            # Chapters thường nằm trong "part.{story_id}.metadata"
            for key, value in prefetched_data.items():
                if key.startswith("part.") and "metadata" in key:
                    # Check limit
                    if config.MAX_CHAPTERS_PER_STORY and len(chapters) >= config.MAX_CHAPTERS_PER_STORY:
                        safe_print(f"   ⏸️ Đã reach limit {config.MAX_CHAPTERS_PER_STORY} chapters")
                        break
                    
                    if "data" in value:
                        chapter_data = value["data"]
                        
                        # Map chapter fields using static method
                        processed_chapter = ChapterScraper.map_prefetched_to_chapter(chapter_data, story_id)
                        if processed_chapter:
                            chapters.append(processed_chapter)
                            safe_print(f"   ✅ Chapter: {chapter_data.get('title')}")
            
            safe_print(f"✅ Đã trích xuất {len(chapters)} chapters")
            return chapters
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất chapters: {e}")
            return []
    
    def save_chapter_to_mongo(self, chapter_data):
        """
        Lưu chapter vào MongoDB
        
        Args:
            chapter_data: dict chứa thông tin chapter (Wattpad schema)
        """
        if not chapter_data or not self.collection_exists("chapters"):
            return
        
        try:
            collection = self.get_collection("chapters")
            if collection is None:
                return
            
            existing = collection.find_one({"chapterId": chapter_data.get("chapterId")})
            
            if existing:
                # Update nếu chapter đã tồn tại
                collection.update_one(
                    {"chapterId": chapter_data.get("chapterId")},
                    {"$set": chapter_data}
                )
            else:
                collection.insert_one(chapter_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu chapter vào MongoDB: {e}")
