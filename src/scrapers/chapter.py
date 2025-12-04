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
from src.scrapers.website import WebsiteScraper
from bs4 import BeautifulSoup
import re


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
            web_chapter_id = str(prefetched_data.get("id"))
            chapter_id = WebsiteScraper.generate_chapter_id(web_chapter_id, prefix="wp")
            
            mapped = {
                "chapterId": chapter_id,              # wp_uuid_v7 (generated)
                "webChapterId": web_chapter_id,      # Original Wattpad chapter ID
                "order": prefetched_data.get("order", 0),
                "chapterName": prefetched_data.get("title"),
                "chapterUrl": prefetched_data.get("url"),
                "publishedTime": prefetched_data.get("createDate"),
                "storyId": str(story_id),            # Parent story ID (wp_uuid_v7)
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
    def extract_chapter_urls_from_html(page_html, story_id, max_chapters=None):
        """
        Extract chapter URLs from HTML page (table of contents)
        Looks for links that are actual chapter pages, not stories
        
        Args:
            page_html: HTML content of story page
            story_id: Story ID (for building URLs)
            max_chapters: Max chapters to extract (from config if None)
        
        Returns:
            List of chapter URLs
        """
        if max_chapters is None:
            max_chapters = config.MAX_CHAPTERS_PER_STORY
        
        try:
            soup = BeautifulSoup(page_html, 'html.parser')
            chapter_urls = []
            
            # Find chapter links - looking for links in table of contents
            # Usually they are in a list or table of chapters
            for link in soup.find_all('a', href=True):
                href_raw = link.get('href')
                if not href_raw:
                    continue
                
                href = str(href_raw) if href_raw else ''
                if not href:
                    continue
                
                # Chapter URLs typically have pattern: /123456-chapter-name
                # NOT /story/123 (that's a story ID)
                # Look for patterns like:
                # - /123456-chapter-name (part number followed by dash and name)
                # - /story/123/part/456 (story part format)
                
                if re.search(r'/\d+-', href) or re.search(r'/part/\d+', href) or re.search(r'/story/\d+/\d+', href):
                    # Make sure it's full URL
                    if not href.startswith('http'):
                        href = config.BASE_URL + href
                    
                    # Extract chapter ID to avoid duplicates
                    # Match either /123456 or /part/123456
                    chapter_id_match = re.search(r'/(\d+)(?:-|/|$)', href)
                    if chapter_id_match:
                        chapter_id = chapter_id_match.group(1)
                        # Skip if chapter ID is likely a story ID (too small range typically)
                        if chapter_id == story_id:
                            continue
                        
                        # Check if already added
                        if not any(chapter_id in url for url in chapter_urls):
                            chapter_urls.append(href)
                            
                            # Check limit
                            if max_chapters and len(chapter_urls) >= max_chapters:
                                break
            
            safe_print(f"   ✅ Extract {len(chapter_urls)} chapter URLs từ HTML")
            return chapter_urls
        except Exception as e:
            safe_print(f"   ⚠️ Lỗi khi extract chapter URLs: {e}")
            return []
    
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
