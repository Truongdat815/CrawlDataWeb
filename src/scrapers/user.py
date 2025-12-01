"""
User scraper module - handles user/author data storage for Wattpad.
Schema:
- userId: user ID/name
- userName: display name
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config
from src.utils.validation import validate_against_schema
from src.schemas.user_schema import USER_SCHEMA


class UserScraper(BaseScraper):
    """Scraper for user/author data (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"users": "users"})
    
    @staticmethod
    def map_api_to_user(api_response):
        """
        Map API user response to Wattpad user schema with validation
        
        Args:
            api_response: API response user object
        
        Returns:
            dict formatted theo Wattpad user schema, or None if invalid
        """
        try:
            mapped = {
                "userId": api_response.get("name"),
                "userName": api_response.get("name"),
                "avatar": api_response.get("avatar"),
                "isFollowing": api_response.get("isFollowing", False)
            }
            
            # ✅ Validate before return
            validated = validate_against_schema(mapped, USER_SCHEMA, strict=False)
            return validated
        except Exception as e:
            safe_print(f"⚠️  User validation failed: {e}")
            return None
    
    @staticmethod
    def extract_user_info_from_prefetched(prefetched_data):
        """
        Trích xuất thông tin user từ prefetched data
        
        Args:
            prefetched_data: window.prefetched object
        
        Returns:
            dict chứa user info (userId, userName, avatar)
        """
        user_info = {
            "userId": None,
            "userName": None,
            "avatar": None
        }
        
        try:
            # User info thường nằm trong prefetched['user.metadata']
            for key, value in prefetched_data.items():
                if key == "user.metadata" and "data" in value:
                    user_data = value["data"]
                    
                    user_info["userId"] = user_data.get("name")
                    user_info["userName"] = user_data.get("name")
                    user_info["avatar"] = user_data.get("avatar")
                    
                    safe_print(f"✅ Trích xuất user: {user_info['userName']}")
                    return user_info
            
            return user_info
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất user info: {e}")
            return user_info
    
    def save_user_to_mongo(self, user_id, user_name):
        """
        Lưu user/author vào MongoDB
        
        Args:
            user_id: ID của user
            user_name: Tên hiển thị của user
        """
        if not user_id or not user_name or not self.collection_exists("users"):
            return
        
        try:
            collection = self.get_collection("users")
            if collection is None:
                return
            
            existing = collection.find_one({"userId": user_id})
            
            user_data = {
                "userId": user_id,
                "userName": user_name
            }
            
            if existing:
                # Update nếu user đã tồn tại
                collection.update_one(
                    {"userId": user_id},
                    {"$set": user_data}
                )
            else:
                collection.insert_one(user_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu user vào MongoDB: {e}")
