
# Entry point for the crawler
from .pipelines.chapter_pipeline import ChapterPipeline
from .scrapers.chapter import ChapterScraper
from .scrapers.chapter_content import ChapterContentScraper
from .scrapers.comment import CommentScraper
from .services.duplicate_checker import DuplicateChecker
from .services.comment_sync_service import CommentSyncService
from .services.user_sync_service import UserSyncService
from pymongo import MongoClient
from src import config

def main():
    db = MongoClient(config.MONGODB_URI)[config.MONGODB_DB_NAME]
    services = {
        "duplicate_checker": DuplicateChecker(db),
        "comment_service": CommentSyncService(db, CommentScraper(None, db)),
        "user_service": UserSyncService(db, None)
    }
    scrapers = {
        "chapter": ChapterScraper(None, db),
        "content": ChapterContentScraper(None, db)
    }
    pipeline = ChapterPipeline(db, scrapers, services)
    # Example usage
    chapter_meta = {
        "chapterId": "your_chapter_id",
        "webChapterId": "your_web_chapter_id"
        # Add other metadata fields as needed
    }
    pipeline.process(chapter_meta)

if __name__ == "__main__":
    main()
