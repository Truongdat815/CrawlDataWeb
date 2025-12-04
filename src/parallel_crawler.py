# -*- coding: utf-8 -*-
"""
Parallel Crawler - Multi-threaded story crawling với anti-bot protection
Crawl nhiều stories đồng thời mà không bị phát hiện là bot
"""

import threading
import time
import random
import re
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Optional, Any
from src import config
from src.scraper_engine import WattpadScraper
from src.scrapers import safe_print
from src.utils.url_utils import extract_story_id_from_url, is_category_url


class ParallelCrawler:
    """
    Multi-level parallel crawler:
    - Level 1: Crawl nhiều stories song song (story-level parallelism)
    - Level 2: Mỗi story crawl chapters song song (chapter-level parallelism)
    - Shared rate limiter để tránh ban IP
    - Shared browser context để giữ session
    """
    
    def __init__(self, max_story_workers=None, max_chapter_workers=None):
        """
        Args:
            max_story_workers: Số stories crawl đồng thời (default: from config)
            max_chapter_workers: Số chapters crawl đồng thời mỗi story (default: from config)
        """
        self.max_story_workers = max_story_workers or config.MAX_STORY_WORKERS
        self.max_chapter_workers = max_chapter_workers or config.MAX_CHAPTER_WORKERS
        
        # Results
        self.results = []
        self.results_lock = threading.Lock()
        
        # Progress tracking (thread-safe)
        self.total_stories = 0
        self.completed_stories = 0
        self.failed_stories = 0
        self.progress_lock = threading.Lock()
        
        # Retry logic (NEW)
        self.retry_queue = []  # Stories to retry
        self.retry_counts = {}  # Track retry attempts per story
        self.retry_lock = threading.Lock()
        
        # Progress checkpoint (NEW)
        self.completed_story_ids = set()  # Track completed stories
        self.checkpoint_lock = threading.Lock()
        
        # Shared rate limiter (thread-safe) - TẤT CẢ threads dùng chung
        from src.scraper_engine import RateLimiter
        self.shared_rate_limiter = RateLimiter()
        
        # MongoDB connection info (shared across threads)
        self.mongo_uri = config.MONGODB_URI if config.MONGODB_ENABLED else None
        self.mongo_db_name = config.MONGODB_DB_NAME if config.MONGODB_ENABLED else None
        
        # Load checkpoint if exists
        self._load_checkpoint()
        
        safe_print("✨ ParallelCrawler initialized")
        safe_print(f"   Story workers: {self.max_story_workers}")
        safe_print(f"   Chapter workers per story: {self.max_chapter_workers}")
        safe_print(f"   Shared rate limiter: {config.MAX_REQUESTS_PER_MINUTE} req/min")
        safe_print(f"   Retry enabled: {config.MAX_STORY_RETRIES > 0} (max {config.MAX_STORY_RETRIES} retries)")
        safe_print(f"   Checkpoint enabled: {config.ENABLE_CHECKPOINTS}")
        if self.completed_story_ids:
            safe_print(f"   📋 Loaded checkpoint: {len(self.completed_story_ids)} stories already completed")
    
    def _load_checkpoint(self):
        """Load progress checkpoint from file"""
        if not config.ENABLE_CHECKPOINTS:
            return
        
        try:
            import json
            if os.path.exists(config.CHECKPOINT_FILE):
                with open(config.CHECKPOINT_FILE, 'r') as f:
                    data = json.load(f)
                    self.completed_story_ids = set(data.get('completed_stories', []))
                    safe_print(f"✅ Checkpoint loaded: {len(self.completed_story_ids)} completed stories")
        except Exception as e:
            safe_print(f"⚠️ Failed to load checkpoint: {e}")
    
    def _save_checkpoint(self):
        """Save progress checkpoint to file (thread-safe)"""
        if not config.ENABLE_CHECKPOINTS:
            return
        
        try:
            import json
            with self.checkpoint_lock:
                data = {
                    'completed_stories': list(self.completed_story_ids),
                    'timestamp': datetime.now().isoformat(),
                    'total_completed': len(self.completed_story_ids)
                }
                # Ensure directory exists
                os.makedirs(os.path.dirname(config.CHECKPOINT_FILE), exist_ok=True)
                with open(config.CHECKPOINT_FILE, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            safe_print(f"⚠️ Failed to save checkpoint: {e}")
    
    def _update_progress(self, success=True, story_id=None):
        """Update progress counter (thread-safe)"""
        with self.progress_lock:
            self.completed_stories += 1
            if not success:
                self.failed_stories += 1
            else:
                # Track successful stories for checkpoint
                if story_id and config.ENABLE_CHECKPOINTS:
                    with self.checkpoint_lock:
                        self.completed_story_ids.add(story_id)
            
            progress_pct = (self.completed_stories / self.total_stories * 100) if self.total_stories > 0 else 0
            safe_print(f"\n{'='*60}")
            safe_print(f"📊 Progress: {self.completed_stories}/{self.total_stories} ({progress_pct:.1f}%)")
            safe_print(f"   ✅ Success: {self.completed_stories - self.failed_stories}")
            safe_print(f"   ❌ Failed: {self.failed_stories}")
            safe_print(f"{'='*60}\n")
            
            # Save checkpoint every N stories
            if config.ENABLE_CHECKPOINTS and self.completed_stories % config.CHECKPOINT_INTERVAL == 0:
                self._save_checkpoint()
                safe_print(f"💾 Checkpoint saved ({len(self.completed_story_ids)} stories)")
    
    def _crawl_story_worker(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        Worker function để crawl 1 story (runs in thread)
        Mỗi thread tạo scraper riêng (Playwright không thread-safe)
        
        Args:
            story_id: Story ID to crawl
            
        Returns:
            Story data dict hoặc None nếu thất bại
        """
        thread_name = threading.current_thread().name
        scraper = None
        
        try:
            safe_print(f"🔄 [{thread_name}] Starting story {story_id}...")
            
            # Random delay trước khi bắt đầu (anti-pattern detection)
            delay = random.uniform(
                config.PARALLEL_RANDOM_DELAY_MIN,
                config.PARALLEL_RANDOM_DELAY_MAX
            )
            time.sleep(delay)
            
            # Tạo scraper riêng cho thread này (Playwright không share được giữa threads)
            scraper = WattpadScraper(max_workers=self.max_chapter_workers)
            
            # Inject shared rate limiter (tất cả threads dùng chung)
            scraper.rate_limiter = self.shared_rate_limiter
            
            # Extract worker ID from thread name (e.g., "StoryWorker_0" -> 0)
            worker_id = thread_name.split('_')[-1] if '_' in thread_name else None
            
            # Start browser với UNIQUE profile directory (tránh conflict)
            # Đăng nhập tự động nếu có credentials trong config
            scraper.start(
                username=config.WATTPAD_USERNAME if hasattr(config, 'WATTPAD_USERNAME') else None,
                password=config.WATTPAD_PASSWORD if hasattr(config, 'WATTPAD_PASSWORD') else None,
                worker_id=worker_id
            )
            
            # Crawl story
            story_data = scraper.scrape_story(
                story_id=story_id,
                fetch_chapters=True,
                fetch_comments=True
            )
            
            if story_data:
                safe_print(f"✅ [{thread_name}] Completed story {story_id}")
                self._update_progress(success=True, story_id=story_id)
                return story_data
            else:
                safe_print(f"❌ [{thread_name}] Failed story {story_id} - No data returned")
                # Add to retry queue if retries enabled
                self._add_to_retry_queue(story_id)
                self._update_progress(success=False)
                return None
                
        except Exception as e:
            safe_print(f"❌ [{thread_name}] Error crawling story {story_id}: {e}")
            traceback.print_exc()
            # Add to retry queue if retries enabled
            self._add_to_retry_queue(story_id)
            self._update_progress(success=False)
            return None
        finally:
            # Đóng scraper của thread này
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
    
    def crawl_stories_parallel(self, story_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl nhiều stories song song với retry logic
        
        Args:
            story_ids: List of story IDs to crawl
            
        Returns:
            List of successfully crawled story data
        """
        if not story_ids:
            safe_print("⚠️ No stories to crawl")
            return []
        
        # Filter out already completed stories from checkpoint
        if config.ENABLE_CHECKPOINTS and self.completed_story_ids:
            original_count = len(story_ids)
            story_ids = [sid for sid in story_ids if sid not in self.completed_story_ids]
            skipped = original_count - len(story_ids)
            if skipped > 0:
                safe_print(f"⏭️ Skipping {skipped} already completed stories (from checkpoint)")
        
        self.total_stories = len(story_ids)
        self.completed_stories = 0
        self.failed_stories = 0
        self.results = []
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🚀 Starting parallel crawl of {len(story_ids)} stories")
        safe_print(f"   Workers: {self.max_story_workers}")
        safe_print(f"   Rate limit: {config.MAX_REQUESTS_PER_MINUTE} req/min")
        safe_print(f"   ⚠️  Each worker creates separate browser (Playwright limitation)")
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
        
        # Final checkpoint save
        if config.ENABLE_CHECKPOINTS:
            self._save_checkpoint()
            safe_print(f"💾 Final checkpoint saved")
        
        elapsed = time.time() - start_time
        
        # Final summary
        safe_print(f"\n{'='*60}")
        safe_print(f"🎉 Parallel crawl completed!")
        safe_print(f"   Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        safe_print(f"   Stories crawled: {len(self.results)}/{len(story_ids)}")
        if retry_results:
            safe_print(f"   Recovered via retry: {len(retry_results)}")
        safe_print(f"   Success rate: {len(self.results)/len(story_ids)*100:.1f}%")
        safe_print(f"   Avg time/story: {elapsed/len(story_ids):.1f}s")
        if len(self.results) > 0:
            safe_print(f"   Speed: {len(self.results)/(elapsed/60):.2f} stories/minute")
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
