"""
MongoDB handler - tất cả các operations liên quan đến MongoDB
"""
from src.utils import safe_print
from src.utils.hash_utils import create_chapter_hash, is_similar_hash, create_story_hash
from typing import Optional

# Import MongoDB
try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False


class MongoHandler:
    """Handler cho tất cả MongoDB operations"""
    
    def __init__(self):
        from src import config
        
        self.mongo_client = None
        self.mongo_db = None
        self.mongo_collection_stories = None
        self.mongo_collection_story_info = None
        self.mongo_collection_chapters = None
        self.mongo_collection_comments = None
        self.mongo_collection_reviews = None
        self.mongo_collection_users = None
        self.mongo_collection_scores = None
        self.mongo_collection_chapter_contents = None
        self.mongo_collection_websites = None
        self.scribblehub_website_id = None  # Lưu website_id của ScribbleHub
        
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                self.mongo_client = MongoClient(config.MONGODB_URI)
                self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                self.mongo_collection_stories = self.mongo_db[config.MONGODB_COLLECTION_STORIES]
                self.mongo_collection_story_info = self.mongo_db[config.MONGODB_COLLECTION_STORY_INFO]
                self.mongo_collection_chapters = self.mongo_db["chapters"]
                self.mongo_collection_comments = self.mongo_db["comments"]
                self.mongo_collection_reviews = self.mongo_db["reviews"]
                self.mongo_collection_users = self.mongo_db["users"]
                self.mongo_collection_scores = self.mongo_db["scores"]
                self.mongo_collection_chapter_contents = self.mongo_db["chapterContents"]
                self.mongo_collection_websites = self.mongo_db["websites"]
                
                # ✅ Tạo tất cả collections nếu chưa tồn tại (đảm bảo collections có sẵn)
                try:
                    existing_collections = self.mongo_db.list_collection_names()
                    collections_to_create = [
                        config.MONGODB_COLLECTION_STORIES,  # "stories"
                        config.MONGODB_COLLECTION_STORY_INFO,  # "storyInfo"
                        "chapters",
                        "comments",
                        "reviews",
                        "users",
                        "scores",
                        "chapterContents",
                        "websites"
                    ]
                    
                    created_count = 0
                    for coll_name in collections_to_create:
                        if coll_name not in existing_collections:
                            # Tạo collection bằng cách insert một document rỗng rồi xóa
                            test_doc = {"_init": True}
                            self.mongo_db[coll_name].insert_one(test_doc)
                            self.mongo_db[coll_name].delete_one({"_init": True})
                            created_count += 1
                            safe_print(f"      ✅ Đã tạo collection: {coll_name}")
                    
                    if created_count > 0:
                        safe_print(f"      ✅ Đã tạo {created_count} collections mới")
                    else:
                        safe_print(f"      ✅ Tất cả {len(collections_to_create)} collections đã tồn tại")
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi tạo collections: {e}")
                    import traceback
                    safe_print(f"      {traceback.format_exc()}")
                
                # Kiểm tra và tạo ScribbleHub website nếu chưa có
                scribblehub_id = self.ensure_scribblehub_website()
                if scribblehub_id:
                    self.scribblehub_website_id = scribblehub_id
                
                safe_print("✅ Đã kết nối MongoDB với 10 collections")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None
    
    def close(self):
        """Đóng kết nối MongoDB"""
        if self.mongo_client:
            self.mongo_client.close()
            safe_print("✅ Đã đóng kết nối MongoDB")
    
    # ========== Check methods ==========
    
    def is_story_scraped(self, web_story_id):
        """Kiểm tra story đã được cào chưa (check theo web_story_id)"""
        if not web_story_id or not self.mongo_collection_stories:
            return False
        try:
            existing = self.mongo_collection_stories.find_one({"webStoryId": web_story_id})
            return existing is not None
        except:
            return False
    
    def is_chapter_scraped(self, web_chapter_id):
        """Kiểm tra chapter đã được cào chưa (check theo web_chapter_id)"""
        if not web_chapter_id or not self.mongo_collection_chapters:
            return False
        try:
            existing = self.mongo_collection_chapters.find_one({"webChapterId": web_chapter_id})
            return existing is not None
        except:
            return False
    
    def is_review_scraped(self, web_review_id):
        """Kiểm tra review đã được cào chưa (check theo web_review_id)"""
        if not web_review_id or not self.mongo_collection_reviews:
            return False
        try:
            existing = self.mongo_collection_reviews.find_one({"webReviewId": web_review_id})
            return existing is not None
        except:
            return False
    
    def is_comment_scraped(self, web_comment_id):
        """Kiểm tra comment đã được cào chưa (check theo web_comment_id)"""
        if not web_comment_id or not self.mongo_collection_comments:
            return False
        try:
            existing = self.mongo_collection_comments.find_one({"webCommentId": web_comment_id})
            return existing is not None
        except:
            return False
    
    def is_chapter_content_scraped(self, chapter_id):
        """Kiểm tra chapter content đã được cào chưa (check theo chapter_id)"""
        if not chapter_id or not self.mongo_collection_chapter_contents:
            return False
        try:
            existing = self.mongo_collection_chapter_contents.find_one({"chapterId": chapter_id})
            return existing is not None
        except:
            return False
    
    # ========== Save methods ==========
    
    def save_story(self, story_data, chapter_1_content: Optional[str] = None, chapter_1_url: Optional[str] = None):
        """
        Lưu story vào MongoDB
        ✅ Check duplicate cross-platform bằng URL và hash chapter 1
        ✅ Lưu hash chapter 1 vào story document
        ✅ Lưu storyHash (hex string) vào story document
        ✅ Xử lý user_id -> userId conversion
        ✅ Thêm language: "English" nếu chưa có
        
        Args:
            story_data: Dict chứa story data
            chapter_1_content: Content của chapter 1 (optional, để check duplicate)
            chapter_1_url: URL của chapter 1 (optional, để check duplicate)
        """
        if not story_data or not self.mongo_collection_stories:
            return
        
        try:
            web_story_id = story_data.get("webStoryId")
            website_id = story_data.get("websiteId", "")
            
            # Đảm bảo không có user_id trong story_data (chỉ dùng userId)
            if "user_id" in story_data:
                # Nếu có user_id nhưng userId rỗng, copy sang userId
                if not story_data.get("userId") and story_data.get("user_id"):
                    story_data["userId"] = story_data["user_id"]
                # Xóa user_id
                del story_data["user_id"]
            
            # Đảm bảo có language
            if "language" not in story_data:
                story_data["language"] = "English"
            
            # Kiểm tra theo web_story_id trước (cùng nền tảng)
            existing = self.mongo_collection_stories.find_one({"webStoryId": web_story_id})
            if existing:
                # Update và lưu hash nếu có
                if chapter_1_content:
                    chapter_1_hash = create_chapter_hash(chapter_1_content)
                    story_data["chapter1Hash"] = chapter_1_hash
                    # ✅ Tạo storyHash bằng SimHash (500 từ đầu chapter 1)
                    story_hash = create_story_hash(chapter_1_content)
                    if story_hash:
                        story_data["storyHash"] = story_hash
                        safe_print(f"        ✅ Đã tạo storyHash (SimHash): {story_hash}")
                # ✅ Nếu chưa có storyHash, tự động lấy chapter 1 content từ DB và tạo
                elif not existing.get("storyHash"):
                    safe_print(f"        🔍 Story chưa có storyHash, đang lấy chapter 1 content từ DB...")
                    chapter_1_content_from_db = self.get_chapter_1_content(existing.get("storyId"))
                    if chapter_1_content_from_db:
                        story_hash = create_story_hash(chapter_1_content_from_db)
                        if story_hash:
                            story_data["storyHash"] = story_hash
                            safe_print(f"        ✅ Đã tạo storyHash từ chapter 1 trong DB (SimHash): {story_hash}")
                    else:
                        safe_print(f"        ⚠️ Không tìm thấy chapter 1 content trong DB, storyHash sẽ được tạo sau khi scrape chapter 1")
                self.mongo_collection_stories.update_one(
                    {"webStoryId": web_story_id},
                    {"$set": story_data}
                )
                safe_print(f"        🔄 Đã cập nhật story {web_story_id} trong MongoDB")
                return
            
            # ✅ Check duplicate cross-platform bằng URL và hash
            if chapter_1_content and chapter_1_url:
                duplicate_story = self.find_duplicate_by_hash(chapter_1_content, chapter_1_url, website_id)
                
                if duplicate_story:
                    # Tìm thấy duplicate → sử dụng story_id cũ
                    existing_story_id = duplicate_story.get("storyId")
                    story_data["storyId"] = existing_story_id
                    
                    # Lưu thêm web_story_id vào array
                    existing_web_ids = duplicate_story.get("webStoryIds", [])
                    if web_story_id not in existing_web_ids:
                        existing_web_ids.append(web_story_id)
                        story_data["webStoryIds"] = existing_web_ids
                    
                    # Lưu hash
                    chapter_1_hash = create_chapter_hash(chapter_1_content)
                    story_data["chapter1Hash"] = chapter_1_hash
                    # Tạo storyHash (hex string)
                    story_hash = create_story_hash(chapter_1_content)
                    if story_hash:
                        story_data["storyHash"] = story_hash
                    
                    self.mongo_collection_stories.update_one(
                        {"storyId": existing_story_id},
                        {"$set": story_data}
                    )
                    
                    safe_print(f"        🔗 Đã liên kết story với story_id cũ: {existing_story_id} (duplicate cross-platform)")
                    return
            
            # Không tìm thấy duplicate → insert mới
            # Lưu hash nếu có
            if chapter_1_content:
                chapter_1_hash = create_chapter_hash(chapter_1_content)
                story_data["chapter1Hash"] = chapter_1_hash
                # Tạo storyHash (hex string)
                story_hash = create_story_hash(chapter_1_content)
                if story_hash:
                    story_data["storyHash"] = story_hash
            
            self.mongo_collection_stories.insert_one(story_data)
            safe_print(f"        ✅ Đã lưu story mới {web_story_id} vào MongoDB")
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu story vào MongoDB: {e}")
    
    def save_story_info(self, story_info_data):
        """Lưu story info vào MongoDB"""
        if not story_info_data or not self.mongo_collection_story_info:
            return
        
        try:
            story_id = story_info_data.get("storyId")
            existing = self.mongo_collection_story_info.find_one({"storyId": story_id})
            
            # Log các giá trị trước khi lưu để debug
            safe_print(f"        🔍 DEBUG save_story_info - Giá trị TRƯỚC KHI lưu:")
            safe_print(f"           - averageViews: '{story_info_data.get('averageViews')}'")
            safe_print(f"           - totalWord: '{story_info_data.get('totalWord')}'")
            safe_print(f"           - averageWords: '{story_info_data.get('averageWords')}'")
            safe_print(f"           - pageViews: '{story_info_data.get('pageViews')}'")
            
            if existing:
                # ✅ Update: Sử dụng $set để ghi đè TẤT CẢ các field, kể cả giá trị rỗng
                self.mongo_collection_story_info.update_one(
                    {"storyId": story_id},
                    {"$set": story_info_data}
                )
                safe_print(f"        ✅ Đã CẬP NHẬT story_info {story_id} vào MongoDB")
                
                # Log giá trị SAU KHI update để verify
                updated = self.mongo_collection_story_info.find_one({"storyId": story_id})
                if updated:
                    safe_print(f"        🔍 DEBUG save_story_info - Giá trị SAU KHI lưu:")
                    safe_print(f"           - averageViews: '{updated.get('averageViews')}'")
                    safe_print(f"           - totalWord: '{updated.get('totalWord')}'")
                    safe_print(f"           - averageWords: '{updated.get('averageWords')}'")
                    safe_print(f"           - pageViews: '{updated.get('pageViews')}'")
            else:
                # Insert mới
                self.mongo_collection_story_info.insert_one(story_info_data)
                safe_print(f"        ✅ Đã INSERT story_info {story_id} vào MongoDB")
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu story info vào MongoDB: {e}")
            import traceback
            safe_print(f"        {traceback.format_exc()}")
    
    def save_chapter(self, chapter_data):
        """
        Lưu chapter vào MongoDB ngay khi cào xong chapter và comments
        ✅ Khóa chính: chapter_id (không phải "id")
        📦 Collection: "chapters"
        """
        if not chapter_data:
            safe_print(f"      ⚠️ Không có chapter_data để lưu")
            return
        
        if not self.mongo_collection_chapters:
            safe_print(f"      ⚠️ MongoDB collection 'chapters' chưa được khởi tạo")
            return
        
        try:
            web_chapter_id = chapter_data.get("webChapterId", "")
            chapter_name = chapter_data.get("chapterName", "")[:50]  # Lấy 50 ký tự đầu
            
            # Tìm theo web_chapter_id (unique identifier từ web)
            existing = self.mongo_collection_chapters.find_one({"webChapterId": web_chapter_id})
            if existing:
                self.mongo_collection_chapters.update_one(
                    {"webChapterId": web_chapter_id},
                    {"$set": chapter_data}
                )
                safe_print(f"      🔄 Đã cập nhật chapter trong MongoDB collection 'chapters': {web_chapter_id} - {chapter_name}...")
            else:
                self.mongo_collection_chapters.insert_one(chapter_data)
                safe_print(f"      ✅ Đã lưu chapter vào MongoDB collection 'chapters': {web_chapter_id} - {chapter_name}...")
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lưu chapter vào MongoDB collection 'chapters': {e}")
            import traceback
            safe_print(f"      {traceback.format_exc()}")
    
    def save_comment(self, comment_data):
        """
        Lưu comment vào MongoDB ngay khi cào xong
        ✅ Schema mới: commentId (PK), webCommentId, commentText, time, chapterId, userId, 
        replyToUserId, parentId, isRoot, react, websiteId, isDeleted
        ✅ Chỉ lưu khi có comment_text (có comment thật sự)
        ✅ Set isDeleted = false khi comment được tìm thấy trên web
        """
        if not comment_data or not self.mongo_collection_comments:
            return
        
        # ✅ Kiểm tra xem có comment_text không (có comment thật sự)
        comment_text = comment_data.get("commentText", "")
        if not comment_text or not comment_text.strip():
            # Không có comment text, không lưu
            return
        
        # ✅ Set isDeleted = false khi comment được tìm thấy trên web
        comment_data["isDeleted"] = False
        
        try:
            web_comment_id = comment_data.get("webCommentId", "")
            existing = self.mongo_collection_comments.find_one({"webCommentId": web_comment_id})
            if existing:
                self.mongo_collection_comments.update_one(
                    {"webCommentId": web_comment_id},
                    {"$set": comment_data}
                )
                # Không log để tránh spam log
                safe_print(f"        🔄 Đã cập nhật comment {comment_data.get('webCommentId')} trong MongoDB")
            else:
                self.mongo_collection_comments.insert_one(comment_data)
                safe_print(f"        ✅ Đã lưu comment {comment_data.get('webCommentId')} vào MongoDB")
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
    
    def save_review(self, review_data):
        """
        Lưu review vào MongoDB ngay khi cào xong
        ✅ Schema mới: review_id (PK), web_review_id, title, time, content, user_id, 
        chapter_id, story_id, score_id, is_review_swap, website_id, isDeleted
        ✅ Set isDeleted = false khi review được tìm thấy trên web
        """
        if not review_data or not self.mongo_collection_reviews:
            return
        
        # ✅ Kiểm tra xem review_data có dữ liệu hợp lệ không
        # Nếu không có web_review_id hoặc các field quan trọng, không lưu
        if not review_data.get("webReviewId") and not review_data.get("reviewId"):
            return
        
        # ✅ Set isDeleted = false khi review được tìm thấy trên web
        review_data["isDeleted"] = False
        
        try:
            existing = self.mongo_collection_reviews.find_one({"webReviewId": review_data.get("webReviewId")})
            if existing:
                self.mongo_collection_reviews.update_one(
                    {"webReviewId": review_data.get("webReviewId")},
                    {"$set": review_data}
                )
                safe_print(f"        🔄 Đã cập nhật review {review_data.get('webReviewId')} trong MongoDB")
            else:
                self.mongo_collection_reviews.insert_one(review_data)
                safe_print(f"        ✅ Đã lưu review {review_data.get('webReviewId')} vào MongoDB")
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu review vào MongoDB: {e}")
    
    def _to_number_or_none(self, value):
        """Helper function để convert value thành number hoặc None"""
        if value is None:
            return None
        try:
            # Thử convert string thành int
            if isinstance(value, str):
                # Loại bỏ dấu phẩy và khoảng trắng
                cleaned = value.replace(",", "").replace(" ", "").strip()
                if cleaned.isdigit():
                    return int(cleaned)
                return None
            elif isinstance(value, (int, float)):
                return int(value)
            return None
        except:
            return None
    
    def save_user(self, web_user_id, username, user_url=None, created_date=None, gender=None, location=None, 
                  followers=None, following=None, comments=None, bio=None, favorites=None, ratings=None,
                  reviews=None, series=None, total_words=None, reviews_received=None):
        """
        Lưu user vào MongoDB ngay khi gặp web_user_id và username
        ✅ Schema: userId, webUserId, username, userUrl, createdDate, gender, 
        location, followers, following, comments, bio, favorites, ratings, reviews,
        numberOfStories, totalWords, totalReviewsReceived, totalRatingsReceived, totalFavoritesReceived
        Args:
            web_user_id: User ID lấy từ web (URL)
            username: Tên người dùng
            user_url: URL của user profile
            created_date: Ngày tạo tài khoản
            gender: Giới tính
            location: Địa điểm
            followers: Số lượng followers
            following: Số lượng following
            comments: Số lượng comments
            bio: Tiểu sử
            favorites: Số lượng favorites
            ratings: Số lượng ratings
            reviews: Số reviews user đã viết (sẽ map thành reviews)
            series: Số series (sẽ map thành numberOfStories)
            total_words: Tổng số từ
            reviews_received: Số reviews nhận được (sẽ map thành totalReviewsReceived)
        Returns:
            user_id: ID được gen (sh_{uuid}) để dùng làm FK
        """
        from src.utils import generate_id
        
        if not web_user_id or not username or not self.mongo_collection_users:
            return None
        
        # Helper function để convert empty string thành None
        def to_none_if_empty(value):
            if value == "" or value == '':
                return None
            return value
        
        try:
            # Convert empty strings thành None
            user_url = to_none_if_empty(user_url) if user_url else None
            created_date = to_none_if_empty(created_date) if created_date else None
            # followers, following, comments đã là int hoặc None từ user_handler, giữ nguyên
            # bio đã được xử lý trong user_handler, giữ nguyên
            
            # Tìm user theo web_user_id
            existing = self.mongo_collection_users.find_one({"webUserId": web_user_id})
            
            # Debug: In giá trị nhận được
            safe_print(f"        🔍 DEBUG save_user: Nhận được giá trị:")
            safe_print(f"           - user_url: {user_url} (type: {type(user_url).__name__})")
            safe_print(f"           - created_date: {created_date} (type: {type(created_date).__name__})")
            safe_print(f"           - followers: {followers} (type: {type(followers).__name__})")
            safe_print(f"           - following: {following} (type: {type(following).__name__})")
            safe_print(f"           - comments: {comments} (type: {type(comments).__name__})")
            safe_print(f"           - bio: {bio[:50] + '...' if bio and len(bio) > 50 else bio} (type: {type(bio).__name__})")
            
            if existing:
                # ✅ Update tất cả fields để đảm bảo schema nhất quán (theo MongoDB schema)
                update_data = {
                    "username": username,  # ✅ Luôn update username
                    "webUserId": web_user_id if web_user_id else None,  # ✅ null hoặc string
                    "userUrl": user_url if user_url is not None else None,  # ✅ string hoặc null
                    "createdDate": created_date if created_date is not None else None,  # ✅ string hoặc null
                    "gender": gender if gender is not None else None,  # ✅ string hoặc null
                    "location": location if location is not None else None,  # ✅ string hoặc null
                    "followers": self._to_number_or_none(followers),  # ✅ number hoặc null
                    "following": self._to_number_or_none(following),  # ✅ number hoặc null
                    "comments": self._to_number_or_none(comments),  # ✅ null hoặc number
                    "bio": bio if bio is not None else None,  # ✅ string hoặc null
                    "favorites": None,  # ✅ null (theo schema)
                    "ratings": None,  # ✅ null (theo schema)
                    "reviews": self._to_number_or_none(reviews),  # ✅ Số reviews user đã viết (number hoặc null)
                    "numberOfStories": self._to_number_or_none(series),  # ✅ number hoặc null
                    "totalWords": self._to_number_or_none(total_words),  # ✅ null hoặc number
                    "totalReviewsReceived": self._to_number_or_none(reviews_received),  # ✅ null hoặc number
                    "totalRatingsReceived": self._to_number_or_none(ratings),  # ✅ number hoặc null
                    "totalFavoritesReceived": self._to_number_or_none(favorites),  # ✅ null hoặc number
                }
                
                # Xóa các field cũ không cần thiết
                unset_data = {}
                fields_to_remove = ["last_active", "birthday", "homepage", "series", "total_pageviews", "reviews_received", "readers"]
                for field in fields_to_remove:
                    if field in existing:
                        unset_data[field] = ""
                
                if update_data or unset_data:
                    update_query = {}
                    if update_data:
                        update_query["$set"] = update_data
                    if unset_data:
                        update_query["$unset"] = unset_data
                    self.mongo_collection_users.update_one(
                        {"webUserId": web_user_id},
                        update_query
                    )
                return existing.get("userId") or existing.get("id")  # Trả về user_id (tương thích với cả cũ và mới)
            else:
                # Tạo id mới - chỉ lưu các field được yêu cầu
                user_id = generate_id()
                # ✅ Đảm bảo tất cả fields khớp với MongoDB schema (theo hình ảnh):
                # userId: string (PK) ✅
                # webUserId: null hoặc string ✅
                # username: string ✅
                # userUrl: string hoặc null ✅
                # createdDate: string hoặc null ✅
                # gender: string hoặc null ✅
                # location: string hoặc null ✅
                # followers: number hoặc null ✅
                # following: number hoặc null ✅
                # comments: null hoặc number ✅
                # bio: string hoặc null ✅
                # favorites: null ✅
                # ratings: null ✅
                # reviews: null ✅
                # numberOfStories: number hoặc null ✅
                # totalWords: null hoặc number ✅
                # totalReviewsReceived: null hoặc number ✅
                # totalRatingsReceived: number hoặc null ✅
                # totalFavoritesReceived: null hoặc number ✅
                user_data = {
                    "userId": user_id,  # ✅ string (PK)
                    "webUserId": web_user_id if web_user_id else None,  # ✅ null hoặc string
                    "username": username,  # ✅ string
                    "userUrl": user_url if user_url is not None else None,  # ✅ string hoặc null
                    "createdDate": created_date if created_date is not None else None,  # ✅ string hoặc null
                    "gender": gender if gender is not None else None,  # ✅ string hoặc null
                    "location": location if location is not None else None,  # ✅ string hoặc null
                    "followers": self._to_number_or_none(followers),  # ✅ number hoặc null
                    "following": self._to_number_or_none(following),  # ✅ number hoặc null
                    "comments": self._to_number_or_none(comments),  # ✅ null hoặc number
                    "bio": bio if bio is not None else None,  # ✅ string hoặc null
                    "favorites": None,  # ✅ null (theo schema)
                    "ratings": None,  # ✅ null (theo schema)
                    "reviews": self._to_number_or_none(reviews),  # ✅ Số reviews user đã viết (number hoặc null)
                    "numberOfStories": self._to_number_or_none(series),  # ✅ number hoặc null
                    "totalWords": self._to_number_or_none(total_words),  # ✅ null hoặc number
                    "totalReviewsReceived": self._to_number_or_none(reviews_received),  # ✅ null hoặc number
                    "totalRatingsReceived": self._to_number_or_none(ratings),  # ✅ number hoặc null
                    "totalFavoritesReceived": self._to_number_or_none(favorites),  # ✅ null hoặc number
                }
                
                self.mongo_collection_users.insert_one(user_data)
                return user_id  # Trả về user_id mới để dùng làm FK
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu user vào MongoDB: {e}")
            return None
    
    def save_score(self, score_id, overall_score="", style_score="", story_score="", grammar_score="", character_score="", review_id=None):
        """
        Lưu score vào MongoDB
        ✅ Schema: scoreId (PK), overallScore, styleScore, storyScore, grammarScore, characterScore, reviewId
        ✅ Chỉ lưu khi có ít nhất 1 score không rỗng (có review)
        
        Args:
            score_id: ID của score (PK)
            overall_score: Overall score
            style_score: Style score
            story_score: Story score
            grammar_score: Grammar score
            character_score: Character score
            review_id: ID của review liên quan (FK, optional)
        """
        if not score_id or not self.mongo_collection_scores:
            return
        
        # ✅ Luôn lưu score nếu có review_id (để link score với review)
        # Ngay cả khi không có score nào, vẫn lưu để có reviewId link
        try:
            score_data = {
                "scoreId": score_id,  # Khóa chính
                "overallScore": overall_score if overall_score and overall_score.strip() else None,
                "styleScore": style_score if style_score and style_score.strip() else None,
                "storyScore": story_score if story_score and story_score.strip() else None,
                "grammarScore": grammar_score if grammar_score and grammar_score.strip() else None,
                "characterScore": character_score if character_score and character_score.strip() else None,
                "reviewId": review_id  # Link đến review (FK) - luôn có khi lưu từ review
            }
            
            # Tìm score theo score_id
            existing = self.mongo_collection_scores.find_one({"scoreId": score_id})
            if existing:
                # Update nếu đã có
                self.mongo_collection_scores.update_one(
                    {"scoreId": score_id},
                    {"$set": score_data}
                )
                safe_print(f"        🔄 Đã cập nhật score {score_id} trong MongoDB")
            else:
                # Insert mới
                self.mongo_collection_scores.insert_one(score_data)
                safe_print(f"        ✅ Đã lưu score {score_id} vào MongoDB")
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu score vào MongoDB: {e}")
    
    def save_chapter_content(self, content_id, content, chapter_id):
        """
        Lưu chapter content vào MongoDB collection chapter_contents
        📦 Collection: "chapter_contents"
        Args:
            content_id: ID của content (khóa chính tự gen - rr_{uuid})
            content: Nội dung chapter
            chapter_id: ID của chapter (FK - rr_{uuid})
        """
        if not content_id or not content or not chapter_id:
            safe_print(f"      ⚠️ Không có đủ thông tin để lưu chapter content (content_id: {content_id}, chapter_id: {chapter_id}, content length: {len(content) if content else 0})")
            return
        
        if not self.mongo_collection_chapter_contents:
            safe_print(f"      ⚠️ MongoDB collection 'chapter_contents' chưa được khởi tạo")
            return
        
        try:
            content_data = {
                "contentId": content_id,  # Schema: contentId (khóa chính, format sh_{uuid}, tự gen)
                "content": content,  # Schema: content
                "chapterId": chapter_id  # Schema: chapter id (FK - sh_{uuid})
            }
            
            # So sánh theo web_chapter_id: Tìm chapter theo chapter_id, lấy web_chapter_id, rồi tìm content
            web_chapter_id = None
            if chapter_id and self.mongo_collection_chapters:
                try:
                    chapter = self.mongo_collection_chapters.find_one({"chapterId": chapter_id})
                    if chapter:
                        web_chapter_id = chapter.get("webChapterId")
                except:
                    pass
            
            # Nếu có web_chapter_id, tìm chapter theo web_chapter_id rồi lấy chapter_id để so sánh
            if web_chapter_id and self.mongo_collection_chapters:
                try:
                    chapter_by_web_id = self.mongo_collection_chapters.find_one({"webChapterId": web_chapter_id})
                    if chapter_by_web_id:
                        existing_chapter_id = chapter_by_web_id.get("chapterId")
                        # Tìm content theo chapter_id
                        existing = self.mongo_collection_chapter_contents.find_one({"chapterId": existing_chapter_id})
                        if existing:
                            # Update nếu đã có
                            self.mongo_collection_chapter_contents.update_one(
                                {"chapterId": existing_chapter_id},
                                {"$set": content_data}
                            )
                        else:
                            # Insert mới
                            self.mongo_collection_chapter_contents.insert_one(content_data)
                            safe_print(f"      ✅ Đã lưu chapter content vào MongoDB collection 'chapter_contents' (chapter_id: {chapter_id}, content length: {len(content)} ký tự)")
                    else:
                        # Insert mới nếu không tìm thấy chapter
                        self.mongo_collection_chapter_contents.insert_one(content_data)
                        safe_print(f"      ✅ Đã lưu chapter content vào MongoDB collection 'chapter_contents' (chapter_id: {chapter_id}, content length: {len(content)} ký tự)")
                except Exception as e:
                    # Fallback: so sánh theo chapter_id nếu lỗi
                    existing = self.mongo_collection_chapter_contents.find_one({"chapterId": chapter_id})
                    if existing:
                        self.mongo_collection_chapter_contents.update_one(
                            {"chapterId": chapter_id},
                            {"$set": content_data}
                        )
                        safe_print(f"      🔄 Đã cập nhật chapter content trong MongoDB collection 'chapter_contents' (chapter_id: {chapter_id})")
                    else:
                        self.mongo_collection_chapter_contents.insert_one(content_data)
                        safe_print(f"      ✅ Đã lưu chapter content vào MongoDB collection 'chapter_contents' (chapter_id: {chapter_id}, content length: {len(content)} ký tự)")
            else:
                # Fallback: so sánh theo chapter_id nếu không có web_chapter_id
                existing = self.mongo_collection_chapter_contents.find_one({"chapterId": chapter_id})
                if existing:
                    self.mongo_collection_chapter_contents.update_one(
                        {"chapterId": chapter_id},
                        {"$set": content_data}
                    )
                    safe_print(f"      🔄 Đã cập nhật chapter content trong MongoDB collection 'chapter_contents' (chapter_id: {chapter_id})")
                else:
                    self.mongo_collection_chapter_contents.insert_one(content_data)
                    safe_print(f"      ✅ Đã lưu chapter content vào MongoDB collection 'chapter_contents' (chapter_id: {chapter_id}, content length: {len(content)} ký tự)")
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lưu chapter content vào MongoDB collection 'chapter_contents': {e}")
            import traceback
            safe_print(f"      {traceback.format_exc()}")
    
    # ========== Get methods ==========
    
    def get_story_by_web_id(self, web_story_id):
        """Lấy story theo web_story_id"""
        if not web_story_id or not self.mongo_collection_stories:
            return None
        try:
            return self.mongo_collection_stories.find_one({"webStoryId": web_story_id})
        except:
            return None
    
    def get_chapter_by_web_id(self, web_chapter_id):
        """Lấy chapter theo web_chapter_id"""
        if not web_chapter_id or not self.mongo_collection_chapters:
            return None
        try:
            return self.mongo_collection_chapters.find_one({"webChapterId": web_chapter_id})
        except:
            return None
    
    def get_chapter_1_content(self, story_id: str) -> Optional[str]:
        """
        Lấy content của chapter 1 từ story_id
        
        Args:
            story_id: ID của story
        
        Returns:
            Content của chapter 1 hoặc None
        """
        if not story_id or not self.mongo_collection_chapters:
            return None
        
        try:
            # Tìm chapter 1 (order = 1 hoặc order = "1")
            chapter = self.mongo_collection_chapters.find_one({
                "storyId": story_id,
                "$or": [
                    {"order": 1},
                    {"order": "1"}
                ]
            })
            
            if not chapter:
                return None
            
            chapter_id = chapter.get("chapterId")
            if not chapter_id or not self.mongo_collection_chapter_contents:
                return None
            
            # Lấy content
            content_doc = self.mongo_collection_chapter_contents.find_one({"chapterId": chapter_id})
            if content_doc:
                return content_doc.get("content", "")
            
            return None
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapter 1 content: {e}")
            return None
    
    def get_chapter_1_url(self, story_id: str) -> Optional[str]:
        """
        Lấy URL của chapter 1 từ story_id
        
        Args:
            story_id: ID của story
        
        Returns:
            URL của chapter 1 hoặc None
        """
        if not story_id or not self.mongo_collection_chapters:
            return None
        
        try:
            # Tìm chapter 1
            chapter = self.mongo_collection_chapters.find_one({
                "storyId": story_id,
                "$or": [
                    {"order": 1},
                    {"order": "1"}
                ]
            })
            
            if chapter:
                return chapter.get("chapterUrl", "")
            
            return None
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapter 1 URL: {e}")
            return None
    
    def find_duplicate_by_hash(self, chapter_1_content: str, chapter_1_url: str, website_id: str):
        """
        Tìm story duplicate dựa trên:
        1. Check URL chapter 1 trước (nếu trùng → duplicate)
        2. Nếu URL không trùng → check hash của 500 từ đầu chapter 1
        
        Args:
            chapter_1_content: Content của chapter 1 (từ story mới)
            chapter_1_url: URL của chapter 1 (từ story mới)
            website_id: ID của website hiện tại (để loại trừ)
        
        Returns:
            Story duplicate nếu tìm thấy, None nếu không
        """
        if not chapter_1_content or not self.mongo_collection_stories:
            return None
        
        try:
            # Bước 1: Check URL chapter 1 trước
            if chapter_1_url:
                # Tìm chapter có cùng URL (từ các website khác)
                if self.mongo_collection_chapters:
                    chapter_with_same_url = self.mongo_collection_chapters.find_one({
                        "chapterUrl": chapter_1_url,
                        "storyId": {"$exists": True}
                    })
                    
                    if chapter_with_same_url:
                        story_id = chapter_with_same_url.get("storyId")
                        # Lấy story từ story_id
                        story = self.mongo_collection_stories.find_one({"storyId": story_id})
                        if story and story.get("websiteId") != website_id:
                            safe_print(f"        🔗 Tìm thấy duplicate qua URL chapter 1: {story.get('storyName')}")
                            return story
            
            # Bước 2: Check hash nếu URL không trùng
            # Tạo hash cho chapter 1 mới
            new_hash = create_chapter_hash(chapter_1_content)
            if not new_hash:
                return None
            
            # Lấy tất cả stories từ các website khác
            all_stories = self.mongo_collection_stories.find({
                "websiteId": {"$ne": website_id},
                "chapter1Hash": {"$exists": True, "$ne": None}  # Chỉ check stories đã có hash
            })
            
            for story in all_stories:
                existing_hash = story.get("chapter1Hash")
                if existing_hash and isinstance(existing_hash, int):
                    # So sánh hash với độ lệch <= 3 bit
                    if is_similar_hash(new_hash, existing_hash, max_distance=3):
                        safe_print(f"        🔗 Tìm thấy duplicate qua hash (độ lệch <= 3 bit): {story.get('storyName')}")
                        return story
            
            return None
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi tìm duplicate bằng hash: {e}")
            return None
    
    def ensure_scribblehub_website(self):
        """Kiểm tra và tạo ScribbleHub website nếu chưa có, trả về website_id"""
        if not self.mongo_collection_websites:
            return None
        
        try:
            from src.utils import generate_id
            
            # Tìm website theo tên
            existing = self.mongo_collection_websites.find_one({"websiteName": "ScribbleHub"})
            if existing:
                # Đã có, trả về website_id
                website_id = existing.get("websiteId")
                return website_id
            else:
                # Chưa có, tạo mới với id tự tạo (uuid)
                website_id = generate_id()
                website_data = {
                    "websiteId": website_id,
                    "websiteName": "ScribbleHub"
                }
                self.mongo_collection_websites.insert_one(website_data)
                safe_print(f"✅ Đã tạo website ScribbleHub với website_id = {website_id}")
                return website_id
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi đảm bảo ScribbleHub website: {e}")
            return None
    
    def save_website(self, website_id, website_name):
        """Lưu website vào MongoDB (update nếu đã có, insert nếu chưa)"""
        if not website_id or not website_name or not self.mongo_collection_websites:
            return None
        
        try:
            existing = self.mongo_collection_websites.find_one({"websiteId": website_id})
            if existing:
                self.mongo_collection_websites.update_one(
                    {"websiteId": website_id},
                    {"$set": {"websiteName": website_name}}
                )
            else:
                website_data = {
                    "websiteId": website_id,
                    "websiteName": website_name
                }
                self.mongo_collection_websites.insert_one(website_data)
            return website_id
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu website vào MongoDB: {e}")
            return None
    
    def get_website_by_id(self, website_id):
        """Lấy website theo website_id"""
        if not website_id or not self.mongo_collection_websites:
            return None
        
        return self.mongo_collection_websites.find_one({"websiteId": website_id})
    
    def update_deleted_comments(self, chapter_id, web_comment_ids_from_web):
        """
        So sánh comments trong DB với comments trên web
        Nếu comment nào có trong DB nhưng không có trên web → cập nhật isDeleted = true
        
        Args:
            chapter_id: ID của chapter (để lọc comments theo chapter)
            web_comment_ids_from_web: List các web_comment_id tìm thấy trên web
        """
        if not chapter_id or not self.mongo_collection_comments:
            return
        
        try:
            # Lấy tất cả comments của chapter từ DB
            db_comments = self.mongo_collection_comments.find({"chapterId": chapter_id})
            
            web_comment_ids_set = set(web_comment_ids_from_web) if web_comment_ids_from_web else set()
            deleted_count = 0
            
            for db_comment in db_comments:
                web_comment_id = db_comment.get("webCommentId")
                if web_comment_id and web_comment_id not in web_comment_ids_set:
                    # Comment có trong DB nhưng không có trên web → đánh dấu deleted
                    self.mongo_collection_comments.update_one(
                        {"webCommentId": web_comment_id},
                        {"$set": {"isDeleted": True}}
                    )
                    deleted_count += 1
            
            if deleted_count > 0:
                safe_print(f"        🗑️  Đã đánh dấu {deleted_count} comments là deleted (không còn trên web)")
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi cập nhật deleted comments: {e}")
    
    def update_deleted_reviews(self, story_id, web_review_ids_from_web):
        """
        So sánh reviews trong DB với reviews trên web
        Nếu review nào có trong DB nhưng không có trên web → cập nhật isDeleted = true
        
        Args:
            story_id: ID của story (để lọc reviews theo story)
            web_review_ids_from_web: List các web_review_id tìm thấy trên web
        """
        if not story_id or not self.mongo_collection_reviews:
            return
        
        try:
            # Lấy tất cả reviews của story từ DB
            db_reviews = self.mongo_collection_reviews.find({"storyId": story_id})
            
            web_review_ids_set = set(web_review_ids_from_web) if web_review_ids_from_web else set()
            deleted_count = 0
            
            for db_review in db_reviews:
                web_review_id = db_review.get("webReviewId")
                if web_review_id and web_review_id not in web_review_ids_set:
                    # Review có trong DB nhưng không có trên web → đánh dấu deleted
                    self.mongo_collection_reviews.update_one(
                        {"webReviewId": web_review_id},
                        {"$set": {"isDeleted": True}}
                    )
                    deleted_count += 1
            
            if deleted_count > 0:
                safe_print(f"        🗑️  Đã đánh dấu {deleted_count} reviews là deleted (không còn trên web)")
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi cập nhật deleted reviews: {e}")
    
    def get_comment_by_web_id(self, web_comment_id):
        """Lấy comment theo web_comment_id"""
        if not web_comment_id or not self.mongo_collection_comments:
            return None
        try:
            return self.mongo_collection_comments.find_one({"webCommentId": web_comment_id})
        except:
            return None
    
