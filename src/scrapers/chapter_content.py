"""
Chapter Content scraper module - handles chapter text content for Wattpad.
Responsible for: chapter body text, HTML content, etc.
"""

import hashlib
from src.scrapers.base import BaseScraper, safe_print
from src import config
from src.utils.validation import validate_against_schema
from src.schemas.chapter_content_schema import CHAPTER_CONTENT_SCHEMA


class ChapterContentScraper(BaseScraper):
    """Scraper for chapter content/body (Wattpad schema)"""
    
    # CSS selectors for extracting content - Updated based on actual Wattpad HTML structure
    CONTENT_CONTAINER_SELECTOR = 'div.panel-reading'
    PARAGRAPH_SELECTOR = 'div.panel-reading p'
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"chapter_contents": "chapter_contents"})
    
    @staticmethod
    def map_html_to_chapter_content(chapter_text, chapter_id):
        """
        Map chapter text content to Wattpad chapter content schema with validation
        
        Args:
            chapter_text: Chapter text content (từ Playwright extraction)
            chapter_id: Parent chapter ID
        
        Returns:
            dict formatted theo Wattpad chapter content schema, or None if invalid
        """
        try:
            # Generate contentId từ chapterId
            content_id = f"{chapter_id}_content"
            
            mapped = {
                "contentId": content_id,
                "chapterId": str(chapter_id),
                "content": chapter_text or "",
            }
            
            # ✅ Validate before return
            validated = validate_against_schema(mapped, CHAPTER_CONTENT_SCHEMA, strict=False)
            return validated
        except Exception as e:
            safe_print(f"⚠️  Chapter content validation failed: {e}")
            return None
    
    async def extract_chapter_content_from_page(self, page, chapter_id):
        """
        Trích xuất nội dung chapter từ Playwright page
        
        Args:
            page: Playwright page object (đã load chapter)
            chapter_id: Chapter ID (parent)
        
        Returns:
            dict chứa chapter content data (mapped + validated)
        """
        try:
            if not page:
                safe_print(f"⚠️  No page object provided")
                return None
            
            full_content = ""
            
            # 1. Chờ khối nội dung tải xong
            # CSS selector: div.panel-reading (content container dựa trên HTML thực tế)
            try:
                await page.wait_for_selector(self.CONTENT_CONTAINER_SELECTOR, timeout=30000)
                safe_print(f"   ✅ Content container loaded (div.panel-reading)")
            except Exception as e:
                safe_print(f"   ⚠️  Content container not found: {e}")
                return None
            
            # 2. Lấy TẤT CẢ các đoạn văn (paragraphs) từ bên trong container
            # Extract paragraph text chỉ từ <p> tags, bỏ qua nested elements (buttons, divs)
            try:
                # Sử dụng Playwright để lấy text từ mỗi <p> tag riêng biệt
                # Điều này đảm bảo chúng ta chỉ lấy text trực tiếp, không lấy text từ buttons/divs
                p_locators = await page.locator(self.PARAGRAPH_SELECTOR).all()
                paragraphs = []
                
                for p_locator in p_locators:
                    # Lấy text content từ <p> tag
                    p_text = await p_locator.inner_text()
                    if p_text and p_text.strip():  # Chỉ lấy nếu không rỗng
                        paragraphs.append(p_text.strip())
                
                safe_print(f"   ✅ Trích xuất {len(paragraphs)} paragraphs")
                
                # 3. Nối các đoạn lại thành một khối văn bản duy nhất
                full_content = "\n\n".join(paragraphs)
                safe_print(f"   ✅ Full content: {len(full_content)} characters")
            except Exception as e:
                safe_print(f"   ⚠️  Lỗi khi lấy paragraphs: {e}")
                return None
            
            # Map và validate
            processed_content = self.map_html_to_chapter_content(full_content, chapter_id)
            if processed_content:
                safe_print(f"✅ Trích xuất chapter content thành công: {len(full_content)} bytes")
            
            return processed_content
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi trích xuất chapter content: {e}")
            return None
    
    @staticmethod
    def extract_text_from_html(page_html):
        """
        Trích xuất text content từ HTML page (parsing)
        
        Args:
            page_html: HTML content string
        
        Returns:
            Extracted text content
        """
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(page_html, 'html.parser')
            
            # Tìm content container
            # Thử nhiều selectors khác nhau
            content_div = None
            
            # 1. Try div.panel-reading (older version)
            content_div = soup.find('div', class_='panel-reading')
            
            # 2. Try article tag (newer version)
            if not content_div:
                content_div = soup.find('article')
            
            # 3. Try div với class chứa 'content'
            if not content_div:
                content_divs = soup.find_all('div')
                for div in content_divs:
                    classes = div.get('class') or []
                    if classes:
                        for cls in classes:
                            if isinstance(cls, str) and 'content' in cls.lower():
                                content_div = div
                                break
                    if content_div:
                        break
            
            if not content_div:
                safe_print(f"⚠️  Không tìm được content container")
                return ""
            
            # Extract paragraphs từ container
            paragraphs = []
            for p in content_div.find_all('p'):
                # Lấy text từ <p> tag, bỏ qua nested elements (buttons, spans)
                p_text = p.get_text(strip=True)
                if p_text and len(p_text.strip()) > 0:
                    paragraphs.append(p_text)
            
            # Join paragraphs
            full_text = "\n\n".join(paragraphs)
            return full_text
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi parse HTML: {e}")
            return ""
    
    @staticmethod
    def extract_text_from_html_with_parse(page_html):
        """
        Trích xuất chapter content từ HTML page (parse + convert to text)
        
        Args:
            page_html: HTML content của chapter page
        
        Returns:
            Extracted chapter text
        """
        try:
            if not page_html:
                return ""
            
            text_content = ChapterContentScraper.extract_text_from_html(page_html)
            return text_content
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi extract text từ HTML: {e}")
            return ""
    
    @staticmethod
    def extract_and_map_chapter_content(page_html, chapter_id):
        """
        Extract chapter content từ HTML page và map vào schema
        
        Args:
            page_html: HTML content của chapter page
            chapter_id: Chapter ID
        
        Returns:
            dict chứa chapter content data (mapped + validated) hoặc None
        """
        try:
            # Extract text từ HTML
            chapter_text = ChapterContentScraper.extract_text_from_html_with_parse(page_html)
            
            if not chapter_text:
                safe_print(f"⚠️  Không extract được text từ HTML")
                return None
            
            # Map vào schema
            processed_content = ChapterContentScraper.map_html_to_chapter_content(chapter_text, chapter_id)
            return processed_content
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi extract chapter content: {e}")
            return None
    
    def extract_chapter_content_from_html(self, page_html, chapter_id):
        """
        Trích xuất nội dung chapter từ HTML string (fallback if async not available)
        
        Args:
            page_html: HTML content của chapter page
            chapter_id: Chapter ID (parent)
        
        Returns:
            dict chứa chapter content data (mapped + validated)
        """
        try:
            if not page_html:
                safe_print(f"⚠️  No HTML content to extract")
                return None
            
            # Map và validate
            processed_content = self.map_html_to_chapter_content(page_html, chapter_id)
            if processed_content:
                safe_print(f"✅ Trích xuất chapter content từ HTML: {len(page_html)} bytes")
            
            return processed_content
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi trích xuất chapter content: {e}")
            return None
    
    def save_chapter_content_to_mongo(self, content_data):
        """
        Lưu chapter content vào MongoDB
        
        Args:
            content_data: dict chứa thông tin chapter content (Wattpad schema)
        """
        if not content_data or not self.collection_exists("chapter_contents"):
            return
        
        try:
            collection = self.get_collection("chapter_contents")
            if collection is None:
                return
            
            existing = collection.find_one({"contentId": content_data.get("contentId")})
            
            if existing:
                # Update nếu content đã tồn tại
                collection.update_one(
                    {"contentId": content_data.get("contentId")},
                    {"$set": content_data}
                )
                safe_print(f"  📝 Cập nhật chapter content: {content_data.get('contentId')}")
            else:
                collection.insert_one(content_data)
                safe_print(f"  ✨ Thêm mới chapter content: {content_data.get('contentId')}")
        except Exception as e:
            safe_print(f"        ⚠️  Lỗi khi lưu chapter content vào MongoDB: {e}")
