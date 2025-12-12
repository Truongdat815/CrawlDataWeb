# -*- coding: utf-8 -*-
"""
DuplicateChecker – kiểm tra trùng lặp khi cào dữ liệu.
Dùng webStoryId / webChapterId / webCommentId làm khóa chính trong cơ sở dữ liệu.
"""

"""
    ĐÃ TỐI ƯU
    Chưa rõ totalChapter và chapter_count cái nào tối ưu hơn
"""
import logging
from ..utils.scraped_checker import ScrapedChecker
from ..scrapers.base import safe_print


class DuplicateChecker:
    """
        DuplicateChecker làm việc dựa trên các web* id:
        - webStoryId (chuỗi số, ví dụ: "163645533")
        - webChapterId (chuỗi số, ví dụ: "987654")
        - webCommentId (chuỗi)
    
        Ưu tiên sử dụng DB được truyền vào qua tham số `db`, 
        và dùng ScrapedChecker như một bộ nhớ đệm (cache) tùy chọn để tăng tốc độ kiểm tra.
    """

    def __init__(self, db):
        self.db = db
        # Try to build a cached checker for faster "story status" queries.
        try:
            self.cache = ScrapedChecker()
        except Exception:
            logging.exception("DuplicateChecker: failed to initialize ScrapedChecker cache")
            self.cache = None

    def should_crawl_chapter(self, web_chapter_id, force=False):
        if force:
            return True
        if not web_chapter_id:
            return True

        try:
            chapter = self.db["chapters"].find_one({"webChapterId": str(web_chapter_id)})
            if not chapter:
                return True  # chưa có metadata → phải crawl

            # Kiểm tra content
            if self._chapter_has_content(chapter):
                return False  # đã crawl

            return True  # chưa có nội dung
        except Exception:
            logging.exception("[DUP_CHECK] DB error in should_crawl_chapter")
            return True

    def check_chapter(self, web_chapter_id):
        if not web_chapter_id:
            return {"exists": False}

        try:
            chapter = self.db["chapters"].find_one({"webChapterId": str(web_chapter_id)})
            if not chapter:
                return {"exists": False}

            return {
                "exists": True,
                "ChapterId": chapter.get("chapterId"),
                "webChapterId": str(web_chapter_id),
                "has_content": self._chapter_has_content(chapter),
                "chapterName": chapter.get("chapterName")
            }
        except Exception:
            logging.exception("[DUP_CHECK] error in check_chapter")
            return {"exists": False}
    
    def check_story(self, web_story_id):
        """
        Trả về trạng thái của một truyện dựa trên webStoryId.

        Returns:
            dict  – giống cấu trúc của ScrapedChecker.get_story_status,  
                hoặc None nếu không tìm thấy.
        """

        if not web_story_id:
            return None

        try:
             # 1) Lấy truyện từ collection stories
            story = self.db["stories"].find_one({"webStoryId": str(web_story_id)})
            if not story:
                return None

            story_id = story.get("storyId")
            web_story_id_str = str(web_story_id)

            # 2) Lấy thông tin tổng chương nếu có từ document `stories` (ưu tiên)
            totalChapter = story.get("totalChapters")
            try:
                totalChapter = int(totalChapter) if totalChapter is not None else None
            except Exception:
                totalChapter = None

            # 3) Đếm chapters từ collection chapters (dùng làm fallback nếu story.totalChapters không có)
            latest = self.db["chapters"].find_one(
                            {"storyId": web_story_id_str},
                            sort=[("order", -1)],
                            projection={"order": 1}
                        )

            if totalChapter is not None:
                chapters_count = totalChapter
            else:
                chapters_count = latest["order"] if latest else 0

            # 4. Lấy danh sách chapterIds để đếm content và comments
            chapters_cursor = self.db["chapters"].find(
                                    {"storyId": str(web_story_id)},
                                    {"chapterId": 1}
                                )
            chapter_docs = list(chapters_cursor)
            chapter_ids = [ch.get("chapterId") for ch in chapter_docs if ch.get("chapterId")]

             # Đếm số content theo chapterId (schema đã chuẩn hoá).
            contents_count = self.db["chapterContents"].count_documents(
                                    {"chapterId": {"$in": chapter_ids}}
                                )

            # Count comments using chapterId
            comments_count = 0
            if chapter_ids:
                comments_count = self.db["comments"].count_documents({"chapterId": {"$in": chapter_ids}})

            # Lấy story Infor
            storyInfor = self.db["storyInfo"].find_one({"storyId": story_id})
            return {
                "exists": True,
                "storyId": story_id,
                "storyName": story.get("storyName"),
                "chapters_count": chapters_count,
                "chapters_with_content": contents_count,
                "comments_count": comments_count,
                "last_updated": story.get("lastUpdated")
            }
        except Exception as e:
            logging.exception("[DUP_CHECK] Lỗi khi check_story %s", web_story_id)
            return None

    def close(self):
        """Cleanup if needed (closes cached checker connection)."""
        try:
            if self.cache:
                self.cache.close()
        except Exception:
            logging.exception("DuplicateChecker.close: failed to close cache")

    def _chapter_has_content(self, chapter):
        """
        Kiểm tra chapter content tồn tại dựa trên chapterId hoặc webChapterId.
       

        Kiểm tra chapter đã có nội dung hay chưa.

        Ưu tiên kiểm tra theo chapterId (schema mới sau normalize):
        - chapterId
        - contentId dạng "{chapterId}_content"

        Nếu không có chapterId (data cũ), fallback sang kiểm tra theo webChapterId.

        Trả về:
            True  -> chapter đã có content trong DB
            False -> chưa có content
    """
        chapter_id = chapter.get("chapterId")

        # Ưu tiên chapterId
        if chapter_id:
            return self.db["chapterContents"].find_one(
                {"chapterId": str(chapter_id)}) is not None

