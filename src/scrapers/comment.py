"""
Comment scraper module - handles chapter/story comments for Wattpad.
Schema:
- commentId: unique comment ID
- parentId: ID of parent comment (if reply, else null)
- react: reaction/sentiment data
- userId: user who commented
- chapterId: chapter being commented on
- createdAt: creation timestamp
- commentText: comment content
- paragraphIndex: nullable, for inline comments
- type: "inline" or "chapter_end"
"""

from src.scrapers.base import BaseScraper, safe_print
from src import config


class CommentScraper(BaseScraper):
    """Scraper for comments on chapters and stories (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"comments": "comments", "users": "users"})
    
    def save_comment_to_mongo(self, comment_data):
        """
        Lưu comment vào MongoDB
        
        Args:
            comment_data: dict chứa thông tin comment (Wattpad schema)
        """
        if not comment_data or not self.collection_exists("comments"):
            return
        
        try:
            collection = self.get_collection("comments")
            if collection is None:
                return
            
            existing = collection.find_one({"commentId": comment_data.get("commentId")})
            
            if existing:
                collection.update_one(
                    {"commentId": comment_data.get("commentId")},
                    {"$set": comment_data}
                )
            else:
                collection.insert_one(comment_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
