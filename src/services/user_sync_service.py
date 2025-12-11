class UserSyncService:
    def __init__(self, db, user_scraper):
        self.db = db
        self.user_scraper = user_scraper
    def sync_user(self, story_id, api_story_data, api_chapters, api_comments_by_chapter):
        """
        Sync chapters and comments for a user/story, based on API data.
        """
        db_story = self.db["stories"].find_one({"storyId": story_id})
        if not db_story:
            from ..scrapers.base import safe_print
            safe_print(f"[UserSyncService] Không tìm thấy storyId={story_id} trong DB!")
            return
        db_total_chapters = db_story.get('totalChapters') or db_story.get('total_chapters')
        api_total_chapters = api_story_data.get('totalChapters') or api_story_data.get('total_chapters')
        if api_total_chapters is None:
            from ..scrapers.base import safe_print
            safe_print(f"[UserSyncService] Không lấy được totalChapters từ API!")
            return
        db_chapter_count = self.db["chapters"].count_documents({"storyId": story_id})
        if db_chapter_count < api_total_chapters:
            from ..scrapers.base import safe_print
            safe_print(f"[UserSyncService] DB chỉ có {db_chapter_count}/{api_total_chapters} chapters, tiến hành cào bổ sung...")
            for idx, ch in enumerate(api_chapters):
                chapter_id = ch.get('chapterId')
                if not chapter_id:
                    continue
                if self.db["chapters"].count_documents({"chapterId": chapter_id}) == 0:
                    self.db["chapters"].insert_one(ch)
                    safe_print(f"[UserSyncService] Đã thêm mới chapterId={chapter_id}")
        for ch in api_chapters:
            chapter_id = ch.get('chapterId')
            if not chapter_id:
                continue
            db_chapter = self.db["chapters"].find_one({"chapterId": chapter_id})
            db_total_comments = db_chapter.get('totalComments') if db_chapter else 0
            api_comments = api_comments_by_chapter.get(chapter_id, [])
            api_total_comments = len(api_comments)
            if db_total_comments != api_total_comments:
                from ..scrapers.base import safe_print
                safe_print(f"[UserSyncService] Chapter {chapter_id}: DB có {db_total_comments} comments, API có {api_total_comments} comments. Tiến hành update...")
                db_comments = list(self.db["comments"].find({"chapterId": chapter_id}))
                db_comment_ids = set(c.get('webCommentId') for c in db_comments if c.get('webCommentId'))
                api_comment_ids = set(c.get('webCommentId') for c in api_comments if c.get('webCommentId'))
                for c in db_comments:
                    cid = c.get('webCommentId')
                    if cid and cid not in api_comment_ids:
                        self.db["comments"].update_one({"_id": c["_id"]}, {"$set": {"isDeleted": True}})
                        safe_print(f"[UserSyncService] Đánh dấu comment đã xóa: {cid}")
                for c in api_comments:
                    cid = c.get('webCommentId')
                    if cid and cid not in db_comment_ids:
                        self.db["comments"].insert_one(c)
                        safe_print(f"[UserSyncService] Đã thêm comment mới: {cid}")
