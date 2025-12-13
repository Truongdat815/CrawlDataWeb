
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
import argparse
from .scraper_engine import WattpadScraper
from .scrapers.base import safe_print

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


def cli_full_sync():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-sync-chapter', help='Run full-sync (detect deletions) for given webChapterId')
    args = parser.parse_args()

    if args.full_sync_chapter:
        web_chapter_id = args.full_sync_chapter
        db = MongoClient(config.MONGODB_URI)[config.MONGODB_DB_NAME]
        scraper = WattpadScraper(db)
        # Initialize Playwright and scrapers
        try:
            scraper.start()
        except Exception:
            pass
        safe_print(f"🔁 Running full-sync for chapter {web_chapter_id}")
        comments = scraper.fetch_comments_from_api_v5(web_chapter_id, chapter_id=None, use_checkpoint=True, full_sync=True)
        safe_print(f"✅ Full-sync completed: fetched {len(comments)} comments")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cli_full_sync()
    else:
        main()
