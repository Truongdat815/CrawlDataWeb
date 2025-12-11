# -*- coding: utf-8 -*-
"""
Duplicate checker - handles checking if stories/chapters already scraped
Operates using webStoryId / webChapterId / webCommentId as primary keys in DB.
"""

import logging
from ..utils.scraped_checker import ScrapedChecker
from ..scrapers.base import safe_print


class DuplicateChecker:
    """
    DuplicateChecker operates on web* ids:
      - webStoryId (string numeric like "163645533")
      - webChapterId (string numeric like "987654")
      - webCommentId (string)
    It prefers to use the DB passed in `db` and uses ScrapedChecker as an optional cached helper.
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
        """
        Decide whether to (re-)crawl a chapter's content.

        Args:
            web_chapter_id: webChapterId (string or numeric)
            force: if True, always crawl

        Returns:
            True  -> crawl content
            False -> skip content (already present)
        """
        if force:
            return True
        if not web_chapter_id:
            return True

        try:
            # Find chapter metadata by webChapterId first
            chapter = self.db["chapters"].find_one({"webChapterId": str(web_chapter_id)})
            if not chapter:
                # No chapter metadata stored → crawl
                return True

            # Use internal chapterId when querying content/comments in DB
            chapter_id = chapter.get("chapterId")
            if chapter_id:
                content = self.db["chapter_contents"].find_one({"chapterId": str(chapter_id)})
                if not content:
                    # Try fallback by contentId pattern
                    content = self.db["chapter_contents"].find_one({"contentId": f"{chapter_id}_content"})
                if not content:
                    return True
                return False

            # If no internal chapterId, fallback to webChapterId-based lookup
            content = self.db["chapter_contents"].find_one({"webChapterId": str(web_chapter_id)})
            if not content:
                return True
            return False
        except Exception as e:
            logging.exception("[DUP_CHECK] Lỗi khi kiểm tra chapter %s", web_chapter_id)
            # Conservative choice: try to crawl on DB errors
            return True

    def check_chapter(self, web_chapter_id, chapter_name=None):
        """
        Return status for a chapter by webChapterId.

        Returns:
            dict: {
                "exists": True/False,
                "chapterId": internal chapterId (if present),
                "webChapterId": web_chapter_id,
                "has_content": True/False,
                "chapterName": str or None
            }
        """
        if not web_chapter_id:
            return {"exists": False}

        try:
            chapter = self.db["chapters"].find_one({"webChapterId": str(web_chapter_id)})
            if not chapter:
                return {"exists": False}

            chapter_id = chapter.get("chapterId")
            has_content = False
            if chapter_id:
                has_content = self.db["chapter_contents"].find_one({"chapterId": str(chapter_id)}) is not None
                if not has_content:
                    has_content = self.db["chapter_contents"].find_one({"contentId": f"{chapter_id}_content"}) is not None
            else:
                has_content = self.db["chapter_contents"].find_one({"webChapterId": str(web_chapter_id)}) is not None

            return {
                "exists": True,
                "chapterId": chapter.get("chapterId"),
                "webChapterId": str(web_chapter_id),
                "has_content": bool(has_content),
                "chapterName": chapter.get("chapterName") or chapter_name
            }
        except Exception as e:
            logging.exception("[DUP_CHECK] Lỗi khi check_chapter %s", web_chapter_id)
            return {"exists": False}

    def check_story(self, web_story_id):
        """
        Return status for a story by webStoryId.

        Returns:
            dict (similar to ScrapedChecker.get_story_status) or None if not found.
        """
        if not web_story_id:
            return None

        try:
            # Find story document by webStoryId or by storyId equals the web id (robust lookup)
            story_doc = self.db["stories"].find_one({"$or": [{"webStoryId": str(web_story_id)}, {"storyId": str(web_story_id)}]})
            if not story_doc:
                return None

            story_id = story_doc.get("storyId")
            web_story_id_str = str(web_story_id)
            # Try using cached ScrapedChecker if available (it expects internal storyId)
            # But only accept the cached result if it indicates chapters exist — otherwise
            # fall back to live DB queries because some migrations stored web IDs in chapter.storyId.
            if self.cache and story_id:
                try:
                    status = self.cache.get_story_status(story_id)
                    if status and status.get("chapters_count", 0) > 0:
                        return status
                    # otherwise ignore cache and compute from DB below
                except Exception:
                    # If cache fails, fall back to DB queries below
                    pass

            # After DB normalization we expect chapters.storyId to contain internal IDs.
            # Use internal storyId to compute counts and avoid fallbacks.
            if not story_id:
                # If still missing internal storyId, fallback to webStoryId-based query
                chapters_cursor = self.db["chapters"].find({"webStoryId": web_story_id_str}, {"chapterId": 1})
            else:
                chapters_cursor = self.db["chapters"].find({"storyId": str(story_id)}, {"chapterId": 1})

            chapter_docs = list(chapters_cursor)
            chapter_ids = [ch.get("chapterId") for ch in chapter_docs if ch.get("chapterId")]

            chapters_count = len(chapter_docs)

            # Count contents by internal chapterId and contentId (normalized)
            contents_count = 0
            if chapter_ids:
                contents_count = self.db["chapter_contents"].count_documents({"chapterId": {"$in": chapter_ids}})
                if contents_count == 0:
                    content_ids = [f"{cid}_content" for cid in chapter_ids if cid]
                    if content_ids:
                        contents_count = self.db["chapter_contents"].count_documents({"contentId": {"$in": content_ids}})

            # Count comments using chapterId
            comments_count = 0
            if chapter_ids:
                comments_count = self.db["comments"].count_documents({"chapterId": {"$in": chapter_ids}})

            return {
                "exists": True,
                "storyId": story_id,
                "storyName": story_doc.get("storyName"),
                "chapters_count": chapters_count,
                "chapters_with_content": contents_count,
                "comments_count": comments_count,
                "last_updated": story_doc.get("time") or story_doc.get("modifiedDate")
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

