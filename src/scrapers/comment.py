"""
Comment scraper module - handles chapter/story comments.
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class CommentScraper(BaseScraper):
    """Scraper for comments on chapters and stories"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"comments": "comments", "users": "users"})
    
    def save_comment_to_mongo(self, comment_data):
        """
        Lưu comment vào MongoDB
        
        Args:
            comment_data: dict chứa thông tin comment
        """
        if not comment_data or not self.collection_exists("comments"):
            return
        
        try:
            collection = self.get_collection("comments")
            existing = collection.find_one({"comment_id": comment_data.get("comment_id")})
            
            if existing:
                collection.update_one(
                    {"comment_id": comment_data.get("comment_id")},
                    {"$set": comment_data}
                )
            else:
                collection.insert_one(comment_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
