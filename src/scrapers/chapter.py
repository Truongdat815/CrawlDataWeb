"""
Chapter scraper module - handles chapter content and metadata storage.
"""

import time
from src.scrapers.base import BaseScraper, safe_print
from src import config


class ChapterScraper(BaseScraper):
    """Scraper for chapter content and metadata"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"chapters": "chapters", "comments": "comments"})
    
    def scrape_chapter(self, chapter_url, story_id):
        """
        Cào chi tiết 1 chương (content + comments)
        
        Args:
            chapter_url: URL của chương
            story_id: ID của bộ truyện
        
        Returns:
            chapter_data dict
        """
        try:
            safe_print(f"    🔖 Cào chương: {chapter_url}")
            self.page.goto(chapter_url, timeout=config.TIMEOUT)
            time.sleep(1)
            
            # Lấy thông tin cơ bản của chương
            chapter_id = self._extract_chapter_id(chapter_url)
            chapter_title = self._extract_chapter_title()
            chapter_number = self._extract_chapter_number()
            
            # Lấy content
            chapter_content = self._extract_chapter_content()
            
            # Lấy comments cho chương này
            chapter_comments = self._scrape_chapter_comments(chapter_id)
            
            chapter_data = {
                "id": chapter_id,
                "story_id": story_id,
                "title": chapter_title,
                "number": chapter_number,
                "url": chapter_url,
                "content": chapter_content,
                "comments": chapter_comments
            }
            
            # Lưu chapter vào MongoDB
            self.save_chapter_to_mongo(chapter_data)
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi cào chương {chapter_url}: {e}")
            return None
    
    def _extract_chapter_id(self, chapter_url):
        """Trích xuất ID chương từ URL"""
        try:
            # Ví dụ URL: https://www.royalroad.com/fiction/21220/mother-of-learning/chapter/521920/...
            parts = chapter_url.split("/")
            return parts[-1].split("-")[0] if parts else ""
        except:
            return ""
    
    def _extract_chapter_title(self):
        """Trích xuất title của chương"""
        try:
            title_elem = self.page.locator("h1").first
            if title_elem.count() > 0:
                return title_elem.inner_text().strip()
        except:
            pass
        return ""
    
    def _extract_chapter_number(self):
        """Trích xuất số thứ tự của chương"""
        try:
            # Thường nằm trong title hoặc breadcrumb
            # Có thể parse từ chapter list position
            return 0  # Placeholder
        except:
            return 0
    
    def _extract_chapter_content(self):
        """Trích xuất nội dung chapter"""
        try:
            content_elem = self.page.locator("div.chapter-content, div[class*='content'], article").first
            if content_elem.count() > 0:
                return content_elem.inner_html()
        except:
            pass
        return ""
    
    def _scrape_chapter_comments(self, chapter_id):
        """
        Cào comments cho chương
        
        Returns:
            list của comment dicts
        """
        comments = []
        try:
            # Placeholder - chi tiết comment scraping logic
            # Thường nằm trong section .comments hoặc .reviews
            pass
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi cào comments: {e}")
        
        return comments
    
    def save_chapter_to_mongo(self, chapter_data):
        """Lưu chapter vào MongoDB"""
        if not chapter_data or not self.collection_exists("chapters"):
            return
        
        try:
            collection = self.get_collection("chapters")
            existing = collection.find_one({"id": chapter_data.get("id")})
            
            if existing:
                collection.update_one(
                    {"id": chapter_data.get("id")},
                    {"$set": chapter_data}
                )
                safe_print(f"      🔄 Đã cập nhật chapter {chapter_data.get('id')}")
            else:
                collection.insert_one(chapter_data)
                safe_print(f"      ✅ Đã lưu chapter {chapter_data.get('id')} vào MongoDB")
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lưu chapter vào MongoDB: {e}")
