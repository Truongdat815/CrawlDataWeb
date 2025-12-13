import json
import logging
import os
import sys
import re
import uuid
import requests
import time
import threading
import random
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from . import config, utils
from .login_service import WattpadLoginService, login_if_needed
from .scrapers.base import safe_print
from .scrapers.user import UserScraper
from .scrapers.website import WebsiteScraper

# Import MongoDB
try:
    from pymongo import MongoClient
    from typing import Optional
    MONGODB_AVAILABLE = True
except ImportError:
    MongoClient = None  # type: ignore
    Optional = None  # type: ignore
    MONGODB_AVAILABLE = False

# Import scrapers

# Import new services and scrapers
from .scrapers.story import StoryScraper
from .scrapers.chapter import ChapterScraper
from .scrapers.chapter_content import ChapterContentScraper
from .scrapers.comment import CommentScraper
from .services.duplicate_checker import DuplicateChecker
from .services.chapter_crawler import ChapterCrawler
from .services.comment_sync_service import CommentSyncService
from .services.user_sync_service import UserSyncService
from .pipelines.chapter_pipeline import ChapterPipeline

# Import playwright-stealth if available
try:
    from playwright_stealth import stealth_sync  # type: ignore[import-not-found]
    STEALTH_AVAILABLE = True
except ImportError:
    stealth_sync = None  # type: ignore
    STEALTH_AVAILABLE = False


class RateLimiter:
    """Thread-safe rate limiter để tránh ban IP"""
    
    def __init__(self, max_requests=None, time_window=60):
        self.max_requests = max_requests or config.MAX_REQUESTS_PER_MINUTE
        self.time_window = time_window  # seconds
        self.request_times = deque()
        self._lock = threading.Lock()  # Thread-safe
    
    def wait_if_needed(self):
        """Wait nếu vượt quá rate limit (thread-safe)"""
        # ✅ FIX: Tách logic tính toán (trong lock) và sleep (ngoài lock)
        sleep_time = 0
        
        with self._lock:
            now = datetime.now()
            
            # Remove requests ngoài time window
            while self.request_times and self.request_times[0] < now - timedelta(seconds=self.time_window):
                self.request_times.popleft()
            
            # Nếu đã max requests, tính sleep time
            if len(self.request_times) >= self.max_requests:
                sleep_time = (self.request_times[0] + timedelta(seconds=self.time_window) - now).total_seconds()
            
            # Record this request TRƯỚC khi sleep (reserve slot)
            self.request_times.append(datetime.now())
        
        # ✅ Sleep NGOÀI lock để không block threads khác
        if sleep_time > 0:
            safe_print(f"⏳ [Thread {threading.current_thread().name}] Rate limit reached. Waiting {sleep_time:.1f}s...")
            time.sleep(sleep_time)
        
        # Random delay cũng ngoài lock
        delay = random.uniform(0.5, 2.0)
        time.sleep(delay)


def retry_request(func, max_retries=None, backoff=None):
    """
    Decorator for retry logic với exponential backoff
    
    Args:
        func: Function to retry
        max_retries: Number of retries (from config if None)
        backoff: Backoff multiplier (from config if None)
    
    Returns:
        Result hoặc None nếu tất cả retries thất bại
    """
    max_retries = max_retries or config.MAX_RETRIES
    backoff = backoff or config.RETRY_BACKOFF
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait_time = backoff ** attempt
                safe_print(f"⚠️ Timeout (attempt {attempt+1}/{max_retries}). Retry in {wait_time}s...")
                time.sleep(wait_time)
            else:
                safe_print(f"❌ Failed after {max_retries} retries (Timeout)")
                return None
        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                wait_time = backoff ** attempt
                safe_print(f"⚠️ Connection error (attempt {attempt+1}/{max_retries}). Retry in {wait_time}s...")
                time.sleep(wait_time)
            else:
                safe_print(f"❌ Failed after {max_retries} retries (Connection error)")
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [429, 503]:  # Rate limit or service unavailable
                if attempt < max_retries:
                    wait_time = backoff ** attempt * 5  # Longer wait for rate limit
                    safe_print(f"⚠️ Server error {e.response.status_code} (attempt {attempt+1}/{max_retries}). Retry in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    safe_print(f"❌ Failed after {max_retries} retries (HTTP {e.response.status_code})")
                    return None
            else:
                safe_print(f"❌ HTTP error {e.response.status_code}: {e}")
                return None
        except Exception as e:
            safe_print(f"❌ Unexpected error: {e}")
            return None
    
    return None


class BrowserManager:
    """
    ✅ OPTIMIZATION: One browser per worker thread (no sharing, no race conditions)
    
    Design:
    - 5 stories = 5 worker threads = 5 browsers
    - Each worker creates its own browser instance
    - No sharing = no race conditions = safe
    - Thread-local browser cache
    
    Browser lifetime:
    1. Created when worker starts
    2. Used for login + prefetch only
    3. Closed when worker finishes
    
    Benefits:
    - Simpler than browser pool
    - No deadlocks
    - No race conditions
    - Each thread is independent
    - Easy to debug
    """
    
    def __init__(self):
        self.browser_cache = {}  # {thread_id: browser}
        self._lock = threading.Lock()
    
    def get_browser_for_thread(self, thread_id: str):
        """Get or create browser for current thread (lazy creation)"""
        with self._lock:
            if thread_id not in self.browser_cache:
                # Will be created on first use in scraper.start()
                return None
            return self.browser_cache.get(thread_id)
    
    def cache_browser(self, thread_id: str, browser):
        """Cache browser for thread"""
        if browser:
            with self._lock:
                self.browser_cache[thread_id] = browser
    
    def remove_browser(self, thread_id: str):
        """Remove browser from cache"""
        with self._lock:
            if thread_id in self.browser_cache:
                del self.browser_cache[thread_id]
    
    def close_all(self):
        """Close all cached browsers"""
        with self._lock:
            for browser in self.browser_cache.values():
                try:
                    browser.close()
                except:
                    pass
            self.browser_cache.clear()


from .utils.story_hash import extract_text_from_wattpad_html, compute_story_hash_from_text
from .utils.date_utils import format_for_db
from .utils.checkpoint import load_checkpoint, save_checkpoint, remove_checkpoint


class WattpadScraper:
    """Wattpad API-based scraper using modular components"""
    def __init__(self, db=None, max_workers=None):
        self.db = db
        self.context = None
        self.page = None
        self.playwright = None
        self.max_workers = max_workers or config.MAX_CHAPTER_WORKERS
        # Rate limiter
        self.rate_limiter = RateLimiter()
        # HTTP session
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": config.DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
        })
        # Proxy config
        if config.HTTP_PROXY or config.HTTPS_PROXY:
            proxies = {}
            if config.HTTP_PROXY:
                proxies["http"] = config.HTTP_PROXY
            if config.HTTPS_PROXY:
                proxies["https"] = config.HTTPS_PROXY
            self.http.proxies.update(proxies)
            safe_print(f"🌐 Proxy configured: {config.HTTPS_PROXY or config.HTTP_PROXY}")
        self._current_proxy = None
        # Login service
        self.login_service = WattpadLoginService()
        # Scrapers (set in start, but initialize as None)
        self.story_scraper = None
        self.story_info_scraper = None
        self.chapter_scraper = None
        self.comment_scraper = None
        self.user_scraper = None
        self.chapter_content_scraper = None
        self.website_scraper = None
        # MongoDB collections
        self.mongo_collection_stories = None
        self.mongo_collection_story_info = None
        self.mongo_collection_chapters = None
        self.mongo_collection_chapter_contents = None
        self.mongo_collection_comments = None
        self.mongo_collection_users = None
        self.mongo_collection_websites = None
        # MongoDB client
        self.mongo_client = None
        self.mongo_db = None
        # Cached service instances (lazy init to avoid re-creating per-call)
        self.duplicate_checker = None
        self.comment_service = None
        self.user_service = None
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                if MongoClient is not None:
                    self.mongo_client = MongoClient(config.MONGODB_URI)
                    self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                    self.mongo_collection_stories = self.mongo_db[config.MONGODB_COLLECTION_STORIES]
                    self.mongo_collection_story_info = self.mongo_db["storyInfo"]
                    self.mongo_collection_chapters = self.mongo_db["chapters"]
                    self.mongo_collection_chapter_contents = self.mongo_db["chapterContents"]
                    self.mongo_collection_comments = self.mongo_db["comments"]
                    self.mongo_collection_users = self.mongo_db["users"]
                    self.mongo_collection_websites = self.mongo_db["websites"]
                    safe_print("✅ Đã kết nối MongoDB với 7 collections (stories, storyInfo, chapters, chapterContents, comments, users, websites)")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

        # Ensure `self.db` references the active MongoDB database when available.
        # Some callers (e.g. ParallelCrawler) construct WattpadScraper without
        # passing a `db` argument, so default to the internal `mongo_db`.
        if self.db is None and self.mongo_db is not None:
            self.db = self.mongo_db
        # If still None, log a warning so DuplicateChecker doesn't receive None unexpectedly
        if self.db is None:
            try:
                import logging
                logging.warning("WattpadScraper initialized without a DB (self.db is None). Some features will use file-only storage.")
            except Exception:
                pass

    def fetch_story_links_from_page(self, page_url):
        """
        Stub method to fetch story links from a page URL.
        Args:
            page_url (str): The URL of the page to scrape.
        Returns:
            list: List of story URLs (empty for now).
        """
        # Deprecated stub: HTML index scraping is disabled by default.
        # The HTTP/session/proxy/login initialization belongs in `__init__` and
        # is already performed there. Keep this method as a small stub so it
        # can be safely re-enabled later behind a config flag without
        # reintroducing duplicated initialization logic.
        safe_print(f"[DEPRECATED] fetch_story_links_from_page called for: {page_url}")
        if getattr(config, "ENABLE_HTML_INDEX_SCRAPING", False):
            safe_print("ℹ️ ENABLE_HTML_INDEX_SCRAPING=True but no implementation provided; returning []")
        return []

    def check_update_chapters(self, story_id):
        """
        Hàm này được gọi khi phát hiện storyUrl hoặc storyHash đã tồn tại trong DB
        Tự động kiểm tra và cập nhật chapter/comment nếu có thay đổi
        """
        # Lấy dữ liệu story từ API
        api_story_data = self.fetch_story_from_api(story_id)
        if not api_story_data:
            safe_print(f"❌ Không lấy được dữ liệu story từ API cho storyId={story_id}")
            return None
        # Lấy danh sách chapters từ API
        api_chapters = api_story_data.get("parts", [])
        # info: parts list received from API
        db = self.mongo_db
        # Initialize or reuse services (lazy cached on the scraper instance)
        if getattr(self, 'duplicate_checker', None) is None:
            try:
                self.duplicate_checker = DuplicateChecker(db)
            except Exception:
                self.duplicate_checker = DuplicateChecker(None)

        if getattr(self, 'comment_service', None) is None:
            try:
                self.comment_service = CommentSyncService(db, CommentScraper(self.page, db))
            except Exception:
                # Fallback to a minimal CommentSyncService if initialization fails
                self.comment_service = CommentSyncService(db, CommentScraper(self.page, None))

        if getattr(self, 'user_service', None) is None:
            self.user_service = UserSyncService(db, None)

        services = {
            "duplicate_checker": self.duplicate_checker,
            "comment_service": self.comment_service,
            "user_service": self.user_service,
        }
        # Nếu DB báo thiếu chương, tự động gọi ChapterCrawler.finish_story
        try:
            web_story_id = str(api_story_data.get("webStoryId"))
            dup = services["duplicate_checker"]
            dup_status = dup.check_story(web_story_id)
            if dup_status and dup_status.get("exists") and (dup_status.get("chapters_count", 0) == 0):
                safe_print(f"[SCRAPER_ENGINE] ℹ️ Story {web_story_id} has 0 chapters in DB — running finish_story to populate metadata")
                chapter_crawler = ChapterCrawler(self)
                res = chapter_crawler.finish_story(web_story_id, story_id)
                safe_print(f"[SCRAPER_ENGINE] ✅ finish_story result: {res}")
        except Exception as e:
            safe_print(f"[SCRAPER_ENGINE] ⚠️ Error while auto-finishing story {story_id}: {e}")
        # Reuse scrapers attached to the engine when available, otherwise
        # lazily instantiate and attach them so subsequent calls reuse them.
        if getattr(self, 'chapter_scraper', None) is None:
            self.chapter_scraper = ChapterScraper(self.page, db)
        if getattr(self, 'chapter_content_scraper', None) is None:
            self.chapter_content_scraper = ChapterContentScraper(self.page, db)

        scrapers = {
            "chapter": self.chapter_scraper,
            "content": self.chapter_content_scraper,
        }
        pipeline = ChapterPipeline(db, scrapers, services)
        # Quick optimization: if the API reports the same number of parts
        # as we already have in DB, skip processing to save work.
        try:
            web_id_for_count = web_story_id
        except Exception:
            web_id_for_count = None

        try:
            if web_id_for_count and self.mongo_collection_chapters is not None:
                # Use duplicate checker if it has cached counts
                dup_status = None
                try:
                    dup_status = self.duplicate_checker.check_story(web_id_for_count)
                except Exception:
                    dup_status = None

                db_chapter_count = None
                if dup_status and isinstance(dup_status.get('chapters_count', None), int):
                    db_chapter_count = dup_status.get('chapters_count')
                else:
                    try:
                        # Try a best-effort count by webStoryId stored in chapters
                        db_chapter_count = self.mongo_collection_chapters.count_documents({'webStoryId': str(web_id_for_count)})
                    except Exception:
                        db_chapter_count = None

                if db_chapter_count is not None and len(api_chapters) == int(db_chapter_count):
                    safe_print(f"ℹ️ No change: API parts ({len(api_chapters)}) == DB chapters ({db_chapter_count}) for {web_id_for_count}")
                    # Fast-path: nothing to do
                    return False
        except Exception:
            # Fall through; we don't want this optimization to break the flow
            pass
        # Map raw API parts to validated chapter_meta before processing the pipeline.
        # This ensures `pipeline.process()` always receives a chapter_meta with
        # `chapterId` and `webChapterId` populated.
        try:
            web_story_id = str(api_story_data.get("id") or api_story_data.get("webStoryId") or story_id)
        except Exception:
            web_story_id = story_id

        # Process chapters in batches to avoid mapping/processing thousands at once.
        # Batch size and sleep interval can be configured via config.CHAPTER_PROCESS_BATCH_SIZE
        # and config.CHAPTER_BATCH_SLEEP_SECONDS. Also respect MAX_CHAPTERS_PER_STORY.
        batch_size = getattr(config, 'CHAPTER_PROCESS_BATCH_SIZE', 50) or 50
        batch_sleep = getattr(config, 'CHAPTER_BATCH_SLEEP_SECONDS', 0.5) or 0.5
        max_to_process = getattr(config, 'MAX_CHAPTERS_PER_STORY', None) or len(api_chapters)
        max_to_process = min(max_to_process, len(api_chapters))

        idx = 0
        while idx < max_to_process:
            end = min(idx + batch_size, max_to_process)
            subset = api_chapters[idx:end]
            for rel, part in enumerate(subset, start=idx + 1):
                try:
                    mapped = None
                    try:
                        mapped = scrapers["chapter"].map_api_part_to_chapter(part, web_story_id, order=rel-1)
                    except Exception as e:
                        safe_print(f"[SCRAPER_ENGINE] ⚠️ map_api_part_to_chapter failed for part index {rel}: {e}")

                    if not mapped:
                        # skip parts we couldn't map/validate
                        continue

                    pipeline.process(mapped)
                except Exception as e:
                    safe_print(f"[SCRAPER_ENGINE] ⚠️ Error processing mapped chapter (index {rel}): {e}")

            # Pause between batches to avoid long-running CPU/memory spikes and reduce pressure
            # on downstream systems (DB / network). This also prevents hammering the pipeline
            # when stories have very large numbers of parts.
            try:
                if end < max_to_process:
                    time.sleep(batch_sleep)
            except Exception:
                pass

            idx = end
        return True

    def _build_proxy_dict(self, proxy_server=None):
        """Helper to build proxy dict for Playwright from proxy server string or config."""
        if not proxy_server:
            proxies_list = getattr(config, 'PROXIES', []) or []
            if proxies_list:
                proxy_server = random.choice(proxies_list)
                self._current_proxy = proxy_server
            elif config.HTTPS_PROXY or config.HTTP_PROXY:
                proxy_server = config.HTTPS_PROXY or config.HTTP_PROXY
                self._current_proxy = proxy_server
        
        if proxy_server:
            return {'server': proxy_server}
        return None

    def _simulate_human_behavior(self, page):
        """Simulate human-like behavior to avoid bot detection"""
        try:
            import random
            # Random delay
            page.wait_for_timeout(random.randint(1000, 3000))
            # Random mouse movement
            page.mouse.move(random.randint(100, 400), random.randint(100, 400))
            # Random scroll
            page.mouse.wheel(0, random.randint(300, 800))
            # Another delay
            page.wait_for_timeout(random.randint(1000, 2000))
        except Exception as e:
            safe_print(f"⚠️ Human behavior simulation failed: {e}")

    def start(self, username=None, password=None, worker_id=None):
        """Khởi động scrapers, Playwright browser, và login
        
        Args:
            username: Wattpad username (optional)
            password: Wattpad password (optional)
            worker_id: Worker ID for parallel crawling (to create unique profile dir)
        """
        try:
            # Khởi tạo Playwright persistent context (simulate real browser)
            from playwright.sync_api import sync_playwright
            import random

            self.playwright = sync_playwright().start()

            # Ensure profile dir exists - UNIQUE per worker to avoid conflicts
            profile_dir = getattr(config, 'PLAYWRIGHT_PROFILE_DIR', None)
            if not profile_dir:
                profile_dir = os.path.join(os.getcwd(), '.pw-profile')
            
            # Add worker_id suffix if provided (for parallel crawling)
            if worker_id is not None:
                profile_dir = f"{profile_dir}_worker_{worker_id}"
            
            os.makedirs(profile_dir, exist_ok=True)

            # Setup proxy using helper
            proxy_dict = self._build_proxy_dict()

            ua = getattr(config, 'PLAYWRIGHT_USER_AGENT', config.DEFAULT_USER_AGENT)

            # Extra headers to bypass bot detection
            extra_headers = {
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
            }

            # Launch persistent context (headless or headful based on config)
            pw = self.playwright
            # playwright runtime object may be typed as Optional in static analysis; ignore for attribute access
            
            # Enhanced stealth arguments for headless mode
            stealth_args = [
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-infobars',
                '--window-size=1280,800',
            ]
            
            # Additional args for headless mode to mimic real browser
            if config.HEADLESS:
                stealth_args.extend([
                    '--disable-gpu',
                    '--disable-setuid-sandbox',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-background-networking',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                ])
            
            self.context = pw.chromium.launch_persistent_context(
                profile_dir,
                headless=config.HEADLESS,
                user_agent=ua,
                proxy=proxy_dict,  # type: ignore[arg-type]
                extra_http_headers=extra_headers,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
                args=stealth_args
            )  # type: ignore[attr-defined]

            # Get page (existing or new)
            pages = self.context.pages
            self.page = pages[0] if pages else self.context.new_page()

            # Apply stealth to page (bypass bot detection)
            if STEALTH_AVAILABLE:
                try:
                    stealth_sync(self.page)  # type: ignore[misc]
                    safe_print("✅ Stealth mode activated")
                except Exception as e:
                    safe_print(f"⚠️ Stealth activation failed: {e}")
            else:
                safe_print("⚠️ playwright-stealth not installed, skipping stealth mode")
                safe_print("   Install with: pip install playwright-stealth")

            safe_print("✅ Playwright persistent context initialized")

            # ========== WATTPAD LOGIN STRATEGY ==========
            # ⚠️ QUAN TRỌNG: Chỉ login 1 lần, sau đó reuse cookies
            # Tránh 5 threads login cùng lúc → account lock / IP ban
            
            # Step 1: Load cookies từ file nếu tồn tại (reuse cơ)
            if config.SKIP_LOGIN_IF_COOKIE_EXISTS and self.login_service.load_cookies_from_file():
                safe_print("🍪 Loaded cookies từ file - Bỏ qua login")
                self.login_service.apply_cookies_to_browser(self.page)
            # Step 2: Nếu có credentials mới, login 1 lần và lưu cookies
            elif username and password:
                safe_print("\n" + "="*60)
                safe_print("🔑 WATTPAD LOGIN (1 lần duy nhất)")
                safe_print("="*60)
                
                # Login qua Playwright
                self.login_service.login_with_playwright(self.page, username, password)
                
                # Lấy cookies từ browser và lưu vào file
                cookies = self.page.context.cookies()
                if cookies:
                    self.login_service.save_cookies_to_file(cookies)
                    safe_print("✅ Cookies lưu vào file - Các threads khác sẽ reuse")
            else:
                safe_print("⚠️ Không có credentials và cookie file, scrape mà không đăng nhập")
                safe_print("   Một số trang có thể cần đăng nhập để xem")

        except Exception as e:
            safe_print(f"⚠️ Lỗi khởi tạo Playwright: {e}")
            safe_print("   Tiếp tục mà không có Playwright (chỉ dùng API)")

        # Khởi tạo scrapers (dù có Playwright hay không)
        from .scrapers.story_info import StoryInfoScraper
        self.story_scraper = StoryScraper(self.page, self.mongo_db)
        self.story_info_scraper = StoryInfoScraper(self.page, self.mongo_db)
        self.chapter_scraper = ChapterScraper(self.page, self.mongo_db)
        self.comment_scraper = CommentScraper(self.page, self.mongo_db)
        self.user_scraper = UserScraper(self.page, self.mongo_db)
        self.chapter_content_scraper = ChapterContentScraper(self.page, self.mongo_db)
        self.website_scraper = WebsiteScraper(self.page, self.mongo_db)
        
        # Tạo Wattpad website entry nếu chưa có (1 lần duy nhất)
        if self.mongo_collection_websites is not None:
            self.wattpad_website = WebsiteScraper.get_or_create_wattpad_website(
                self.mongo_collection_websites
            )
        else:
            self.wattpad_website = None
        
        safe_print("✅ Bot đã khởi động! (Wattpad API crawler + Playwright + Login)")

    @staticmethod
    def fetch_story_links_from_page(page_url: str, max_stories: int | None = None):
        """
        Backward-compatible static stub for extracting story links from a
        category/browse page. Older callers may pass `max_stories` as a
        keyword — accept it and behave as before (no-op / disabled by
        default).

        Returns an empty list unless `config.ENABLE_HTML_INDEX_SCRAPING`
        is set and a concrete implementation is provided later.
        """
        safe_print(f"[fetch_story_links_from_page] Extracting stories from: {page_url}")

        # Respect optional max_stories and config default
        max_stories = int(max_stories) if max_stories else getattr(config, 'MAX_STORIES_PER_BATCH', None)

        extracted = []
        seen = set()

        # Try fast path: HTTP GET + BeautifulSoup
        try:
            headers = {"User-Agent": getattr(config, 'DEFAULT_USER_AGENT', 'python-requests')}
            resp = requests.get(page_url, headers=headers, timeout=getattr(config, 'REQUEST_TIMEOUT', 15))
            if resp is not None and resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a.get('href')
                    if not href:
                        continue

                    # Normalize
                    href_str = str(href)
                    # Accept patterns like '/123456-title' or '/story/123456-title' or '/story/123456'
                    if re.search(r'/story/\d+', href_str) or re.search(r'/\d+-', href_str) or re.search(r'/\d+$', href_str):
                        if not href_str.startswith('http'):
                            if href_str.startswith('/'):
                                href_str = config.BASE_URL + href_str
                            else:
                                href_str = config.BASE_URL + '/' + href_str

                        if href_str not in seen:
                            extracted.append(href_str)
                            seen.add(href_str)
                            if max_stories and len(extracted) >= max_stories:
                                break

                if extracted:
                    safe_print(f"   ✅ Extracted {len(extracted)} story links via requests parser")
                    return extracted[:max_stories] if max_stories else extracted
        except Exception as e:
            safe_print(f"   ⚠️ HTTP parse failed: {e}")

        # Fallback: Use Playwright to execute JS and try to read window.prefetched or DOM
        try:
            try:
                from playwright.sync_api import sync_playwright
            except Exception:
                sync_playwright = None

            if sync_playwright is None:
                safe_print("   ⚠️ Playwright not available — cannot perform JS-rendered fallback")
                return extracted

            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(page_url, wait_until='load', timeout=getattr(config, 'REQUEST_TIMEOUT', 15) * 1000)
            page.wait_for_timeout(1500)

            # Try window.prefetched first (contains parts metadata)
            try:
                pref = page.evaluate('() => window.prefetched')
            except Exception:
                pref = None

            if pref and isinstance(pref, dict):
                for key, value in pref.items():
                    if key.startswith('part.') and isinstance(value, dict) and 'metadata' in key:
                        data = value.get('data') or {}
                        url = data.get('url') or data.get('chapterUrl')
                        cid = data.get('id') or data.get('chapterId')
                        if url:
                            link = url if url.startswith('http') else config.BASE_URL + url
                        elif cid:
                            link = f"{config.BASE_URL}/{cid}"
                        else:
                            continue

                        if link not in seen:
                            extracted.append(link)
                            seen.add(link)
                            if max_stories and len(extracted) >= max_stories:
                                break

                if extracted:
                    browser.close()
                    pw.stop()
                    safe_print(f"   ✅ Extracted {len(extracted)} story links via Playwright prefetched")
                    return extracted[:max_stories] if max_stories else extracted

            # As last resort, parse page content DOM
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if not href:
                    continue
                href_str = str(href)
                if re.search(r'/story/\d+', href_str) or re.search(r'/\d+-', href_str) or re.search(r'/\d+$', href_str):
                    if not href_str.startswith('http'):
                        if href_str.startswith('/'):
                            href_str = config.BASE_URL + href_str
                        else:
                            href_str = config.BASE_URL + '/' + href_str

                    if href_str not in seen:
                        extracted.append(href_str)
                        seen.add(href_str)
                        if max_stories and len(extracted) >= max_stories:
                            break

            browser.close()
            pw.stop()
            if extracted:
                safe_print(f"   ✅ Extracted {len(extracted)} story links via Playwright DOM parse")
                return extracted[:max_stories] if max_stories else extracted
        except Exception as e:
            safe_print(f"   ⚠️ Playwright fallback failed: {e}")

        # Nothing found
        return extracted

    def _rotate_proxy_and_restart(self):
        """Choose a different proxy from config.PROXIES and restart the Playwright context."""
        try:
            proxies_list = getattr(config, 'PROXIES', []) or []
            if not proxies_list:
                safe_print("ℹ️ No proxies configured to rotate")
                return False

            # Choose a new proxy different from current
            candidates = [p for p in proxies_list if p != self._current_proxy]
            if not candidates:
                candidates = proxies_list
            new_proxy = random.choice(candidates)
            self._current_proxy = new_proxy
            safe_print(f"🔁 Rotating proxy: {new_proxy}")

            # Close existing context
            try:
                if self.context is not None:
                    try:
                        self.context.close()
                    except Exception:
                        pass
            except Exception:
                pass

            # Launch new persistent context with new proxy
            profile_dir = getattr(config, 'PLAYWRIGHT_PROFILE_DIR', None)
            if not profile_dir:
                profile_dir = os.path.join(os.getcwd(), '.pw-profile')
            os.makedirs(profile_dir, exist_ok=True)

            proxy_dict = self._build_proxy_dict(new_proxy)
            ua = getattr(config, 'PLAYWRIGHT_USER_AGENT', config.DEFAULT_USER_AGENT)

            # Extra headers to bypass bot detection (same as start())
            extra_headers = {
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
            }

            pw = self.playwright
            if pw is None:
                return False
            
            # Enhanced stealth arguments (same as start())
            stealth_args = [
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-infobars',
                '--window-size=1280,800',
            ]
            
            if config.HEADLESS:
                stealth_args.extend([
                    '--disable-gpu',
                    '--disable-setuid-sandbox',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-background-networking',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                ])
            
            self.context = pw.chromium.launch_persistent_context(
                profile_dir,
                headless=config.HEADLESS,
                user_agent=ua,
                proxy=proxy_dict,  # type: ignore[arg-type]
                extra_http_headers=extra_headers,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
                args=stealth_args
            )  # type: ignore[attr-defined]
            pages = self.context.pages
            self.page = pages[0] if pages else self.context.new_page()
            
            # Apply stealth to new page
            if STEALTH_AVAILABLE:
                try:
                    stealth_sync(self.page)  # type: ignore[misc]
                except Exception:
                    pass
            
            self._current_proxy = new_proxy
            safe_print("✅ Restarted Playwright context with new proxy")
            return True
        except Exception as e:
            safe_print(f"⚠️ Failed to rotate proxy and restart context: {e}")
            return False


    def stop(self):
        """Đóng MongoDB connection và Playwright"""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
        if self.mongo_client:
            self.mongo_client.close()
            safe_print("✅ Đã đóng kết nối MongoDB")
        safe_print("zzz Bot đã tắt.")

    # ==================== WATTPAD API METHODS ====================
    
    def scrape_stories_from_api(self, story_ids, fields=None):
        """
        Cào nhiều bộ truyện từ Wattpad API
        
        Args:
            story_ids: List of story IDs to scrape
            fields: API fields to retrieve (default: all standard fields)
        
        Returns:
            List of processed story data
        """
        if not story_ids:
            safe_print("❌ Không có story ID nào được cung cấp!")
            return []
        
        if fields is None:
            # Include tags and categories so story mapping can use API-provided values
            fields = "id,title,length,voteCount,readCount,createDate,lastPublishedPart,user(name,avatar),cover,url,numParts,isPaywalled,paidModel,completed,mature,description,tags,categories"
        
        safe_print(f"📚 Đang cào {len(story_ids)} bộ truyện từ Wattpad API...")
        
        stories_data = []
        for idx, story_id in enumerate(story_ids, 1):
            try:
                story_data = self.fetch_story_from_api(story_id, fields)
                if story_data:
                    if self.story_scraper is None:
                        safe_print(f"⚠️ [{idx}/{len(story_ids)}] Story scraper chưa được khởi tạo")
                        continue
                    processed = self.story_scraper.scrape_story_metadata(story_data)
                    if processed:
                        stories_data.append(processed)
                        safe_print(f"✅ [{idx}/{len(story_ids)}] Cào: {story_data.get('title')}")
                else:
                    safe_print(f"⚠️ [{idx}/{len(story_ids)}] Lỗi khi lấy story ID {story_id}")
            except Exception as e:
                safe_print(f"❌ [{idx}/{len(story_ids)}] Lỗi: {e}")
                continue
        
        safe_print(f"\n🎉 Hoàn thành cào {len(stories_data)}/{len(story_ids)} bộ truyện")
        return stories_data

    def check_paid_content(self, story_id):
        """
        Kiểm tra xem story có yêu cầu trả phí hay không
        Sử dụng API: /v5/story/{story_id}/paid-content/metadata
        
        Args:
            story_id: Story ID
        
        Returns:
            dict with 'has_full_access' and 'is_paid' or None if error
        """
        if not self.page:
            safe_print("⚠️ Playwright page not available for paid content check")
            return None
        
        try:
            # Use Playwright to call API (cần cookies/auth)
            url = f"{config.BASE_URL}/v5/story/{story_id}/paid-content/metadata"
            
            self.rate_limiter.wait_if_needed()
            response = self.page.request.get(url)
            
            if response.status == 200:
                data = response.json()
                story_info = data.get("story", {})
                has_full_access = story_info.get("has_full_access", True)
                is_paid = bool(story_info.get("price"))
                
                return {
                    "has_full_access": has_full_access,
                    "is_paid": is_paid,
                    "price": story_info.get("price", [])
                }
            else:
                safe_print(f"⚠️ Paid content API returned status {response.status}")
                return None
                
        except Exception as e:
            safe_print(f"⚠️ Error checking paid content: {e}")
            return None

    def fetch_story_from_api(self, story_id, fields=None):
        """
        Lấy dữ liệu 1 bộ truyện từ Wattpad API
        Với rate limiting và retry logic
        
        Args:
            story_id: Story ID
            fields: API fields to retrieve
        
        Returns:
            API response dict or None
        """
        if fields is None:
            # Include tags and categories in default fields
            fields = "id,title,length,voteCount,readCount,createDate,modifyDate,lastPublishedPart,user(name,avatar),cover,url,numParts,isPaywalled,paidModel,completed,mature,description,tags,categories"
        
        url = f"{config.BASE_URL}/api/v3/stories/{story_id}"
        params = {"fields": fields}
        
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        # Retry with backoff
        def make_request():
            response = self.http.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            # Inspect raw text to aid debugging when API returns minimal payload
            try:
                text = response.text
            except Exception:
                text = None

            # Parse JSON and log raw text when payload appears minimal
            data = None
            try:
                data = response.json()
            except Exception:
                # If JSON parsing fails, log raw text for debugging and re-raise
                logging.exception("fetch_story_from_api: failed to parse JSON for %s; raw response truncated:", story_id)
                if text:
                    logging.debug(text[:2000])
                raise

            try:
                if isinstance(data, dict):
                    minimal_keys = set(data.keys()) <= {"id", "webStoryId", "storyId"}
                    if minimal_keys or len(data) <= 2:
                        logging.debug("fetch_story_from_api: minimal payload for %s — raw response (truncated): %s", story_id, (text[:2000] if text else "<no-text>"))
            except Exception:
                logging.exception("fetch_story_from_api: error inspecting payload for %s", story_id)

            return data
        
        try:
            return retry_request(make_request)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi fetch story {story_id}: {e}")
            return None

    def fetch_comments_from_api_v5(self, web_chapter_id, chapter_id=None, use_checkpoint=True, full_sync=False):
        """
        Lấy comments từ Wattpad API v5 (endpoint mới) - dùng Playwright từ main thread
        
        Args:
            web_chapter_id: Original Wattpad chapter/part ID (for API calls)
            chapter_id: Internal chapter UUID (for saving to DB, optional)
        
        Returns:
            List of comments (limited by MAX_COMMENTS_PER_CHAPTER)
        """
        # Use web_chapter_id for DB if chapter_id not provided
        db_chapter_id = chapter_id or web_chapter_id
        
        # Sequential processing using Playwright (thread-safe, main thread only)
        self._v5_saved_flag = False
        collected = []
        seen = set()

        # Checkpoint support: load previous cursor if requested
        checkpoint = None
        if use_checkpoint:
            try:
                checkpoint = load_checkpoint(web_chapter_id)
            except Exception:
                checkpoint = None
            if checkpoint and checkpoint.get('finished'):
                safe_print(f"      ✅ Checkpoint for {web_chapter_id} shows finished — skipping fetch")
                return []

        # When doing a full sync we collect all mapped comments and call
        # CommentSyncService once at the end so deletions can be detected.
        full_sync_collected = [] if full_sync else None

        def process_page(resource_id, namespace, cursor=None):
            """Fetch and process a single page using Playwright"""
            key = (resource_id, namespace, cursor)
            if key in seen:
                return
            seen.add(key)

            try:
                # Use Playwright to fetch (browser cookies/token)
                if not self.page:
                    safe_print("⚠️ No Playwright page available")
                    return
                
                # Log pagination info
                cursor_display = f"cursor={cursor[:30]}..." if cursor and len(cursor) > 30 else f"cursor={cursor}"
                safe_print(f"      📄 Fetching {namespace} page: {cursor_display if cursor else 'page 1'}")
                
                self.rate_limiter.wait_if_needed()
                data = CommentScraper.fetch_v5_page_via_playwright(self.page, resource_id, namespace, cursor)

                # If no data and we have proxies configured, try rotating proxy and retry once
                if (not data or "comments" not in data) and getattr(config, 'PROXIES', []):
                    safe_print("⚠️ No data from v5 endpoint; attempting proxy rotation and retry")
                    try:
                        rotated = self._rotate_proxy_and_restart()
                        if rotated:
                            self.rate_limiter.wait_if_needed()
                            data = CommentScraper.fetch_v5_page_via_playwright(self.page, resource_id, namespace, cursor)
                    except Exception as e:
                        safe_print(f"⚠️ Proxy rotation attempt failed: {e}")

                if not data or "comments" not in data:
                    return

                # Delegate mapping & saving to CommentScraper
                try:
                    parent_id = resource_id if namespace == 'comments' else None
                    website_id = self.wattpad_website.get("websiteId") if self.wattpad_website else None
                    mapped_list, parents, next_cursor = CommentScraper.process_v5_comments_page(
                        data, db_chapter_id, namespace, 
                        comment_scraper=self.comment_scraper,
                        parent_comment_id=parent_id,
                        website_id=website_id
                    )
                except Exception as e:
                    safe_print(f"      ⚠️ Error processing v5 page: {e}")
                    mapped_list, parents, next_cursor = [], [], None

                if mapped_list:
                    try:
                        from .services.comment_sync_service import CommentSyncService
                        comment_sync = CommentSyncService(self.mongo_db, self.comment_scraper)

                        # Ensure each mapped comment includes `content` and `webChapterId`
                        for m in mapped_list:
                            if 'content' not in m and 'commentText' in m:
                                m['content'] = m.get('commentText')
                            m.setdefault('webChapterId', resource_id)

                        if full_sync_collected is not None:
                            # Collect for final full sync (do not persist per-page)
                            for m in mapped_list:
                                full_sync_collected.append(m)
                        else:
                            # Incremental mode: persist per-page (upsert) and update checkpoint
                            comment_sync.sync_comments(resource_id, web_comments=mapped_list)
                            # Add to collected (respecting max limit)
                            added_count = 0
                            for m in mapped_list:
                                if config.MAX_COMMENTS_PER_CHAPTER and len(collected) >= config.MAX_COMMENTS_PER_CHAPTER:
                                    break
                                collected.append(m)
                                added_count += 1
                            self._v5_saved_flag = True
                            safe_print(f"      ✅ Synced {added_count} comments (total: {len(collected)}/{config.MAX_COMMENTS_PER_CHAPTER or 'unlimited'})")

                        # Update checkpoint with next_cursor (if any)
                        try:
                            if use_checkpoint:
                                save_checkpoint(web_chapter_id, next_cursor=next_cursor, finished=(next_cursor is None))
                        except Exception:
                            pass
                    except Exception as e:
                        safe_print(f"      ⚠️ Error during comment sync/collect: {e}")

                # Recursively fetch replies (only for 'parts' namespace with replyCount > 0)
                if namespace == 'parts' and parents:
                    safe_print(f"      💬 Found {len(parents)} comments with replies, fetching...")
                    for p in parents:
                        process_page(p, 'comments', None)

                # Pagination
                if next_cursor and (not config.MAX_COMMENTS_PER_CHAPTER or len(collected) < config.MAX_COMMENTS_PER_CHAPTER):
                    cursor_short = next_cursor[:40] + '...' if len(next_cursor) > 40 else next_cursor
                    safe_print(f"      ➡️ Next page available, continuing pagination... (cursor: {cursor_short})")
                    process_page(resource_id, namespace, next_cursor)
                elif not next_cursor:
                    safe_print(f"      ℹ️ No more pages (reached end)")

            except Exception as e:
                safe_print(f"      ⚠️ Lỗi fetch comments v5 ({resource_id} {namespace}): {e}")
                return

        # Start from main thread (no ThreadPoolExecutor - Playwright sequential)
        # Use 'parts' namespace for chapter-level comments
        # If checkpoint has a saved next_cursor, resume from there
        start_cursor = None
        if checkpoint and checkpoint.get('next_cursor'):
            start_cursor = checkpoint.get('next_cursor')
            safe_print(f"      🔁 Resuming from checkpoint cursor for {web_chapter_id}")

        process_page(web_chapter_id, 'parts', start_cursor)

        # If full_sync, persist all collected comments at once so deletions are detected
        if full_sync and full_sync_collected is not None:
            try:
                from .services.comment_sync_service import CommentSyncService
                comment_sync = CommentSyncService(self.mongo_db, self.comment_scraper)
                for m in full_sync_collected:
                    m.setdefault('webChapterId', web_chapter_id)
                comment_sync.sync_comments(web_chapter_id, web_comments=full_sync_collected)
                try:
                    if use_checkpoint:
                        save_checkpoint(web_chapter_id, next_cursor=None, finished=True)
                except Exception:
                    pass
                collected = full_sync_collected[:config.MAX_COMMENTS_PER_CHAPTER] if config.MAX_COMMENTS_PER_CHAPTER else full_sync_collected
            except Exception as e:
                safe_print(f"      ⚠️ Full-sync persist failed: {e}")

        return collected

    def fetch_comments_from_api(self, story_id, part_id):
        """
        Lấy comments từ Wattpad API
        Với rate limiting, retry logic, và limit comments
        
        Args:
            story_id: Story ID
            part_id: Chapter/Part ID
        
        Returns:
            List of comments (limited by MAX_COMMENTS_PER_CHAPTER)
        """
        url = f"{config.BASE_URL}/api/v3/stories/{story_id}/parts/{part_id}/comments"
        
        all_comments = []
        pagination_cursor = None
        
        try:
            while True:
                # Check limit
                if config.MAX_COMMENTS_PER_CHAPTER and len(all_comments) >= config.MAX_COMMENTS_PER_CHAPTER:
                    safe_print(f"   ⏸️ Đã reach limit {config.MAX_COMMENTS_PER_CHAPTER} comments")
                    break
                
                # Apply rate limiting
                self.rate_limiter.wait_if_needed()
                
                params = {}
                if pagination_cursor:
                    params["after"] = pagination_cursor
                
                def make_request():
                    response = self.http.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
                    response.raise_for_status()
                    return response.json()
                
                data = retry_request(make_request)
                if not data:
                    break
                
                if "comments" in data:
                    comments_to_add = data["comments"]
                    
                    # Trim if would exceed limit
                    if config.MAX_COMMENTS_PER_CHAPTER:
                        remaining = config.MAX_COMMENTS_PER_CHAPTER - len(all_comments)
                        comments_to_add = comments_to_add[:remaining]
                    
                    all_comments.extend(comments_to_add)
                
                # Check for next page and limit
                if config.MAX_COMMENTS_PER_CHAPTER and len(all_comments) >= config.MAX_COMMENTS_PER_CHAPTER:
                    break
                
                if "pagination" in data and "after" in data["pagination"]:
                    pagination_cursor = data["pagination"]["after"]
                else:
                    break
            
            return all_comments
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy comments: {e}")
            return []

    def fetch_chapters_from_api(self, story_id):
        """
        Lấy danh sách tất cả chapters từ Wattpad API
        
        LƯU Ý: Wattpad API /parts endpoint yêu cầu authorization header
        Fallback: Sử dụng prefetched data hoặc HTML parsing
        
        Args:
            story_id: Story ID
        
        Returns:
            List of chapter data (limited by MAX_CHAPTERS_PER_STORY)
        """
        # Sử dụng endpoint đúng: /api/v3/stories/{story_id} để lấy danh sách parts
        url = f"{config.BASE_URL}/api/v3/stories/{story_id}"
        params = {"fields": "id,title,parts"}

        # Checkpoint: if we have cached parts for this story, return them
        try:
            cached = load_checkpoint(str(story_id), kind='chapters')
            if cached and isinstance(cached.get('payload'), list):
                safe_print(f"   🔁 Loaded chapters from checkpoint for {story_id} ({len(cached.get('payload'))} parts)")
                return cached.get('payload')
        except Exception:
            pass

        try:
            self.rate_limiter.wait_if_needed()
            def make_request():
                response = self.http.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
                return response.json()
            data = retry_request(make_request)
            if data and "parts" in data:
                parts = data["parts"]
                # Save checkpoint payload for chapters so we can resume without hitting API
                try:
                    # Normalize parts to list of dicts containing id and commentCount for compactness
                    compact = []
                    for p in parts:
                        try:
                            compact.append({'webChapterId': str(p.get('id') or p.get('webChapterId') or p.get('chapterId')), 'commentCount': int(p.get('commentCount', 0))})
                        except Exception:
                            try:
                                compact.append({'webChapterId': str(p.get('id') or p.get('webChapterId') or p.get('chapterId'))})
                            except Exception:
                                continue
                    save_checkpoint(str(story_id), kind='chapters', payload={'parts': compact}, finished=True)
                except Exception:
                    pass
                return parts
            else:
                return []
        except Exception as e:
            safe_print(f"⚠️ API /stories/{{id}} không khả dụng: {e}")
            return []

    def check_and_sync_comments_totals(self, story_id: str, source: str = 'web', auto_sync: str = 'changed'):
        """Check saved overall comment total (processed chapters only) and optionally sync chapters that decreased.

        Args:
            story_id: story identifier used for chapters checkpoint
            source: 'web' to pull current counts from API, 'db' to read from DB
            auto_sync: 'none' | 'changed' | 'story' — default 'changed'
        Returns:
            dict with saved_overall, current_overall, decreased_chapters list
        """
        try:
            # Load saved per-chapter totals from chapters checkpoint
            ckp = load_checkpoint(str(story_id), kind='chapters')
            if not ckp or not isinstance(ckp, dict):
                safe_print(f"⚠️ No chapters checkpoint for {story_id}")
                return {'error': 'no_checkpoint'}

            payload = ckp.get('payload') or {}
            saved_totals = payload.get('chapters_totals') or {}
            if not saved_totals:
                # Fallback: if payload.parts exists, but chapters_totals missing, try to use parts commentCount
                parts = payload.get('parts') or []
                saved_totals = {str(p.get('webChapterId')): int(p.get('commentCount', 0)) for p in parts if p.get('webChapterId')}

            if not saved_totals:
                safe_print(f"⚠️ No saved per-chapter totals in checkpoint for {story_id}")
                return {'error': 'no_saved_totals'}

            # Build current totals for the same set of processed chapters
            current_totals = {}
            processed_keys = list(saved_totals.keys())

            if source == 'web':
                # Fetch parts from API (this will prefer cached checkpoint if available)
                parts = self.fetch_chapters_from_api(story_id)
                parts_map = {str(p.get('id') or p.get('webChapterId') or p.get('chapterId')): int(p.get('commentCount', 0) or 0) for p in parts}
                for k in processed_keys:
                    current_totals[k] = parts_map.get(k, 0)
            else:
                # Read from DB collection 'chapters'
                try:
                    col = self.mongo_collection_chapters
                    for k in processed_keys:
                        doc = None
                        try:
                            doc = col.find_one({'webChapterId': str(k)})
                        except Exception:
                            doc = None
                        current_totals[k] = int(doc.get('totalComments', 0) if doc else 0)
                except Exception:
                    for k in processed_keys:
                        current_totals[k] = 0

            # Compute overall sums and decreased chapters
            saved_overall = sum(int(v or 0) for v in saved_totals.values())
            current_overall = sum(int(v or 0) for v in current_totals.values())
            decreased = [k for k, sv in saved_totals.items() if int(current_totals.get(k, 0)) < int(sv or 0)]

            safe_print(f"[CHECK] story={story_id} saved_overall={saved_overall} current_overall={current_overall} decreased={len(decreased)}")

            # If auto_sync requested for changed chapters, run full-sync per decreased chapter
            synced = []
            if auto_sync == 'changed' and decreased:
                for web_chapter_id in decreased:
                    try:
                        # try to find internal chapterId
                        chapter_doc = None
                        try:
                            chapter_doc = self.mongo_collection_chapters.find_one({'webChapterId': str(web_chapter_id)}) if self.mongo_collection_chapters is not None else None
                        except Exception:
                            chapter_doc = None
                        chapter_id = chapter_doc.get('chapterId') if chapter_doc else None
                        safe_print(f"[CHECK] Syncing decreased chapter {web_chapter_id} (chapterId={chapter_id})")
                        # Run full-sync for this chapter (will call CommentSyncService and detect deletes)
                        self.fetch_comments_from_api_v5(web_chapter_id, chapter_id=chapter_id, use_checkpoint=False, full_sync=True)
                        synced.append(web_chapter_id)
                    except Exception as e:
                        safe_print(f"[CHECK] Failed to sync chapter {web_chapter_id}: {e}")

                # After syncing, refresh current_totals from DB or web
                refreshed = {}
                if source == 'web':
                    parts = self.fetch_chapters_from_api(story_id)
                    parts_map = {str(p.get('id') or p.get('webChapterId') or p.get('chapterId')): int(p.get('commentCount', 0) or 0) for p in parts}
                    for k in processed_keys:
                        refreshed[k] = parts_map.get(k, 0)
                else:
                    for k in processed_keys:
                        try:
                            doc = self.mongo_collection_chapters.find_one({'webChapterId': str(k)}) if self.mongo_collection_chapters is not None else None
                        except Exception:
                            doc = None
                        refreshed[k] = int(doc.get('totalComments', 0) if doc else 0)

                # Update checkpoint saved totals to refreshed values
                try:
                    new_payload = payload
                    new_payload['chapters_totals'] = refreshed
                    new_payload['overall_comments_total'] = sum(int(v or 0) for v in refreshed.values())
                    save_checkpoint(str(story_id), kind='chapters', payload=new_payload, finished=ckp.get('finished') if isinstance(ckp, dict) else False)
                except Exception:
                    pass

            return {
                'saved_overall': saved_overall,
                'current_overall': current_overall,
                'decreased': decreased,
                'synced': synced,
            }
        except Exception as e:
            safe_print(f"[CHECK] Unexpected error while checking totals for {story_id}: {e}")
            return {'error': str(e)}

    def fetch_categories(self):
        """
        Lấy danh sách categories từ Wattpad API
        Với rate limiting và retry logic
        
        Returns:
            List of categories with mapping
        """
        url = f"{config.BASE_URL}/api/v3/categories"
        
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        def make_request():
            response = self.http.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        
        try:
            categories = retry_request(make_request)
            if not categories:
                return {}
            
            # Tạo mapping id → name_english
            category_map = {cat["id"]: cat["name_english"] for cat in categories}
            safe_print(f"✅ Đã lấy {len(category_map)} categories")
            return category_map
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy categories: {e}")
            return {}

    def scrape_story(self, story_id, fetch_chapters=True, fetch_comments=True, story_url=None):
        """
        Cào toàn bộ thông tin bộ truyện:
        1. Metadata từ API /api/v3/stories/{id}
        2. Tags + Categories từ HTML window.prefetched
        3. Chapters từ HTML window.prefetched
        4. Comments từ HTML window.prefetched
        
        Args:
            story_id: Story ID hoặc full URL to scrape
            fetch_chapters: Whether to fetch chapter list
            fetch_comments: Whether to fetch comments
            story_url: Story URL (optional, will be extracted from story_id if URL is provided)
        
        Returns:
            Complete story data dict
        """
        import re
        # ======= CHECK TRÙNG STORY URL TRÊN DB (CÙNG NỀN TẢNG) =======
        # Ưu tiên kiểm tra trước khi check hash
        story_url_to_check = story_url
        if not story_url_to_check and isinstance(story_id, str) and story_id.startswith('http'):
            story_url_to_check = story_id
        if hasattr(self, 'mongo_collection_stories') and self.mongo_collection_stories is not None and story_url_to_check:
            existing_url = self.mongo_collection_stories.find_one({'storyUrl': story_url_to_check})
            if existing_url:
                safe_print(f"⚠️ [CONSOLE] Truyện với storyUrl này đã tồn tại trong DB (storyId={existing_url.get('storyId')}, storyName={existing_url.get('storyName')}). Chuyển sang chế độ check update.")
                safe_print(f"[CONSOLE] Đang gọi check_update_chapters cho storyId={existing_url.get('storyId')}")
                try:
                    res = self.check_update_chapters(existing_url.get('storyId'))
                    safe_print(f"[CONSOLE] check_update_chapters result: {res}")
                except Exception as e:
                    safe_print(f"[CONSOLE] check_update_chapters raised: {e}")

        first_chapter_html = None

        # Handle nếu story_id là URL
        if isinstance(story_id, str) and story_id.startswith('http'):
            # Extract ID từ URL: https://www.wattpad.com/STORYID-title
            story_url = story_id
            match = re.search(r'wattpad\.com/(\d+)', story_id)
            if match:
                story_id = match.group(1)
            else:
                safe_print(f"❌ Không thể extract story ID từ URL: {story_id}")
                return None

        safe_print(f"\n{'='*60}")
        safe_print(f"📖 Bắt đầu cào story ID: {story_id}")
        safe_print(f"{'='*60}")

        # Variable to store freeChapter info from first chapter
        free_chapter_from_html = None

        # ✅ CHECK: Story đã được cào hay chưa
        dup_checker = DuplicateChecker(self.db)
        # Determine webStoryId before checking; DuplicateChecker expects webStoryId
        web_story_id_to_check = None
        try:
            if isinstance(story_id, str) and story_id.isdigit():
                web_story_id_to_check = story_id
            else:
                if self.mongo_collection_stories is not None:
                    doc = self.mongo_collection_stories.find_one({"storyId": str(story_id)})
                    if doc and doc.get("webStoryId"):
                        web_story_id_to_check = doc.get("webStoryId")
        except Exception:
            web_story_id_to_check = None

        story_status = dup_checker.check_story(web_story_id_to_check) if web_story_id_to_check else None
        if story_status:
            # If story exists, check whether chapters and contents are complete
            try:
                chapters_count = story_status.get("chapters_count", 0)
                chapters_with_content = story_status.get("chapters_with_content", 0)

                if chapters_count and chapters_with_content and chapters_count == chapters_with_content:
                    # Fully scraped -> safe to return
                    dup_checker.close()
                    return story_status

                # Story exists but incomplete -> delegate to ChapterCrawler to finish missing chapters/content
                safe_print("ℹ️ Story exists but chapters/content incomplete — delegating to ChapterCrawler to finish")

                # Try to determine web_story_id from DB (preferred)
                web_story_id = None
                try:
                    if self.mongo_collection_stories is not None:
                        story_doc = self.mongo_collection_stories.find_one({"storyId": str(story_id)})
                        if story_doc is not None:
                            web_story_id = story_doc.get("webStoryId") or story_doc.get("web_story_id") or story_doc.get("web_id")
                except Exception:
                    web_story_id = None

                # If not found in DB, try to fetch metadata from API to obtain web ID
                if not web_story_id:
                    try:
                        api_meta = self.fetch_story_from_api(story_id)
                        if api_meta:
                            web_story_id = str(api_meta.get("id") or api_meta.get("webStoryId") or api_meta.get("storyId"))
                    except Exception:
                        web_story_id = None

                if not web_story_id:
                    safe_print("❌ Cannot determine webStoryId for this story; returning existing status")
                    dup_checker.close()
                    return story_status

                # Import ChapterCrawler lazily to avoid circular imports
                from .services.chapter_crawler import ChapterCrawler

                chapter_crawler = ChapterCrawler(self)
                try:
                    finish_res = chapter_crawler.finish_story(web_story_id, story_id)
                    safe_print(f"[SCRAPER_ENGINE] ✅ finish_story result: {finish_res}")
                except Exception as e:
                    safe_print(f"[SCRAPER_ENGINE] ⚠️ Error running ChapterCrawler.finish_story: {e}")
                    finish_res = None
                dup_checker.close()
                # NOTE: Do not return early here. finish_story only populates
                # chapter metadata in the DB; we must continue the full
                # `scrape_story` flow so chapter content is fetched and saved.
                safe_print(f"ℹ️ Continuing full scrape to fetch chapter content after finish_story")
            except Exception as e:
                safe_print(f"⚠️ Error while delegating to ChapterCrawler: {e}")
                dup_checker.close()
                return story_status
        dup_checker.close()

        # 1. Fetch story metadata từ API
        story_data = self.fetch_story_from_api(story_id)
        if not story_data:
            safe_print(f"❌ Không thể lấy metadata cho story {story_id}")
            return None

        # Some Wattpad API responses may be minimal (only contain id/webStoryId).
        # If so, try progressive fallbacks to obtain chapters/metadata:
        # 1) Call fetch_chapters_from_api to get `parts` list
        # 2) If Playwright available, fetch `window.prefetched` from chapter URL
        # 3) As last resort, call ChapterCrawler.finish_story to populate minimal chapter metadata
        try:
            if isinstance(story_data, dict):
                minimal_keys = set(story_data.keys()) <= {"id", "webStoryId", "storyId"}
                # Also treat very small payloads as minimal
                if minimal_keys or len(story_data) <= 2:
                    safe_print(f"⚠️ API returned minimal metadata for {story_id}; attempting fallbacks to obtain chapters")

                    # Try fetch_chapters_from_api (parts from API)
                    try:
                        parts = self.fetch_chapters_from_api(story_id)
                        if parts:
                            safe_print(f"   ✅ Obtained {len(parts)} parts via fetch_chapters_from_api fallback")
                            story_data["parts"] = parts
                        else:
                            # Try prefetched HTML (requires Playwright page)
                            chapter_url = None
                            # Build a plausible chapter URL from last part id or story id
                            if story_data.get("id"):
                                chapter_url = f"{config.BASE_URL}/{story_data.get('id')}"
                            elif story_data.get("webStoryId"):
                                chapter_url = f"{config.BASE_URL}/{story_data.get('webStoryId')}"

                            if chapter_url and self.page:
                                prefetched = self.fetch_html_prefetched_data(chapter_url)
                                if prefetched:
                                    safe_print(f"   ✅ Obtained prefetched data via Playwright fallback")
                                    extra_info = StoryScraper.extract_story_info_from_prefetched(prefetched, story_id)
                                    # Merge possible parts into story_data
                                    if extra_info and extra_info.get("parts"):
                                        story_data["parts"] = extra_info.get("parts")

                            # If still no parts, try ChapterCrawler.finish_story to populate minimal chapters
                            if not story_data.get("parts"):
                                try:
                                    safe_print(f"   ℹ️ Attempting ChapterCrawler.finish_story as final fallback for {story_id}")
                                    from .services.chapter_crawler import ChapterCrawler
                                    chapter_crawler = ChapterCrawler(self)
                                    finish_res = chapter_crawler.finish_story(str(story_data.get("id") or story_id), story_id)
                                    safe_print(f"   ✅ finish_story result: {finish_res}")
                                    # After finish_story, try loading chapters from DB
                                    if self.mongo_collection_chapters is not None:
                                        db_parts = list(self.mongo_collection_chapters.find({"storyId": str(finish_res or story_id)}))
                                        if db_parts:
                                            story_data["parts"] = db_parts
                                except Exception as e:
                                    safe_print(f"   ⚠️ finish_story fallback failed: {e}")
                    except Exception as e:
                        safe_print(f"   ⚠️ Error during fallback attempts: {e}")
        except Exception:
            # Defensive: do not fail scraping because fallback checks raised
            safe_print(f"⚠️ Unexpected error in fallback logic for story {story_id}")

        # Lấy story URL từ API response nếu không được provide
        if not story_url and story_data.get("url"):
            story_url = story_data["url"]
            if not story_url.startswith("http"):
                story_url = config.BASE_URL + story_url

        if story_url:
            safe_print(f"   URL: {story_url}")

        # Try to fetch from HTML prefetched data (tags, categories, chapters)
        extra_info = None
        prefetched_data = None

        # Để fetch prefetched, cần URL của CHAPTER, không phải story overview
        # Nếu có lastPublishedPart, dùng chapter URL đó
        chapter_url_for_prefetch = None
        if story_data.get("lastPublishedPart"):
            last_part = story_data["lastPublishedPart"]
            # Cách 1: Nếu có url field
            if last_part.get("url"):
                chapter_url_for_prefetch = last_part["url"]
                if not chapter_url_for_prefetch.startswith("http"):
                    chapter_url_for_prefetch = config.BASE_URL + chapter_url_for_prefetch
            # Cách 2: Build URL từ part ID
            elif last_part.get("id"):
                part_id = last_part["id"]
                chapter_url_for_prefetch = f"{config.BASE_URL}/{part_id}"
        else:
            safe_print(f"   ℹ️ Không có lastPublishedPart, bỏ qua prefetched data")

        if chapter_url_for_prefetch:
            safe_print(f"   🌐 Đang fetch HTML prefetched data...")
            prefetched_data = self.fetch_html_prefetched_data(chapter_url_for_prefetch)
            if prefetched_data:
                extra_info = StoryScraper.extract_story_info_from_prefetched(prefetched_data, story_id)

                # 2a. Extract author from prefetched data (cho truyện free/premium có prefetched)
                user_info_from_prefetch = UserScraper.extract_user_info_from_prefetched(prefetched_data)
                if user_info_from_prefetch and user_info_from_prefetch.get("userName"):
                    if self.user_scraper:
                        self.user_scraper.save_user_to_mongo(
                            user_info_from_prefetch["userName"],
                            user_info_from_prefetch["userName"],
                            user_info_from_prefetch.get("avatar")
                        )
                        safe_print(f"   ✅ Saved author from prefetched: {user_info_from_prefetch['userName']}")

        # 2b. Extract and save author/user info from API response (fallback + bổ sung)
        if story_data.get("user"):
            user_data = story_data["user"]
            user_name = user_data.get("name")
            avatar = user_data.get("avatar")

            if user_name and self.user_scraper:
                self.user_scraper.save_user_to_mongo(
                    user_name,  # Use username as userId
                    user_name,
                    avatar
                )
                safe_print(f"   ✅ Saved author from API: {user_name}")

        # 3. Process story metadata (kèm tags + categories)
        if self.story_scraper is None:
            safe_print(f"❌ Story scraper chưa được khởi tạo")
            return None
        processed_story = StoryScraper.map_api_to_story(story_data, extra_info)

        if not processed_story:
            safe_print(f"❌ Lỗi khi xử lý story metadata")
            return None

        # 4. CHECK PAID CONTENT trước khi fetch chapters
        is_paid_story = False
        has_full_access = True

        if fetch_chapters:
            safe_print(f"   💰 Đang kiểm tra paid content...")
            paid_info = self.check_paid_content(story_id)
            
            if paid_info:
                is_paid_story = paid_info.get("is_paid", False)
                has_full_access = paid_info.get("has_full_access", True)
                
                if is_paid_story:
                    if has_full_access:
                        safe_print(f"   💰 Paid story - Đã có quyền truy cập (có thể đã mua)")
                        safe_print(f"      💵 Price: {paid_info.get('price', 'Unknown')}")
                    else:
                        safe_print(f"   💰 Paid story - CHƯA có quyền truy cập đầy đủ")
                        safe_print(f"      💵 Price: {paid_info.get('price', 'Unknown')}")
                        safe_print(f"      ℹ️  Sẽ cào các chapters MIỄN PHÍ (nếu có)")
                        # KHÔNG skip, vẫn cho cào free chapters
        
        # 5. Optionally fetch chapters
        if fetch_chapters:
            safe_print(f"   📚 Đang lấy danh sách chapters...")
            chapters = []
            chapter_urls = []

            # Prefer `parts` from story_data as authoritative chapter list (if available)
            parts_from_api = story_data.get("parts") or []
            if parts_from_api and isinstance(parts_from_api, list):
                safe_print(f"   ℹ️ Sử dụng `parts[]` từ API làm nguồn chapters ({len(parts_from_api)})")
                for idx_p, p in enumerate(parts_from_api, 1):
                    web_chapter_id = str(p.get("id"))
                    chapter_id = WebsiteScraper.generate_chapter_id(web_chapter_id, prefix="wp")
                    
                    chapter_obj = {
                        "chapterId": chapter_id,              # wp_uuid_v7
                        "webChapterId": web_chapter_id,      # Original Wattpad ID
                        "order": idx_p - 1,
                        "chapterName": p.get("title"),
                        "chapterUrl": p.get("url") if p.get("url") and p.get("url").startswith("http") else (config.BASE_URL + str(p.get("url")) if p.get("url") else f"{config.BASE_URL}/{p.get('id')}"),
                        "publishedTime": format_for_db(p.get("createDate")) or p.get("createDate"),
                        "storyId": story_id,                 # Parent wp_uuid_v7
                        "voted": p.get("voteCount", 0),
                        "views": p.get("readCount", 0),
                        "totalComments": p.get("commentCount", 0),
                    }
                    chapters.append(chapter_obj)

            # If we already populated chapters from parts[], skip HTML/API discovery
            if not chapters:
            
                # Step 1: Extract chapter URLs from story overview page
                # NOTE: HTML overview extraction disabled to avoid navigating the
                # browser to the story overview (which may load external/irrelevant
                # links). If you want to re-enable this behavior, set
                # `ENABLE_HTML_INDEX_SCRAPING = True` in config and implement a
                # safe extractor. For now we skip Playwright navigation entirely.
                safe_print("   ℹ️ HTML overview chapter extraction disabled; skipping Playwright navigation")
                
                # Step 2: If no URLs found, fallback to API or prefetched
                if not chapter_urls:
                    chapters = self.fetch_chapters_from_api(story_id)
                    if not chapters and prefetched_data:
                        chapters = ChapterScraper.extract_chapters_from_prefetched(prefetched_data, story_id)
                else:
                    # Build basic chapter objects từ URLs
                    for url in chapter_urls:
                        # Extract chapter ID - should be at start after domain
                        # URL format: https://www.wattpad.com/1234567-chapter-name
                        chapter_id_match = re.search(r'/([0-9]+)(?:-|/|$)', url)
                        if chapter_id_match:
                            web_chapter_id = chapter_id_match.group(1)
                            chapter_id = WebsiteScraper.generate_chapter_id(web_chapter_id, prefix="wp")
                            
                            chapter_obj = {
                                "chapterId": chapter_id,         # wp_uuid_v7
                                "webChapterId": web_chapter_id,  # Original Wattpad ID
                                "storyId": story_id,             # Parent wp_uuid_v7
                                "chapterUrl": url,
                                "chapterName": f"Chapter {len(chapters) + 1}",
                            }
                            chapters.append(chapter_obj)
            
            # Normalize `chapters` list: if it's a raw `parts` list from API
            # (contains dicts with 'id' etc.) convert to the internal chapter_obj
            try:
                if chapters and isinstance(chapters, list) and len(chapters) > 0 and isinstance(chapters[0], dict) and ('id' in chapters[0] or 'title' in chapters[0]) and not chapters[0].get('chapterId'):
                    safe_print("   🔧 Normalizing raw API parts into chapter objects...")
                    normalized = []
                    for idx_p, p in enumerate(chapters, 1):
                        web_chapter_id = str(p.get('id') or p.get('webChapterId') or p.get('chapterId') or '')
                        chapter_id = WebsiteScraper.generate_chapter_id(web_chapter_id, prefix="wp") if web_chapter_id else None
                        chapter_obj = {
                            "chapterId": chapter_id,
                            "webChapterId": web_chapter_id,
                            "order": idx_p - 1,
                            "chapterName": p.get('title'),
                            "chapterUrl": p.get('url') if p.get('url') and str(p.get('url')).startswith('http') else (config.BASE_URL + str(p.get('url')) if p.get('url') else f"{config.BASE_URL}/{p.get('id')}"),
                            "publishedTime": format_for_db(p.get('createDate') or p.get('modifyDate')) or (p.get('createDate') or p.get('modifyDate')),
                            "storyId": story_id,
                            "voted": p.get('voteCount', 0),
                            "views": p.get('readCount', 0),
                            "totalComments": p.get('commentCount', 0),
                        }
                        normalized.append(chapter_obj)
                    chapters = normalized
            except Exception:
                pass

            if chapters:
                # Step 3: Scrape từng chapter - FOR EACH CHAPTER: content + comments + metadata
                safe_print(f"   📖 Bắt đầu cào {min(len(chapters), config.MAX_CHAPTERS_PER_STORY or len(chapters))} chapters...")
                # chapters list prepared (normalized if needed)
                
                max_to_fetch = config.MAX_CHAPTERS_PER_STORY or len(chapters)
                
                for idx, chapter in enumerate(chapters, 1):
                    if idx > max_to_fetch:
                        break
                    
                    chapter_id = chapter.get("chapterId")  # UUID for DB
                    web_chapter_id = chapter.get("webChapterId")  # Original Wattpad ID for API
                    
                    if not chapter_id:
                        continue
                    
                    # Build chapter URL if not available
                    chapter_url = chapter.get("chapterUrl")
                    if not chapter_url:
                        chapter_url = f"{config.BASE_URL}/{chapter_id}"
                    
                    # Skip content extraction if no page available
                    if not self.page or not self.chapter_content_scraper:
                        safe_print(f"\n   📖 [{idx}/{max_to_fetch}] Chapter: {chapter.get('chapterName')} (không có Playwright page)")
                        continue
                    
                    try:
                        safe_print(f"\n   📖 [{idx}/{max_to_fetch}] Cào chapter: {chapter.get('chapterName')}")
                        
                        # ✅ CHECK: Chapter đã được cào hay chưa (chỉ skip nếu đã có content)
                        dup_checker = DuplicateChecker(self.mongo_db)
                        # Use should_crawl_chapter to decide whether to fetch content
                        try:
                            should_crawl = dup_checker.should_crawl_chapter(web_chapter_id)
                        except Exception:
                            should_crawl = True

                        if not should_crawl:
                            # If content exists, still sync comments (new/edited/deleted)
                            try:
                                if fetch_comments and web_chapter_id and (self.mongo_db is not None):
                                    # Try to fetch comments for this chapter via available methods.
                                    web_comments = None
                                    try:
                                        fetcher = getattr(self.comment_scraper, 'fetch_comments', None)
                                        if callable(fetcher):
                                            web_comments = fetcher(web_chapter_id)
                                        else:
                                            # Fallback to scraper_engine's v5 fetch (uses Playwright/session)
                                            web_comments = self.fetch_comments_from_api_v5(web_chapter_id, chapter_id=chapter_id)
                                    except Exception:
                                        try:
                                            web_comments = self.fetch_comments_from_api_v5(web_chapter_id, chapter_id=chapter_id)
                                        except Exception:
                                            web_comments = []

                                    from .services.comment_sync_service import CommentSyncService
                                    comment_sync = CommentSyncService(self.mongo_db, self.comment_scraper)
                                    comment_sync.sync_comments(web_chapter_id, web_comments=web_comments)
                                    safe_print(f"      ✅ Synced comments for existing chapter webChapterId={web_chapter_id}")
                            except Exception as e:
                                safe_print(f"      ⚠️ Lỗi khi sync comments for existing chapter {web_chapter_id}: {e}")

                            dup_checker.close()
                            safe_print(f"      ℹ️ Skipping chapter (already has content): webChapterId={web_chapter_id}")
                            continue  # Skip to next chapter
                        dup_checker.close()
                        
                        # Step 3a: Navigate tới chapter URL
                        self.rate_limiter.wait_if_needed()
                        self.page.goto(chapter_url, wait_until="load", timeout=config.REQUEST_TIMEOUT * 1000)
                        self.page.wait_for_timeout(2000)
                        self._simulate_human_behavior(self.page)
                        
                        # Step 3a.1: Extract freeChapter info from FIRST chapter only
                        if idx == 1 and self.story_info_scraper:
                            page_html_for_free_check = self.page.content()
                            free_chapter_from_html = self.story_info_scraper.extract_free_chapter_from_html(page_html_for_free_check)
                        
                        # Step 3b: Fetch window.prefetched data của chapter này
                        chapter_prefetched_data = self.page.evaluate("() => window.prefetched")
                        
                        if chapter_prefetched_data:
                            # Extract metadata từ prefetched (NEW SCHEMA)
                            for key, value in chapter_prefetched_data.items():
                                if key.startswith("part.") and "metadata" in key:
                                    if "data" in value:
                                        chapter_meta = value["data"]
                                        chapter["chapterName"] = chapter_meta.get("title", chapter.get("chapterName"))
                                        chapter["views"] = chapter_meta.get("readCount", 0)
                                        chapter["voted"] = chapter_meta.get("voteCount", 0)
                                        chapter["order"] = chapter_meta.get("order", idx - 1)
                                        chapter["totalComments"] = chapter_meta.get("commentCount", 0)
                                        chapter["publishedTime"] = format_for_db(chapter_meta.get("createDate")) or chapter_meta.get("createDate")
                                        # ✅ KEEP webChapterId from URL parsing (line 1068) - don't overwrite with None
                                        # chapter["webChapterId"] was already set from URL parsing above
                                        safe_print(f"      ✅ Metadata: {chapter['chapterName']}")
                                        break
                        else:
                            # Nếu không có prefetched data, dùng placeholder name
                            chapter["chapterName"] = f"Chapter {idx}: {chapter.get('chapterName', 'Unknown')}"
                            chapter["order"] = idx - 1
                        
                        # Step 3c: Extract chapter content từ API v2 qua Playwright
                        # ✅ Dùng Playwright để giữ session/cookies cho API v2
                        # Lợi ích: Tránh lỗi 400, giữ authentication state
                        
                        chapter_text = None
                        if web_chapter_id and str(web_chapter_id).isdigit():
                            try:
                                # Fetch từ API v2 sử dụng Playwright (sync)
                                chapter_text = self.chapter_content_scraper.fetch_chapter_content_from_apiv2_sync(
                                    self.page,
                                    web_chapter_id
                                )
                            except Exception as e:
                                safe_print(f"      ⚠️ Lỗi fetch API v2: {e}")
                        else:
                            safe_print(f"      ⚠️ webChapterId không hợp lệ: {web_chapter_id}")
                        
                        if chapter_text:
                            # Map vào schema
                            safe_print(f"      [DEBUG] Mapping chapter_text to chapter_content for chapter_id={chapter_id}")
                            chapter_content = self.chapter_content_scraper.map_html_to_chapter_content(chapter_text, chapter_id)
                            # Save first chapter HTML/text for hashing
                            if idx == 1:
                                    first_chapter_html = chapter_text
                                    # TÍNH HASH VÀ GÁN VÀO STORY NGAY SAU KHI LẤY CHAPTER 1
                                    safe_print(f"   [DEBUG] chapter_text (raw) chapter 1: {repr(chapter_text)}")
                                    # Nếu có thẻ <p> thì extract, còn không thì dùng trực tiếp
                                    if '<p>' in chapter_text:
                                        clean_text = extract_text_from_wattpad_html(chapter_text)
                                    else:
                                        clean_text = chapter_text
                                    safe_print(f"   [DEBUG] clean_text chapter 1: {repr(clean_text)}")
                                    story_hash = compute_story_hash_from_text(clean_text)
                                    safe_print(f"   [DEBUG] storyHash (chapter 1): {story_hash}")
                                    processed_story['storyHash'] = story_hash
                                    safe_print(f"   ✅ storyHash (chapter 1): {story_hash}")
                            if chapter_content and chapter_content.get("content"):
                                content_len = len(chapter_content.get('content', ''))
                                safe_print(f"      ✅ Content (API): {content_len} bytes")
                                # Save chapter_content to MongoDB
                                if self.chapter_content_scraper:
                                    safe_print(f"      [DEBUG] Saving chapter_content to MongoDB for chapter_id={chapter_id}")
                                    self.chapter_content_scraper.save_chapter_content_to_mongo(chapter_content)
                            else:
                                safe_print(f"      ⚠️ Không thể parse content từ API")
                        else:
                            safe_print(f"      ⚠️ Không extract được content từ API")
                            if is_paid_story and not has_full_access:
                                safe_print(f"      🔒 Chapter này có thể cần trả phí - bỏ qua")
                        
                        # Step 3d: Extract comments cho CHAPTER NÀY (không phải chapter cuối cùng)
                        chapter_comments = None
                        if fetch_comments:
                            safe_print(f"      💬 Đang lấy comments...")
                            # Use API v5 with Playwright (only method)
                            # ✅ IMPORTANT: Pass webChapterId (for API) and chapterId (UUID for DB)
                            chapter_comments = None
                            try:
                                chapter_comments = self.fetch_comments_from_api_v5(
                                    web_chapter_id=web_chapter_id,
                                    chapter_id=chapter_id
                                )
                            except Exception as e:
                                safe_print(f"      ⚠️ Lỗi API v5: {e}")
                            if chapter_comments:
                                # ✅ LƯUÍ: Không lưu comments trong chapter object
                                # Comments sẽ được lưu riêng vào comments collection
                                safe_print(f"      ✅ Comments: {len(chapter_comments)} comments")
                                # ====== Chỉ check comment deleted nếu chapter đã từng cào (tồn tại trong DB) ======
                                try:
                                    # CommentChecker không còn tồn tại, nếu cần kiểm tra comment deleted hãy dùng CommentSyncService hoặc bỏ qua đoạn này
                                    pass
                                except Exception as e:
                                    safe_print(f"      ⚠️ Lỗi khi check/update comment deleted: {e}")
                        
                        # Step 3e: Save chapter to MongoDB (NGAY SAU KHI HOÀN THÀNH)
                        if self.chapter_scraper:
                            self.chapter_scraper.save_chapter_to_mongo(chapter)
                        
                        # Step 3f: Save comments to MongoDB (nếu có)
                        if fetch_comments and chapter_comments and self.comment_scraper:
                            # If v5 fetcher already saved comments to DB, skip double-saving
                            if getattr(self, '_v5_saved_flag', False):
                                safe_print(f"      ℹ️ Comments already saved by v5 fetcher; skipping duplicate save")
                            else:
                                for comment in chapter_comments:
                                    user_name = comment.get("userName")  # Extract userName from comment (display name)
                                    safe_print(f"      [DEBUG] Saving comment to MongoDB commentId={comment.get('commentId')} user={user_name}")
                                    self.comment_scraper.save_comment_to_mongo(comment, user_name=user_name)

                        # Step 3g: If we did NOT fetch comments in this run (e.g. content-skip
                        # branch), run CommentSyncService to detect new/edited/deleted
                        # comments. If chapter_comments exists (we just fetched them),
                        # no need to run the sync step for first-time fetch.
                        if fetch_comments and not chapter_comments and web_chapter_id and (self.mongo_db is not None):
                            try:
                                from .services.comment_sync_service import CommentSyncService
                                comment_sync = CommentSyncService(self.mongo_db, self.comment_scraper)
                                comment_sync.sync_comments(web_chapter_id)
                                safe_print(f"      ✅ Comment sync completed for webChapterId={web_chapter_id}")
                            except Exception as e:
                                safe_print(f"      ⚠️ Lỗi khi sync comments: {e}")
                        
                    except Exception as e:
                        safe_print(f"      ⚠️ Lỗi: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Don't add chapters to story document - they're stored separately
                # processed_story["chapters"] = chapters  # REMOVED - chapters in separate collection
                safe_print(f"\n   ✅ Hoàn thành cào {len(chapters)} chapters")
        
        # ======= CHECK STORYHASH TRƯỚC KHI LƯU DB =======
        if 'storyHash' in processed_story and processed_story['storyHash']:
            existing = None
            if self.mongo_collection_stories is not None:
                existing = self.mongo_collection_stories.find_one({'storyHash': processed_story['storyHash']})
            if existing:
                safe_print(f"\n⚠️ [CONSOLE] Truyện với storyHash này đã tồn tại trong DB (storyId={existing.get('storyId')}, storyName={existing.get('storyName')}). Gọi check update chapter.")
                # Nếu có hàm check_update_chapters thì gọi nhưng không return sớm;
                # tiếp tục luồng để đảm bảo content được cào.
                safe_print(f"[CONSOLE] Đang gọi check_update_chapters cho storyId={existing.get('storyId')} (WattpadScraper)")
                try:
                    res = self.check_update_chapters(existing.get('storyId'))
                    safe_print(f"[CONSOLE] check_update_chapters result: {res}")
                except Exception as e:
                    safe_print(f"[CONSOLE] check_update_chapters raised: {e}")

        # Save story to MongoDB (WITHOUT chapters array)
        if self.story_scraper:
            safe_print(f"   💾 Đang lưu story vào MongoDB...")
            # Make sure no chapters array in story document
            if "chapters" in processed_story:
                del processed_story["chapters"]
            self.story_scraper.save_story_to_mongo(processed_story)
            
            # Also save story info (stats/metrics)
            if self.story_info_scraper:
                safe_print(f"   💾 Đang lưu story info vào MongoDB...")
                story_info = self.story_info_scraper.map_api_to_story_info(story_data, free_chapter_override=free_chapter_from_html)
                if story_info:
                    # Set websiteId from wattpad_website
                    website_id = self.wattpad_website.get("websiteId") if self.wattpad_website else None
                    if website_id:
                        story_info["websiteId"] = website_id
                    self.story_info_scraper.save_story_info(story_info)
        
        # storyHash đã được tạo duy nhất khi cào chapter 1 ở trên, không gen lại nữa
        if 'storyHash' not in processed_story:
            processed_story['storyHash'] = None
            safe_print(f"   ⚠️ Không lấy được nội dung chapter đầu tiên để hash")
        safe_print(f"✅ Hoàn thành cào story: {processed_story.get('storyName')}")
        return processed_story

    # ==================== PAGE SCRAPING METHODS ====================
    
    def scrape_stories_from_page(self, page_url, fetch_chapters=True, fetch_comments=True):
        """
        Quét tất cả stories từ 1 trang
        
        Args:
            page_url: URL trang danh sách
            fetch_chapters: Có lấy chapters không
            fetch_comments: Có lấy comments không
        
        Returns:
            List of scraped story data
        """
        safe_print(f"\n{'='*60}")
        safe_print(f"📄 Quét trang: {page_url}")
        safe_print(f"{'='*60}")
        
        # 1. Get story links from page
        story_links = self.fetch_story_links_from_page(page_url)
        if not story_links:
            safe_print(f"❌ Không tìm được stories trên trang")
            return []
        
        # 2. Scrape từng story
        results = []
        for idx, story_url in enumerate(story_links, 1):
            safe_print(f"\n[{idx}/{len(story_links)}] {story_url}")
            
            # Extract story ID
            story_id_match = re.search(r'/(\d+)', story_url)
            if not story_id_match:
                safe_print(f"  ⚠️ Không extract được story ID")
                continue
            
            story_id = story_id_match.group(1)
            
            # Scrape story
            result = self.scrape_story(
                story_id=story_id,
                story_url=story_url,
                fetch_chapters=fetch_chapters,
                fetch_comments=fetch_comments
            )
            
            if result:
                results.append(result)
        
        safe_print(f"\n{'='*60}")
        safe_print(f"✅ Quét xong {len(results)}/{len(story_links)} stories")
        safe_print(f"{'='*60}")
        
        return results

    # ==================== HTML SCRAPING METHODS ====================
    
    def fetch_html_prefetched_data(self, story_url):
        """
        Lấy dữ liệu từ window.prefetched trong HTML page
        Dùng Playwright để execute JavaScript (window.prefetched được render bởi JS)
        
        Args:
            story_url: Full URL to story chapter
        
        Returns:
            dict with prefetched data or None
        """
        # Nếu không có page object (Playwright chưa init), trả về None
        if self.page is None:
            safe_print(f"⚠️ Playwright page chưa init, bỏ qua prefetched data")
            return None
        
        try:
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()
            
            safe_print(f"   🌐 Đang fetch HTML với Playwright (execute JS)...")
            safe_print(f"   📍 URL: {story_url}")
            
            # Navigate to page (Playwright sẽ execute tất cả JS)
            # Use wait_until="load" để page load xong, không chờ networkidle
            self.page.goto(story_url, wait_until="load", timeout=config.REQUEST_TIMEOUT * 1000)
            
            # Chờ một chút để JS render xong
            self.page.wait_for_timeout(3000)
            
            # Lấy window.prefetched object từ browser context
            prefetched_data = self.page.evaluate("() => window.prefetched")
            
            if prefetched_data:
                safe_print(f"✅ Đã lấy prefetched data từ browser (Playwright)")
                safe_print(f"   Keys: {list(prefetched_data.keys())}")
                return prefetched_data
            else:
                safe_print(f"⚠️ window.prefetched không có trong page")
                # Debug: Check window object
                try:
                    window_keys = self.page.evaluate("() => Object.keys(window).slice(0, 20)")
                    safe_print(f"   Window keys sample: {window_keys}")
                except:
                    pass
                return None
                
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi fetch HTML với Playwright: {e}")
            import traceback
            traceback.print_exc()
            return None
            return None

    # ==================== UTILITY METHODS ====================


# For backward compatibility
RoyalRoadScraper = WattpadScraper
