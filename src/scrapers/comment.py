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
from src.utils.validation import validate_against_schema
from src.schemas.comment_schema import COMMENT_SCHEMA


class CommentScraper(BaseScraper):
    """Scraper for comments on chapters and stories (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"comments": "comments", "users": "users"})
    
    @staticmethod
    def map_api_to_comment(comment_data, chapter_id):
        """
        Map API comment response to Wattpad comment schema with validation
        
        Args:
            comment_data: API response comment object
            chapter_id: Parent chapter ID
        
        Returns:
            dict formatted theo Wattpad comment schema, or None if invalid
        """
        try:
            mapped = {
                "commentId": str(comment_data.get("id")),
                "parentId": comment_data.get("parentId"),
                "react": comment_data.get("voteCount", 0),
                "userId": comment_data.get("author", {}).get("name"),
                "chapterId": str(chapter_id),
                "createdAt": comment_data.get("createdAt"),
                "commentText": comment_data.get("body", ""),
                "paragraphIndex": comment_data.get("paragraphIndex"),
                "type": "inline" if comment_data.get("paragraphIndex") else "chapter_end"
            }
            
            # ✅ Validate before return
            validated = validate_against_schema(mapped, COMMENT_SCHEMA, strict=False)
            return validated
        except Exception as e:
            safe_print(f"⚠️  Comment validation failed: {e}")
            return None
    
    @staticmethod
    def extract_comment_info_from_prefetched(prefetched_data, chapter_id):
        """
        Trích xuất thông tin comment từ prefetched data
        
        Args:
            prefetched_data: window.prefetched object
            chapter_id: Chapter ID (parent)
        
        Returns:
            List of comment data (limited by MAX_COMMENTS_PER_CHAPTER)
        """
        comments = []
        
        try:
            # Comments thường nằm trong "comment.{chapter_id}.metadata"
            for key, value in prefetched_data.items():
                if key.startswith("comment.") and "metadata" in key:
                    # Check limit
                    if config.MAX_COMMENTS_PER_CHAPTER and len(comments) >= config.MAX_COMMENTS_PER_CHAPTER:
                        safe_print(f"   ⏸️ Đã reach limit {config.MAX_COMMENTS_PER_CHAPTER} comments")
                        break
                    
                    if "data" in value:
                        comment_data = value["data"]
                        
                        # Map comment fields using static method
                        processed_comment = CommentScraper.map_api_to_comment(comment_data, chapter_id)
                        if processed_comment:
                            comments.append(processed_comment)
                            safe_print(f"   ✅ Comment: {comment_data.get('body', '')[:50]}")
            
            safe_print(f"✅ Đã trích xuất {len(comments)} comments")
            return comments
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất comments: {e}")
            return []
    
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
