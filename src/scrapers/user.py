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
import requests


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
            # User info có thể nằm trong nhiều keys khác nhau
            for key, value in prefetched_data.items():
                # Case 1: user.metadata (user profile page)
                if key == "user.metadata" and "data" in value:
                    user_data = value["data"]
                    
                    user_info["userId"] = user_data.get("name") or user_data.get("username")
                    user_info["userName"] = user_data.get("name") or user_data.get("username")
                    user_info["avatar"] = user_data.get("avatar")
                    
                    if user_info["userName"]:
                        safe_print(f"      📌 User từ user.metadata: {user_info['userName']}")
                        return user_info
                
                # Case 2: part.XXXXX.metadata -> group.user (story author)
                if key.startswith("part.") and key.endswith(".metadata") and "data" in value:
                    part_data = value.get("data", {})
                    
                    # User info nằm trong part.data.group.user
                    if "group" in part_data and isinstance(part_data["group"], dict):
                        group_data = part_data["group"]
                        
                        if "user" in group_data and isinstance(group_data["user"], dict):
                            user_data = group_data["user"]
                            
                            user_info["userId"] = user_data.get("username") or user_data.get("name")
                            user_info["userName"] = user_data.get("username") or user_data.get("name")
                            user_info["avatar"] = user_data.get("avatar")
                            
                            if user_info["userName"]:
                                safe_print(f"      📌 User từ part.group.user: {user_info['userName']}")
                                return user_info
            
            return user_info
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất user info: {e}")
            return user_info
    
    def fetch_user_from_api(self, username):
        """
        Fetch user info from API v3/users
        
        Args:
            username: Username to fetch
        
        Returns:
            dict: Mapped user data or None if failed
        """
        try:
            api_url = f"https://www.wattpad.com/api/v3/users/{username}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.wattpad.com/'
            }
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                api_data = response.json()
                username = api_data.get("username")
                
                # Generate userId từ username (UUID v7)
                from src.scrapers.website import WebsiteScraper
                user_id = WebsiteScraper.generate_user_id(username)
                
                # Map theo USER_SCHEMA
                user_data = {
                    "userId": user_id,
                    "webUserId": None,
                    "username": username,
                    "userUrl": api_data.get("deeplink"),
                    "createdDate": api_data.get("createDate"),
                    "gender": api_data.get("gender"),
                    "location": api_data.get("location"),
                    "followers": api_data.get("numFollowers"),
                    "following": api_data.get("numFollowing"),
                    "comments": None,
                    "bio": api_data.get("description") or None,  # None if empty
                    "favorites": None,
                    "ratings": None,
                    "reviews": None,
                    "numberOfStories": api_data.get("numStoriesPublished"),
                    "totalWords": None,
                    "totalReviewsReceived": None,
                    "totalRatingsReceived": api_data.get("votesReceived"),
                    "totalFavoritesReceived": None,
                }
                
                return user_data
            else:
                safe_print(f"⚠️ API v3/users trả về status {response.status_code} cho {username}")
                return None
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi fetch user từ API: {e}")
            return None
    
    def save_user_to_mongo(self, user_id, user_name, avatar=None):
        """
        Lưu user/author vào MongoDB, fetch từ API nếu cần
        
        Args:
            user_id: ID của user (hoặc username)
            user_name: Tên hiển thị của user (hoặc username)
            avatar: Avatar URL (optional, deprecated - sẽ lấy từ API)
        """
        username = user_name or user_id
        if not username or not self.collection_exists("users"):
            return
        
        try:
            collection = self.get_collection("users")
            if collection is None:
                return
            
            # Tìm user theo username
            existing = collection.find_one({"username": username})
            
            if not existing:
                # Fetch từ API v3/users
                user_data = self.fetch_user_from_api(username)
                if user_data:
                    collection.insert_one(user_data)
                    safe_print(f"✅ Lưu user mới từ API: {username}")
                else:
                    # Fallback: lưu thông tin cơ bản nếu API fail
                    from src.scrapers.website import WebsiteScraper
                    user_id = WebsiteScraper.generate_user_id(username)
                    user_data = {
                        "userId": user_id,
                        "webUserId": None,
                        "username": username,
                        "userUrl": None,
                        "createdDate": None,
                        "gender": None,
                        "location": None,
                        "followers": None,
                        "following": None,
                        "comments": None,
                        "bio": None,
                        "favorites": None,
                        "ratings": None,
                        "reviews": None,
                        "numberOfStories": None,
                        "totalWords": None,
                        "totalReviewsReceived": None,
                        "totalRatingsReceived": None,
                        "totalFavoritesReceived": None,
                    }
                    collection.insert_one(user_data)
                    safe_print(f"⚠️ Lưu user với thông tin cơ bản: {username}")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu user vào MongoDB: {e}")
