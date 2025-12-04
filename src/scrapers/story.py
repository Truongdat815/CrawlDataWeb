"""
Story scraper module - handles story metadata scraping and storage for Wattpad.
Responsible for: title, description, stats, images, author info, etc.
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config
from src.utils.validation import validate_against_schema
from src.utils import download_image
from src.schemas.story_schema import STORY_SCHEMA


class StoryScraper(BaseScraper):
    """Scraper for story metadata (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"stories": config.MONGODB_COLLECTION_STORIES})
    
    @staticmethod
    def map_api_to_story(story_data, extra_info=None):
        """
        Map API response + extra_info to Wattpad story schema
        Download cover image và lưu đường dẫn local vào JSON
        
        Args:
            story_data: API response từ /api/v3/stories/{id}
            extra_info: dict từ HTML window.prefetched (tags, categories, language)
        
        Returns:
            story_data dict với đầy đủ thông tin story
        """
        try:
            story_id = story_data.get("id")
            cover_url = story_data.get("cover")
            
            # Download cover image nếu có URL
            cover_img_path = None
            if cover_url:
                safe_print(f"   📥 Đang download ảnh cover...")
                cover_img_path = download_image(cover_url, story_id)
                if cover_img_path:
                    safe_print(f"   ✅ Ảnh cover: {cover_img_path}")
            
            # Mapping from API response to new schema
            processed_story = {
                "storyId": story_id,
                "webStoryId": None,                  # Wattpad doesn't have separate web ID
                "storyName": story_data.get("title"),
                "storyUrl": story_data.get("url"),
                "coverImage": cover_img_path if cover_img_path else cover_url,  # Use local path if available
                "category": None,
                "status": "completed" if story_data.get("completed") else "ongoing",
                "genres": None,                      # Wattpad uses tags instead of genres
                "tags": [],
                "description": story_data.get("description", ""),
                "userId": story_data.get("user", {}).get("name"),
                "totalChapters": story_data.get("numParts", 0),
            }
            # Prefer tags/categories from API response if available
            api_tags = story_data.get("tags")
            if api_tags and isinstance(api_tags, list):
                processed_story["tags"] = api_tags

            # categories may be returned as a list or single value
            api_cats = story_data.get("categories") or story_data.get("category")
            if api_cats:
                if isinstance(api_cats, list) and len(api_cats) > 0:
                    processed_story["category"] = api_cats[0]
                elif isinstance(api_cats, dict):
                    # sometimes category may be an object with 'id' or 'name'
                    processed_story["category"] = api_cats.get("id") or api_cats.get("name")
                else:
                    # assume string
                    processed_story["category"] = api_cats

            # Fallback to extra info từ HTML prefetched (nếu có and API didn't provide)
            if extra_info:
                if not processed_story.get("tags") and "tags" in extra_info:
                    processed_story["tags"] = extra_info.get("tags", [])
                if not processed_story.get("category") and "categories" in extra_info:
                    cats = extra_info.get("categories", [])
                    if cats and len(cats) > 0:
                        processed_story["category"] = cats[0]

            # NOTE: do NOT persist `parts` inside story document.
            # Chapters metadata should be handled separately by `ChapterScraper`.
            
            # ✅ Validate before return
            validated = validate_against_schema(processed_story, STORY_SCHEMA, strict=False)
            return validated
            
        except Exception as e:
            safe_print(f"⚠️ Story validation failed: {e}")
            return None
    
    def scrape_story_metadata(self, story_data, extra_info=None):
        """
        Xử lý metadata của 1 bộ truyện từ API Wattpad
        
        Args:
            story_data: API response từ /api/v3/stories/{id}
            extra_info: dict từ HTML window.prefetched (tags, categories, language)
        
        Returns:
            story_data dict với đầy đủ thông tin story
        """
        return self.map_api_to_story(story_data, extra_info)
    
    @staticmethod
    def extract_story_info_from_prefetched(prefetched_data, story_id):
        """
        Trích xuất thông tin story từ window.prefetched
        
        Args:
            prefetched_data: window.prefetched object
            story_id: Story ID
        
        Returns:
            dict chứa {tags, categories, language, ...} từ prefetched
        """
        story_info = {
            "tags": [],
            "categories": [],
            "language": "en"
        }
        
        try:
            # Story metadata thường nằm trong prefetched['story'] hoặc tương tự
            for key, value in prefetched_data.items():
                # Tags thường có format "tag.{something}" hoặc trong "story.metadata"
                if key == "story.metadata" and "data" in value:
                    story_meta = value["data"]
                    
                    # Extract tags nếu có
                    if "tags" in story_meta:
                        story_info["tags"] = story_meta.get("tags", [])
                    
                    # Extract categories nếu có
                    if "categories" in story_meta:
                        story_info["categories"] = story_meta.get("categories", [])
                    
                    # Extract language nếu có
                    if "language" in story_meta:
                        story_info["language"] = story_meta.get("language", "en")
                    
                    safe_print(f"✅ Trích xuất tags ({len(story_info['tags'])}): {', '.join(story_info['tags'][:3])}")
            
            return story_info
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất story info: {e}")
            return story_info
    
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