"""
Story scraper module - handles story metadata scraping and storage.
Responsible for: title, description, stats, images, author info, etc.
"""

import time
from src.scrapers.base import BaseScraper, safe_print
from src import config, utils


class StoryScraper(BaseScraper):
    """Scraper for story metadata (không gồm chapters/reviews/comments)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"stories": config.MONGODB_COLLECTION_STORIES})
    
    def scrape_story_metadata(self, story_url):
        """
        Cào metadata của 1 bộ truyện (không gồm chapters, reviews, comments)
        
        Returns:
            story_data dict với đầy đủ thông tin story
        """
        safe_print(f"🌍 Đang truy cập truyện: {story_url}")
        self.page.goto(story_url, timeout=config.TIMEOUT)
        
        # Lấy ID truyện từ URL
        story_id = story_url.split("/")[4]
        
        # Lấy title
        title = self.page.locator("h1").first.inner_text()
        
        # Lấy cover image
        img_url_raw = self.page.locator(".cover-art-container img").get_attribute("src")
        local_img_path = utils.download_image(img_url_raw, story_id)
        
        # Lấy author
        author_id = self.page.locator(".fic-title h4 a").first.get_attribute("href").split("/")[2]
        author_name = self.page.locator(".fic-title h4 a").first.inner_text()
        
        # Lấy category và status
        category = self.page.locator(".fiction-info span").first.inner_text()
        status = self.page.locator(".fiction-info span:nth-child(2)").first.inner_text()
        
        # Lấy tags
        tags = self.page.locator(".tags a").all_inner_texts()
        
        # Lấy description
        description = self._extract_description()
        
        # Lấy scores
        scores = self._extract_scores()
        
        # Lấy stats
        stats = self._extract_stats()
        
        # Tạo story data object
        story_data = {
            "id": story_id,
            "name": title,
            "url": story_url,
            "cover_image": local_img_path,
            "author_id": author_id,
            "author_name": author_name,
            "category": category,
            "status": status,
            "tags": tags,
            "description": description,
            **stats,  # Merge stats dict
            **scores,  # Merge scores dict
            "reviews": [],
            "chapters": []
        }
        
        safe_print(f"✅ Đã cào metadata cho: {title}")
        return story_data
    
    def _extract_description(self):
        """Trích xuất description từ HTML"""
        try:
            desc_container = self.page.locator(".description").first
            if desc_container.count() > 0:
                html_content = desc_container.inner_html()
                return self._convert_html_to_formatted_text(html_content)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
        return ""
    
    def _extract_scores(self):
        """Trích xuất các điểm đánh giá"""
        try:
            base_locator = ".stats-content ul.list-unstyled li:nth-child({}) span"
            return {
                "style_score": self.page.locator(base_locator.format(4)).inner_text(),
                "story_score": self.page.locator(base_locator.format(6)).inner_text(),
                "grammar_score": self.page.locator(base_locator.format(8)).inner_text(),
                "character_score": self.page.locator(base_locator.format(10)).inner_text(),
            }
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy scores: {e}")
            return {}
    
    def _extract_stats(self):
        """Trích xuất các thống kê (views, followers, ratings, etc)"""
        try:
            stats_locator = self.page.locator("div.col-sm-6 li.font-red-sunglo")
            return {
                "total_views": stats_locator.nth(0).inner_text(),
                "average_views": stats_locator.nth(1).inner_text(),
                "followers": stats_locator.nth(2).inner_text(),
                "favorites": stats_locator.nth(3).inner_text(),
                "ratings": stats_locator.nth(4).inner_text(),
                "page_views": stats_locator.nth(5).inner_text(),
            }
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy stats: {e}")
            return {}
    
    def _convert_html_to_formatted_text(self, html_content):
        """
        Chuyển HTML sang text với định dạng hợp lý
        """
        import re
        
        # Thay thế các tag HTML thành newlines
        text = html_content
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        text = re.sub(r'</div>', '\n', text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n', text)
        text = text.strip()
        
        return text
    
    def save_story_to_mongo(self, story_data):
        """Lưu story vào MongoDB"""
        if not story_data or not self.collection_exists("stories"):
            return
        
        try:
            collection = self.get_collection("stories")
            existing = collection.find_one({"id": story_data.get("id")})
            
            if existing:
                collection.update_one(
                    {"id": story_data.get("id")},
                    {"$set": story_data}
                )
                safe_print(f"🔄 Đã cập nhật story {story_data.get('id')} trong MongoDB")
            else:
                collection.insert_one(story_data)
                safe_print(f"✅ Đã lưu story {story_data.get('id')} vào MongoDB")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu story vào MongoDB: {e}")
