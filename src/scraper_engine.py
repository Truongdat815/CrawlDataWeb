import json
import os
import sys
import re
import requests
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from src import config, utils

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
    UserScraper, safe_print
)


class RateLimiter:
    """Rate limiter để tránh ban IP"""
    
    def __init__(self, max_requests=None, time_window=60):
        self.max_requests = max_requests or config.MAX_REQUESTS_PER_MINUTE
        self.time_window = time_window  # seconds
        self.request_times = deque()
    
    def wait_if_needed(self):
        """Wait nếu vượt quá rate limit"""
        now = datetime.now()
        
        # Remove requests ngoài time window
        while self.request_times and self.request_times[0] < now - timedelta(seconds=self.time_window):
            self.request_times.popleft()
        
        # Nếu đã max requests, wait
        if len(self.request_times) >= self.max_requests:
            sleep_time = (self.request_times[0] + timedelta(seconds=self.time_window) - now).total_seconds()
            if sleep_time > 0:
                safe_print(f"⏳ Rate limit reached. Waiting {sleep_time:.1f}s...")
                time.sleep(sleep_time)
        
        # Record this request
        self.request_times.append(datetime.now())


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
        self.browser = None
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
        
        # Khởi tạo MongoDB client nếu được bật
        self.mongo_client = None
        self.mongo_db = None
        
        # Initialize scrapers (will be set in start())
        self.story_scraper = None
        self.chapter_scraper = None
        self.comment_scraper = None
        self.user_scraper = None
        
        # Legacy collections (backward compatibility)
        self.mongo_collection_stories = None
        self.mongo_collection_chapters = None
        self.mongo_collection_comments = None
        self.mongo_collection_users = None
        
        self.mongo_client = None
        self.mongo_db = None
        
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                if MongoClient is not None:
                    self.mongo_client = MongoClient(config.MONGODB_URI)
                    self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                    # Keep for backward compatibility
                    self.mongo_collection_stories = self.mongo_db[config.MONGODB_COLLECTION_STORIES]
                    self.mongo_collection_chapters = self.mongo_db["chapters"]
                    self.mongo_collection_comments = self.mongo_db["comments"]
                    self.mongo_collection_users = self.mongo_db["users"]
                    safe_print("✅ Đã kết nối MongoDB với 4 collections (Wattpad schema)")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

    def start(self):
        """Khởi động scrapers (Wattpad API không cần browser)"""
        # Khởi tạo scrapers
        self.story_scraper = StoryScraper(self.page, self.mongo_db)
        self.chapter_scraper = ChapterScraper(self.page, self.mongo_db)
        self.comment_scraper = CommentScraper(self.page, self.mongo_db)
        self.user_scraper = UserScraper(self.page, self.mongo_db)
        
        safe_print("✅ Bot đã khởi động! (Wattpad API crawler)")

    def stop(self):
        """Đóng MongoDB connection"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
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
            fields = "id,title,voteCount,readCount,createDate,lastPublishedPart,user(name,avatar),cover,url,numParts,isPaywalled,paidModel,completed,mature,description"
        
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
            fields = "id,title,voteCount,readCount,createDate,lastPublishedPart,user(name,avatar),cover,url,numParts,isPaywalled,paidModel,completed,mature,description"
        
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
            story_id: Story ID to scrape
            fetch_chapters: Whether to fetch chapter list
            fetch_comments: Whether to fetch comments
            story_url: Story URL (để fetch HTML prefetched data)
        
        Returns:
            Complete story data dict
        """
        safe_print(f"\n{'='*60}")
        safe_print(f"📖 Bắt đầu cào story ID: {story_id}")
        safe_print(f"{'='*60}")
        
        # 1. Fetch story metadata từ API
        story_data = self.fetch_story_from_api(story_id)
        if not story_data:
            safe_print(f"❌ Không thể lấy metadata cho story {story_id}")
            return None
        
        # Try to fetch from HTML prefetched data (tags, categories, chapters)
        extra_info = None
        prefetched_data = None
        if story_url:
            safe_print(f"   🌐 Đang fetch HTML prefetched data...")
            prefetched_data = self.fetch_html_prefetched_data(story_url)
            if prefetched_data:
                extra_info = self.extract_story_info_from_prefetched(prefetched_data)
        
        # 3. Process story metadata (kèm tags + categories)
        if self.story_scraper is None:
            safe_print(f"❌ Story scraper chưa được khởi tạo")
            return None
        processed_story = self.story_scraper.scrape_story_metadata(story_data, extra_info)
        
        if not processed_story:
            safe_print(f"❌ Lỗi khi xử lý story metadata")
            return None
        
        # 4. Optionally fetch chapters
        if fetch_chapters and prefetched_data:
            safe_print(f"   📚 Đang lấy danh sách chapters...")
            chapters = self.extract_chapters_from_prefetched(prefetched_data, story_id)
            if chapters:
                processed_story["chapters"] = chapters
        
        # 5. Optionally fetch comments
        if fetch_comments and story_data.get("lastPublishedPart"):
            part_id = story_data["lastPublishedPart"].get("id")
            if part_id:
                safe_print(f"   💬 Đang lấy comments...")
                comments = self.fetch_comments_from_api(story_id, part_id)
                if comments:
                    processed_story["comments"] = comments
        
        safe_print(f"✅ Hoàn thành cào story: {processed_story.get('storyName')}")
        return processed_story

    # ==================== PAGE SCRAPING METHODS ====================
    
    def fetch_story_links_from_page(self, page_url, max_stories=None):
        """
        Quét trang Wattpad để lấy danh sách story links
        
        Args:
            page_url: URL trang danh sách stories
            max_stories: Max số stories để lấy (None = tất cả, hoặc dùng config.MAX_STORIES_PER_BATCH)
        
        Returns:
            List of story URLs
        """
        if max_stories is None:
            max_stories = config.MAX_STORIES_PER_BATCH
        
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        def make_request():
            response = self.http.get(page_url, timeout=config.REQUEST_TIMEOUT)
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
        Với rate limiting và retry logic
        
        Args:
            story_url: Full URL to story chapter
        
        Returns:
            dict with prefetched data or None
        """
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        def make_request():
            response = self.http.get(story_url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.content
        
        try:
            content = retry_request(make_request)
            if not content:
                return None
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find window.prefetched script tag
            scripts = soup.find_all('script', type='application/json')
            
            for script in scripts:
                if script.string and ('prefetched' in script.string or 'window.prefetched' in script.string):
                    try:
                        # Extract JSON from script content
                        json_str = script.string
                        
                        # Remove "window.prefetched = " prefix if present
                        if 'window.prefetched' in json_str:
                            json_str = json_str.split('=', 1)[1].strip()
                            if json_str.endswith(';'):
                                json_str = json_str[:-1]
                        
                        prefetched_data = json.loads(json_str)
                        safe_print(f"✅ Đã lấy prefetched data từ HTML")
                        return prefetched_data
                    except json.JSONDecodeError:
                        continue
            
            safe_print(f"⚠️ Không tìm thấy window.prefetched trong HTML")
            return None
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi fetch HTML: {e}")
            return None

    def extract_chapters_from_prefetched(self, prefetched_data, story_id):
        """
        Trích xuất chapters từ prefetched data
        
        Args:
            prefetched_data: window.prefetched object
            story_id: Story ID
        
        Returns:
            List of chapter data (limited by MAX_CHAPTERS_PER_STORY)
        """
        chapters = []
        
        try:
            # Chapters thường nằm trong "part.{story_id}.metadata"
            for key, value in prefetched_data.items():
                if key.startswith("part.") and "metadata" in key:
                    # Check limit
                    if config.MAX_CHAPTERS_PER_STORY and len(chapters) >= config.MAX_CHAPTERS_PER_STORY:
                        safe_print(f"   ⏸️ Đã reach limit {config.MAX_CHAPTERS_PER_STORY} chapters")
                        break
                    
                    if "data" in value:
                        chapter_data = value["data"]
                        
                        # Map chapter fields
                        processed_chapter = {
                            "chapterId": chapter_data.get("id"),
                            "storyId": story_id,
                            "chapterName": chapter_data.get("title"),
                            "voted": chapter_data.get("voteCount", 0),
                            "views": chapter_data.get("readCount", 0),
                            "order": chapter_data.get("order", 0),
                            "publishedTime": chapter_data.get("createDate"),
                            "lastUpdated": chapter_data.get("modifyDate"),
                            "chapterUrl": chapter_data.get("url"),
                            "wordCount": chapter_data.get("wordCount", 0),
                            "rating": chapter_data.get("rating", 0),
                            "commentCount": chapter_data.get("commentCount", 0)
                        }
                        chapters.append(processed_chapter)
                        safe_print(f"   ✅ Chapter: {chapter_data.get('title')}")
            
            safe_print(f"✅ Đã trích xuất {len(chapters)} chapters")
            return chapters
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất chapters: {e}")
            return []

    def extract_story_info_from_prefetched(self, prefetched_data):
        """
        Trích xuất thông tin story từ prefetched data
        (tags, categories, language, author info)
        
        Args:
            prefetched_data: window.prefetched object
        
        Returns:
            dict with story info
        """
        try:
            story_info = {
                "tags": [],
                "categories": [],
                "language": None,
                "author": None
            }
            
            # Tìm story group data
            for key, value in prefetched_data.items():
                if "story." in key and "metadata" in key:
                    if "data" in value and "group" in value["data"]:
                        group = value["data"]["group"]
                        
                        # Extract tags
                        if "tags" in group:
                            story_info["tags"] = group["tags"]
                        
                        # Extract categories
                        if "categories" in group:
                            story_info["categories"] = group["categories"]
                        
                        # Extract language
                        if "language" in group:
                            story_info["language"] = group["language"]
                        
                        # Extract author
                        if "user" in group:
                            story_info["author"] = group["user"]
                        
                        safe_print(f"✅ Tags: {len(story_info['tags'])}")
                        safe_print(f"✅ Categories: {story_info['categories']}")
                        return story_info
            
            return story_info
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi trích xuất story info: {e}")
            return None

    # ==================== UTILITY METHODS ====================

    def _save_to_json(self, data):
        """
        Lưu dữ liệu vào file JSON
        """
        filename = f"{data['storyId']}_{utils.clean_text(data.get('storyName', 'unknown'))}.json"
        save_path = os.path.join(config.JSON_DIR, filename)
        
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            safe_print(f"💾 Đã lưu dữ liệu vào file: {save_path}")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu file JSON: {e}")


# For backward compatibility
RoyalRoadScraper = WattpadScraper
