import json
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
from src import config, utils
from src.login_service import WattpadLoginService, login_if_needed

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
from src.scrapers import (
    StoryScraper, ChapterScraper, CommentScraper, 
    UserScraper, ChapterContentScraper, WebsiteScraper, safe_print
)

# Import duplicate checker
from src.utils.duplicate_checker import DuplicateChecker

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


class WattpadScraper:
    """Wattpad API-based scraper using modular components"""
    
    def __init__(self, max_workers=None):
        self.context = None
        self.page = None
        self.playwright = None
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Rate limiter
        self.rate_limiter = RateLimiter()
        
        # Reusable HTTP session for connection pooling + default headers
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": config.DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
        })
        # Configure proxies if set in config
        if config.HTTP_PROXY or config.HTTPS_PROXY:
            proxies = {}
            if config.HTTP_PROXY:
                proxies["http"] = config.HTTP_PROXY
            if config.HTTPS_PROXY:
                proxies["https"] = config.HTTPS_PROXY
            self.http.proxies.update(proxies)
            safe_print(f"🌐 Proxy configured: {config.HTTPS_PROXY or config.HTTP_PROXY}")
        
        # Track current proxy used for Playwright context
        self._current_proxy = None
        
        # Initialize login service
        self.login_service = WattpadLoginService()
        
        # Initialize scrapers (will be set in start())
        self.story_scraper = None
        self.chapter_scraper = None
        self.comment_scraper = None
        self.user_scraper = None
        self.chapter_content_scraper = None
        
        # Legacy collections (backward compatibility)
        self.mongo_collection_stories = None
        self.mongo_collection_chapters = None
        self.mongo_collection_comments = None
        self.mongo_collection_users = None
        
        # Khởi tạo MongoDB client nếu được bật
        self.mongo_client = None
        self.mongo_db = None
        
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                if MongoClient is not None:
                    self.mongo_client = MongoClient(config.MONGODB_URI)
                    self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                    # Create all required collections
                    self.mongo_collection_stories = self.mongo_db[config.MONGODB_COLLECTION_STORIES]
                    self.mongo_collection_story_info = self.mongo_db["story_info"]
                    self.mongo_collection_chapters = self.mongo_db["chapters"]
                    self.mongo_collection_chapter_contents = self.mongo_db["chapter_contents"]
                    self.mongo_collection_comments = self.mongo_db["comments"]
                    self.mongo_collection_users = self.mongo_db["users"]
                    self.mongo_collection_websites = self.mongo_db["websites"]
                    safe_print("✅ Đã kết nối MongoDB với 7 collections (stories, story_info, chapters, chapter_contents, comments, users, websites)")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

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

            # Đăng nhập vào Wattpad nếu có credentials
            if username and password:
                safe_print("\n" + "="*60)
                safe_print("🔑 WATTPAD LOGIN")
                safe_print("="*60)
                
                # Kiểm tra xem đã đăng nhập chưa
                if self.login_service.is_already_logged_in(self.page):
                    safe_print("✅ Đã đăng nhập rồi - Bỏ qua bước login")
                else:
                    # Chưa đăng nhập -> Thực hiện login
                    self.login_service.login_with_playwright(self.page, username, password)
            else:
                # Load cookies từ file nếu có
                if self.login_service.load_cookies_from_file():
                    self.login_service.apply_cookies_to_browser(self.page)
                    safe_print("✅ Đã load cookies từ file")
                else:
                    safe_print("⚠️ Không có credentials, scrape mà không đăng nhập")
                    safe_print("   Một số trang có thể cần đăng nhập để xem")

        except Exception as e:
            safe_print(f"⚠️ Lỗi khởi tạo Playwright: {e}")
            safe_print("   Tiếp tục mà không có Playwright (chỉ dùng API)")

        # Khởi tạo scrapers (dù có Playwright hay không)
        from src.scrapers.story_info import StoryInfoScraper
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
            return response.json()
        
        try:
            return retry_request(make_request)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi fetch story {story_id}: {e}")
            return None

    def fetch_comments_from_api_v5(self, web_chapter_id, chapter_id=None):
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
                    # Pass parent_comment_id when fetching replies (namespace='comments')
                    parent_id = resource_id if namespace == 'comments' else None
                    # Pass websiteId from wattpad_website (key is 'website_id' in DB)
                    website_id = self.wattpad_website.get("website_id") if self.wattpad_website else None
                    # Use db_chapter_id (UUID) for saving to DB
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
                    # respect MAX_COMMENTS_PER_CHAPTER
                    added_count = 0
                    for m in mapped_list:
                        if config.MAX_COMMENTS_PER_CHAPTER and len(collected) >= config.MAX_COMMENTS_PER_CHAPTER:
                            break
                        collected.append(m)
                        added_count += 1
                    # mark that comments were saved by process_v5_comments_page
                    self._v5_saved_flag = True
                    safe_print(f"      ✅ Processed {added_count} comments (total: {len(collected)}/{config.MAX_COMMENTS_PER_CHAPTER or 'unlimited'})")

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
        # Use web_chapter_id (original Wattpad ID) for API calls
        process_page(web_chapter_id, 'parts', None)

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
        # Hiện tại endpoint /parts không work public
        # Sẽ fallback tới prefetched data trong scrape_story()
        
        url = f"{config.BASE_URL}/api/v3/stories/{story_id}/parts"
        
        try:
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()
            
            def make_request():
                response = self.http.get(url, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
                return response.json()
            
            data = retry_request(make_request)
            if data and "parts" in data:
                return data["parts"]
            else:
                return []
        except Exception as e:
            safe_print(f"⚠️ API /parts không khả dụng: {e}")
            return []

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
        dup_checker = DuplicateChecker()
        story_status = dup_checker.check_story(story_id)
        if story_status:
            dup_checker.close()
            return story_status  # Return existing data instead of None
        dup_checker.close()
        
        # 1. Fetch story metadata từ API
        story_data = self.fetch_story_from_api(story_id)
        if not story_data:
            safe_print(f"❌ Không thể lấy metadata cho story {story_id}")
            return None
        
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
                        "publishedTime": p.get("createDate"),
                        "storyId": story_id,                 # Parent wp_uuid_v7
                        "voted": p.get("voteCount", 0),
                        "views": p.get("readCount", 0),
                        "totalComments": p.get("commentCount", 0),
                    }
                    chapters.append(chapter_obj)

            # If we already populated chapters from parts[], skip HTML/API discovery
            if not chapters:
            
                # Step 1: Extract chapter URLs from story overview page
                if self.page:
                    try:
                        # Navigate to story overview page to get table of contents
                        story_overview_url = f"{config.BASE_URL}/story/{story_id}"
                        safe_print(f"   🔍 Đang extract danh sách chapters từ story overview...")
                        
                        self.rate_limiter.wait_if_needed()
                        self.page.goto(story_overview_url, wait_until="load", timeout=config.REQUEST_TIMEOUT * 1000)
                        self.page.wait_for_timeout(2000)
                        self._simulate_human_behavior(self.page)
                        
                        page_html = self.page.content()
                        chapter_urls = ChapterScraper.extract_chapter_urls_from_html(page_html, story_id, config.MAX_CHAPTERS_PER_STORY)
                        
                        if chapter_urls:
                            safe_print(f"   ✅ Tìm được {len(chapter_urls)} chapters từ HTML")
                            for i, url in enumerate(chapter_urls, 1):
                                safe_print(f"      [{i}] {url}")
                        
                    except Exception as e:
                        safe_print(f"   ⚠️ Lỗi khi extract từ story page: {e}")
                
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
            
            if chapters:
                # Step 3: Scrape từng chapter - FOR EACH CHAPTER: content + comments + metadata
                safe_print(f"   📖 Bắt đầu cào {min(len(chapters), config.MAX_CHAPTERS_PER_STORY or len(chapters))} chapters...")
                
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
                        
                        # ✅ CHECK: Chapter đã được cào hay chưa
                        dup_checker = DuplicateChecker()
                        if dup_checker.check_chapter(chapter_id, chapter.get('chapterName')):
                            dup_checker.close()
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
                                        chapter["publishedTime"] = chapter_meta.get("createDate")
                                        # ✅ KEEP webChapterId from URL parsing (line 1068) - don't overwrite with None
                                        # chapter["webChapterId"] was already set from URL parsing above
                                        safe_print(f"      ✅ Metadata: {chapter['chapterName']}")
                                        break
                        else:
                            # Nếu không có prefetched data, dùng placeholder name
                            chapter["chapterName"] = f"Chapter {idx}: {chapter.get('chapterName', 'Unknown')}"
                            chapter["order"] = idx - 1
                        
                        # Step 3c: Extract chapter content từ HTML
                        page_html = self.page.content()
                        chapter_content = ChapterContentScraper.extract_and_map_chapter_content(page_html, chapter_id)
                        
                        if chapter_content and chapter_content.get("content"):
                            # ✅ LƯUÍ: Không lưu content trong chapter object
                            # Content sẽ được lưu riêng vào chapter_content collection
                            content_len = len(chapter_content.get('content', ''))
                            safe_print(f"      ✅ Content: {content_len} bytes")
                            
                            # Save chapter_content to MongoDB (collection riêng)
                            if self.chapter_content_scraper:
                                self.chapter_content_scraper.save_chapter_content_to_mongo(chapter_content)
                        else:
                            # Check if paid chapter (empty content)
                            safe_print(f"      ⚠️ Không extract được content")
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
                                    web_chapter_id=web_chapter_id or chapter_id,
                                    chapter_id=chapter_id
                                )
                            except Exception as e:
                                safe_print(f"      ⚠️ Lỗi API v5: {e}")
                            
                            if chapter_comments:
                                # ✅ LƯUÍ: Không lưu comments trong chapter object
                                # Comments sẽ được lưu riêng vào comments collection
                                safe_print(f"      ✅ Comments: {len(chapter_comments)} comments")
                        
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
                                    self.comment_scraper.save_comment_to_mongo(comment, user_name=user_name)
                        
                    except Exception as e:
                        safe_print(f"      ⚠️ Lỗi: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Don't add chapters to story document - they're stored separately
                # processed_story["chapters"] = chapters  # REMOVED - chapters in separate collection
                safe_print(f"\n   ✅ Hoàn thành cào {len(chapters)} chapters")
        
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
                    website_id = self.wattpad_website.get("website_id") if self.wattpad_website else None
                    if website_id:
                        story_info["websiteId"] = website_id
                    self.story_info_scraper.save_story_info(story_info)
        
        safe_print(f"✅ Hoàn thành cào story: {processed_story.get('storyName')}")
        return processed_story

    # ==================== PAGE SCRAPING METHODS ====================
    
    @staticmethod
    def fetch_story_links_from_page(page_url, max_stories=None):
        """
        Quét trang Wattpad để lấy danh sách story links (STATIC - không cần rate limiter)
        
        Args:
            page_url: URL trang danh sách stories
            max_stories: Max số stories để lấy (None = tất cả, hoặc dùng config.MAX_STORIES_PER_BATCH)
        
        Returns:
            List of story URLs
        """
        if max_stories is None:
            max_stories = config.MAX_STORIES_PER_BATCH
        
        def make_request():
            response = requests.get(
                page_url,
                timeout=config.REQUEST_TIMEOUT,
                headers={"User-Agent": config.DEFAULT_USER_AGENT}
            )
            response.raise_for_status()
            return response.content
        
        try:
            content = retry_request(make_request)
            if not content:
                return []
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            story_links = []
            
            # Tìm story links - các cách khác nhau tùy vào layout trang
            # Cách 1: Links có dạng /story/{id}-{title}
            for link in soup.find_all('a', href=True):
                href_raw = link.get('href')
                if href_raw is None:
                    continue
                
                # Convert to string if needed
                href = str(href_raw) if href_raw else ''
                if not href:
                    continue
                
                # Match story URLs
                if re.search(r'/story/\d+', href) or re.search(r'/\d+\-', href):
                    # Ensure full URL
                    if not href.startswith('http'):
                        href = config.BASE_URL + href
                    
                    # Extract story ID để check duplicate
                    story_id_match = re.search(r'/(\d+)', href)
                    if story_id_match:
                        story_id = story_id_match.group(1)
                        
                        # Check if already added
                        existing = [url for url in story_links if story_id in url]
                        if not existing:
                            story_links.append(href)
                            
                            # Check limit
                            if max_stories and len(story_links) >= max_stories:
                                break
            
            safe_print(f"✅ Tìm được {len(story_links)} stories trên trang")
            return story_links
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi quét trang: {e}")
            return []

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

    def _save_to_json(self, data):
        """
        Lưu dữ liệu vào file JSON (WITHOUT chapters array)
        """
        # Remove chapters array if present (chapters stored separately in DB)
        data_to_save = data.copy()
        if "chapters" in data_to_save:
            del data_to_save["chapters"]
        
        # Sanitize filename
        story_name = data_to_save.get('storyName', 'unknown')
        safe_name = story_name.replace('/', '_').replace('\\', '_').replace('|', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace(':', '_')[:50]
        # Use webStoryId for filename (original Wattpad ID is more readable)
        web_story_id = data_to_save.get('webStoryId', data_to_save.get('storyId', 'unknown'))
        filename = f"{web_story_id}_{safe_name}.json"
        save_path = os.path.join(config.JSON_DIR, filename)
        
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            safe_print(f"💾 Đã lưu dữ liệu vào file: {save_path}")

        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu file JSON: {e}")
    

# For backward compatibility
RoyalRoadScraper = WattpadScraper
