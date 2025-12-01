"""
User scraper module - handles user/author data storage for Wattpad.
Schema:
- userId: user ID/name
- userName: display name
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class UserScraper(BaseScraper):
    """Scraper for user/author data (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"users": "users"})
    
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
