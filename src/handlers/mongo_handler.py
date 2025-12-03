"""
MongoDB handler - tất cả các operations liên quan đến MongoDB
"""
from src.utils import safe_print

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
                self.mongo_collection_chapter_contents = self.mongo_db["chapter_contents"]
                self.mongo_collection_websites = self.mongo_db["websites"]
                
                # Kiểm tra và tạo ScribbleHub website nếu chưa có
                scribblehub_id = self.ensure_scribblehub_website()
                if scribblehub_id:
                    self.scribblehub_website_id = scribblehub_id
                
                safe_print("✅ Đã kết nối MongoDB với 9 collections")
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
            existing = self.mongo_collection_stories.find_one({"web_story_id": web_story_id})
            return existing is not None
        except:
            return False
    
    def is_chapter_scraped(self, web_chapter_id):
        """Kiểm tra chapter đã được cào chưa (check theo web_chapter_id)"""
        if not web_chapter_id or not self.mongo_collection_chapters:
            return False
        try:
            existing = self.mongo_collection_chapters.find_one({"web_chapter_id": web_chapter_id})
            return existing is not None
        except:
            return False
    
    def is_review_scraped(self, web_review_id):
        """Kiểm tra review đã được cào chưa (check theo web_review_id)"""
        if not web_review_id or not self.mongo_collection_reviews:
            return False
        try:
            existing = self.mongo_collection_reviews.find_one({"web_review_id": web_review_id})
            return existing is not None
        except:
            return False
    
    def is_comment_scraped(self, web_comment_id):
        """Kiểm tra comment đã được cào chưa (check theo web_comment_id)"""
        if not web_comment_id or not self.mongo_collection_comments:
            return False
        try:
            existing = self.mongo_collection_comments.find_one({"web_comment_id": web_comment_id})
            return existing is not None
        except:
            return False
    
    def is_chapter_content_scraped(self, chapter_id):
        """Kiểm tra chapter content đã được cào chưa (check theo chapter_id)"""
        if not chapter_id or not self.mongo_collection_chapter_contents:
            return False
        try:
            existing = self.mongo_collection_chapter_contents.find_one({"chapter_id": chapter_id})
            return existing is not None
        except:
            return False
    
    # ========== Save methods ==========
    
    def save_story(self, story_data):
        """Lưu story vào MongoDB (có thể update nhiều lần khi có thêm chapters/reviews)"""
        if not story_data or not self.mongo_collection_stories:
            return
        
        try:
            existing = self.mongo_collection_stories.find_one({"web_story_id": story_data.get("web_story_id")})
            if existing:
                self.mongo_collection_stories.update_one(
                    {"web_story_id": story_data.get("web_story_id")},
                    {"$set": story_data}
                )
            else:
                self.mongo_collection_stories.insert_one(story_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu story vào MongoDB: {e}")
    
    def save_story_info(self, story_info_data):
        """Lưu story info vào MongoDB"""
        if not story_info_data or not self.mongo_collection_story_info:
            return
        
        try:
            existing = self.mongo_collection_story_info.find_one({"story_id": story_info_data.get("story_id")})
            if existing:
                self.mongo_collection_story_info.update_one(
                    {"story_id": story_info_data.get("story_id")},
                    {"$set": story_info_data}
                )
            else:
                self.mongo_collection_story_info.insert_one(story_info_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu story info vào MongoDB: {e}")
    
    def save_chapter(self, chapter_data):
        """Lưu chapter vào MongoDB ngay khi cào xong chapter và comments"""
        if not chapter_data or not self.mongo_collection_chapters:
            return
        
        try:
            existing = self.mongo_collection_chapters.find_one({"web_chapter_id": chapter_data.get("web_chapter_id")})
            if existing:
                self.mongo_collection_chapters.update_one(
                    {"web_chapter_id": chapter_data.get("web_chapter_id")},
                    {"$set": chapter_data}
                )
                safe_print(f"      🔄 Đã cập nhật chapter {chapter_data.get('web_chapter_id')} trong MongoDB")
            else:
                self.mongo_collection_chapters.insert_one(chapter_data)
                safe_print(f"      ✅ Đã lưu chapter {chapter_data.get('web_chapter_id')} vào MongoDB")
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lưu chapter vào MongoDB: {e}")
    
    def save_comment(self, comment_data):
        """Lưu comment vào MongoDB ngay khi cào xong"""
        if not comment_data or not self.mongo_collection_comments:
            return
        
        try:
            existing = self.mongo_collection_comments.find_one({"web_comment_id": comment_data.get("web_comment_id")})
            if existing:
                self.mongo_collection_comments.update_one(
                    {"web_comment_id": comment_data.get("web_comment_id")},
                    {"$set": comment_data}
                )
            else:
                self.mongo_collection_comments.insert_one(comment_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
    
    def save_review(self, review_data):
        """Lưu review vào MongoDB ngay khi cào xong"""
        if not review_data or not self.mongo_collection_reviews:
            return
        
        try:
            existing = self.mongo_collection_reviews.find_one({"web_review_id": review_data.get("web_review_id")})
            if existing:
                self.mongo_collection_reviews.update_one(
                    {"web_review_id": review_data.get("web_review_id")},
                    {"$set": review_data}
                )
            else:
                self.mongo_collection_reviews.insert_one(review_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu review vào MongoDB: {e}")
    
    def save_user(self, web_user_id, username):
        """
        Lưu user vào MongoDB ngay khi gặp web_user_id và username
        Args:
            web_user_id: User ID lấy từ web (URL)
            username: Tên người dùng
        Returns:
            user_id: ID được gen (rr_{uuid}) để dùng làm FK
        """
        from src.utils import generate_id
        
        if not web_user_id or not username or not self.mongo_collection_users:
            return None
        
        try:
            # Tìm user theo web_user_id
            existing = self.mongo_collection_users.find_one({"web_user_id": web_user_id})
            if existing:
                # Update nếu username thay đổi
                if existing.get("username") != username:
                    self.mongo_collection_users.update_one(
                        {"web_user_id": web_user_id},
                        {"$set": {"username": username}}
                    )
                return existing.get("id")  # Trả về id đã có
            else:
                # Tạo id mới
                user_id = generate_id()
                user_data = {
                    "id": user_id,  # Schema: id (khóa chính, format rr_{uuid})
                    "web_user_id": web_user_id,  # Schema: web_user_id (lấy từ URL)
                    "username": username  # Schema: username
                }
                self.mongo_collection_users.insert_one(user_data)
                return user_id  # Trả về id mới để dùng làm FK
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu user vào MongoDB: {e}")
            return None
    
    def save_score(self, score_id, overall_score="", style_score="", story_score="", grammar_score="", character_score="", review_id=None):
        """
        Lưu tất cả 5 scores vào MongoDB trong 1 document duy nhất (chỉ cho review)
        
        Args:
            score_id: ID được gen (rr_{uuid}) - khóa chính
            overall_score: Giá trị overall score
            style_score: Giá trị style score
            story_score: Giá trị story score
            grammar_score: Giá trị grammar score
            character_score: Giá trị character score
            review_id: FK to reviews (rr_{uuid})
        """
        if not score_id or not self.mongo_collection_scores:
            return
        
        try:
            score_data = {
                "id": score_id,  # Schema: id (khóa chính, format rr_{uuid})
                "overall_score": overall_score,  # Schema: overall score
                "style_score": style_score,  # Schema: style score
                "story_score": story_score,  # Schema: story score
                "grammar_score": grammar_score,  # Schema: grammar score
                "character_score": character_score  # Schema: character score
            }
            
            # Thêm FK review_id
            if review_id:
                score_data["review_id"] = review_id  # FK to reviews (rr_{uuid})
            
            # So sánh theo web_review_id: Tìm review theo review_id, lấy web_review_id, rồi tìm score
            web_review_id = None
            if review_id and self.mongo_collection_reviews:
                try:
                    review = self.mongo_collection_reviews.find_one({"id": review_id})
                    if review:
                        web_review_id = review.get("web_review_id")
                except:
                    pass
            
            # Nếu có web_review_id, tìm review theo web_review_id rồi lấy review_id để so sánh score
            if web_review_id and self.mongo_collection_reviews:
                try:
                    review_by_web_id = self.mongo_collection_reviews.find_one({"web_review_id": web_review_id})
                    if review_by_web_id:
                        existing_review_id = review_by_web_id.get("id")
                        # Tìm score theo review_id
                        existing = self.mongo_collection_scores.find_one({"review_id": existing_review_id})
                        if existing:
                            # Update nếu đã có
                            self.mongo_collection_scores.update_one(
                                {"review_id": existing_review_id},
                                {"$set": score_data}
                            )
                        else:
                            # Insert mới
                            self.mongo_collection_scores.insert_one(score_data)
                    else:
                        # Insert mới nếu không tìm thấy review
                        self.mongo_collection_scores.insert_one(score_data)
                except:
                    # Fallback: so sánh theo score_id nếu lỗi
                    existing = self.mongo_collection_scores.find_one({"id": score_id})
                    if existing:
                        self.mongo_collection_scores.update_one(
                            {"id": score_id},
                            {"$set": score_data}
                        )
                    else:
                        self.mongo_collection_scores.insert_one(score_data)
            else:
                # Fallback: so sánh theo score_id nếu không có web_review_id
                existing = self.mongo_collection_scores.find_one({"id": score_id})
                if existing:
                    self.mongo_collection_scores.update_one(
                        {"id": score_id},
                        {"$set": score_data}
                    )
                else:
                    self.mongo_collection_scores.insert_one(score_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu score vào MongoDB: {e}")
    
    def save_chapter_content(self, content_id, content, chapter_id):
        """
        Lưu chapter content vào MongoDB collection chapter_contents
        Args:
            content_id: ID của content (khóa chính tự gen - rr_{uuid})
            content: Nội dung chapter
            chapter_id: ID của chapter (FK - rr_{uuid})
        """
        if not content_id or not content or not chapter_id or not self.mongo_collection_chapter_contents:
            return
        
        try:
            content_data = {
                "id": content_id,  # Schema: id (khóa chính, format rr_{uuid}, tự gen)
                "content": content,  # Schema: content
                "chapter_id": chapter_id  # Schema: chapter id (FK - rr_{uuid})
            }
            
            # So sánh theo web_chapter_id: Tìm chapter theo chapter_id, lấy web_chapter_id, rồi tìm content
            web_chapter_id = None
            if chapter_id and self.mongo_collection_chapters:
                try:
                    chapter = self.mongo_collection_chapters.find_one({"id": chapter_id})
                    if chapter:
                        web_chapter_id = chapter.get("web_chapter_id")
                except:
                    pass
            
            # Nếu có web_chapter_id, tìm chapter theo web_chapter_id rồi lấy chapter_id để so sánh
            if web_chapter_id and self.mongo_collection_chapters:
                try:
                    chapter_by_web_id = self.mongo_collection_chapters.find_one({"web_chapter_id": web_chapter_id})
                    if chapter_by_web_id:
                        existing_chapter_id = chapter_by_web_id.get("id")
                        # Tìm content theo chapter_id
                        existing = self.mongo_collection_chapter_contents.find_one({"chapter_id": existing_chapter_id})
                        if existing:
                            # Update nếu đã có
                            self.mongo_collection_chapter_contents.update_one(
                                {"chapter_id": existing_chapter_id},
                                {"$set": content_data}
                            )
                        else:
                            # Insert mới
                            self.mongo_collection_chapter_contents.insert_one(content_data)
                    else:
                        # Insert mới nếu không tìm thấy chapter
                        self.mongo_collection_chapter_contents.insert_one(content_data)
                except:
                    # Fallback: so sánh theo chapter_id nếu lỗi
                    existing = self.mongo_collection_chapter_contents.find_one({"chapter_id": chapter_id})
                    if existing:
                        self.mongo_collection_chapter_contents.update_one(
                            {"chapter_id": chapter_id},
                            {"$set": content_data}
                        )
                    else:
                        self.mongo_collection_chapter_contents.insert_one(content_data)
            else:
                # Fallback: so sánh theo chapter_id nếu không có web_chapter_id
                existing = self.mongo_collection_chapter_contents.find_one({"chapter_id": chapter_id})
                if existing:
                    self.mongo_collection_chapter_contents.update_one(
                        {"chapter_id": chapter_id},
                        {"$set": content_data}
                    )
                else:
                    self.mongo_collection_chapter_contents.insert_one(content_data)
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lưu chapter content vào MongoDB: {e}")
    
    # ========== Get methods ==========
    
    def get_story_by_web_id(self, web_story_id):
        """Lấy story theo web_story_id"""
        if not web_story_id or not self.mongo_collection_stories:
            return None
        try:
            return self.mongo_collection_stories.find_one({"web_story_id": web_story_id})
        except:
            return None
    
    def get_chapter_by_web_id(self, web_chapter_id):
        """Lấy chapter theo web_chapter_id"""
        if not web_chapter_id or not self.mongo_collection_chapters:
            return None
        try:
            return self.mongo_collection_chapters.find_one({"web_chapter_id": web_chapter_id})
        except:
            return None
    
    def ensure_scribblehub_website(self):
        """Kiểm tra và tạo ScribbleHub website nếu chưa có, trả về website_id"""
        if not self.mongo_collection_websites:
            return None
        
        try:
            from src.utils import generate_id
            
            # Tìm website theo tên
            existing = self.mongo_collection_websites.find_one({"website_name": "ScribbleHub"})
            if existing:
                # Đã có, trả về website_id
                website_id = existing.get("website_id")
                return website_id
            else:
                # Chưa có, tạo mới với id tự tạo (uuid)
                website_id = generate_id()
                website_data = {
                    "website_id": website_id,
                    "website_name": "ScribbleHub"
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
            existing = self.mongo_collection_websites.find_one({"website_id": website_id})
            if existing:
                self.mongo_collection_websites.update_one(
                    {"website_id": website_id},
                    {"$set": {"website_name": website_name}}
                )
            else:
                website_data = {
                    "website_id": website_id,
                    "website_name": website_name
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
        
        return self.mongo_collection_websites.find_one({"website_id": website_id})
    
    def get_comment_by_web_id(self, web_comment_id):
        """Lấy comment theo web_comment_id"""
        if not web_comment_id or not self.mongo_collection_comments:
            return None
        try:
            return self.mongo_collection_comments.find_one({"web_comment_id": web_comment_id})
        except:
            return None

