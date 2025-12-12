from datetime import datetime

class CommentSyncService:
    def __init__(self, db, comment_scraper):
        self.db = db
        self.comment_scraper = comment_scraper

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
        # Determine internal chapterId from chapters collection if available
        chapter_id = None
        try:
            chap = self.db["chapters"].find_one({"webChapterId": str(web_chapter_id)})
            if chap and chap.get("chapterId"):
                chapter_id = chap.get("chapterId")
        except Exception:
            chapter_id = None

        # Comments collection historically keyed by chapterId (internal). If we
        # have chapterId, query by that; otherwise fallback to webChapterId field.
        if chapter_id:
            db_comments = list(self.db["comments"].find({"chapterId": str(chapter_id)}))
        else:
            db_comments = list(self.db["comments"].find({"webChapterId": web_chapter_id}))

        web_map = {c["webCommentId"]: c for c in web_comments_list}
        db_map = {c["webCommentId"]: c for c in db_comments}

        # Pass chapter_id so inserted comments include internal chapterId when available
        self._sync_new_comments(web_map, db_map, web_chapter_id, chapter_id)
        self._sync_edited_comments(web_map, db_map)
        self._sync_deleted_comments(web_map, db_map)

    def _sync_new_comments(self, web_map, db_map, web_chapter_id, chapter_id=None):
        for web_id, web_comment in web_map.items():
            if web_id not in db_map:
                # Ensure required fields for comments collection
                web_comment["webChapterId"] = web_chapter_id
                if chapter_id:
                    web_comment["chapterId"] = str(chapter_id)
                web_comment["isDeleted"] = False
                self.db["comments"].insert_one(web_comment)

    def _sync_edited_comments(self, web_map, db_map):
        for web_id in web_map:
            if web_id in db_map:
                web_text = web_map[web_id].get("content")
                db_text = db_map[web_id].get("content")
                if web_text != db_text:
                    self.db["comments"].update_one(
                        {"webCommentId": web_id},
                        {"$set": {
                            "content": web_text,
                            "editedAt": web_map[web_id].get("editedAt"),
                            "isEdited": True
                        }}
                    )

    def _sync_deleted_comments(self, web_map, db_map):
        # Đánh dấu isDeleted=True cho các comment đã bị xóa trên web, với COSOLOG
        for db_id, db_comment in db_map.items():
            if db_id not in web_map:
                self.db["comments"].update_one(
                    {"webCommentId": db_id},
                    {"$set": {
                        "isDeleted": True,
                        "deletedAt": datetime.utcnow()
                    }}
                )
                # COSOLOG for deleted comment
                from ..scrapers.base import safe_print
                safe_print(f"[COSOLOG] 🗑️ Đã phát hiện và đánh dấu comment đã xóa: webCommentId={db_id} (chapterId={db_comment.get('chapterId')})")
