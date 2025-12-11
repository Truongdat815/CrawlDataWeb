
# Chapter pipeline: orchestrates chapter crawling and syncing
from ..services.duplicate_checker import DuplicateChecker
from ..services.comment_sync_service import CommentSyncService
from ..services.user_sync_service import UserSyncService
from ..scrapers.chapter import ChapterScraper
from ..scrapers.chapter_content import ChapterContentScraper
from ..scrapers.comment import CommentScraper

class ChapterPipeline:
    def __init__(self, db, scrapers, services):
        self.db = db
        self.duplicate_checker = services["duplicate_checker"]
        self.comment_service = services["comment_service"]
        self.user_service = services["user_service"]
        self.chapter_scraper = scrapers["chapter"]
        self.content_scraper = scrapers["content"]

    def process(self, chapter_meta):
        chapter_id = chapter_meta["chapterId"]
        web_chapter_id = chapter_meta["webChapterId"]

        # 1️⃣ LUÔN LƯU METADATA
        if hasattr(self.chapter_scraper, "save_meta"):
            self.chapter_scraper.save_meta(chapter_meta)

        # 2️⃣ CRAWL CONTENT NẾU CẦN
        # Use webChapterId for duplicate checks
        should_crawl = self.duplicate_checker.should_crawl_chapter(web_chapter_id)
        if should_crawl:
            content = self.content_scraper.fetch_content(web_chapter_id)
            self.content_scraper.save_content(chapter_id, content)

        # 3️⃣ LUÔN SYNC COMMENT
        self.comment_service.sync_comments(web_chapter_id)

        # 4️⃣ LUÔN SYNC USER
        if hasattr(self.user_service, "sync_users_from_comments"):
            self.user_service.sync_users_from_comments(web_chapter_id)
