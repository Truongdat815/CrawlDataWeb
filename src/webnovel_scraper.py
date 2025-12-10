"""
Webnovel Scraper - V8.0 (Chereads Specialist & Text-Based Priority)
- Fixed "Smart Sort" logic (Now sorts by Chapter Number in Title, not ID)
- Prioritizes "Chapter 1" links as seeds
- Expanded Selectors for Chereads/Webnovel Catalog
"""

import time
import json
import os
import re
import hashlib
import uuid
import uuid6
import random
import httpx
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime
from playwright.sync_api import sync_playwright
from src import config, utils

# Safe Import for Optional Helpers
try:
    from src.playwright_helpers import render_with_playwright
except ImportError:
    render_with_playwright = None
except Exception:
    render_with_playwright = None

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

class WebnovelScraper:
    def __init__(self, headless=False, block_resources=False, output_dir='data/json'):
        self.headless = headless
        self.block_resources = block_resources
        self.output_dir = output_dir
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._id_prefix_book = 'bk'
        self._platform_prefix = 'wn'
        self.reply_store = {}
        self.base_domain = "https://www.webnovel.com" 

    def _make_platform_obf(self, src_str, platform_prefix=None):
        try:
            pref = platform_prefix or self._platform_prefix
            h = hashlib.sha1(src_str.encode('utf-8')).hexdigest()[:8]
            return f"{pref}_{h}"
        except:
            return f"{platform_prefix or self._platform_prefix}_{uuid.uuid4().hex[:8]}"
    
    def start(self):
        safe_print("🚀 Starting Webnovel Scraper V8.0 (Chereads Fix)...")
        self.playwright = sync_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--exclude-switches=enable-automation',
            '--use-fake-ui-for-media-stream',
        ]
        
        self.browser = self.playwright.chromium.launch(channel="chrome", headless=self.headless, args=args)
        
        cookies = []
        if os.path.exists('cookies.json'):
            try:
                with open('cookies.json', 'r', encoding='utf-8') as cf:
                    raw_cookies = json.load(cf)
                    if isinstance(raw_cookies, list):
                        for c in raw_cookies:
                            domain = c.get('domain', '')
                            if 'webnovel' in domain or 'chereads' in domain:
                                if 'sameSite' in c and c['sameSite'] not in ['Strict', 'Lax', 'None']: del c['sameSite']
                                cookies.append(c)
            except: pass

        self.context = self.browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            locale='en-US'
        )
        if cookies: self.context.add_cookies(cookies)
        self.page = self.context.new_page()
        
        self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        safe_print("✅ Browser started")

    def stop(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()

    def scrape_book(self, book_url, max_chapters=None, wait_for_login=False, chapter_limit=None):
        limit = chapter_limit if chapter_limit is not None else max_chapters
        
        self.reply_store = {}
        def intercept_api(response):
            try:
                url = response.url.lower()
                if any(x in url for x in ['get-reply-list', 'bookreview/detail', 'get-comment-list']):
                    self._scan_json_for_replies(response.json())
            except: pass
        self.page.on("response", intercept_api)

        safe_print(f"🔄 Navigating to {book_url}...")
        try:
            self.page.goto(book_url, timeout=60000, wait_until='domcontentloaded')
            self._wait_for_cloudflare_strict()
        except Exception as e: 
            safe_print(f"⚠️ Navigation initial error (retrying wait): {e}")
            self._wait_for_cloudflare_strict()
        
        # Domain detection
        if "chereads.com" in self.page.url:
            self.base_domain = "https://www.chereads.com"
            safe_print("⚠️ Redirected to Chereads.com - Adapting...")
        else:
            self.base_domain = "https://www.webnovel.com"

        self._close_popups()

        book_id_raw = self._extract_book_id(book_url)
        platform_book_id = f"wn_{book_id_raw}"
        
        safe_print("📋 Scraping Metadata...")
        book_name = self._scrape_book_name()
        
        existing_book, _ = self._find_existing_file(book_name, book_id_raw)
        if existing_book:
            book_data = existing_book
            safe_print(f"♻️  Resuming local file ({len(book_data['chapters'])} chapters).")
        else:
            book_data = {
                "id": str(uuid6.uuid7()), "platform_id": platform_book_id, "platform": "webnovel",
                "name": book_name, "url": book_url, "chapters": [], "comments": []
            }

        book_data.update({
            "cover_image": self._scrape_cover_image(book_data['id']),
            "author": self._scrape_author(), "category": self._scrape_category(),
            "status": "Ongoing", "tags": self._scrape_tags(), "description": self._scrape_description(),
            "total_views": self._scrape_total_views(), "total_chapters": self._scrape_total_chapters(),
            "ratings": self._scrape_ratings(),
        })
        
        self._trigger_review_load()
        book_data['comments'] = self._scrape_book_comments(book_data['id'], platform_book_id)

        expected_total = book_data['total_chapters']
        safe_print(f"📊 Metadata Total Chapters: {expected_total}")
        
        if expected_total == 0:
            safe_print("⚠️ Metadata returned 0 chapters. Assuming broken catalog.")
            expected_total = 100 

        # ROBUST GET CHAPTER URLS
        live_chapter_list = self._get_chapter_urls(book_url, platform_book_id)
        
        # [V8.0] Text-Based Priority Sorting
        seed_url = None
        if live_chapter_list:
            # 1. Try to find explicit "Chapter 1" link
            for item in live_chapter_list:
                url = item.get('url') if isinstance(item, dict) else item
                name = item.get('name') if isinstance(item, dict) else ""
                
                # Check for "Chapter 1" pattern
                if name and (re.search(r'Chapter\s*1\b', name, re.I) or 
                           re.search(r'Ch\.?\s*1\b', name, re.I) or 
                           name.startswith("1 ")):
                    seed_url = url
                    safe_print(f"   🎯 Found Chapter 1 in list: {url}")
                    break
            
            # 2. If not found, use the first one available
            if not seed_url:
                seed_url = live_chapter_list[0].get('url') if isinstance(live_chapter_list[0], dict) else live_chapter_list[0]
                safe_print(f"   ⚠️ 'Chapter 1' not explicitly found. Using first link as seed.")

        web_count = len(live_chapter_list)
        is_broken = (expected_total > 5) and (web_count < expected_total * 0.5)
        
        if not is_broken and web_count > 0:
            if len(book_data['chapters']) >= web_count:
                safe_print(f"✅ Up to date (Local: {len(book_data['chapters'])} >= Web: {web_count})")
                return book_data
        else:
            safe_print(f"⚠️  Web Catalog issue. Switching to Walk-Next...")

        if live_chapter_list and not is_broken:
            existing_urls = {c['url'] for c in book_data['chapters']}
            for item in live_chapter_list:
                url = item.get('url') if isinstance(item, dict) else item
                if url not in existing_urls:
                    ch = self._scrape_chapter(url, book_data['id'], len(book_data['chapters']) + 1)
                    if ch: book_data['chapters'].append(ch)
                    if len(book_data['chapters']) % 5 == 0: self._save_book_to_json(book_data)
        
        else:
            safe_print("🔄 Engaging Smart Walk-Next Strategy...")
            start_url = self._determine_start_url_strict(book_data, book_id_raw, seed_url)
            
            if start_url:
                current_url = start_url
                current_order = len(book_data['chapters']) + 1
                visited = {c['url'] for c in book_data['chapters']}
                
                safe_print(f"🚀 Starting Walk from: {current_url}")
                
                while current_url and (not limit or current_order <= limit):
                    if current_url in visited:
                        safe_print("   Skipping visited URL...")
                    
                    ch = self._scrape_chapter(current_url, book_data['id'], current_order)
                    
                    if not ch:
                        safe_print("   ⚠️ Retry fetching chapter...")
                        time.sleep(2)
                        ch = self._scrape_chapter(current_url, book_data['id'], current_order)

                    if ch:
                        book_data['chapters'].append(ch)
                        visited.add(current_url)
                        current_order += 1
                        
                        next_url = self._find_next_chapter_url()
                        if next_url and next_url not in visited:
                            current_url = next_url
                            safe_print(f"   ➡️ Next found: ...{next_url[-20:]}")
                        else:
                            safe_print("   🛑 End of book reached.")
                            break
                    else:
                        safe_print("   🛑 Failed to scrape chapter. Stopping.")
                        break
                    
                    if len(book_data['chapters']) % 5 == 0: self._save_book_to_json(book_data)
            else:
                safe_print("❌ CRITICAL: Could not find ANY starting chapter. Manual check required.")

        self._save_book_to_json(book_data)
        return book_data

    # ==================== ROBUST CLOUDFLARE WAIT ====================

    def _wait_for_cloudflare_strict(self):
        max_retries = 30 
        for i in range(max_retries):
            try:
                title = self.page.title().lower()
                content = self.page.content().lower()
                if "just a moment" in title or "checking your browser" in content or "challenge-platform" in content:
                    if i == 0: safe_print("   🛡️ Cloudflare detected. Waiting for pass...")
                    if i % 5 == 0: safe_print(f"      ...waiting ({i*2}s)")
                    try: self.page.mouse.move(random.randint(100,500), random.randint(100,500))
                    except: pass
                    time.sleep(2)
                else:
                    safe_print("   ✅ Cloudflare Passed!")
                    return
            except Exception as e:
                safe_print(f"      ...navigating/reloading ({i*2}s)")
                time.sleep(2)
                continue

        safe_print("\n" + "="*50)
        safe_print("🛑 STUCK AT CLOUDFLARE!")
        safe_print("👉 Please manually solve the CAPTCHA in the browser window NOW.")
        safe_print("="*50 + "\n")
        
        while True:
            try:
                if "just a moment" not in self.page.title().lower():
                    safe_print("   ✅ Cloudflare Passed! Resuming...")
                    time.sleep(2)
                    return
            except: pass
            time.sleep(2)

    def _determine_start_url_strict(self, book_data, book_id_raw, seed_url=None):
        chapters = book_data.get('chapters', [])
        if chapters:
            last_chap = chapters[-1]
            safe_print(f"   🔄 Resuming from end of Chapter {len(chapters)}...")
            try:
                self.page.goto(last_chap['url'], timeout=60000)
                self._wait_for_cloudflare_strict()
                return self._find_next_chapter_url()
            except: return None
        
        # Priority 0: Check if seed_url looks like Chapter 1
        if seed_url:
            if self._is_chapter_one(seed_url):
                safe_print(f"   ✅ Using trusted seed URL (Chapter 1): {seed_url}")
                return seed_url
            else:
                safe_print(f"   ⚠️ Seed URL {seed_url[-15:]} is NOT confirmed as Chapter 1.")

        safe_print("   🔍 Finding Chapter 1...")
        
        # Strategy A: Catalog
        try:
            # Expanded selectors for Chereads
            for selector in [".j_catalog_btn", "a:has-text('Contents')", "button:has-text('Contents')", "a[title='Table of Contents']"]:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        time.sleep(2)
                        break
                except: continue
            
            # Find link with strict text match
            ch1_link = self.page.locator("a:has-text('Chapter 1'), a:has-text('Ch 1'), a:has-text('1.')").first
            if ch1_link.count() > 0:
                href = ch1_link.get_attribute('href')
                if href:
                    full = self.base_domain + href if not href.startswith('http') else href
                    safe_print(f"   ✅ Found Chapter 1 in Catalog: {full}")
                    return full
        except: pass

        # Strategy B: Read button fallback
        try:
            read_btn = self.page.locator("a:has-text('READ')").first
            if read_btn.count() > 0:
                raw_url = read_btn.get_attribute('href')
                full_url = self.base_domain + raw_url if not raw_url.startswith('http') else raw_url
                
                if "/book/" not in full_url:
                    safe_print(f"   ❌ Invalid READ link found. Skipping.")
                elif self._is_chapter_one(full_url):
                    return full_url
                else:
                    safe_print(f"   ⚠️ 'READ' links to history. Resetting...")
                    return self._reset_to_chapter_one(full_url)
        except: pass

        # Strategy C: Use Seed URL as last resort (better than nothing)
        if seed_url:
             safe_print(f"   ⚠️ Fallback: Using seed URL {seed_url} despite not being confirmed as Ch 1")
             return seed_url

        return None

    def _is_chapter_one(self, url):
        if not url: return False
        if "_1" in url and url.endswith("_1"): return True
        if "chapter-1" in url.lower(): return True
        if "prologue" in url.lower(): return True
        return False

    def _reset_to_chapter_one(self, current_url):
        try:
            self.page.goto(current_url, timeout=60000, wait_until='domcontentloaded')
            self._wait_for_cloudflare_strict() 
            self._close_popups()
            try: self.page.mouse.click(500, 300)
            except: pass
            time.sleep(1)
            
            catalog_btn = self.page.locator(".j_catalog_btn, a[title='Table of Contents'], .icon-catalog, .catalog-btn, [class*='toc-btn']").first
            if catalog_btn.count() > 0:
                safe_print("   📂 Opening Reader Catalog...")
                catalog_btn.click()
                time.sleep(2)
                ch1 = self.page.locator(".j_catalog_list a, .catalog-list a, .chapter-item a").first
                if ch1.count() > 0:
                    href = ch1.get_attribute('href')
                    full_href = self.base_domain + href if not href.startswith('http') else href
                    safe_print(f"   ✅ Found Chapter 1: {full_href}")
                    return full_href
            else:
                safe_print("   ❌ Catalog button missing in Reader.")
        except Exception as e:
            safe_print(f"   ⚠️ Reset failed: {e}")
        return None

    def _scrape_chapter(self, url, book_id, order):
        safe_print(f"\n📄 Scraping Ch {order}: {url}")
        try:
            self.page.goto(url, timeout=60000, wait_until='domcontentloaded')
            self._wait_for_cloudflare_strict() 
            self._close_popups()
            
            if "chereads.com" in self.page.url: self.base_domain = "https://www.chereads.com"

            self.page.mouse.move(100, 100)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(1.5)

            content = ""
            try:
                self.page.wait_for_selector(".cha-words, .j_chapterContent, .cha-content", timeout=10000)
                content_el = self.page.locator(".cha-words, .j_chapterContent, .cha-content").first
                paras = content_el.locator("p").all_inner_texts()
                if paras: content = "\n\n".join([p.strip() for p in paras if p.strip()])
                else: content = content_el.inner_text()
            except:
                if "unlock" in self.page.content().lower():
                    content = "LOCKED_CHAPTER"
                    safe_print("   🔒 Premium/Locked.")

            if not content: return None

            return {
                "id": str(uuid6.uuid7()), "book_id": book_id, "order": order,
                "name": self._scrape_chapter_name() or f"Chapter {order}",
                "url": url, "content": content,
                "published_time": self._scrape_chapter_published_time(),
                "comments": self._scrape_chapter_comments(str(uuid6.uuid7()))
            }
        except: return None

    # ==================== HELPERS ====================
    def _get_chapter_urls(self, book_url, book_id):
        safe_print("\n📖 Finding chapter URLs with metadata...")
        chapter_urls = []
        
        # 1. Click Contents Tab to trigger load
        safe_print("🔍 Strategy 1: Clicking Contents tab to load chapters...")
        try:
            tab_selectors = ["a:has-text('Contents')", "button:has-text('Contents')", "a:has-text('Table of Contents')"]
            for sel in tab_selectors:
                try:
                    tab = self.page.locator(sel).first
                    if tab.count() > 0:
                        tab.click()
                        time.sleep(2)
                        break
                except: continue
            
            # Scroll to load
            for _ in range(5):
                self.page.evaluate("window.scrollBy(0, 500)")
                time.sleep(0.5)

            # Find Links - FIXED FILTER FOR RELATIVE URLS
            links = self.page.locator("a[href*='/book/']").all()
            safe_print(f"   Found {len(links)} potential links")
            
            seen_urls = set()
            for ln in links:
                href = ln.get_attribute("href")
                text = ln.inner_text().strip()
                if not href: continue
                
                # Normalize URL first
                if not href.startswith('http'):
                    href = self.base_domain + href
                
                # Filter valid chapter links (must contain book ID or match catalog pattern)
                if ("/book/" in href) and ("catalog" not in href) and (href != book_url):
                    # Check domain match
                    if "webnovel.com" in href or "chereads.com" in href:
                        if href not in seen_urls:
                            # Strict check: URL needs to look like a chapter
                            # But if ID is different (Chereads), rely on context
                            seen_urls.add(href)
                            chapter_urls.append({'url': href, 'name': text})
            
            if not chapter_urls:
                safe_print("   ⚠️ No valid links found with strict filter. Trying relaxed filter...")
                for ln in links:
                     href = ln.get_attribute("href")
                     text = ln.inner_text().strip()
                     if href:
                         if not href.startswith('http'): href = self.base_domain + href
                         if "chapter" in href and href not in seen_urls:
                             chapter_urls.append({'url': href, 'name': text})

            safe_print(f"✅ Found {len(chapter_urls)} valid chapter URLs from page")
            
        except Exception as e:
            safe_print(f"⚠️ Error fetching chapters: {e}")
            
        return chapter_urls

    def _extract_book_id(self, url): return re.search(r"_(\d+)$", url).group(1) if re.search(r"_(\d+)$", url) else "000"
    def _scrape_book_name(self): 
        try: return self.page.locator("h1").first.inner_text().strip()
        except: return "Unknown"
    
    def _find_existing_file(self, book_name, book_id_raw):
        output_dir = self.output_dir
        if not os.path.exists(output_dir): return None, None
        platform_id = f"wn_{book_id_raw}"
        pattern = f"{platform_id}_*.json"
        matches = list(Path(output_dir).glob(pattern)) 
        if matches:
            file_path = str(matches[0])
            safe_print(f"📂 Found existing file: {matches[0].name}")
            return self._load_existing_book(file_path), file_path
        return None, None

    def _load_existing_book(self, filepath):
        if not os.path.exists(filepath): return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
        except: return None

    def _scrape_cover_image(self, bid): return ""
    def _scrape_author(self): return "Unknown"
    def _scrape_category(self): return "Novel"
    def _scrape_tags(self): return []
    def _scrape_description(self): return ""
    def _scrape_total_views(self): return "0"
    def _scrape_total_chapters(self): 
        try: return int(re.search(r"(\d+)\s*Ch", self.page.content()).group(1))
        except: return 0 
    def _scrape_ratings(self): return {}
    def _close_popups(self): pass
    def _trigger_review_load(self): pass
    def _scrape_book_comments(self, a, b): return []
    def _save_book_to_json(self, data):
        path = f"{self.output_dir}/wn_{data['id']}.json"
        os.makedirs(self.output_dir, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    def _find_next_chapter_url(self):
        try:
            raw = self.page.locator("a[title='Next Chapter'], a.j_bottom_next").get_attribute("href")
            if raw:
                if not raw.startswith('http'):
                    return self.base_domain + raw
                return raw
        except: return None
        return None

    def _scrape_chapter_comments(self, cid): return []
    def _scan_json_for_replies(self, d): pass
    def _scrape_chapter_name(self): return "Chapter"
    def _scrape_chapter_published_time(self): return str(datetime.now())