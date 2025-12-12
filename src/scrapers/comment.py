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

from .base import BaseScraper, safe_print
from .. import config
from ..utils.validation import validate_against_schema
from ..schemas.comment_schema import COMMENT_SCHEMA
from .website import WebsiteScraper
import uuid
import requests
from ..utils.date_utils import format_for_db


class CommentScraper(BaseScraper):
    """Scraper for comments on chapters and stories (Wattpad schema)"""
    
    def __init__(self, page=None, mongo_db=None):
        super().__init__(page, mongo_db, config)
        self.init_collections({"comments": "comments", "users": "users"})
    
    def fetch_and_map_user(self, username):
        """
        Fetch user info from API v3/users and map to schema
        
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
                from .website import WebsiteScraper
                user_id = WebsiteScraper.generate_user_id(username)
                
                # Map theo USER_SCHEMA
                user_data = {
                    "userId": user_id,
                    "webUserId": None,
                    "username": username,
                    "userUrl": api_data.get("deeplink"),
                    "createdDate": format_for_db(api_data.get("createDate")) or api_data.get("createDate"),
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
                safe_print(f"      ⚠️ API v3/users trả về status {response.status_code} cho {username}")
                return None
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi fetch user từ API: {e}")
            return None

    @staticmethod
    def map_v5_comment(api_comment, chapter_id):
        """
        Map Wattpad v5 comment object to new COMMENT_SCHEMA
        Returns validated dict or None
        """
        try:
            # Extract web commentId
            web_comment_id = None
            try:
                web_comment_id = api_comment.get("commentId", {}).get("resourceId")
            except Exception:
                web_comment_id = None
            
            # Generate UUID v7 for commentId (non-deterministic)
            if web_comment_id:
                comment_id = WebsiteScraper.generate_comment_id(web_comment_id, prefix="wp")
            else:
                # Fallback: generate random uuid7 if no web ID
                comment_id = WebsiteScraper.generate_comment_id(None, prefix="wp")
                web_comment_id = str(uuid.uuid4())  # Random web ID as placeholder

            # Extract resource info
            res = api_comment.get("resource") or {}
            resource_namespace = res.get("namespace")
            
            # Determine if this is a root comment (namespace == 'parts' means chapter-level root)
            is_root = resource_namespace == "parts"
            
            # Extract real user data
            user_data = api_comment.get("user") or {}
            user_name = user_data.get("name", "Anonymous")
            user_avatar = user_data.get("avatar")
            
            # Debug log
            if not user_name or user_name == "Anonymous":
                safe_print(f"      ⚠️ No user data in comment! API keys: {list(api_comment.keys())}")
                if "user" in api_comment:
                    safe_print(f"         User object keys: {list(user_data.keys())}")

            mapped = {
                "commentId": comment_id,             # wp_uuid_v7
                "webCommentId": web_comment_id,      # Original Wattpad comment ID
                "commentText": api_comment.get("text", ""),
                "time": format_for_db(api_comment.get("created")) or api_comment.get("created"),
                "chapterId": str(chapter_id),
                "userId": user_name,                 # Use real username as userId
                "userName": user_name,               # Display name
                "replyToUserId": None,               # Not available in v5 API
                "parentId": None,                    # Will be set for reply comments in process_v5_comments_page
                "isRoot": is_root,
                "react": api_comment.get("sentiments", {}).get(":like:", {}).get("count", 0) if isinstance(api_comment.get("sentiments"), dict) else 0,
                "websiteId": None,                   # To be set when website collection is implemented
                "isDeleted": False,                  # Default: comment is not deleted
                # Keep extra fields for user scraper
                "_userAvatar": user_avatar,
            }

            # Validate
            validated = validate_against_schema(mapped, COMMENT_SCHEMA, strict=False)
            return validated
        except Exception as e:
            safe_print(f"⚠️ map_v5_comment failed: {e}")
            return None

    @staticmethod
    def process_v5_comments_page(api_data, chapter_id, namespace='paragraphs', comment_scraper=None, parent_comment_id=None, website_id=None):
        """
        Process a v5 comments page JSON: map & save comments, return (mapped_list, parent_ids_with_replies, next_cursor)
        
        Args:
            parent_comment_id: For namespace='comments', this is the parent comment ID for replies
            website_id: Wattpad website ID to assign to comments
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
                
                # Set websiteId if provided
                if website_id:
                    mapped['websiteId'] = website_id

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
                # API v5 pagination cursor là full string, không chỉ resourceId
                # Format: "resourceId#hash1#timestamp#hash2"
                # Lấy toàn bộ pagination.after nếu là string, nếu không thì lấy resourceId
                after_data = pagination.get('after')
                if isinstance(after_data, str):
                    next_cursor = after_data
                elif isinstance(after_data, dict):
                    # Fallback: nếu là dict thì thử lấy resourceId hoặc serialize
                    # Có thể cần encode thành format "id#hash#timestamp#hash"
                    next_cursor = after_data.get('resourceId')
                else:
                    next_cursor = None

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
                safe_print(f"   URL: {url}")
                return None

            try:
                data = resp.json()
                # Debug log
                if data:
                    comments_count = len(data.get('comments', []))
                    pagination_info = data.get('pagination', {})
                    safe_print(f"   🔍 API Response: {comments_count} comments, pagination: {bool(pagination_info)}")
                    
                    # Debug pagination structure
                    if pagination_info and pagination_info.get('after'):
                        after_value = pagination_info.get('after')
                        safe_print(f"   📄 Pagination.after type: {type(after_value).__name__}")
                        if isinstance(after_value, dict):
                            safe_print(f"      Keys: {list(after_value.keys())}")
                        else:
                            safe_print(f"      Value: {str(after_value)[:100]}")
                    
                    if comments_count == 0:
                        safe_print(f"   ⚠️ API returned 0 comments. Full response keys: {list(data.keys())}")
                        safe_print(f"   📍 URL requested: {url}")
                return data
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
                        # Check if user already exists (dùng username để tìm)
                        existing_user = users_collection.find_one({"username": user_name})
                        if not existing_user:
                            # Fetch full user info from API v3/users
                            user_data = self.fetch_and_map_user(user_name)
                            if user_data:
                                users_collection.insert_one(user_data)
                                safe_print(f"      ✅ Lưu user mới: {user_name}")
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lưu user: {e}")
        
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
