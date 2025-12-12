# -*- coding: utf-8 -*-
"""
Parallel Crawler - Multi-threaded story crawling với anti-bot protection
✅ OPTIMIZED: Browser pooling + API-only chapter crawl
"""

import threading
import time
import random
import re
import os
import traceback
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Optional, Any
from src import config
from .scraper_engine import WattpadScraper, BrowserManager
from .scrapers import safe_print
from .utils.url_utils import extract_story_id_from_url, is_category_url


class ParallelCrawler:
    """
    ✅ OPTIMIZED Multi-level parallel crawler:
    - Level 1: N stories crawled in parallel (each has 1 browser)
    - Level 2: Each story crawls chapters (API-only, no browser)
    - Shared rate limiter to prevent IP ban
    - Browser design: 5 stories = 5 browsers (simple, safe, no sharing)
    """
    
    def __init__(self, max_story_workers=None, max_chapter_workers=None):
        """
        Args:
            max_story_workers: Number of stories to crawl in parallel
            max_chapter_workers: Number of chapters per story (deprecated in this version)
        """
        self.max_story_workers = max_story_workers or config.MAX_STORY_WORKERS
        self.max_chapter_workers = max_chapter_workers or config.MAX_CHAPTER_WORKERS
        
        # ✅ NEW: Browser manager for per-thread browsers
        # Design: 5 stories = 5 workers = 5 browsers (1:1 mapping)
        # No sharing, no race conditions, thread-safe
        self.browser_manager = BrowserManager()
        
        # Results
        self.results = []
        self.results_lock = threading.Lock()
        
        # Progress tracking (thread-safe)
        self.total_stories = 0
        self.completed_stories = 0
        self.failed_stories = 0
        self.progress_lock = threading.Lock()
        
        # Retry logic
        self.retry_queue = []
        self.retry_counts = {}
        self.retry_lock = threading.Lock()
        
        # Progress checkpoint (disabled - checkpoint files are no longer used)
        
        # Shared rate limiter (thread-safe)
        from .scraper_engine import RateLimiter
        self.shared_rate_limiter = RateLimiter()
        
        # MongoDB connection info
        self.mongo_uri = config.MONGODB_URI if config.MONGODB_ENABLED else None
        self.mongo_db_name = config.MONGODB_DB_NAME if config.MONGODB_ENABLED else None
        # Ensure any future checks use 'is not None' for mongo_db, mongo_collection, etc.
        
        safe_print("✨ ParallelCrawler initialized")
        safe_print(f"   Story workers: {self.max_story_workers}")
        safe_print(f"   ✅ Browser design: 1 per worker (5 workers = 5 browsers)")
        safe_print(f"   ✅ Chapter crawl: 100% API (no browser)")
        safe_print(f"   ✅ Shared rate limiter: {config.MAX_REQUESTS_PER_MINUTE} req/min")
        safe_print(f"   Retry enabled: {config.MAX_STORY_RETRIES > 0} (max {config.MAX_STORY_RETRIES} retries)")
    
    # Note: checkpoint file support removed. No _load_checkpoint implementation.
    
    # Note: checkpoint file support removed. No _save_checkpoint implementation.
    
    def _update_progress(self, success=True, story_id=None):
        """Update progress counter (thread-safe)"""
        with self.progress_lock:
            self.completed_stories += 1
            if not success:
                self.failed_stories += 1
            
            progress_pct = (self.completed_stories / self.total_stories * 100) if self.total_stories > 0 else 0
            safe_print(f"\n{'='*60}")
            safe_print(f"📊 Progress: {self.completed_stories}/{self.total_stories} ({progress_pct:.1f}%)")
            safe_print(f"   ✅ Success: {self.completed_stories - self.failed_stories}")
            safe_print(f"   ❌ Failed: {self.failed_stories}")
            safe_print(f"{'='*60}\n")
            
            # Checkpoint files disabled; no file saves performed here.
    
    def _crawl_story_worker(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        ✅ OPTIMIZED: Worker function to crawl 1 story
        
        Key optimizations:
        - Reuse browser from pool (not create new)
        - Load cookies from file (no re-login)
        - Chapter crawl: API-only (no browser)
        - Minimal browser lifetime
        
        Args:
            story_id: Story ID to crawl
            
        Returns:
            Story data dict or None if failed
        """
        thread_name = threading.current_thread().name
        scraper = None
        # Cosolog: log rõ ràng khi bắt đầu crawl story
        safe_print(f"[COSOLOG] 🟢 Bắt đầu crawl story: {story_id} (Thread: {thread_name})")
        try:
            safe_print(f"\n{'='*60}")
            safe_print(f"📖 Bắt đầu cào story ID: {story_id} (Thread: {thread_name})")
            safe_print(f"{'='*60}")
            
            # Random delay (anti-pattern detection)
            delay = random.uniform(
                config.PARALLEL_RANDOM_DELAY_MIN,
                config.PARALLEL_RANDOM_DELAY_MAX
            )
            time.sleep(delay)
            
            # Create scraper (browser will be created/reused internally)
            scraper = WattpadScraper(max_workers=self.max_chapter_workers)
            
            # Inject shared rate limiter
            scraper.rate_limiter = self.shared_rate_limiter
            
            # Extract worker ID
            worker_id = thread_name.split('_')[-1] if '_' in thread_name else None
            
            # Start browser (loads cookies from file, no re-login)
            scraper.start(worker_id=worker_id)
            
            # ✅ OPTIMIZED: Crawl story with API-only chapters
            safe_print(f"[DEBUG] Gọi scrape_story cho story_id={story_id}")
            story_data = scraper.scrape_story(
                story_id=story_id,
                fetch_chapters=True,
                fetch_comments=True
            )
            safe_print(f"[DEBUG] Kết quả scrape_story cho story_id={story_id}: {'ĐÃ CÓ' if story_data else 'KHÔNG CÓ'}")
            
            if story_data:
                safe_print(f"✅ [{thread_name}] Completed story {story_id}")
                self._update_progress(success=True, story_id=story_id)
                return story_data
            else:
                safe_print(f"❌ [{thread_name}] Failed story {story_id} - No data returned")
                self._add_to_retry_queue(story_id)
                self._update_progress(success=False)
                return None
                
        except Exception as e:
            safe_print(f"❌ [{thread_name}] Error crawling story {story_id}: {e}")
            traceback.print_exc()
            self._add_to_retry_queue(story_id)
            self._update_progress(success=False)
            return None
        finally:
            # Close scraper (but keep browser for reuse if needed)
            if scraper:
                try:
                    scraper.stop()
                except Exception as e:
                    safe_print(f"⚠️ [{thread_name}] Cleanup error for story {story_id}: {e}")
    
    def _add_to_retry_queue(self, story_id: str):
        """Add failed story to retry queue (thread-safe)"""
        if config.MAX_STORY_RETRIES <= 0:
            return
        
        with self.retry_lock:
            retry_count = self.retry_counts.get(story_id, 0)
            if retry_count < config.MAX_STORY_RETRIES:
                self.retry_queue.append(story_id)
                self.retry_counts[story_id] = retry_count + 1
                safe_print(f"🔄 Story {story_id} added to retry queue (attempt {retry_count + 1}/{config.MAX_STORY_RETRIES})")
    
    def _get_retry_batch(self) -> List[str]:
        """Get stories to retry (thread-safe)"""
        with self.retry_lock:
            batch = self.retry_queue[:]
            self.retry_queue.clear()
            return batch
    
    def _do_initial_login(self):
        """
        ⚠️ CRITICAL: Login 1 lần duy nhất trong main thread
        Mục đích: Tránh 5 threads login đồng thời → account lock / IP ban
        
        Workflow:
        1. Main thread: Tạo WattpadScraper, login, save cookies vào file
        2. Worker threads: Mỗi thread load cookies từ file, reuse session
        3. Result: Chỉ 1 login request duy nhất (thay vì 5)
        
        Returns: None (cookies saved to file)
        """
        # Kiểm tra credentials
        username = config.WATTPAD_USERNAME if hasattr(config, 'WATTPAD_USERNAME') else None
        password = config.WATTPAD_PASSWORD if hasattr(config, 'WATTPAD_PASSWORD') else None
        
        # Nếu không có credentials hoặc cookie file đã tồn tại, bỏ qua
        if not username or not password:
            safe_print("⚠️ No credentials provided - Skipping initial login")
            return
        
        if config.SKIP_LOGIN_IF_COOKIE_EXISTS and os.path.exists(config.COOKIE_FILE):
            safe_print(f"🍪 Cookie file already exists ({config.COOKIE_FILE}) - Reusing cookies")
            return
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🔑 INITIAL LOGIN (Main Thread - 1 lần duy nhất)")
        safe_print(f"   Username: {username}")
        safe_print(f"   Saving cookies to: {config.COOKIE_FILE}")
        safe_print(f"   Workers sẽ reuse cookies này")
        safe_print(f"{'='*60}\n")
        
        scraper = None
        try:
            # Tạo scraper trong main thread để login
            scraper = WattpadScraper(max_workers=self.max_chapter_workers)
            scraper.rate_limiter = self.shared_rate_limiter
            
            # Login - this will save cookies to file automatically
            scraper.start(username=username, password=password, worker_id="MainThread")
            
            safe_print("✅ Initial login successful - Cookies saved for worker threads\n")
            
        except Exception as e:
            safe_print(f"❌ Initial login failed: {e}")
            safe_print(f"⚠️ Workers will attempt to scrape without login\n")
            traceback.print_exc()
        finally:
            if scraper:
                try:
                    scraper.stop()
                except Exception as e:
                    safe_print(f"⚠️ Cleanup error during initial login: {e}")
    
    def crawl_stories_parallel(self, story_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl nhiều stories song parallel với cookie-based session reuse
        
        ✅ OPTIMIZATION: 
        - 1 login ở main thread → save cookies
        - N workers reuse cookies → no multi-login risk
        
        Args:
            story_ids: List of story IDs to crawl
            
        Returns:
            List of successfully crawled story data
        """
        if not story_ids:
            safe_print("⚠️ No stories to crawl")
            return []
        
        # Checkpoint files are not used; crawl all provided story IDs.
        
        self.total_stories = len(story_ids)
        self.completed_stories = 0
        self.failed_stories = 0
        self.results = []
        
        # ⚠️ CRITICAL: Do initial login BEFORE creating workers
        # This ensures cookies are saved and workers can reuse them
        self._do_initial_login()
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🚀 Starting parallel crawl of {len(story_ids)} stories")
        safe_print(f"   Workers: {self.max_story_workers}")
        safe_print(f"   Rate limit: {config.MAX_REQUESTS_PER_MINUTE} req/min")
        safe_print(f"   ✅ Workers will reuse cookies (single login strategy)")
        safe_print(f"{'='*60}\n")
        
        start_time = time.time()
        
        # Use ThreadPoolExecutor for story-level parallelism
        # Mỗi thread tạo browser riêng (Playwright không thread-safe)
        with ThreadPoolExecutor(
            max_workers=self.max_story_workers,
            thread_name_prefix="StoryWorker"
        ) as executor:
            # Submit all stories to thread pool
            future_to_story = {
                executor.submit(self._crawl_story_worker, story_id): story_id
                for story_id in story_ids
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_story):
                story_id = future_to_story[future]
                try:
                    result = future.result()
                    if result:
                        with self.results_lock:
                            self.results.append(result)
                except Exception as e:
                    safe_print(f"❌ Thread exception for story {story_id}: {e}")
                    self._update_progress(success=False)
        
        # Retry failed stories if enabled
        retry_results = []
        if config.MAX_STORY_RETRIES > 0:
            retry_batch = self._get_retry_batch()
            if retry_batch:
                safe_print(f"\n{'='*60}")
                safe_print(f"🔄 RETRY PHASE: {len(retry_batch)} failed stories")
                safe_print(f"{'='*60}")
                time.sleep(config.RETRY_DELAY)  # Wait before retry
                
                # Retry with same parallel logic
                with ThreadPoolExecutor(
                    max_workers=self.max_story_workers,
                    thread_name_prefix="RetryWorker"
                ) as executor:
                    future_to_story = {
                        executor.submit(self._crawl_story_worker, story_id): story_id
                        for story_id in retry_batch
                    }
                    
                    for future in as_completed(future_to_story):
                        story_id = future_to_story[future]
                        try:
                            result = future.result()
                            if result:
                                with self.results_lock:
                                    retry_results.append(result)
                                    self.results.append(result)
                        except Exception as e:
                            safe_print(f"❌ Retry failed for story {story_id}: {e}")
                
                safe_print(f"✅ Retry phase completed: {len(retry_results)}/{len(retry_batch)} recovered")
        
        # Final checkpoint saving and export removed (checkpoint-from-file disabled).
        
        elapsed = time.time() - start_time
        
        # ✅ FIX: Prevent division by zero
        # Final summary
        safe_print(f"\n{'='*60}")
        safe_print(f"🎉 Parallel crawl completed!")
        safe_print(f"   Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        safe_print(f"   Stories crawled: {len(self.results)}/{len(story_ids)}")
        if retry_results:
            safe_print(f"   Recovered via retry: {len(retry_results)}")
        
        # ✅ Only calculate metrics if we have stories
        if len(story_ids) > 0:
            success_rate = (len(self.results) / len(story_ids) * 100)
            safe_print(f"   Success rate: {success_rate:.1f}%")
            avg_time = elapsed / len(story_ids)
            safe_print(f"   Avg time/story: {avg_time:.1f}s")
        else:
            safe_print(f"   ⚠️ No stories were extracted from URLs")
        
        if len(self.results) > 0 and elapsed > 0:
            speed = len(self.results) / (elapsed / 60)
            safe_print(f"   Speed: {speed:.2f} stories/minute")
        safe_print(f"{'='*60}\n")
        
        return self.results
    
    def extract_story_ids_from_page(self, page_url: str, max_stories: Optional[int] = None) -> List[str]:
        """
        Extract story IDs từ category/browse page (genre, tag, home, etc)
        
        Args:
            page_url: URL of category/browse page
            max_stories: Max stories to extract (default: config.MAX_STORIES_PER_BATCH)
            
        Returns:
            List of story IDs
        """
        safe_print(f"\n🔍 Extracting stories from page: {page_url}")
        
        try:
            # Use static method (no scraper instance needed)
            story_links = WattpadScraper.fetch_story_links_from_page(page_url, max_stories=max_stories)
            
            if not story_links:
                safe_print(f"⚠️ No stories found on page: {page_url}")
                return []
            
            # Extract IDs (with duplicate removal)
            story_ids = []
            seen = set()
            for link in story_links:
                match = re.search(r'/(\d+)', link)
                if match:
                    story_id = match.group(1)
                    if story_id not in seen:
                        story_ids.append(story_id)
                        seen.add(story_id)
            
            safe_print(f"✅ Extracted {len(story_ids)} unique story IDs from page")
            return story_ids
            
        except Exception as e:
            safe_print(f"❌ Failed to extract stories from page: {e}")
            return []
    
    def crawl_stories_from_urls(self, story_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl stories from URLs (extracts story IDs first)
        Supports:
        - Story IDs: "12345"
        - Story URLs: "https://www.wattpad.com/story/12345-title"
        - Category/Browse URLs: "https://www.wattpad.com/stories/fantasy"
        
        Args:
            story_urls: List of story URLs, IDs, or category URLs
            
        Returns:
            List of successfully crawled story data
        """
        story_ids = []
        category_count = 0
        direct_count = 0
        
        for url in story_urls:
            url = url.strip()
            
            # Case 1: Category/Browse page
            if is_category_url(url):
                safe_print(f"\n📂 Extracting from category page: {url}")
                category_count += 1
                try:
                    page_story_ids = self.extract_story_ids_from_page(url)
                    if page_story_ids:
                        safe_print(f"   ✅ Found {len(page_story_ids)} stories")
                        story_ids.extend(page_story_ids)
                    else:
                        safe_print(f"   ⚠️ No stories found on this page")
                except Exception as e:
                    safe_print(f"   ❌ Failed to extract stories: {e}")
            
            # Case 2: Individual story URL or ID
            else:
                story_id = extract_story_id_from_url(url)
                if story_id:
                    story_ids.append(story_id)
                    direct_count += 1
                else:
                    safe_print(f"⚠️ Could not extract story ID from: {url}")
        
        # Remove duplicates while preserving order
        story_ids = list(dict.fromkeys(story_ids))
        
        safe_print(f"\n{'='*60}")
        safe_print(f"📊 URL Processing Summary:")
        safe_print(f"   Category pages processed: {category_count}")
        safe_print(f"   Direct story URLs/IDs: {direct_count}")
        safe_print(f"   Total unique stories to crawl: {len(story_ids)}")
        safe_print(f"{'='*60}")
        
        if not story_ids:
            safe_print("❌ No valid story IDs found!")
            return []
        
        return self.crawl_stories_parallel(story_ids)
