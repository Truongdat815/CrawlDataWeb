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
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class ChapterScraper(BaseScraper):
    """Scraper for chapter content and metadata (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"chapters": "chapters"})
    
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
