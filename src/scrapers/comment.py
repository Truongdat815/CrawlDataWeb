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
from bs4 import BeautifulSoup
import uuid


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
    
    @staticmethod
    def extract_comments_from_html(page_html, chapter_id):
        """
        Extract comments từ HTML DOM của chapter page (chapter_end comments)
        
        HTML structure:
        <div class="commentCardContentContainer__F9gGk gap8__gx3K6">
            <div class="authorProfileRow__GMsIH">
                <h3 aria-hidden="true" class="title-action">username</h3>
            </div>
            <div class="commentCardContent__Vc9vg">
                <pre class="text-body-sm">comment text</pre>
            </div>
            <div class="commentCardMeta__Xy9U9">
                <p class="postedDate__xcq5D">1 tháng trước</p>
            </div>
        </div>
        
        Args:
            page_html: HTML content of chapter page
            chapter_id: Chapter ID (parent)
        
        Returns:
            List of comment dicts (limited by MAX_COMMENTS_PER_CHAPTER)
        """
        comments = []
        
        try:
            soup = BeautifulSoup(page_html, 'html.parser')
            
            # Find all comment containers
            comment_containers = soup.find_all('div', class_='commentCardContentContainer__F9gGk')
            
            for container in comment_containers:
                # Check limit
                if config.MAX_COMMENTS_PER_CHAPTER and len(comments) >= config.MAX_COMMENTS_PER_CHAPTER:
                    break
                
                try:
                    # Extract username
                    username_elem = container.find('h3', class_='title-action')
                    username = username_elem.get_text(strip=True) if username_elem else "Anonymous"
                    
                    # Extract comment text
                    comment_text_elem = container.find('pre', class_='text-body-sm')
                    comment_text = comment_text_elem.get_text(strip=True) if comment_text_elem else ""
                    
                    # Extract posted date
                    date_elem = container.find('p', class_='postedDate__xcq5D')
                    posted_date = date_elem.get_text(strip=True) if date_elem else "Unknown"
                    
                    # Skip empty comments
                    if not comment_text:
                        continue
                    
                    # Create comment object
                    comment = {
                        "commentId": str(uuid.uuid4()),  # Generate unique ID since HTML doesn't have it
                        "parentId": None,
                        "react": 0,  # Like count not visible in basic HTML
                        "userId": username,
                        "chapterId": str(chapter_id),
                        "createdAt": posted_date,
                        "commentText": comment_text,
                        "paragraphIndex": None,
                        "type": "chapter_end"
                    }
                    
                    # Validate
                    validated = validate_against_schema(comment, COMMENT_SCHEMA, strict=False)
                    if validated:
                        comments.append(validated)
                        safe_print(f"      ✅ Comment từ {username}: {comment_text[:50]}")
                
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi parse comment: {e}")
                    continue
            
            if comments:
                safe_print(f"      ✅ Extracted {len(comments)} comments từ HTML")
            return comments
        
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi extract comments từ HTML: {e}")
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
