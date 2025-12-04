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
import uuid


class CommentScraper(BaseScraper):
    """Scraper for comments on chapters and stories (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"comments": "comments", "users": "users"})
    



    @staticmethod
    def map_v5_comment(api_comment, chapter_id):
        """
        Map Wattpad v5 comment object to new COMMENT_SCHEMA
        Returns validated dict or None
        """
        try:
            # Extract commentId
            cid = None
            try:
                cid = api_comment.get("commentId", {}).get("resourceId")
            except Exception:
                cid = None
            if not cid:
                cid = str(uuid.uuid4())

            # Extract resource info
            res = api_comment.get("resource") or {}
            resource_namespace = res.get("namespace")
            
            # Determine if this is a root comment (namespace == 'parts' means chapter-level root)
            is_root = resource_namespace == "parts"
            
            # Extract real user data
            user_data = api_comment.get("user") or {}
            user_name = user_data.get("name", "Anonymous")
            user_avatar = user_data.get("avatar")

            mapped = {
                "commentId": cid,
                "webCommentId": None,                # Wattpad doesn't have separate web ID
                "commentText": api_comment.get("text", ""),
                "time": api_comment.get("created"),
                "chapterId": str(chapter_id),
                "userId": user_name,                 # Use real username as userId
                "replyToUserId": None,               # Not available in v5 API
                "parentId": None,                    # Will be set for reply comments in process_v5_comments_page
                "isRoot": is_root,
                "react": api_comment.get("sentiments", {}).get(":like:", {}).get("count", 0) if isinstance(api_comment.get("sentiments"), dict) else 0,
                "websiteId": None,                   # To be set when website collection is implemented
                # Keep extra fields for user scraper
                "_userName": user_name,
                "_userAvatar": user_avatar,
            }

            # Validate
            validated = validate_against_schema(mapped, COMMENT_SCHEMA, strict=False)
            return validated
        except Exception as e:
            safe_print(f"⚠️ map_v5_comment failed: {e}")
            return None

    @staticmethod
    def process_v5_comments_page(api_data, chapter_id, namespace='paragraphs', comment_scraper=None, parent_comment_id=None):
        """
        Process a v5 comments page JSON: map & save comments, return (mapped_list, parent_ids_with_replies, next_cursor)
        
        Args:
            parent_comment_id: For namespace='comments', this is the parent comment ID for replies
        """
        results = []
        parents = []
        next_cursor = None

        try:
            comments = api_data.get('comments', [])
            for api_comment in comments:
                mapped = CommentScraper.map_v5_comment(api_comment, chapter_id)
                if not mapped:
                    continue
                
                # Set parentId for reply comments
                if namespace == 'comments' and parent_comment_id:
                    mapped['parentId'] = parent_comment_id
                    mapped['isRoot'] = False

                # Save to DB via existing method
                try:
                    # If a CommentScraper instance is provided, use it to persist
                    if comment_scraper is not None:
                        try:
                            comment_scraper.save_comment_to_mongo(mapped, user_name=mapped.get('userName'))
                        except Exception as e:
                            safe_print(f"⚠️ Error saving mapped v5 comment: {e}")
                    else:
                        # No scraper provided - skip saving here
                        pass
                except Exception as e:
                    safe_print(f"⚠️ Error saving mapped v5 comment: {e}")

                results.append(mapped)

                # If this top-level comment has replies, record parent id
                # For 'parts' namespace, check replyCount to fetch replies from 'comments' namespace
                if namespace == 'parts' and api_comment.get('replyCount', 0) > 0:
                    parent_res_id = api_comment.get('commentId', {}).get('resourceId')
                    if parent_res_id:
                        parents.append(parent_res_id)

            pagination = api_data.get('pagination') or {}
            if pagination and pagination.get('after'):
                next_cursor = pagination['after'].get('resourceId')

            return results, parents, next_cursor
        except Exception as e:
            safe_print(f"⚠️ process_v5_comments_page failed: {e}")
            return [], [], None


    @staticmethod
    def fetch_v5_page_via_playwright(page, resource_id, namespace='parts', cursor=None, limit=None):
        """
        Use Playwright page context to call Wattpad v5 comments endpoint from the browser (uses page cookies/token).
        
        Args:
            page: Playwright page object
            resource_id: Chapter ID or Comment ID (format: chapterId_hash for inline, or commentId for replies)
            namespace: 'parts' for chapter comments, 'comments' for replies, 'paragraphs' for inline
            cursor: Pagination cursor (format: resourceId for parts/paragraphs, or complex format for after)
            limit: Optional limit for number of comments
        
        Returns JSON dict or None.
        """
        try:
            origin = 'https://www.wattpad.com'
            params = []
            if cursor:
                params.append(f"after={cursor}")
            if limit:
                params.append(f"limit={limit}")
            qs = "?" + "&".join(params) if params else ""
            url = f"{origin}/v5/comments/namespaces/{namespace}/resources/{resource_id}/comments{qs}"

            # Use Playwright's request API (re-uses browser cookies and auth)
            try:
                resp = page.request.get(url, headers={"Accept": "application/json"})
            except Exception as e:
                safe_print(f"⚠️ Playwright request.get failed: {e}")
                return None

            status = getattr(resp, 'status', None) or getattr(resp, 'status_code', None)
            if status is not None and int(status) >= 400:
                safe_print(f"⚠️ Playwright request returned status {status}")
                return None

            try:
                return resp.json()
            except Exception:
                try:
                    text = resp.text()
                    import json as _json
                    return _json.loads(text)
                except Exception as e:
                    safe_print(f"⚠️ Failed to parse Playwright response: {e}")
                    return None
        except Exception as e:
            safe_print(f"⚠️ fetch_v5_page_via_playwright unexpected: {e}")
            return None

    def save_comment_to_mongo(self, comment_data, user_name=None):
        """
        Lưu comment vào MongoDB (lưu userId là UUID)
        Đồng thời lưu user info vào collection users
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
                collection.insert_one(comment_data)  # Lưu cả userId (UUID) và userName
            
            # Save user info dựa vào userName (để tìm user đã tồn tại hay chưa)
            if not user_name:
                user_name = comment_data.get("userName")
            
            if user_name and user_name != "Anonymous" and self.collection_exists("users"):
                try:
                    users_collection = self.get_collection("users")
                    if users_collection is not None:
                        # Check if user already exists (dùng userName để tìm, vì userId là UUID)
                        existing_user = users_collection.find_one({"userName": user_name})
                        if not existing_user:
                            user_data = {
                                "userId": comment_data.get("userId"),  # UUID from comment
                                "userName": user_name,
                                "avatar": None,
                                "isFollowing": False
                            }
                            users_collection.insert_one(user_data)
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lưu user: {e}")
        
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
