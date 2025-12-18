from datetime import datetime
from ..scrapers.user import UserScraper

class CommentSyncService:
    def __init__(self, db, comment_scraper):
        self.db = db
        self.comment_scraper = comment_scraper
        # Per-run cache to avoid duplicate user API calls/inserts
        self._seen_usernames = set()

    def _get_text_field(self, doc):
        """Return canonical comment text searching known fields."""
        if not doc:
            return ""
        return doc.get("commentText") or ""

    def _ensure_text_fields(self, doc, text):
        """Ensure canonical and legacy text fields are present for compatibility."""
        doc["commentText"] = text

    def sync_comments(self, web_chapter_id, web_comments=None):
        """
        ĐÃ TỐI ƯU
        Đồng bộ:
        - Comment mới
        - Comment chỉnh sửa
        - Comment bị xóa
        """
        # Ưu tiên dùng danh sách comment được truyền vào. 
        # Nếu không có, thử gọi comment_scraper.fetch_comments() (nếu tồn tại).
        # Nếu không có cả hai → dùng danh sách rỗng.

        if web_comments is None:
            try:
                fetcher = getattr(self.comment_scraper, 'fetch_comments', None)
                if callable(fetcher):
                    web_comments = fetcher(web_chapter_id)
                else:
                    # No fetch available on comment_scraper; caller should pass web_comments
                    web_comments = []
            except Exception:
                web_comments = []

        # Chuẩn hóa web_comments thành một list (generator, dict hoặc iterable đều được convert).
        # Lưu vào web_comments_list để đảm bảo phía dưới luôn làm việc với list thống nhất.

        web_comments_list = []
        if isinstance(web_comments, list):
            web_comments_list = web_comments
        elif web_comments is None:
            web_comments_list = []
        elif isinstance(web_comments, dict):
            web_comments_list = [web_comments]
        else:
            try:
                web_comments_list = list(web_comments)  # type: ignore[arg-type]
            except Exception:
                web_comments_list = []
        # Resolve canonical webChapterId and internal chapterId from `chapters` collection
        chapter_id = None
        canonical_web_chapter_id = web_chapter_id
        try:
            # First assume the incoming id is a webChapterId
            chap = self.db["chapters"].find_one({"webChapterId": str(web_chapter_id)})
            if not chap:
                # Fallback: caller may have passed internal chapterId
                chap = self.db["chapters"].find_one({"chapterId": str(web_chapter_id)})
            if chap:
                chapter_id = chap.get("chapterId")
                # If DB has a stored webChapterId, use it as canonical
                if chap.get("webChapterId"):
                    canonical_web_chapter_id = str(chap.get("webChapterId"))
        except Exception:
            chapter_id = None
            canonical_web_chapter_id = web_chapter_id

        # Query comments by internal chapterId when available, otherwise by canonical webChapterId
        if chapter_id:
            db_comments = list(self.db["comments"].find({"chapterId": str(chapter_id)}))
        else:
            db_comments = list(self.db["comments"].find({"webChapterId": canonical_web_chapter_id}))

        web_map = {c.get("webCommentId"): c for c in web_comments_list}
        db_map = {c.get("webCommentId"): c for c in db_comments}

        # Pass canonical_web_chapter_id so inserted comments include the correct webChapterId
        self._sync_new_comments(web_map, db_map, canonical_web_chapter_id, chapter_id)
        self._sync_edited_comments(web_map, db_map)
        self._sync_deleted_comments(web_map, db_map)

    def _sync_new_comments(self, web_map, db_map, web_chapter_id, chapter_id=None):
        for web_id, web_comment in web_map.items():
            if web_id not in db_map:
                # Normalize text fields and ensure required meta fields
                text = self._get_text_field(web_comment) or ""
                self._ensure_text_fields(web_comment, text)
                web_comment["webChapterId"] = web_chapter_id
                if chapter_id:
                    web_comment["chapterId"] = str(chapter_id)
                web_comment["isDeleted"] = False
                self.db["comments"].insert_one(web_comment)

                # After inserting comment, ensure comment's user exists in users collection
                try:
                    user_name = web_comment.get("userName")
                    if user_name and user_name != "Anonymous" and "users" in self.db.list_collection_names():
                        # Deduplicate within this run
                        if user_name in self._seen_usernames:
                            continue

                        users_col = self.db.get_collection("users")
                        existing_user = None
                        try:
                            existing_user = users_col.find_one({"username": user_name})
                        except Exception:
                            existing_user = None

                        if existing_user:
                            self._seen_usernames.add(user_name)
                        else:
                            try:
                                page = getattr(self.comment_scraper, 'page', None)
                                user_scraper = UserScraper(page, self.db)
                                avatar = web_comment.get("_userAvatar")
                                user_scraper.save_user_to_mongo(user_name, user_name, avatar=avatar)
                                self._seen_usernames.add(user_name)
                            except Exception:
                                # Avoid retry storm in same run; mark seen anyway
                                self._seen_usernames.add(user_name)
                                continue
                except Exception:
                    # Non-fatal: continue processing other comments
                    pass

    def _sync_edited_comments(self, web_map, db_map):
        for web_id in web_map:
            if web_id in db_map:
                web_text = self._get_text_field(web_map[web_id])
                db_text = self._get_text_field(db_map[web_id])
                if web_text != db_text:
                    # Update canonical field `commentText` and keep `content` for compatibility
                    self.db["comments"].update_one(
                        {"webCommentId": web_id},
                        {"$set": {
                            "commentText": web_text,
                            "editedAt": web_map[web_id].get("editedAt"),
                            "isEdited": True
                        }}
                    )

    def _sync_deleted_comments(self, web_map, db_map):
        # Đánh dấu isDeleted=True cho các comment đã bị xóa trên web, với COSOLOG
        for db_id, db_comment in db_map.items():
            if db_id not in web_map:
                # Only mark as deleted; do not write `deletedAt` anymore
                self.db["comments"].update_one(
                    {"webCommentId": db_id},
                    {"$set": {
                        "isDeleted": True
                    }}
                )
                # COSOLOG for deleted comment
                from ..scrapers.base import safe_print
                safe_print(f"[COSOLOG] 🗑️ Đã phát hiện và đánh dấu comment đã xóa: webCommentId={db_id} (chapterId={db_comment.get('chapterId')})")
