"""
User scraper module - handles user/author data storage.
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class UserScraper(BaseScraper):
    """Scraper for user/author data"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"users": "users"})
    
    def save_user_to_mongo(self, user_id, username):
        """
        Lưu user/author vào MongoDB
        
        Args:
            user_id: ID của user từ URL profile
            username: Tên hiển thị của user
        """
        if not user_id or not username or not self.collection_exists("users"):
            return
        
        try:
            collection = self.get_collection("users")
            existing = collection.find_one({"user_id": user_id})
            
            if existing:
                # Update nếu username thay đổi
                if existing.get("username") != username:
                    collection.update_one(
                        {"user_id": user_id},
                        {"$set": {"username": username}}
                    )
            else:
                user_data = {
                    "user_id": user_id,
                    "username": username
                }
                collection.insert_one(user_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu user vào MongoDB: {e}")
