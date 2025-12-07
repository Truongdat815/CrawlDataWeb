# -*- coding: utf-8 -*-
"""
Per-Chapter Crawler with Step-Level Retry
✅ Refactored chapter crawling logic:
- Each API step (fetch chapters, scrape chapter, fetch comments) retries independently
- Per-chapter checkpointing for resume capability
- Minimal waste when individual steps fail
- Dynamic concurrency: adapts to rate limits
"""

import time
import threading
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from src import config
from src.scrapers import safe_print
from src.utils.chapter_checkpoint import get_chapter_checkpoint_manager
from src.utils.step_retry import (
    step_retry, RETRYABLE_NETWORK_ERRORS, 
    STEP_RETRIES, get_step_retry_decorator
)
from src.utils.dynamic_concurrency import DynamicConcurrencyManager


class ChapterCrawler:
    """
    Per-chapter crawler with step-level retry
    
    Each chapter crawl is broken into independent steps:
    1. Fetch chapters list (retry 3x)
    2. For each chapter:
       a. Fetch chapter content (retry 3x)
       b. Fetch chapter comments (retry 3x independently)
       c. Save to DB
    """
    
    def __init__(self, scraper_engine, concurrency_manager: Optional[DynamicConcurrencyManager] = None):
        """
        Args:
            scraper_engine: WattpadScraper instance for API calls
            concurrency_manager: DynamicConcurrencyManager (auto-created if None)
        """
        self.scraper_engine = scraper_engine
        self.checkpoint_manager = get_chapter_checkpoint_manager()
        self.rate_limiter = scraper_engine.rate_limiter
        
        # Dynamic concurrency manager
        self.concurrency_manager = concurrency_manager or DynamicConcurrencyManager(
            max_workers=config.MAX_CHAPTER_WORKERS
        )
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect if error is rate limit related"""
        error_str = str(error).lower()
        return any(phrase in error_str for phrase in [
            "rate limit",
            "429",
            "too many requests",
            "throttled",
            "quota",
            "banned"
        ])
    
    def _is_timeout_error(self, error: Exception) -> bool:
        """Detect if error is timeout related"""
        return isinstance(error, TimeoutError) or "timeout" in str(error).lower()
    
    @step_retry(
        max_retries=3,
        initial_backoff=1.0,
        step_name="fetch_chapters_list",
        retryable_exceptions=RETRYABLE_NETWORK_ERRORS,
        fatal_exceptions=(ValueError,)
    )
    def _fetch_chapters_list(self, story_id: str) -> Optional[List[Dict]]:
        """
        Step 1: Fetch chapter list from API (retry independently)
        
        Retryable: Network errors, timeouts, API rate limits
        Fatal: Invalid story ID
        """
        try:
            self.rate_limiter.wait_if_needed()
            return self.scraper_engine.fetch_chapters_from_api(story_id)
        except TimeoutError as e:
            # Timeout = reduce concurrency
            self.concurrency_manager.on_timeout()
            raise
        except Exception as e:
            # Check if rate limit error
            if self._is_rate_limit_error(e):
                self.concurrency_manager.on_rate_limit()
            raise
    
    @step_retry(
        max_retries=3,
        initial_backoff=1.5,
        step_name="scrape_chapter_content",
        retryable_exceptions=RETRYABLE_NETWORK_ERRORS,
        fatal_exceptions=(ValueError,)
    )
    def _scrape_chapter_content(
        self, 
        story_id: str, 
        chapter_id: str, 
        web_chapter_id: str,
        chapter_name: str
    ) -> Optional[Dict]:
        """
        Step 2a: Scrape chapter content (retry independently per chapter)
        
        ✅ FIX: Dùng Playwright để gọi API (bypass Cloudflare)
        - Playwright load chapter page (JavaScript + Cloudflare pass)
        - Gọi API từ browser context (có cookies/headers hợp lệ)
        - API trả về content
        
        Retryable: Navigation timeout, parsing failures, API errors
        Fatal: Invalid chapter ID
        """
        if not self.scraper_engine.page:
            safe_print(f"⚠️ No page available for chapter {chapter_id}")
            return None
        
        self.rate_limiter.wait_if_needed()
        
        # Navigate to chapter (Cloudflare validation happens here)
        chapter_url = f"{config.BASE_URL}/{web_chapter_id}"
        self.scraper_engine.page.goto(
            chapter_url, 
            wait_until="load", 
            timeout=config.REQUEST_TIMEOUT * 1000
        )
        self.scraper_engine.page.wait_for_timeout(2000)
        self.scraper_engine._simulate_human_behavior(self.scraper_engine.page)
        
        # ✅ FIX: Gọi API từ BROWSER CONTEXT (có Cloudflare validation)
        try:
            from bs4 import BeautifulSoup
            
            safe_print(f"      📡 Calling API from browser context...")
            
            # Gọi API thông qua browser.evaluate (tương đương fetch() bên trong browser)
            chapter_text = self.scraper_engine.page.evaluate(
                """
                async (id) => {
                    try {
                        const response = await fetch(`https://www.wattpad.com/apiv2/?m=storytext&id=${id}&page=`);
                        return await response.text();
                    } catch(e) {
                        return null;
                    }
                }
                """,
                web_chapter_id  # Pass chapter ID vào evaluate
            )
            
            if chapter_text:
                safe_print(f"      ✅ API response received: {len(chapter_text)} bytes")
                
                # Parse HTML response
                soup = BeautifulSoup(chapter_text, 'html.parser')
                
                # Extract paragraphs
                paragraphs = []
                for p in soup.find_all('p'):
                    p_text = p.get_text().strip()
                    if p_text:
                        paragraphs.append(p_text)
                
                if paragraphs:
                    full_content = "\n\n".join(paragraphs)
                    safe_print(f"      ✅ Extracted: {len(full_content)} chars, {len(paragraphs)} paragraphs")
                    
                    # Map to schema
                    chapter_data = {
                        "chapterId": chapter_id,
                        "webChapterId": web_chapter_id,
                        "content": full_content,
                        "contentLength": len(full_content)
                    }
                    return chapter_data
                else:
                    safe_print(f"      ⚠️ No content paragraphs found in API response")
                    return None
            else:
                safe_print(f"      ⚠️ API returned empty response")
                return None
        
        except Exception as e:
            safe_print(f"      ❌ Browser API call failed: {e}")
            raise
    
    @step_retry(
        max_retries=3,
        initial_backoff=2.0,
        step_name="scrape_chapter_comments",
        retryable_exceptions=RETRYABLE_NETWORK_ERRORS,
        fatal_exceptions=(ValueError,)
    )
    def _scrape_chapter_comments(
        self, 
        story_id: str, 
        chapter_id: str, 
        web_chapter_id: str
    ) -> Optional[List[Dict]]:
        """
        Step 2b: Scrape chapter comments (retry independently per chapter)
        
        IMPORTANT: This runs independently from content scraping!
        If comments fail but content succeeded, we still keep the content.
        
        Retryable: API rate limits, network errors
        Fatal: Invalid chapter ID
        """
        self.rate_limiter.wait_if_needed()
        
        comments = self.scraper_engine.comment_scraper.scrape_chapter_comments(
            story_id=story_id,
            chapter_id=chapter_id,
            web_chapter_id=web_chapter_id,
            max_comments=config.MAX_COMMENTS_PER_CHAPTER
        )
        
        return comments or []
    
    def crawl_chapters(
        self, 
        story_id: str, 
        web_story_id: str,
        fetch_comments: bool = True
    ) -> Dict[str, Any]:
        """
        Crawl all chapters for a story with per-chapter retry logic
        
        Returns:
            {
                "total_chapters": int,
                "crawled_chapters": int,
                "failed_chapters": [web_chapter_id, ...],
                "chapters": [chapter_data, ...]
            }
        """
        safe_print(f"\n{'='*60}")
        safe_print(f"📚 Starting chapter crawl for story {story_id}")
        safe_print(f"{'='*60}")
        
        # Step 1: Fetch chapter list (retry 3x)
        try:
            chapters = self._fetch_chapters_list(story_id)
        except Exception as e:
            safe_print(f"❌ Failed to fetch chapters after retries: {e}")
            return {
                "total_chapters": 0,
                "crawled_chapters": 0,
                "failed_chapters": [],
                "chapters": []
            }
        
        if not chapters:
            safe_print(f"⚠️ No chapters found for story {story_id}")
            return {
                "total_chapters": 0,
                "crawled_chapters": 0,
                "failed_chapters": [],
                "chapters": []
            }
        
        # Load checkpoint for this story
        checkpoint = self.checkpoint_manager.get_or_create_checkpoint(web_story_id)
        checkpoint.total_chapters = len(chapters)
        
        # Get list of chapters to crawl (skip already crawled/failed)
        web_chapter_ids = [ch.get("webChapterId") or str(ch.get("id")) for ch in chapters]
        pending_chapters = self.checkpoint_manager.get_pending_chapters(web_story_id, web_chapter_ids)
        
        safe_print(f"   📊 Chapter status:")
        safe_print(f"      Total: {len(chapters)}")
        safe_print(f"      ✅ Already crawled: {len(checkpoint.crawled_chapters)}")
        safe_print(f"      ❌ Failed: {len(checkpoint.failed_chapters)}")
        safe_print(f"      ⏳ Pending: {len(pending_chapters)}")
        
        crawled_chapters = []
        failed_chapter_ids = []
        
        # Step 2: Crawl each chapter with independent retries
        max_chapters = config.MAX_CHAPTERS_PER_STORY or len(chapters)
        for idx, chapter in enumerate(chapters, 1):
            if idx > max_chapters:
                safe_print(f"⏹️ Reached max chapters limit: {max_chapters}")
                break
            
            chapter_id = chapter.get("chapterId")
            web_chapter_id = str(chapter.get("webChapterId") or chapter.get("id"))
            chapter_name = chapter.get("chapterName", f"Chapter {idx}")
            
            # Skip if already crawled or permanently failed
            if self.checkpoint_manager.is_chapter_crawled(web_story_id, web_chapter_id):
                safe_print(f"\n   ⏭️ [{idx}/{max_chapters}] {chapter_name} - Already crawled ✅")
                continue
            
            if self.checkpoint_manager.is_chapter_failed(web_story_id, web_chapter_id):
                safe_print(f"\n   ⏭️ [{idx}/{max_chapters}] {chapter_name} - Permanently failed ❌")
                continue
            
            safe_print(f"\n   📖 [{idx}/{max_chapters}] Crawling: {chapter_name}")
            safe_print(f"      Workers: {self.concurrency_manager.get_current_workers()} | {self.concurrency_manager.get_status_string()}")
            
            chapter_success = False
            
            # Step 2a: Scrape chapter content (retry 3x)
            try:
                chapter_data = self._scrape_chapter_content(
                    story_id=story_id,
                    chapter_id=chapter_id,
                    web_chapter_id=web_chapter_id,
                    chapter_name=chapter_name
                )
                
                if chapter_data:
                    safe_print(f"      ✅ Content scraped")
                    
                    # Record success in concurrency manager
                    self.concurrency_manager.on_success()
                    
                    # Step 2b: Scrape comments independently (retry 3x)
                    if fetch_comments:
                        try:
                            comments = self._scrape_chapter_comments(
                                story_id=story_id,
                                chapter_id=chapter_id,
                                web_chapter_id=web_chapter_id
                            )
                            if comments:
                                chapter_data["comments"] = comments
                                safe_print(f"      ✅ Comments scraped: {len(comments)} comments")
                            else:
                                safe_print(f"      ⚠️ No comments found")
                        except Exception as e:
                            # Comments failure is NOT fatal
                            # We keep the chapter content even if comments fail
                            # Check if it's rate limit
                            if self._is_rate_limit_error(e):
                                self.concurrency_manager.on_rate_limit()
                            safe_print(f"      ⚠️ Comments failed: {e}")
                            chapter_data["comments"] = []
                    
                    crawled_chapters.append(chapter_data)
                    self.checkpoint_manager.mark_chapter_crawled(web_story_id, web_chapter_id)
                    chapter_success = True
                    safe_print(f"      ✅ Chapter saved")
            
            except Exception as e:
                safe_print(f"      ❌ Content scraping failed: {e}")
                
                # Detect error type
                if self._is_rate_limit_error(e):
                    self.concurrency_manager.on_rate_limit()
                elif self._is_timeout_error(e):
                    self.concurrency_manager.on_timeout()
                
                # Check if we should retry
                retry_count = self.checkpoint_manager.increment_chapter_retry(
                    web_story_id, 
                    web_chapter_id
                )
                
                if self.checkpoint_manager.should_retry_chapter(web_story_id, web_chapter_id):
                    safe_print(f"      ⏳ Will retry later (attempt {retry_count}/{config.MAX_CHAPTER_RETRIES})")
                else:
                    safe_print(f"      ❌ Max retries reached - Permanently failed")
                    self.checkpoint_manager.mark_chapter_failed(web_story_id, web_chapter_id)
                    failed_chapter_ids.append(web_chapter_id)
            
            # Save checkpoint periodically
            if idx % 5 == 0:
                self.checkpoint_manager.save_checkpoint(web_story_id)
                safe_print(f"   💾 Checkpoint saved ({len(crawled_chapters)} chapters)")
        
        # Finalize checkpoint
        self.checkpoint_manager.finalize_story(web_story_id)
        
        # Summary
        safe_print(f"\n{'='*60}")
        safe_print(f"📊 Chapter crawl completed:")
        safe_print(f"   ✅ Successfully crawled: {len(crawled_chapters)}")
        safe_print(f"   ❌ Failed: {len(failed_chapter_ids)}")
        safe_print(f"{'='*60}\n")
        
        return {
            "total_chapters": len(chapters),
            "crawled_chapters": len(crawled_chapters),
            "failed_chapters": failed_chapter_ids,
            "chapters": crawled_chapters,
            "checkpoint": self.checkpoint_manager.get_checkpoint_status(web_story_id)
        }


class ParallelChapterCrawler:
    """
    Crawl chapters from multiple stories in parallel
    - Each story gets a dedicated thread
    - Within each story, chapters are crawled sequentially with per-chapter retry
    """
    
    def __init__(self, scraper_engine):
        self.scraper_engine = scraper_engine
        self.chapter_crawler = ChapterCrawler(scraper_engine)
    
    def crawl_multiple_stories_chapters(
        self,
        story_chapters: List[Dict[str, str]],
        max_parallel: int = 3,
        fetch_comments: bool = True
    ) -> List[Dict]:
        """
        Crawl chapters for multiple stories in parallel
        
        Args:
            story_chapters: [
                {"story_id": "...", "web_story_id": "..."},
                ...
            ]
            max_parallel: Number of stories to crawl in parallel
            fetch_comments: Whether to fetch comments
        
        Returns:
            List of crawl results
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {
                executor.submit(
                    self.chapter_crawler.crawl_chapters,
                    item["story_id"],
                    item["web_story_id"],
                    fetch_comments
                ): item["story_id"]
                for item in story_chapters
            }
            
            for future in as_completed(futures):
                story_id = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    safe_print(f"❌ Error crawling story {story_id}: {e}")
                    results.append({
                        "story_id": story_id,
                        "total_chapters": 0,
                        "crawled_chapters": 0,
                        "failed_chapters": [],
                        "chapters": [],
                        "error": str(e)
                    })
        
        return results
