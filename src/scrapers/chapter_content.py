"""
Chapter Content scraper module - handles chapter text content for Wattpad.
Responsible for: chapter body text, HTML content, etc.
"""

import hashlib
import re
import requests
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper, safe_print
from src import config
from src.utils.validation import validate_against_schema
from src.schemas.chapter_content_schema import CHAPTER_CONTENT_SCHEMA


class ChapterContentScraper(BaseScraper):
    """Scraper for chapter content/body (Wattpad schema)"""
    
    # CSS selectors for extracting content - Updated based on actual Wattpad HTML structure
    CONTENT_CONTAINER_SELECTOR = 'div.panel-reading'
    PARAGRAPH_SELECTOR = 'div.panel-reading p'
    
    # API endpoint for chapter content
    APIV2_ENDPOINT = "https://www.wattpad.com/apiv2/"
    
    def __init__(self, page=None, mongo_db=None, cookies=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"chapter_contents": "chapter_contents"})
        self.cookies = cookies or {}
    
    @staticmethod
    def clean_html_content(html_content):
        """
        Lọc HTML content để chỉ lấy text thuần túy từ các thẻ <p>
        Xử lý cả trường hợp content bị escape trong <pre> tag (từ API v2)
        
        Args:
            html_content: HTML content string chứa các thẻ <p>
        
        Returns:
            str: Nội dung text đã được làm sạch và format
        """
        try:
            if not html_content:
                return ""
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Kiểm tra xem có <pre> tag không (response từ API v2)
            pre_tag = soup.find('pre')
            if pre_tag:
                # Lấy text từ <pre> (đây là escaped HTML)
                escaped_html = pre_tag.get_text()
                # Parse escaped HTML thành soup mới
                soup = BeautifulSoup(escaped_html, 'html.parser')
            
            # Tìm tất cả thẻ <p>
            paragraphs = soup.find_all('p')
            
            # Lấy text từ mỗi paragraph
            clean_texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text:  # Chỉ thêm nếu không rỗng
                    clean_texts.append(text)
            
            # Nối các đoạn lại với double newline để tạo format đẹp
            cleaned_content = "\n\n".join(clean_texts)
            
            return cleaned_content
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi clean HTML content: {e}")
            return ""
    
    def fetch_chapter_content_from_apiv2_sync(self, page, chapter_id):
        """
        Fetch chapter content từ Wattpad API v2 endpoint qua Playwright (SYNC wrapper)
        API: https://www.wattpad.com/apiv2/?m=storytext&id={chapter_id}&page=
        
        Args:
            page: Playwright page object (đã có session/cookies)
            chapter_id: Chapter ID (part ID) - phải là numeric
        
        Returns:
            str: Nội dung chapter đã được làm sạch và format, hoặc None nếu lỗi
        """
        try:
            safe_print(f"   📡 Fetching chapter content từ API v2 (Playwright): {chapter_id}")
            
            if not page:
                safe_print(f"   ⚠️  Không có Playwright page object")
                return None
            
            # Validate chapter_id - phải là số
            chapter_id_str = str(chapter_id).strip()
            if not chapter_id_str.isdigit():
                safe_print(f"   ⚠️  Chapter ID không hợp lệ (phải là số): {chapter_id_str}")
                return None
            
            # API v2 URL - page= để lấy toàn bộ nội dung
            api_url = f"https://www.wattpad.com/apiv2/?m=storytext&id={chapter_id}&page="
            
            safe_print(f"   📄 API URL: {api_url}")
            
            # Dùng Playwright để fetch API (giữ nguyên cookies và session)
            try:
                response = page.goto(api_url, wait_until="load", timeout=30000)
                
                if response and response.status == 200:
                    # Lấy nội dung từ page
                    html_content = page.content()
                    
                    # Clean HTML để lấy text thuần túy
                    cleaned_content = self.clean_html_content(html_content)
                    
                    if cleaned_content:
                        safe_print(f"   ✅ Fetched content: {len(cleaned_content)} characters")
                        return cleaned_content
                    else:
                        safe_print(f"   ⚠️  Không thể extract text từ API response")
                        return None
                else:
                    status = response.status if response else "unknown"
                    safe_print(f"   ⚠️  API request failed: {status}")
                    return None
            except Exception as e:
                safe_print(f"   ⚠️  Lỗi khi goto API URL: {e}")
                return None
                
        except Exception as e:
            safe_print(f"   ⚠️  Lỗi khi fetch từ API v2: {e}")
            return None

    async def fetch_chapter_content_from_apiv2(self, page, chapter_id):
        """
        Fetch chapter content từ Wattpad API v2 endpoint qua Playwright
        API: https://www.wattpad.com/apiv2/?m=storytext&id={chapter_id}&page=
        
        Args:
            page: Playwright page object (đã có session/cookies)
            chapter_id: Chapter ID (part ID) - phải là numeric
        
        Returns:
            str: Nội dung chapter đã được làm sạch và format, hoặc None nếu lỗi
        """
        try:
            safe_print(f"   📡 Fetching chapter content từ API v2 (Playwright): {chapter_id}")
            
            if not page:
                safe_print(f"   ⚠️  Không có Playwright page object")
                return None
            
            # Validate chapter_id - phải là số
            chapter_id_str = str(chapter_id).strip()
            if not chapter_id_str.isdigit():
                safe_print(f"   ⚠️  Chapter ID không hợp lệ (phải là số): {chapter_id_str}")
                return None
            
            # API v2 URL - page= để lấy toàn bộ nội dung
            api_url = f"https://www.wattpad.com/apiv2/?m=storytext&id={chapter_id}&page="
            
            safe_print(f"   📄 API URL: {api_url}")
            
            # Dùng Playwright để fetch API (giữ nguyên cookies và session)
            try:
                response = await page.goto(api_url, wait_until="load", timeout=30000)
                
                if response and response.status == 200:
                    # Lấy nội dung từ page
                    html_content = await page.content()
                    
                    # Clean HTML để lấy text thuần túy
                    cleaned_content = self.clean_html_content(html_content)
                    
                    if cleaned_content:
                        safe_print(f"   ✅ Fetched content: {len(cleaned_content)} characters")
                        return cleaned_content
                    else:
                        safe_print(f"   ⚠️  Không thể extract text từ API response")
                        return None
                else:
                    status = response.status if response else "unknown"
                    safe_print(f"   ⚠️  API request failed: {status}")
                    return None
            except Exception as e:
                safe_print(f"   ⚠️  Lỗi khi goto API URL: {e}")
                return None
                
        except Exception as e:
            safe_print(f"   ⚠️  Lỗi khi fetch từ API v2: {e}")
            return None
    
    async def extract_chapter_content_using_apiv2(self, page, chapter_id):
        """
        Extract chapter content sử dụng API v2 qua Playwright
        
        Args:
            page: Playwright page object
            chapter_id: Chapter ID (part ID)
        
        Returns:
            dict chứa chapter content data (mapped + validated) hoặc None nếu lỗi
        """
        try:
            # Fetch content từ API v2
            chapter_text = await self.fetch_chapter_content_from_apiv2(page, chapter_id)
            
            if not chapter_text:
                safe_print(f"⚠️  Không lấy được content từ API v2 cho chapter {chapter_id}")
                return None
            
            # Map vào schema
            processed_content = self.map_html_to_chapter_content(chapter_text, chapter_id)
            
            if processed_content:
                safe_print(f"✅ Extract chapter content thành công từ API v2: {len(chapter_text)} characters")
            
            return processed_content
        except Exception as e:
            safe_print(f"⚠️  Lỗi khi extract chapter content từ API v2: {e}")
            return None
    
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
            from datetime import datetime
            
            # Generate contentId từ chapterId
            content_id = f"{chapter_id}_content"
            
            mapped = {
                "contentId": content_id,
                "chapterId": str(chapter_id),
                "content": chapter_text or "",
                "createdAt": datetime.utcnow().isoformat() + "Z",  # ISO format with Z suffix
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
