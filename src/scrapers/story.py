"""
Story scraper module - handles story metadata scraping and storage for Wattpad.
Responsible for: title, description, stats, images, author info, etc.
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class StoryScraper(BaseScraper):
    """Scraper for story metadata (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"stories": config.MONGODB_COLLECTION_STORIES})
    
    def scrape_story_metadata(self, story_data, extra_info=None):
        """
        Xử lý metadata của 1 bộ truyện từ API Wattpad
        Mapping fields từ API response sang Wattpad schema:
        - storyId: từ id
        - storyName: từ title
        - storyUrl: từ url
        - coverImg: từ cover
        - description: từ description
        - totalChapters: từ numParts
        - totalViews: từ readCount
        - voted: từ voteCount
        - status: từ completed (true/false)
        - userId: từ user.name
        - time: từ createDate
        - tags: từ extra_info (HTML prefetched)
        - category: từ extra_info (HTML prefetched)
        - freeChapter: true (mặc định Wattpad)
        
        Args:
            story_data: API response từ /api/v3/stories/{id}
            extra_info: dict từ HTML window.prefetched (tags, categories, language)
        
        Returns:
            story_data dict với đầy đủ thông tin story
        """
        try:
            # Mapping từ API response
            processed_story = {
                "storyId": story_data.get("id"),
                "storyName": story_data.get("title"),
                "storyUrl": story_data.get("url"),
                "coverImg": story_data.get("cover"),
                "category": None,
                "status": "completed" if story_data.get("completed") else "ongoing",
                "tags": [],
                "description": story_data.get("description", ""),
                "totalChapters": story_data.get("numParts", 0),
                "totalViews": story_data.get("readCount", 0),
                "voted": story_data.get("voteCount", 0),
                "mature": story_data.get("mature", False),
                "freeChapter": not story_data.get("isPaywalled", False),
                "time": story_data.get("createDate"),
                "userId": story_data.get("user", {}).get("name")
            }
            
            # Add extra info từ HTML prefetched (nếu có)
            if extra_info:
                if "tags" in extra_info:
                    processed_story["tags"] = extra_info.get("tags", [])
                if "categories" in extra_info:
                    # Lấy category ID đầu tiên (nếu có)
                    cats = extra_info.get("categories", [])
                    if cats and len(cats) > 0:
                        processed_story["category"] = cats[0]
            
            return processed_story
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi xử lý metadata story: {e}")
            return None
    
    def save_story_to_mongo(self, story_data):
        """
        Lưu story vào MongoDB
        
        Args:
            story_data: dict chứa thông tin story (Wattpad schema)
        """
        if not story_data or not self.collection_exists("stories"):
            return
        
        try:
            collection = self.get_collection("stories")
            if collection is None:
                return
            
            existing = collection.find_one({"storyId": story_data.get("storyId")})
            
            if existing:
                # Update nếu story đã tồn tại
                collection.update_one(
                    {"storyId": story_data.get("storyId")},
                    {"$set": story_data}
                )
                safe_print(f"  📝 Cập nhật story: {story_data.get('storyName')}")
            else:
                collection.insert_one(story_data)
                safe_print(f"  ✨ Thêm mới story: {story_data.get('storyName')}")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu story vào MongoDB: {e}")