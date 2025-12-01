"""
Review scraper module - handles story reviews and ratings.
"""

import time
from src.scrapers.base import BaseScraper, safe_print
from src import config


class ReviewScraper(BaseScraper):
    """Scraper for story reviews"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"reviews": "reviews", "users": "users"})
    
    def scrape_reviews(self, story_url, story_id):
        """
        Cào tất cả reviews cho một bộ truyện
        
        Args:
            story_url: URL của bộ truyện
            story_id: ID của bộ truyện
        
        Returns:
            list của review dicts
        """
        reviews = []
        
        try:
            safe_print("... Đang lấy reviews cho toàn bộ truyện")
            self.page.goto(story_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Scroll để load reviews section
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Lấy tất cả review elements
            review_elements = self.page.locator("div.review, div[class*='review']").all()
            
            for idx, review_elem in enumerate(review_elements):
                try:
                    review_data = self._parse_review(review_elem, story_id)
                    if review_data:
                        reviews.append(review_data)
                        self.save_review_to_mongo(review_data)
                except Exception as e:
                    safe_print(f"    ⚠️ Lỗi khi parse review {idx + 1}: {e}")
                    continue
            
            safe_print(f"✅ Đã lấy được {len(reviews)} reviews")
            return reviews
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi cào reviews: {e}")
            return reviews
    
    def _parse_review(self, review_elem, story_id):
        """
        Parse một review element
        
        Args:
            review_elem: Playwright locator element
            story_id: ID của bộ truyện
        
        Returns:
            review_data dict hoặc None
        """
        try:
            review_id = self._extract_review_id(review_elem)
            if not review_id:
                return None
            
            # Trích xuất thông tin review
            user_id = self._extract_review_user_id(review_elem)
            username = self._extract_review_username(review_elem)
            title = self._extract_review_title(review_elem)
            content = self._extract_review_content(review_elem)
            rating = self._extract_review_rating(review_elem)
            
            review_data = {
                "review_id": review_id,
                "story_id": story_id,
                "user_id": user_id,
                "username": username,
                "title": title,
                "content": content,
                "rating": rating
            }
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None
    
    def _extract_review_id(self, review_elem):
        """Trích xuất ID của review"""
        try:
            # Thường từ data attribute hoặc URL
            review_id = review_elem.get_attribute("data-review-id")
            if not review_id:
                # Fallback: lấy từ link nếu có
                link = review_elem.locator("a").first
                if link.count() > 0:
                    href = link.get_attribute("href")
                    if href:
                        review_id = href.split("/")[-1]
            return review_id
        except:
            return None
    
    def _extract_review_user_id(self, review_elem):
        """Trích xuất ID người dùng"""
        try:
            # Từ profile link
            user_link = review_elem.locator("a[href*='/profile/']").first
            if user_link.count() > 0:
                href = user_link.get_attribute("href")
                return href.split("/")[2] if "/" in href else ""
        except:
            pass
        return ""
    
    def _extract_review_username(self, review_elem):
        """Trích xuất tên người dùng"""
        try:
            username_elem = review_elem.locator("a[href*='/profile/'], .username, .reviewer-name").first
            if username_elem.count() > 0:
                return username_elem.inner_text().strip()
        except:
            pass
        return ""
    
    def _extract_review_title(self, review_elem):
        """Trích xuất tiêu đề review"""
        try:
            title_elem = review_elem.locator("h3, .review-title, strong").first
            if title_elem.count() > 0:
                return title_elem.inner_text().strip()
        except:
            pass
        return ""
    
    def _extract_review_content(self, review_elem):
        """Trích xuất nội dung review"""
        try:
            content_elem = review_elem.locator("div.review-content, p, div[class*='content']").first
            if content_elem.count() > 0:
                return content_elem.inner_text().strip()
        except:
            pass
        return ""
    
    def _extract_review_rating(self, review_elem):
        """Trích xuất rating của review"""
        try:
            # Từ stars hoặc rating element
            rating_elem = review_elem.locator("div.stars, .rating, [class*='rating']").first
            if rating_elem.count() > 0:
                text = rating_elem.inner_text()
                # Parse số từ text (ví dụ "5 stars" -> 5)
                import re
                match = re.search(r'\d+', text)
                return int(match.group()) if match else 0
        except:
            pass
        return 0
    
    def save_review_to_mongo(self, review_data):
        """Lưu review vào MongoDB"""
        if not review_data or not self.collection_exists("reviews"):
            return
        
        try:
            collection = self.get_collection("reviews")
            existing = collection.find_one({"review_id": review_data.get("review_id")})
            
            if existing:
                collection.update_one(
                    {"review_id": review_data.get("review_id")},
                    {"$set": review_data}
                )
            else:
                collection.insert_one(review_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu review vào MongoDB: {e}")
