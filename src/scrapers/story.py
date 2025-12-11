"""
Story scraper module - handles story metadata scraping and storage for Wattpad.
Responsible for: title, description, stats, images, author info, etc.
"""

from .base import BaseScraper, safe_print
from .. import config
from ..utils.validation import validate_against_schema
from ..utils import download_image
from ..schemas.story_schema import STORY_SCHEMA
from .website import WebsiteScraper
import requests


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
            web_story_id = str(story_data.get("id"))  # Original Wattpad ID
            story_id = WebsiteScraper.generate_story_id(web_story_id, prefix="wp")
            cover_url = story_data.get("cover")
            
            # Download cover image nếu có URL
            cover_img_path = None
            if cover_url:
                safe_print(f"   📥 Đang download ảnh cover...")
                cover_img_path = download_image(cover_url, web_story_id)  # Use web_story_id for filename
                if cover_img_path:
                    safe_print(f"   ✅ Ảnh cover: {cover_img_path}")
            
            # Mapping from API response to new schema
            # Some pages do not include a userId; keep it None intentionally.
            processed_story = {
                "storyId": story_id,                  # wp_uuid_v7 (generated)
                "webStoryId": web_story_id,          # Original Wattpad ID
                "storyName": story_data.get("title"),
                "storyUrl": story_data.get("url"),
                "coverImage": cover_img_path if cover_img_path else cover_url,  # Use local path if available
                "category": None,
                "status": "completed" if story_data.get("completed") else "ongoing",
                "genres": None,                      # Wattpad uses tags instead of genres
                "tags": [],
                "description": story_data.get("description", ""),
                "userId": None,
                "totalChapters": story_data.get("numParts", 0),
                # Store language as a simple string (language name). We'll normalize below.
                "language": None,
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
            language_name = None
            if extra_info:
                # tags/categories from prefetched if API didn't provide
                if not processed_story.get("tags") and "tags" in extra_info:
                    processed_story["tags"] = extra_info.get("tags", [])
                if not processed_story.get("category") and "categories" in extra_info:
                    cats = extra_info.get("categories", [])
                    if cats and len(cats) > 0:
                        processed_story["category"] = cats[0]

            # If API provided language, normalize it here
            ld = story_data.get("language")
            if isinstance(ld, dict):
                language_name = ld.get("name")
            elif isinstance(ld, str):
                language_name = ld

            # If API did not provide language, allow fallback to extra_info
            # extra_info may contain a simple 'language' key (string) populated
            # by extract_story_info_from_prefetched(), so use that as fallback.
            if not language_name and extra_info:
                lang_from_extra = extra_info.get("language")
                if isinstance(lang_from_extra, dict):
                    # sometimes prefetched may store object; use 'name' if present
                    language_name = lang_from_extra.get("name") or lang_from_extra.get("id") or None
                elif isinstance(lang_from_extra, str):
                    language_name = lang_from_extra

            # Final language stored as simple string (language name if available)
            processed_story["language"] = language_name

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
            "language": None
        }
        
        try:
            # Story metadata thường nằm trong các block '*.metadata'
            for key, value in prefetched_data.items():
                # value expected to contain a 'data' dict
                data_block = None
                if isinstance(value, dict) and "data" in value:
                    data_block = value.get("data")

                if not data_block:
                    continue

                # Extract tags nếu có
                if "tags" in data_block and data_block.get("tags"):
                    story_info["tags"] = data_block.get("tags", [])

                # Extract categories nếu có
                if "categories" in data_block and data_block.get("categories"):
                    story_info["categories"] = data_block.get("categories", [])

                # New: extract language from group.language if present
                # Some prefetched blocks (e.g., part.<id>.metadata) include a
                # 'group' object which holds story-level metadata including language.
                grp = data_block.get("group")
                if isinstance(grp, dict):
                    lang_obj = grp.get("language")
                    if lang_obj:
                        # language may be object or string
                        if isinstance(lang_obj, dict):
                            story_info["language"] = lang_obj.get("name") or lang_obj.get("id") or None
                        elif isinstance(lang_obj, str):
                            story_info["language"] = lang_obj

                # Also allow language directly under data_block (fallback)
                if not story_info.get("language") and "language" in data_block:
                    ld = data_block.get("language")
                    if isinstance(ld, dict):
                        story_info["language"] = ld.get("name") or ld.get("id") or None
                    elif isinstance(ld, str):
                        story_info["language"] = ld

                # Log if we extracted tags
                if story_info.get("tags"):
                    try:
                        safe_print(f"✅ Trích xuất tags ({len(story_info['tags'])}): {', '.join(story_info['tags'][:3])}")
                    except Exception:
                        pass

            return story_info
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất story info: {e}")
            return story_info

    @staticmethod
    def fetch_metadata_minimal(web_story_id: str) -> dict:
        """
        Fetch minimal story metadata from Wattpad API.

        Returns dict with keys (may be None):
          - total_chapters (int)
          - updated_at (str)
          - chapter_ids (list) optional if API returns parts list
        """
        try:
            api_url = f"https://www.wattpad.com/api/v3/stories/{web_story_id}"
            headers = {
                'User-Agent': config.DEFAULT_USER_AGENT,
                'Accept': 'application/json',
                'Referer': 'https://www.wattpad.com/'
            }
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                safe_print(f"⚠️ Minimal metadata fetch returned {resp.status_code} for {web_story_id}")
                return {}

            data = resp.json()
            # Defensive extraction: try common keys
            total = data.get('numParts') or data.get('totalParts') or data.get('partsCount')
            updated = data.get('updateDate') or data.get('updatedAt') or data.get('lastUpdateDate') or data.get('modifiedDate')
            # language may be present as object or string
            lang_name = None
            ld = data.get('language')
            if isinstance(ld, dict):
                lang_name = ld.get('name') or ld.get('id') or ld.get('code')
            elif isinstance(ld, str):
                lang_name = ld
            chapter_ids = None
            # some responses include 'parts' list with id fields
            parts = data.get('parts') or data.get('chapters')
            if isinstance(parts, list) and len(parts) > 0:
                # try to collect web chapter ids if available
                chapter_ids = []
                for p in parts:
                    if isinstance(p, dict):
                        cid = p.get('id') or p.get('webChapterId') or p.get('chapterId')
                        if cid:
                            chapter_ids.append(str(cid))
            return {
                'total_chapters': int(total) if total is not None else None,
                'updated_at': updated,
                'language_name': lang_name,
                'chapter_ids': chapter_ids,
            }
        except Exception as e:
            safe_print(f"⚠️ Error fetching minimal metadata for {web_story_id}: {e}")
            return {}
    
    def save_story_to_mongo(self, story_data):
        """
        Lưu story vào MongoDB
        
        Args:
            story_data: dict chứa thông tin story (Wattpad schema)
        """
        if story_data is None or not self.collection_exists("stories"):
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