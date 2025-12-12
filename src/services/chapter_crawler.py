# -*- coding: utf-8 -*-
"""
Per-Chapter Crawler with Step-Level Retry

Responsibilities:
- Fetch parts list for a story from the API (with fallbacks)
- Map API parts to chapter schema and persist metadata (delegates to ChapterScraper)
- Insert minimal placeholders when the pipeline makes no progress to avoid
  infinite finish_story loops caused by downstream failures.
"""

import time
from typing import Dict, Optional, Any

from .. import config
from ..scrapers import safe_print
from .step_retry import step_retry, StepRetryConfig
from ..scrapers.website import WebsiteScraper


class ChapterCrawler:
    """Per-chapter crawler with step-level retry and defensive placeholders."""

    def __init__(self, scraper_engine, concurrency_manager: Optional[Any] = None):
        """Initialize with a reference to the parent `WattpadScraper` engine."""
        self.scraper_engine = scraper_engine
        # Rate limiter is shared from the engine
        self.rate_limiter = getattr(scraper_engine, 'rate_limiter', None)
        self.concurrency_manager = concurrency_manager

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect if error is rate limit related."""
        try:
            error_str = str(error).lower()
            return any(phrase in error_str for phrase in [
                "rate limit",
                "429",
                "too many requests",
                "throttled",
            ])
        except Exception:
            return False

    def finish_story(self, web_story_id: str, story_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Populate missing chapter metadata for a story.

        Returns a dict: {"total_parts": int, "inserted": int, "placeholders": int}
        """
        try:
            parts = self.scraper_engine.fetch_chapters_from_api(web_story_id)
        except Exception as e:
            safe_print(f"[CHAPTER_CRAWLER] ⚠️ Failed to fetch parts for {web_story_id}: {e}")
            return {"total_parts": 0, "inserted": 0, "placeholders": 0}

        if not parts:
            safe_print(f"[CHAPTER_CRAWLER] ℹ️ No parts returned from API for {web_story_id} — attempting fallbacks")
            # Fallback: try prefetched data via Playwright
            try:
                chapter_url = f"{config.BASE_URL}/{web_story_id}"
                if hasattr(self.scraper_engine, 'fetch_html_prefetched_data'):
                    prefetched = self.scraper_engine.fetch_html_prefetched_data(chapter_url)
                    if prefetched:
                        from ..scrapers.story import StoryScraper
                        extra = StoryScraper.extract_story_info_from_prefetched(prefetched, web_story_id)
                        if extra and extra.get('parts'):
                            parts = extra.get('parts')
                            safe_print(f"[CHAPTER_CRAWLER] ✅ Obtained {len(parts)} parts from prefetched data for {web_story_id}")
            except Exception as e:
                safe_print(f"[CHAPTER_CRAWLER] ⚠️ Prefetched fallback failed for {web_story_id}: {e}")

            if not parts:
                safe_print(f"[CHAPTER_CRAWLER] ℹ️ No chapters discovered after fallbacks for {web_story_id}")
                return {"total_parts": 0, "inserted": 0, "placeholders": 0}

        # Respect MAX_CHAPTERS_PER_STORY configuration
        try:
            max_ch = getattr(config, 'MAX_CHAPTERS_PER_STORY', None)
            original_total = len(parts)
            if max_ch and isinstance(max_ch, int) and max_ch > 0:
                parts = parts[:max_ch]
        except Exception:
            original_total = len(parts)

        inserted = 0
        total = len(parts)
        col = None
        try:
            col = self.scraper_engine.mongo_collection_chapters
        except Exception:
            col = None

        # Delegate mapping/persistence to ChapterScraper when available
        try:
            from ..scrapers.chapter import ChapterScraper
            if getattr(self.scraper_engine, 'chapter_scraper', None):
                chapter_scraper = self.scraper_engine.chapter_scraper
            else:
                chapter_scraper = ChapterScraper(page=None, mongo_db=self.scraper_engine.db)
        except Exception:
            chapter_scraper = None

        for idx, p in enumerate(parts, 1):
            try:
                if chapter_scraper is not None:
                    mapped = chapter_scraper.map_api_part_to_chapter(p, story_id, order=idx-1)
                else:
                    web_chapter_id = str(p.get("id") or p.get("webChapterId") or p.get("chapterId"))
                    if not web_chapter_id:
                        continue
                    chapter_id = WebsiteScraper.generate_chapter_id(web_chapter_id, prefix="wp")
                    mapped = {
                        "chapterId": chapter_id,
                        "webChapterId": web_chapter_id,
                        "order": idx - 1,
                        "chapterName": p.get("title") or f"Chapter {idx}",
                        "chapterUrl": p.get("url") or f"{config.BASE_URL}/{web_chapter_id}",
                        "publishedTime": p.get("createDate"),
                        "storyId": story_id,
                        "voted": p.get("voteCount", 0),
                        "views": p.get("readCount", 0),
                        "totalComments": p.get("commentCount", 0),
                    }
            except Exception as e:
                safe_print(f"[CHAPTER_CRAWLER] ⚠️ Failed to map chapter part for story {web_story_id}: {e}")
                mapped = None

            if not mapped:
                continue

            try:
                if chapter_scraper is not None:
                    inserted_flag = chapter_scraper.save_chapter_to_mongo(mapped)
                    if inserted_flag:
                        inserted += 1
                        safe_print(f"[CHAPTER_CRAWLER] ✨ Inserted chapter metadata: {mapped.get('chapterName')} ({mapped.get('webChapterId')})")
                else:
                    if col is not None:
                        col.insert_one(mapped)
                        inserted += 1
                        safe_print(f"[CHAPTER_CRAWLER] ✨ Inserted chapter metadata (fallback): {mapped.get('chapterName')} ({mapped.get('webChapterId')})")
            except Exception as e:
                safe_print(f"[CHAPTER_CRAWLER] ⚠️ Failed to persist chapter {mapped.get('webChapterId')}: {e}")

        # If we made no progress, insert minimal placeholders (upsert) to avoid
        # infinite retry loops by callers. Placeholders are marked with
        # `_placeholder: True` so downstream processors can replace them.
        placeholder_inserted = 0
        try:
            if inserted == 0 and total > 0 and col is not None:
                safe_print(f"[CHAPTER_CRAWLER] ⚠️ No chapters were inserted by scraper; inserting minimal placeholders to avoid retry loops")
                for idx, p in enumerate(parts, 1):
                    try:
                        web_chapter_id = str(p.get("id") or p.get("webChapterId") or p.get("chapterId"))
                        if not web_chapter_id:
                            continue
                        chapter_id = WebsiteScraper.generate_chapter_id(web_chapter_id, prefix="wp")
                        placeholder = {
                            "chapterId": chapter_id,
                            "webChapterId": web_chapter_id,
                            "order": idx - 1,
                            "chapterName": p.get("title") or f"Chapter {idx}",
                            "chapterUrl": p.get("url") or f"{config.BASE_URL}/{web_chapter_id}",
                            "publishedTime": p.get("createDate"),
                            "storyId": story_id,
                            "_placeholder": True,
                        }
                        try:
                            res = col.update_one({"webChapterId": web_chapter_id}, {"$setOnInsert": placeholder}, upsert=True)
                            if getattr(res, 'upserted_id', None):
                                placeholder_inserted += 1
                        except Exception as e:
                            safe_print(f"[CHAPTER_CRAWLER] ⚠️ Failed upsert placeholder for {web_chapter_id}: {e}")
                    except Exception:
                        continue

                if placeholder_inserted:
                    safe_print(f"[CHAPTER_CRAWLER] ✨ Inserted {placeholder_inserted} placeholder chapters for {web_story_id}")
                    inserted += placeholder_inserted
        except Exception as e:
            safe_print(f"[CHAPTER_CRAWLER] ⚠️ Error while inserting placeholders: {e}")

        safe_print(f"[CHAPTER_CRAWLER] ✅ finish_story for {web_story_id}: inserted {inserted}/{total} parts (placeholders: {placeholder_inserted})")
        return {"total_parts": total, "inserted": inserted, "placeholders": placeholder_inserted}

