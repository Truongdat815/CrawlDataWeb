
# Chapter pipeline: orchestrates chapter crawling and syncing
from ..services.duplicate_checker import DuplicateChecker
from ..services.comment_sync_service import CommentSyncService
from ..services.user_sync_service import UserSyncService
from ..scrapers.chapter import ChapterScraper
from ..scrapers.chapter_content import ChapterContentScraper
from ..scrapers.comment import CommentScraper
from ..utils.checkpoint import load_checkpoint, save_checkpoint
from ..scrapers.base import safe_print

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
        # Update chapters checkpoint totals for processed chapters
        try:
            # Determine story id
            story_id = chapter_meta.get('storyId')
            if not story_id and hasattr(self, 'db') and self.db is not None:
                try:
                    col = self.db.get_collection('chapters') if hasattr(self.db, 'get_collection') else self.db['chapters']
                    doc = col.find_one({'chapterId': chapter_id})
                    if doc:
                        story_id = doc.get('storyId')
                except Exception:
                    story_id = None

            if story_id:
                try:
                    ckp = load_checkpoint(str(story_id), kind='chapters') or {}
                    payload = ckp.get('payload', {}) if isinstance(ckp, dict) else {}
                    chapters_totals = payload.get('chapters_totals', {}) if isinstance(payload, dict) else {}
                    # Use totalComments field from chapter_meta (fallback to 0)
                    total = int(chapter_meta.get('totalComments') or chapter_meta.get('commentCount') or 0)
                    chapters_totals[str(web_chapter_id)] = total
                    payload['chapters_totals'] = chapters_totals
                    payload['overall_comments_total'] = sum(int(v or 0) for v in chapters_totals.values())
                    save_checkpoint(str(story_id), kind='chapters', payload=payload, finished=bool(ckp.get('finished')) if isinstance(ckp, dict) else False)
                except Exception:
                    pass
        except Exception:
            pass

        # 2️⃣ CRAWL CONTENT NẾU CẦN
        # Use webChapterId for duplicate checks
        should_crawl = self.duplicate_checker.should_crawl_chapter(web_chapter_id)
        # Debug: log decision
        try:
            safe_print(f"   ℹ️ Pipeline: chapter={chapter_id} webChapterId={web_chapter_id} should_crawl={should_crawl}")
        except Exception:
            pass

        if should_crawl:
            # Check content checkpoint to avoid re-downloading/saving
            try:
                ckp = load_checkpoint(str(web_chapter_id), kind='content')
                if ckp and ckp.get('finished'):
                    safe_print(f"   🔁 Content checkpoint for {web_chapter_id} shows finished — skipping content fetch")
                    saved = True
                else:
                    content = self.content_scraper.fetch_content(web_chapter_id)
                    try:
                        saved = self.content_scraper.save_content(chapter_id, content)
                        safe_print(f"   ℑ save_content returned: {saved}")
                    except Exception as e:
                        safe_print(f"   ⚠️ Exception while saving content for {chapter_id}: {e}")
                        saved = False
                # If saved successfully, mark content checkpoint finished
                if saved:
                    try:
                        save_checkpoint(str(web_chapter_id), kind='content', payload={'chapterId': chapter_id}, finished=True)
                    except Exception:
                        pass
            except Exception:
                # Fallback to original flow on any checkpoint error
                content = self.content_scraper.fetch_content(web_chapter_id)
                try:
                    saved = self.content_scraper.save_content(chapter_id, content)
                    safe_print(f"   ℑ save_content returned: {saved}")
                    if saved:
                        try:
                            save_checkpoint(str(web_chapter_id), kind='content', payload={'chapterId': chapter_id}, finished=True)
                        except Exception:
                            pass
                except Exception as e:
                    safe_print(f"   ⚠️ Exception while saving content for {chapter_id}: {e}")

        # 3️⃣ LUÔN SYNC COMMENT
        self.comment_service.sync_comments(web_chapter_id)

        # 4️⃣ LUÔN SYNC USER
        if hasattr(self.user_service, "sync_users_from_comments"):
            self.user_service.sync_users_from_comments(web_chapter_id)
