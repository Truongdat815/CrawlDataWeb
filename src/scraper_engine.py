import json
import os
import sys
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from src import config, utils

# Import MongoDB
try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

# Import scrapers
from src.scrapers import (
    StoryScraper, ChapterScraper, CommentScraper, 
    UserScraper, safe_print
)


class WattpadScraper:
    """Wattpad API-based scraper using modular components"""
    
    def __init__(self, max_workers=None):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Khởi tạo MongoDB client nếu được bật
        self.mongo_client = None
        self.mongo_db = None
        
        # Initialize scrapers (will be set in start())
        self.story_scraper = None
        self.chapter_scraper = None
        self.comment_scraper = None
        self.user_scraper = None
        
        # Legacy collections (backward compatibility)
        self.mongo_collection_stories = None
        self.mongo_collection_chapters = None
        self.mongo_collection_comments = None
        self.mongo_collection_users = None
        
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                self.mongo_client = MongoClient(config.MONGODB_URI)
                self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                # Keep for backward compatibility
                self.mongo_collection_stories = self.mongo_db[config.MONGODB_COLLECTION_STORIES]
                self.mongo_collection_chapters = self.mongo_db["chapters"]
                self.mongo_collection_comments = self.mongo_db["comments"]
                self.mongo_collection_users = self.mongo_db["users"]
                safe_print("✅ Đã kết nối MongoDB với 4 collections (Wattpad schema)")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

    def start(self):
        """Khởi động scrapers (Wattpad API không cần browser)"""
        # Khởi tạo scrapers
        self.story_scraper = StoryScraper(self.page, self.mongo_db)
        self.chapter_scraper = ChapterScraper(self.page, self.mongo_db)
        self.comment_scraper = CommentScraper(self.page, self.mongo_db)
        self.user_scraper = UserScraper(self.page, self.mongo_db)
        
        safe_print("✅ Bot đã khởi động! (Wattpad API crawler)")

    def stop(self):
        """Đóng MongoDB connection"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.mongo_client:
            self.mongo_client.close()
            safe_print("✅ Đã đóng kết nối MongoDB")
        safe_print("zzz Bot đã tắt.")

    # ==================== WATTPAD API METHODS ====================
    
    def scrape_stories_from_api(self, story_ids, fields=None):
        """
        Cào nhiều bộ truyện từ Wattpad API
        
        Args:
            story_ids: List of story IDs to scrape
            fields: API fields to retrieve (default: all standard fields)
        
        Returns:
            List of processed story data
        """
        if not story_ids:
            safe_print("❌ Không có story ID nào được cung cấp!")
            return []
        
        if fields is None:
            fields = "id,title,voteCount,readCount,createDate,lastPublishedPart,user(name,avatar),cover,url,numParts,isPaywalled,paidModel,completed,mature,description"
        
        safe_print(f"📚 Đang cào {len(story_ids)} bộ truyện từ Wattpad API...")
        
        stories_data = []
        for idx, story_id in enumerate(story_ids, 1):
            try:
                story_data = self.fetch_story_from_api(story_id, fields)
                if story_data:
                    processed = self.story_scraper.scrape_story_metadata(story_data)
                    if processed:
                        stories_data.append(processed)
                        safe_print(f"✅ [{idx}/{len(story_ids)}] Cào: {story_data.get('title')}")
                else:
                    safe_print(f"⚠️ [{idx}/{len(story_ids)}] Lỗi khi lấy story ID {story_id}")
            except Exception as e:
                safe_print(f"❌ [{idx}/{len(story_ids)}] Lỗi: {e}")
                continue
        
        safe_print(f"\n🎉 Hoàn thành cào {len(stories_data)}/{len(story_ids)} bộ truyện")
        return stories_data

    def fetch_story_from_api(self, story_id, fields=None):
        """
        Lấy dữ liệu 1 bộ truyện từ Wattpad API
        
        Args:
            story_id: Story ID
            fields: API fields to retrieve
        
        Returns:
            API response dict or None
        """
        if fields is None:
            fields = "id,title,voteCount,readCount,createDate,lastPublishedPart,user(name,avatar),cover,url,numParts,isPaywalled,paidModel,completed,mature,description"
        
        url = f"{config.BASE_URL}/api/v3/stories/{story_id}"
        params = {"fields": fields}
        
        try:
            response = requests.get(url, params=params, timeout=config.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi fetch story {story_id}: {e}")
            return None

    def fetch_comments_from_api(self, story_id, part_id):
        """
        Lấy comments từ Wattpad API
        
        Args:
            story_id: Story ID
            part_id: Chapter/Part ID
        
        Returns:
            List of comments
        """
        url = f"{config.BASE_URL}/api/v3/stories/{story_id}/parts/{part_id}/comments"
        
        all_comments = []
        pagination_cursor = None
        
        try:
            while True:
                params = {}
                if pagination_cursor:
                    params["after"] = pagination_cursor
                
                response = requests.get(url, params=params, timeout=config.TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if "comments" in data:
                    all_comments.extend(data["comments"])
                
                # Check for next page
                if "pagination" in data and "after" in data["pagination"]:
                    pagination_cursor = data["pagination"]["after"]
                else:
                    break
            
            return all_comments
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy comments: {e}")
            return []

    def fetch_categories(self):
        """
        Lấy danh sách categories từ Wattpad API
        
        Returns:
            List of categories with mapping
        """
        url = f"{config.BASE_URL}/api/v3/categories"
        
        try:
            response = requests.get(url, timeout=config.TIMEOUT)
            response.raise_for_status()
            categories = response.json()
            
            # Tạo mapping id → name_english
            category_map = {cat["id"]: cat["name_english"] for cat in categories}
            safe_print(f"✅ Đã lấy {len(category_map)} categories")
            return category_map
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy categories: {e}")
            return {}

    def scrape_story(self, story_id, fetch_chapters=True, fetch_comments=True):
        """
        Cào toàn bộ thông tin bộ truyện (metadata + chapters + comments)
        
        Args:
            story_id: Story ID to scrape
            fetch_chapters: Whether to fetch chapter list
            fetch_comments: Whether to fetch comments
        
        Returns:
            Complete story data dict
        """
        safe_print(f"\n{'='*60}")
        safe_print(f"📖 Bắt đầu cào story ID: {story_id}")
        safe_print(f"{'='*60}")
        
        # 1. Fetch story metadata
        story_data = self.fetch_story_from_api(story_id)
        if not story_data:
            safe_print(f"❌ Không thể lấy metadata cho story {story_id}")
            return None
        
        # 2. Process with scraper
        processed_story = self.story_scraper.scrape_story_metadata(story_data)
        
        if not processed_story:
            safe_print(f"❌ Lỗi khi xử lý story metadata")
            return None
        
        # 3. Optionally fetch chapters
        if fetch_chapters:
            safe_print(f"   📚 Đang lấy danh sách chapters...")
            # TODO: Implement chapter list fetching when API endpoint is known
            pass
        
        # 4. Optionally fetch comments
        if fetch_comments and story_data.get("lastPublishedPart"):
            part_id = story_data["lastPublishedPart"].get("id")
            if part_id:
                safe_print(f"   💬 Đang lấy comments...")
                comments = self.fetch_comments_from_api(story_id, part_id)
                for comment in comments:
                    self.comment_scraper.save_comment_to_mongo({
                        "commentId": comment["commentId"]["resourceId"],
                        "parentId": None,  # TODO: Extract from API if available
                        "react": comment.get("sentiments", {}),
                        "userId": comment["user"]["name"],
                        "chapterId": comment["resource"]["resourceId"],
                        "createdAt": comment["created"],
                        "commentText": comment["text"],
                        "paragraphIndex": None,
                        "type": "chapter_end"
                    })
        
        safe_print(f"✅ Hoàn thành cào story: {processed_story.get('storyName')}")
        return processed_story

    # ==================== UTILITY METHODS ====================

    def _save_to_json(self, data):
        """
        Lưu dữ liệu vào file JSON
        """
        filename = f"{data['storyId']}_{utils.clean_text(data.get('storyName', 'unknown'))}.json"
        save_path = os.path.join(config.JSON_DIR, filename)
        
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            safe_print(f"💾 Đã lưu dữ liệu vào file: {save_path}")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu file JSON: {e}")


# For backward compatibility
RoyalRoadScraper = WattpadScraper
