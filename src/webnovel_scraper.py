"""
Webnovel Scraper - Clean Architecture
Scrape books, chapters, and comments from webnovel.com

Schema:
    Book: id, name, url, cover_image, author, category, genre, status, tags, description,
          total_views, total_chapters, power_ranking_position, power_ranking_title,
          ratings{}, comments[], chapters[]
    Chapter: id, book_id, order, name, url, content, published_time, comments[]
    Comment: comment_id, user_id, user_name, time, content, score{}, replies[]
"""

import time
import json
import os
import re
import hashlib
import uuid
import uuid6  # UUID v7 for time-sortable IDs
import random
import httpx
from urllib.parse import urljoin
try:
    import cloudscraper
except Exception:
    cloudscraper = None
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None
from datetime import datetime
from playwright.sync_api import sync_playwright
from src import config, utils
try:
    from src.playwright_helpers import render_with_playwright
except Exception:
    render_with_playwright = None


def safe_print(*args, **kwargs):
    """Print with UTF-8 encoding safety for Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)


class WebnovelScraper:
    """Main scraper class for Webnovel.com"""
    
    def __init__(self, headless=False, block_resources=False, output_dir='data/json'):
        """
        Initialize WebnovelScraper
        
        Args:
            headless (bool): Run browser in headless mode (default: False for better Cloudflare bypass)
            block_resources (bool): Block images/fonts/css for faster scraping (default: False)
            output_dir (str): Directory to save JSON files (default: 'data/json')
        """
        self.headless = headless
        self.block_resources = block_resources
        self.output_dir = output_dir
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.net_logs = []
        # ID helpers
        self._id_prefix_book = 'bk'
        self._id_prefix_chapter = 'ch'
        self._id_prefix_comment = 'cmt'
        self._id_prefix_reply = 'rep'
        self._platform_prefix = 'wn'

    def _make_internal_id(self, prefix='id'):
        """Generate UUID v7 (time-sortable) ID"""
        return str(uuid6.uuid7())

    def _make_platform_obf(self, src_str, platform_prefix=None):
        """Create an obfuscated platform id from a stable source string (sha1 -> short)."""
        try:
            pref = platform_prefix or self._platform_prefix
            h = hashlib.sha1(src_str.encode('utf-8')).hexdigest()[:8]
            return f"{pref}_{h}"
        except:
            return f"{platform_prefix or self._platform_prefix}_{uuid.uuid4().hex[:8]}"
    
    def start(self):
        """Initialize browser with anti-detection settings"""
        safe_print("🚀 Starting Webnovel Scraper...")
        safe_print(f"   Mode: {'Headless' if self.headless else 'Visual'}")
        safe_print(f"   Block Resources: {'Yes' if self.block_resources else 'No'}")
        
        self.playwright = sync_playwright().start()
        
        # SYSTEM CHROME STRATEGY: Use actual Google Chrome instead of Chromium
        # This bypasses Cloudflare detection more effectively
        self.browser = self.playwright.chromium.launch(
            channel="chrome",  # Use system Chrome instead of bundled Chromium
            headless=self.headless,  # Use configured headless mode
            args=[
                '--disable-blink-features=AutomationControlled',  # Hide automation
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context WITHOUT hardcoded User-Agent (let Chrome use its native UA)
        # Hardcoded UA causes version mismatch → Cloudflare flags it
        context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            # NO user_agent - let Chrome provide its own native User-Agent
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        # Keep context reference for cookie injection
        self.context = context
        self.page = context.new_page()
        
        # FAST MODE: Block images/fonts/css/media to speed up scraping
        if self.block_resources:
            safe_print("⚡ Fast Mode: Blocking images, fonts, CSS, and media...")
            self.page.route("**/*.{png,jpg,jpeg,gif,svg,webp,ico,css,woff,woff2,ttf,mp4,mp3,wav}", 
                           lambda route: route.abort())

        # If a cookies.json file exists in repo root, load it into the context
        try:
            if os.path.exists('cookies.json'):
                try:
                    with open('cookies.json', 'r', encoding='utf-8') as cf:
                        cookies = json.load(cf)
                        if isinstance(cookies, list) and cookies:
                            # Normalize cookie dicts if necessary
                            to_add = []
                            for c in cookies:
                                if 'name' in c and 'value' in c:
                                    # Must provide either 'url' or 'domain'+'path'
                                    if 'url' not in c and 'domain' in c:
                                        # ensure path
                                        if 'path' not in c:
                                            c['path'] = '/'
                                    to_add.append(c)
                            if to_add:
                                try:
                                    self.context.add_cookies(to_add)
                                    safe_print(f"🔑 Loaded {len(to_add)} cookies from cookies.json")
                                except Exception as e:
                                    safe_print(f"⚠️ Failed to add cookies: {e}")
                except Exception as e:
                    safe_print(f"⚠️  Could not read cookies.json: {e}")
        except Exception:
            pass
        
        # Remove webdriver flag
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        safe_print("✅ Browser started (stealth mode)")
    
    def stop(self):
        """Cleanup resources"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        safe_print("🛑 Browser stopped")

    def export_cookies_interactive(self, target_url='https://www.webnovel.com/', save_path='cookies.json'):
        """Open browser, let user login manually, then save cookies to `save_path`.

        Usage: call `start()` first to initialize browser/context, then call this method.
        The method navigates to `target_url`, prints instructions, waits for ENTER, then
        exports cookies from the current browser context into a JSON file consumable
        by `context.add_cookies()` (and by the scraper when loading `cookies.json`).
        """
        try:
            if not getattr(self, 'page', None):
                safe_print("⚠️ Browser not started. Call start() before exporting cookies.")
                return None

            safe_print(f"🔐 Opening: {target_url} — please log in in the opened browser window.")
            try:
                self.page.goto(target_url, timeout=config.TIMEOUT, wait_until='domcontentloaded')
            except Exception:
                # ignore navigation errors; page will still be usable
                pass

            safe_print("📌 Please complete the login flow in the browser window.")
            safe_print("📌 After you successfully log in, return to this terminal and press ENTER.")
            input()

            # Give the page a moment to settle and set cookies
            time.sleep(1.2)

            cookies = self.context.cookies()
            if not cookies:
                safe_print("⚠️ No cookies found in browser context after login.")
                return None

            # Normalize and save
            out = []
            for c in cookies:
                # Keep keys: name, value, domain, path, expires, httpOnly, secure, sameSite
                entry = {
                    'name': c.get('name'),
                    'value': c.get('value'),
                    'domain': c.get('domain'),
                    'path': c.get('path', '/'),
                }
                if 'expires' in c:
                    entry['expires'] = c.get('expires')
                if 'httpOnly' in c:
                    entry['httpOnly'] = c.get('httpOnly')
                if 'secure' in c:
                    entry['secure'] = c.get('secure')
                if 'sameSite' in c:
                    entry['sameSite'] = c.get('sameSite')
                out.append(entry)

            try:
                with open(save_path, 'w', encoding='utf-8') as sf:
                    json.dump(out, sf, ensure_ascii=False, indent=2)
                safe_print(f"🔑 Saved {len(out)} cookies to: {save_path}")
                return save_path
            except Exception as e:
                safe_print(f"⚠️ Failed to save cookies to {save_path}: {e}")
                return None
        except Exception as e:
            safe_print(f"⚠️ export_cookies_interactive error: {e}")
            return None
    
    # ==================== MAIN SCRAPER ====================
    
    def scrape_book(self, book_url, max_chapters=None, wait_for_login=False, chapter_limit=None):
        """
        Scrape complete book with all data
        
        Args:
            book_url: URL of the book to scrape
            max_chapters: Maximum number of chapters to scrape (None = all) - DEPRECATED, use chapter_limit
            wait_for_login: If True, pause and wait for manual login before scraping
            chapter_limit: Limit number of chapters to scrape (None = all, overrides max_chapters)
        
        Returns:
            dict: Complete book data following schema
        """
        # Use chapter_limit if provided, otherwise fall back to max_chapters
        limit = chapter_limit if chapter_limit is not None else max_chapters
        safe_print(f"\n{'='*60}")
        safe_print(f"📖 SCRAPING BOOK: {book_url}")
        safe_print(f"{'='*60}\n")
        
        # Navigate to book page with random delay (OPTIMIZED: domcontentloaded)
        try:
            self.page.goto(book_url, timeout=config.TIMEOUT, wait_until='domcontentloaded')
            safe_print("⚡ Book page DOM loaded (skipped waiting for ads/images)")
        except Exception as goto_err:
            safe_print(f"⚠️  Navigation to book page failed or timed out: {goto_err}")
        self._random_sleep(1.5, 2.5)

        # Close any login/pop-up overlays that block interaction
        try:
            self._close_popups()
        except:
            pass
        
        # Wait for manual login if requested
        if wait_for_login:
            safe_print("\n" + "="*60)
            safe_print("⏸️  MANUAL LOGIN REQUIRED")
            safe_print("="*60)
            safe_print("📌 Please log in to Webnovel in the browser window")
            safe_print("📌 After logging in, press ENTER here to continue...")
            safe_print("="*60 + "\n")
            input()  # Wait for user to press Enter
            safe_print("✅ Continuing scrape with authenticated session...\n")
            self._random_sleep()
        
        # Extract platform book ID from URL (kept for API/selector use)
        book_id_raw = self._extract_book_id(book_url)
        platform_book_id = f"wn_{book_id_raw}"

        # Generate UUID v7 for primary ID (time-sortable)
        internal_book_id = str(uuid6.uuid7())
        
        # Scrape book metadata with FINAL SCHEMA
        book_data = {
            "id": internal_book_id,  # UUID v7 primary key
            "platform_id": platform_book_id,  # Original Webnovel ID for traceability
            "platform": "webnovel",
            "name": self._scrape_book_name(),
            "url": book_url,
            "cover_image": self._scrape_cover_image(internal_book_id),
            "author": self._scrape_author(),
            "category": self._scrape_category(),
            "status": self._get_status_from_api(book_id_raw),  # Scrape status (Ongoing/Completed)
            "tags": self._scrape_tags(),
            "description": self._scrape_description(),
            "total_views": self._scrape_total_views(),
            "total_chapters": self._scrape_total_chapters(),
            "power_ranking_position": self._scrape_power_ranking_position(),
            "power_ranking_title": self._scrape_power_ranking_title(),
            "ratings": self._scrape_ratings(),
            "comments": self._scrape_book_comments(internal_book_id, platform_book_id),
            "chapters": []
        }
        
        # Scrape chapters with smart limit and locked chapter detection
        chapter_list = self._get_chapter_urls(book_url, platform_book_id)
        if chapter_list:
            if limit:
                chapter_list = chapter_list[:limit]
                safe_print(f"\n📚 Found {len(chapter_list)} chapters (limited to {limit})\n")
            else:
                safe_print(f"\n📚 Found {len(chapter_list)} chapters to scrape\n")

            consecutive_empty = 0  # Track consecutive locked/empty chapters
            MAX_CONSECUTIVE_EMPTY = 5  # Stop if 5 consecutive chapters are locked

            for index, item in enumerate(chapter_list):
                # item may be a dict {url,order,name,published_time} or a raw url string
                if isinstance(item, dict):
                    url = item.get('url')
                    order = item.get('order', index + 1)  # Use order from TOC or fallback to index
                    toc_name = item.get('name')
                    toc_published = item.get('published_time')
                else:
                    url = item
                    order = index + 1
                    toc_name = None
                    toc_published = None

                chapter = self._scrape_chapter(url, internal_book_id, platform_book_id, order, toc_name, toc_published)
                if chapter:
                    # Check if chapter content is empty/locked (less than 50 chars)
                    content_len = len(chapter.get('content', '') or '')
                    if content_len < 50:
                        consecutive_empty += 1
                        safe_print(f"⚠️  Chapter {order} appears locked/empty ({content_len} chars) - consecutive: {consecutive_empty}/{MAX_CONSECUTIVE_EMPTY}")
                        
                        # Stop if we hit too many consecutive locked chapters
                        if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                            safe_print(f"\n🔒 Hit {MAX_CONSECUTIVE_EMPTY} consecutive locked chapters. Stopping scrape to save time.")
                            safe_print(f"   Scraped {len(book_data['chapters'])} chapters successfully.\n")
                            break
                    else:
                        consecutive_empty = 0  # Reset counter on successful chapter
                    
                    book_data["chapters"].append(chapter)
                safe_print(f"✅ Chapter {order}/{len(chapter_list)} completed")
        
        # Save to JSON
        self._save_book_to_json(book_data)
        
        safe_print(f"\n{'='*60}")
        safe_print(f"✅ BOOK SCRAPING COMPLETED")
        safe_print(f"   Name: {book_data['name']}")
        safe_print(f"   Chapters: {len(book_data['chapters'])}")
        safe_print(f"   Comments: {len(book_data['comments'])}")
        safe_print(f"{'='*60}\n")
        
        return book_data
    
    # ==================== BOOK METADATA SCRAPERS ====================
    
    def _extract_book_id(self, url):
        """Extract book ID from URL"""
        match = re.search(r"_(\d{10,})$", url)
        if match:
            return match.group(1)
        match = re.search(r"(\d{10,})", url)
        return match.group(1) if match else "unknown"

    def _extract_book_slug(self, url):
        """Extract book slug (text part) from URL like /book/slug_bookid"""
        try:
            m = re.search(r"/book/([a-z0-9\-]+)_\d{10,}", url, re.I)
            if m:
                return m.group(1)
        except:
            pass
        return ""
    
    def _scrape_book_name(self):
        """Scrape book title"""
        try:
            title_el = self.page.locator("h1").first
            if title_el.count() > 0:
                title = title_el.inner_text().strip()
                safe_print(f"📌 Title: {title}")
                return title
        except:
            pass
        return self.page.title().split('|')[0].strip()
    
    def _scrape_author(self):
        """Scrape author name"""
        try:
            author_el = self.page.locator("a[href*='/profile/']").first
            if author_el.count() > 0:
                author = author_el.inner_text().strip()
                safe_print(f"✍️  Author: {author}")
                return author
        except:
            pass
        return "Unknown Author"
    
    def _scrape_cover_image(self, book_id):
        """Download and save cover image"""
        try:
            img_el = self.page.locator("img[src*='bookcover'], img[src*='book-pic'], img.book-cover").first
            if img_el.count() > 0:
                img_url = img_el.get_attribute("src")
                if img_url and img_url.startswith("//"):
                    img_url = "https:" + img_url
                
                local_path = utils.download_image(img_url, book_id)
                if local_path:
                    safe_print(f"🖼️  Cover saved: {local_path}")
                    return local_path
        except Exception as e:
            safe_print(f"⚠️  Cover error: {e}")
        return None
    
    def _scrape_category(self):
        """Scrape category from book header (e.g., 'Theater', 'Video Games', 'Anime & Comics')"""
        try:
            # PRIORITY 1: Extract category link from header (most reliable)
            # Category appears as a link below the book title, linking to /category/ page
            category_selectors = [
                "a[href*='/category/']",  # Direct category link (most reliable)
                ".j_book_info a[href*='/category/']",  # Within book info container
                ".det-hd-detail a[href*='/category/']",  # Within detail header
                "p.ell a[href*='/category/']",  # Common pattern for ellipsis paragraphs
                ".j_book_info h2 + div a",  # Link after h2 (book title)
                ".det-info a[href*='/category/']"
            ]
            
            for selector in category_selectors:
                try:
                    category_link = self.page.locator(selector).first
                    if category_link.count() > 0:
                        category = category_link.inner_text().strip()
                        # Validate it's not empty and not a number
                        if category and len(category) > 2 and not category.isdigit():
                            safe_print(f"📂 Category: {category}")
                            return category
                except:
                    continue
            
            # PRIORITY 2: Try broader link search in header area
            try:
                # Get all links in book info area
                info_links = self.page.locator(".j_book_info a, .det-hd-detail a, p.ell a").all()
                for link in info_links:
                    try:
                        href = link.get_attribute('href') or ''
                        if '/category/' in href:
                            category = link.inner_text().strip()
                            if category and len(category) > 2 and not category.isdigit():
                                safe_print(f"📂 Category (broad search): {category}")
                                return category
                    except:
                        continue
            except:
                pass
            
            # PRIORITY 3: Look for common category names in header text
            # Common categories: Theater, Video Games, Anime & Comics, Movies, TV, etc.
            common_categories = [
                'Theater', 'Theatre', 'Video Games', 'Anime & Comics', 'Movies', 'TV',
                'Books', 'Comics', 'Games', 'Eastern Fantasy', 'Western Fantasy',
                'Urban', 'Sci-fi', 'Horror', 'Action', 'Romance', 'Fan-Fiction', 'Fanfic'
            ]
            
            try:
                header_text = self.page.locator(".j_book_info, .det-hd-detail").first.inner_text()
                for cat in common_categories:
                    if cat in header_text:
                        safe_print(f"📂 Category (text match): {cat}")
                        return cat
            except:
                pass
            
            # FALLBACK: Generic link selector (last resort)
            try:
                generic_link = self.page.locator("span._ml a").first
                if generic_link.count() > 0:
                    category = generic_link.inner_text().strip()
                    if category and len(category) > 2 and not category.isdigit():
                        safe_print(f"📂 Category (fallback): {category}")
                        return category
            except:
                pass
                
        except Exception as e:
            safe_print(f"⚠️  Category extraction error: {e}")
        
        safe_print(f"⚠️  Category: Not found")
        return ""
    
    def _get_status_from_api(self, book_id):
        """Get book status from WebNovel API or page HTML (Ongoing/Completed)"""
        # Try extracting from page HTML first (more reliable)
        try:
            # Look for status indicator in the page
            status_selectors = [
                "span.status",
                "span.book-status",
                "span[class*='status']",
                "p.status"
            ]
            
            for selector in status_selectors:
                try:
                    status_el = self.page.locator(selector).first
                    if status_el.count() > 0:
                        status_text = status_el.inner_text().strip().lower()
                        if 'completed' in status_text or 'finish' in status_text:
                            safe_print("📖 Status: Completed")
                            return "Completed"
                        elif 'ongoing' in status_text or 'updating' in status_text:
                            safe_print("📖 Status: Ongoing")
                            return "Ongoing"
                except:
                    continue
            
            # Fallback: check full page text
            page_text = self.page.locator("body").inner_text().lower()
            if "status: completed" in page_text or "status:completed" in page_text:
                safe_print("📖 Status: Completed (from page text)")
                return "Completed"
            elif "status: ongoing" in page_text or "status:ongoing" in page_text:
                safe_print("📖 Status: Ongoing (from page text)")
                return "Ongoing"
            
            # Try API as last resort
            try:
                api_url = f"https://www.webnovel.com/apiajax/api/GetBookinfoPage?bookId={book_id}"
                response = httpx.get(api_url, timeout=5, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.webnovel.com/',
                    'Accept': 'application/json'
                })
                if response.status_code == 200:
                    data = response.json()
                    book_info = data.get('data', {})
                    book_status_code = book_info.get('bookStatus')
                    if book_status_code == 1:
                        safe_print("📖 Status (from API): Ongoing")
                        return "Ongoing"
                    elif book_status_code == 2:
                        safe_print("📖 Status (from API): Completed")
                        return "Completed"
            except:
                pass
            
        except Exception as e:
            safe_print(f"⚠️  Status detection error: {e}")
        
        safe_print("📖 Status: None (not detected)")
        return None
    
    def _scrape_tags(self):
        """Scrape all tags"""
        tags = []
        try:
            tags_container = self.page.locator("div.m-tags").first
            if tags_container.count() > 0:
                tag_elements = tags_container.locator("p.m-tag").all()
                for tag_el in tag_elements:
                    tag = tag_el.inner_text().strip().lstrip('#').strip()
                    if tag:
                        tags.append(tag)
            safe_print(f"🏷️  Tags: {tags}")
        except:
            pass
        return tags
    
    def _scrape_description(self):
        """Scrape book description/synopsis"""
        try:
            # Try multiple selectors
            desc_paras = self.page.locator("div._synopsis p, section.j_synopsis p").all()
            if desc_paras:
                desc = "\n".join([p.inner_text().strip() for p in desc_paras if p.inner_text().strip()])
                safe_print(f"📝 Description: {desc[:100]}...")
                return desc
            
            # Fallback: find Synopsis section
            desc_container = self.page.locator("text=Synopsis").locator('..').first
            if desc_container.count() > 0:
                desc_text = desc_container.inner_text()
                lines = [line.strip() for line in desc_text.split('\n') if line.strip()]
                filtered_lines = []
                for line in lines:
                    if line.lower() in ['synopsis', 'tags', 'fans', 'see all', 'general audiences', 'weekly power status']:
                        continue
                    if line.startswith('#') or 'Contributed' in line or 'Power' in line:
                        break
                    filtered_lines.append(line)
                desc = "\n".join(filtered_lines).strip()
                safe_print(f"📝 Description: {desc[:100]}...")
                return desc
        except:
            pass
        return ""
    
    def _scrape_total_views(self):
        """Scrape total view count"""
        try:
            page_text = self.page.locator("body").inner_text()
            match = re.search(r"([\d,\.KMkm]+)\s*Views?", page_text, re.I)
            if match:
                views = match.group(1)
                safe_print(f"👁️  Views: {views}")
                return views
        except:
            pass
        return "0"
    
    def _scrape_total_chapters(self):
        """Scrape total chapter count as integer"""
        try:
            page_text = self.page.locator("body").inner_text()
            match = re.search(r"(\d+[\d,\.]*)\s*Chapters?", page_text, re.I)
            if match:
                chapters_str = match.group(1).replace(',', '').replace('.', '')
                chapters = int(chapters_str)
                safe_print(f"📚 Chapters: {chapters}")
                return chapters
        except:
            pass
        return 0
    
    def _scrape_power_ranking_position(self):
        """Scrape power ranking position (e.g., #3)"""
        try:
            # Exact selector from F12: <a class="vam rank-tag td300 mr16" title="＃3 Originals' Power Ranking">
            rank_el = self.page.locator("a.rank-tag[title*='#'], a.rank-tag[title*='＃']").first
            if rank_el.count() > 0:
                title_text = rank_el.get_attribute("title") or rank_el.inner_text()
                # Handle both # and ＃ (full-width)
                match = re.search(r"[#＃](\d+)", title_text)
                if match:
                    position = int(match.group(1))
                    safe_print(f"🏆 Ranking Position: #{position}")
                    return position
        except:
            pass
        return None
    
    def _scrape_power_ranking_title(self):
        """Scrape power ranking title (e.g., 'Originals' Power Ranking')"""
        try:
            rank_el = self.page.locator("a.rank-tag[title*='#'], a.rank-tag[title*='＃']").first
            if rank_el.count() > 0:
                title_text = rank_el.get_attribute("title") or rank_el.inner_text()
                # Remove "#3 " or "＃3 " prefix to get title
                match = re.search(r"[#＃]\d+\s+(.+)", title_text)
                if match:
                    title = match.group(1).strip()
                    safe_print(f"🏆 Ranking Title: {title}")
                    return title
        except:
            pass
        return None
    
    def _scrape_ratings(self):
        """Scrape all rating scores"""
        ratings = {
            "total_ratings": 0,
            "overall_score": 0.0,
            "writing_quality": 0.0,
            "stability_of_updates": 0.0,
            "story_development": 0.0,
            "character_design": 0.0,
            "world_background": 0.0
        }
        
        try:
            # STRATEGY 1: Try to extract from ._score element (most accurate)
            try:
                score_elem = self.page.locator("._score, .score, [class*='_score']").first
                if score_elem.count() > 0:
                    score_text = score_elem.inner_text().strip()
                    # Try to extract number like "4.29" or "4.3"
                    score_match = re.search(r'(\d+\.\d+)', score_text)
                    if score_match:
                        ratings["overall_score"] = float(score_match.group(1))
                        safe_print(f"   ✅ Found score from ._score element: {ratings['overall_score']}")
            except:
                pass
            
            # STRATEGY 2: Try meta tags (often contain accurate rating data)
            if ratings["overall_score"] == 0.0:
                try:
                    # Look for rating meta tags
                    meta_selectors = [
                        "meta[property='books:rating:value']",
                        "meta[itemprop='ratingValue']",
                        "meta[name='rating']"
                    ]
                    for selector in meta_selectors:
                        try:
                            meta = self.page.locator(selector).first
                            if meta.count() > 0:
                                content = meta.get_attribute('content')
                                if content:
                                    ratings["overall_score"] = float(content)
                                    safe_print(f"   ✅ Found score from meta tag: {ratings['overall_score']}")
                                    break
                        except:
                            continue
                except:
                    pass
            
            # STRATEGY 3: Extract from Review Tab/Section Header (CRITICAL FIX)
            if ratings["overall_score"] == 0.0 or ratings["total_ratings"] == 0:
                try:
                    # Click Review tab to reveal review info header
                    review_tab_clicked = False
                    for tab_sel in ["button:has-text('Review')", "a:has-text('Review')", "li:has-text('Review')"]:
                        try:
                            tab = self.page.locator(tab_sel).first
                            if tab.count() > 0:
                                tab.click(timeout=3000)
                                self._random_sleep(1, 2)
                                review_tab_clicked = True
                                safe_print(f"   📝 Clicked Review tab to reveal rating info")
                                break
                        except:
                            continue
                    
                    # Now look for Review Info Header container
                    # Common patterns: h4 with large score + review count
                    review_containers = [
                        ".review-header",
                        ".review-info",
                        "div:has(h4):has-text('Score')",
                        "div:has(h4):has-text('Review')",
                        "section.m-review-header",
                        ".j_review_info"
                    ]
                    
                    for container_sel in review_containers:
                        try:
                            container = self.page.locator(container_sel).first
                            if container.count() > 0:
                                container_text = container.inner_text()
                                
                                # Extract score (e.g., "4.29")
                                if ratings["overall_score"] == 0.0:
                                    score_match = re.search(r'(\d+\.\d+)(?:\s*Score)?', container_text)
                                    if score_match:
                                        ratings["overall_score"] = float(score_match.group(1))
                                        safe_print(f"   ✅ Found score from Review header: {ratings['overall_score']}")
                                
                                # Extract review count (e.g., "7 Reviews")
                                if ratings["total_ratings"] == 0:
                                    reviews_match = re.search(r'(\d+)\s*Reviews?', container_text, re.I)
                                    if reviews_match:
                                        ratings["total_ratings"] = int(reviews_match.group(1))
                                        safe_print(f"   ✅ Found {ratings['total_ratings']} reviews from Review header")
                                
                                if ratings["overall_score"] > 0 or ratings["total_ratings"] > 0:
                                    break
                        except:
                            continue
                    
                    # Also check h4 tags directly (often contain score as large number)
                    if ratings["overall_score"] == 0.0:
                        try:
                            h4_elements = self.page.locator("h4").all()
                            for h4 in h4_elements:
                                h4_text = h4.inner_text().strip()
                                # Look for large decimal number like "4.29"
                                if re.match(r'^\d+\.\d+$', h4_text):
                                    ratings["overall_score"] = float(h4_text)
                                    safe_print(f"   ✅ Found score from h4 badge: {ratings['overall_score']}")
                                    break
                        except:
                            pass
                    
                except Exception as review_err:
                    safe_print(f"   ⚠️  Review section extraction failed: {review_err}")
            
            # STRATEGY 4: Parse from page text near "Reviews" or "Score"
            page_text = self.page.locator("body").inner_text()
            
            # Look for patterns like "7 Reviews" and "4.29 Score"
            if ratings["total_ratings"] == 0:
                reviews_match = re.search(r'(\d+)\s*Reviews?', page_text, re.I)
                if reviews_match:
                    ratings["total_ratings"] = int(reviews_match.group(1))
                    safe_print(f"   ✅ Found {ratings['total_ratings']} reviews from text")
            
            if ratings["overall_score"] == 0.0:
                # Look for "4.29 Score" pattern
                score_match = re.search(r'(\d+\.\d+)\s*Score', page_text, re.I)
                if score_match:
                    ratings["overall_score"] = float(score_match.group(1))
                    safe_print(f"   ✅ Found score from text: {ratings['overall_score']}")
            
            # FALLBACK: Original regex pattern
            if ratings["overall_score"] == 0.0:
                match = re.search(r"(\d+\.\d{1,2})\s*\((\d+)\s*ratings?\)", page_text, re.I)
                if match:
                    ratings["overall_score"] = float(match.group(1))
                    ratings["total_ratings"] = int(match.group(2))
            
            # Parse 5 category scores
            score_items = self.page.locator("li:has(strong)").all()
            for item in score_items:
                try:
                    label = item.locator("strong").inner_text().strip().lower()
                    stars = item.locator("svg.g_star._on, span.g_star svg._on").count()
                    
                    if "writing quality" in label:
                        ratings["writing_quality"] = float(stars)
                    elif "stability" in label:
                        ratings["stability_of_updates"] = float(stars)
                    elif "story" in label:
                        ratings["story_development"] = float(stars)
                    elif "character" in label:
                        ratings["character_design"] = float(stars)
                    elif "world" in label or "background" in label:
                        ratings["world_background"] = float(stars)
                except:
                    continue
            
            # CRITICAL FALLBACK: Calculate overall_score from sub-ratings if it's still 0
            if ratings["overall_score"] == 0.0:
                sub_ratings = [
                    ratings["writing_quality"],
                    ratings["stability_of_updates"],
                    ratings["story_development"],
                    ratings["character_design"],
                    ratings["world_background"]
                ]
                # Filter out zero values
                non_zero_ratings = [r for r in sub_ratings if r > 0]
                
                if non_zero_ratings:
                    calculated_score = sum(non_zero_ratings) / len(non_zero_ratings)
                    ratings["overall_score"] = round(calculated_score, 2)
                    safe_print(f"   📊 Calculated overall_score from sub-ratings: {ratings['overall_score']}")
            
            safe_print(f"⭐ Ratings: {ratings['overall_score']} ({ratings['total_ratings']} ratings)")
        except Exception as e:
            safe_print(f"⚠️  Rating extraction error: {e}")
        
        return ratings

    def _close_popups(self):
        """Attempt to close common modal dialogs/popups that block the page.

        This will try a series of close buttons, press Escape, then remove
        persistent overlay elements to avoid accidental redirects (eg. login
        modal or app-download prompts).
        """
        try:
            safe_print("🔐 Attempting to close popups (if any)...")

            # Try common close buttons/selectors
            close_selectors = [
                "button[aria-label='Close']",
                "button[aria-label=close]",
                "button:has-text('Close')",
                "button:has-text('×')",
                "button:has-text('X')",
                ".modal-close",
                ".close",
                ".popup-close",
                ".wn-modal .close",
                ".dialog__close"
            ]

            for sel in close_selectors:
                try:
                    els = self.page.locator(sel).all()
                    if els:
                        for el in els[:3]:
                            try:
                                el.scroll_into_view_if_needed()
                                el.click()
                                time.sleep(0.6)
                            except:
                                continue
                except:
                    continue

            # Press Escape to close overlays
            try:
                self.page.keyboard.press('Escape')
                time.sleep(0.5)
            except:
                pass

            # As a last resort, remove overlay/modal elements by class names
            try:
                self.page.evaluate("""
                    (() => {
                        const selectors = ['.modal', '.popup', '.dialog', '.wn-modal', '.login-modal', '.app-download', '.g_mod_login', '.g_mod_wrap'];
                        selectors.forEach(s => {
                            document.querySelectorAll(s).forEach(el => el.remove());
                        });
                        // remove big overlay backgrounds
                        document.querySelectorAll('[class*="overlay"]').forEach(el => el.remove());
                        // remove known login iframe
                        const ifr = document.getElementById('loginIfr');
                        if (ifr && ifr.parentElement) { ifr.parentElement.remove(); }
                        // also try to disable pointer-events on any element that still covers the page
                        document.querySelectorAll('*').forEach(el => {
                            try { if (getComputedStyle(el).position === 'fixed' && getComputedStyle(el).zIndex >= 1000) { el.style.pointerEvents='none'; } } catch(e) {}
                        });
                    })()
                """)
                time.sleep(0.5)
            except:
                pass

            safe_print("🔐 Popups closed (if any)")
        except Exception as e:
            safe_print(f"⚠️  _close_popups error: {e}")
    
    def _random_sleep(self, min_sec=0.5, max_sec=1.5):
        """Sleep for a random duration to mimic human behavior - balanced speed & reliability"""
        duration = random.uniform(min_sec, max_sec)
        time.sleep(duration)
    
    def _smooth_scroll(self, distance=500, steps=5):
        """Scroll smoothly in steps to mimic human scrolling"""
        step_distance = distance // steps
        for _ in range(steps):
            self.page.evaluate(f"window.scrollBy(0, {step_distance})")
            time.sleep(random.uniform(0.1, 0.3))
    
    # ==================== BOOK COMMENTS SCRAPER ====================
    
    def _scrape_book_comments(self, internal_book_id, platform_book_id):
        """
        Scrape ALL comments on book page with pagination and replies
        Uses Network Interception (Option A) for reliable data extraction
        
        Returns:
            list[CommentOnBook]: All comments with replies
        """
        safe_print("\n💬 Scraping book comments via Network Interception...")
        comments = []
        
        # Storage for intercepted API responses
        self.captured_comment_data = []
        self.captured_reply_data = {}
        
        def handle_comment_response(response):
            """Intercept and store comment/review API responses"""
            try:
                url = response.url
                
                # Check if this is a comment/review API endpoint
                is_comment_api = any(pattern in url.lower() for pattern in [
                    'getcommentlist', 'get-comment-list',
                    'getreviewlist', 'get-review-list',
                    'bookreview', 'book-review',
                    'review/list', 'comment/list'
                ])
                
                if not is_comment_api:
                    return
                
                # Only process JSON responses
                content_type = response.headers.get('content-type', '')
                if 'json' not in content_type.lower():
                    return
                
                try:
                    data = response.json()
                    if data:
                        # Store the response data
                        self.captured_comment_data.append({
                            'url': url,
                            'data': data,
                            'status': response.status
                        })
                        safe_print(f"   🎯 Intercepted API response: {url[:80]}...")
                except Exception as json_err:
                    pass
            except Exception as e:
                pass
        
        try:
            # Start network interception
            self.page.on('response', handle_comment_response)
            safe_print("   📡 Network interception enabled")
            
            # First, try to parse JSON-LD reviews embedded in the page (fast, unauthenticated)
            try:
                jsonld_scripts = self.page.locator("script[type='application/ld+json']").all()
                parsed_from_jsonld = []
                def extract_reviews_from_obj(obj):
                    if not isinstance(obj, dict):
                        return []
                    out = []
                    # If this object is a Book and has reviews
                    t = obj.get('@type') or obj.get('type')
                    if t and ('Book' in t) and obj.get('review'):
                        for rv in obj.get('review'):
                            try:
                                author = None
                                if isinstance(rv.get('author'), dict):
                                    author = rv.get('author', {}).get('name')
                                else:
                                    author = rv.get('author')
                                body = rv.get('reviewBody') or rv.get('description') or ''
                                date = rv.get('datePublished') or ''
                                score_val = None
                                try:
                                    score_val = float(rv.get('reviewRating', {}).get('ratingValue')) if rv.get('reviewRating') and rv.get('reviewRating').get('ratingValue') else None
                                except:
                                    score_val = None
                                comment = {
                                    'comment_id': f"wn_{str(uuid.uuid4())[:8]}",
                                    'story_id': book_id,
                                    'user_id': f"wn_{str(uuid.uuid4())[:8]}",
                                    'user_name': author or 'Anonymous',
                                    'time': date,
                                    'content': body,
                                    'score': {'overall': score_val},
                                    'replies': []
                                }
                                out.append(comment)
                            except:
                                continue
                    # Also look for nested review lists
                    for k, v in obj.items():
                        if isinstance(v, dict):
                            out.extend(extract_reviews_from_obj(v))
                        elif isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict):
                                    out.extend(extract_reviews_from_obj(item))
                    return out

                for s in jsonld_scripts:
                    try:
                        txt = s.inner_text()
                        if not txt or len(txt) < 10:
                            continue
                        data = json.loads(txt)
                        # data may be dict or list
                        if isinstance(data, list):
                            root_objs = data
                        else:
                            # handle @graph wrapper
                            if isinstance(data, dict) and data.get('@graph') and isinstance(data.get('@graph'), list):
                                root_objs = data.get('@graph')
                            else:
                                root_objs = [data]
                        for obj in root_objs:
                            parsed = extract_reviews_from_obj(obj)
                            if parsed:
                                parsed_from_jsonld.extend(parsed)
                    except Exception:
                        continue
                if parsed_from_jsonld:
                    safe_print(f"✅ Parsed {len(parsed_from_jsonld)} book reviews from JSON-LD")
                    return parsed_from_jsonld
            except Exception:
                pass

            # Click Reviews tab if exists and wait for API responses
            try:
                review_tab = self.page.locator("button:has-text('Review'), a:has-text('Review'), a:has-text('Comments'), button:has-text('Comments'), a:has-text('About'), button:has-text('About')").first
                if review_tab.count() > 0:
                    safe_print("   📑 Clicking Reviews tab...")
                    review_tab.click()
                    # Wait for API responses to be captured
                    self._random_sleep(2, 4)  # Give time for initial page + API calls
            except:
                pass

            safe_print("📜 Collecting book comments with pagination...")
            collected = []
            seen_comment_ids = set()
            
            # Extract comments from initial page (captured API data)
            if self.captured_comment_data:
                safe_print(f"   ✅ Processing {len(self.captured_comment_data)} intercepted API response(s)")
                for api_response in self.captured_comment_data:
                    extracted = self._extract_comments_from_api_response(
                        api_response['data'], 
                        internal_book_id, 
                        platform_book_id
                    )
                    for comment in extracted:
                        cid = comment.get('comment_id')
                        if cid and cid not in seen_comment_ids:
                            seen_comment_ids.add(cid)
                            collected.append(comment)
                safe_print(f"   ✅ Extracted {len(collected)} comments from API responses")
            
            # If API didn't capture anything, immediately parse HTML for page 1
            if not collected:
                page_comments, _ = self._parse_book_comments(internal_book_id, platform_book_id, return_ids=True)
                for comment in page_comments:
                    cid = comment.get('comment_id')
                    if cid and cid not in seen_comment_ids:
                        seen_comment_ids.add(cid)
                        collected.append(comment)
                if collected:
                    safe_print(f"   ✅ Page 1: {len(collected)} comments (HTML parsing)")
            
            # Close login modal if it appears (blocks pagination)
            try:
                login_modal = self.page.locator(".g_mod_login._on, .g_mod_wrap._on").first
                if login_modal.count() > 0 and login_modal.is_visible():
                    safe_print(f"   🔒 Closing login modal...")
                    # Try Escape key first
                    self.page.keyboard.press("Escape")
                    self._random_sleep(0.5, 1)
            except:
                pass
            
            # CRITICAL: Scroll to bottom to trigger pagination rendering
            try:
                safe_print(f"   📜 Scrolling to load pagination...")
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._random_sleep(2, 3)
            except:
                pass
            
            # Parse pagination to determine total pages
            detected_pages = 1
            pagination_container = None
            try:
                pagination_container = self.page.locator("div.ui-page-x").first
                if pagination_container.count() > 0:
                    # Find all numbered page links
                    page_links = pagination_container.locator("a.ui-page[data-page]").all()
                    page_numbers = []
                    for link in page_links:
                        try:
                            page_num = link.get_attribute('data-page')
                            if page_num and page_num.isdigit():
                                page_numbers.append(int(page_num))
                        except:
                            continue
                    if page_numbers:
                        detected_pages = max(page_numbers)
                        safe_print(f"   📄 Detected {detected_pages} total pages")
            except Exception as e:
                safe_print(f"   ⚠️ Could not detect pagination: {e}")
            
            # Now paginate through remaining pages (2 to detected_pages)
            if detected_pages > 1 and pagination_container:
                safe_print(f"\n   ➡️  Paginating through pages 2-{detected_pages}...")
                
                for page_num in range(2, detected_pages + 1):
                    try:
                        before_count = len(collected)
                        
                        # Find link to next page
                        next_page_link = pagination_container.locator(f"a.ui-page[data-page='{page_num}']").first
                        
                        if next_page_link.count() == 0:
                            safe_print(f"      ⚠️ Page {page_num} link not found - stopping")
                            break
                        
                        safe_print(f"   📄 Loading page {page_num}...")
                        
                        # Clear captured API data
                        self.captured_comment_data = []
                    
                        # Scroll link into view and click
                        try:
                            next_page_link.scroll_into_view_if_needed(timeout=3000)
                        except:
                            pass
                        
                        self._random_sleep(0.5, 1)
                        next_page_link.click(timeout=5000)
                        
                        # Wait for page to load
                        try:
                            self.page.wait_for_function(f"""
                                () => {{
                                    const current = document.querySelector('.ui-page-current');
                                    return current && current.textContent.trim() == '{page_num}';
                                }}
                            """, timeout=5000)
                        except:
                            pass
                        
                        # Wait for content to render
                        self._random_sleep(1.5, 2.5)
                        
                        # Parse HTML from new page (API likely won't work for Webnovel)
                        page_comments, _ = self._parse_book_comments(internal_book_id, platform_book_id, return_ids=True)
                        new_count = 0
                        for comment in page_comments:
                            cid = comment.get('comment_id')
                            if cid and cid not in seen_comment_ids:
                                seen_comment_ids.add(cid)
                                collected.append(comment)
                                new_count += 1
                        
                        safe_print(f"   ✅ Page {page_num}: +{new_count} new comments (total: {len(collected)})")
                        
                        # Stop if no new comments
                        if new_count == 0:
                            safe_print(f"      ⚠️ No new comments on page {page_num} - stopping pagination")
                            break
                        
                    except Exception as page_err:
                        safe_print(f"      ⚠️ Error on page {page_num}: {page_err}")
                        break
            
            # ATTEMPT REPLY EXTRACTION (may require login - will handle gracefully)
            safe_print(f"\n   💬 Attempting to extract comment replies...")
            replies_extracted = 0
            
            # Try to close login modal first
            try:
                login_modal = self.page.locator(".g_mod_login._on, .g_mod_wrap._on").first
                if login_modal.count() > 0 and login_modal.is_visible():
                    safe_print(f"   🔒 Login modal detected, attempting to close...")
                    self.page.keyboard.press("Escape")
                    self._random_sleep(1, 1.5)
            except:
                pass
            
            # Navigate back to page 1 to start reply extraction
            try:
                pagination_cont = self.page.locator("div.ui-page-x").first
                if pagination_cont.count() > 0 and detected_pages > 1:
                    first_page_link = pagination_cont.locator("a.ui-page[data-page='1']").first
                    if first_page_link.count() > 0:
                        first_page_link.click(timeout=5000)
                        self._random_sleep(2, 3)
            except:
                pass
            
            # Extract replies from comments on each page
            for page_num in range(1, min(detected_pages + 1, 3)):  # Limit to first 2 pages to avoid too long runtime
                try:
                    safe_print(f"   📄 Page {page_num}: Checking for replies...")
                    comment_sections = self.page.locator(".m-comment").all()
                    page_replies = 0
                    
                    for sec in comment_sections:
                        try:
                            # Get comment ID to match with collected comments
                            data_ejs = sec.get_attribute('data-ejs')
                            if not data_ejs:
                                continue
                            parsed = json.loads(data_ejs)
                            raw_id = str(parsed.get('reviewId') or parsed.get('id'))
                            
                            # Find matching comment
                            matching_comment = None
                            for c in collected:
                                if c.get('_raw_id') == raw_id:
                                    matching_comment = c
                                    break
                            
                            if not matching_comment:
                                continue
                            
                            # Skip if already has replies
                            if matching_comment.get('replies') and len(matching_comment['replies']) > 0:
                                continue
                            
                            # Look for reply button
                            reply_btn = sec.locator("a.m-comment-reply-btn").first
                            if reply_btn.count() == 0:
                                continue
                            
                            btn_text = reply_btn.inner_text()
                            if not btn_text or 'repl' not in btn_text.lower():
                                continue
                            
                            # Try to click (may be blocked by login modal)
                            try:
                                reply_btn.scroll_into_view_if_needed(timeout=3000)
                                self._random_sleep(0.3, 0.5)
                                reply_btn.click(timeout=3000)
                                self._random_sleep(1, 1.5)
                                
                                # Check for login modal blocking
                                login_check = self.page.locator(".g_mod_login._on").first
                                if login_check.count() > 0 and login_check.is_visible():
                                    safe_print(f"   ⚠️  Login required for replies - skipping remaining")
                                    # Close modal and stop trying
                                    self.page.keyboard.press("Escape")
                                    self._random_sleep(0.5, 1)
                                    raise Exception("Login required")
                                
                                # Extract replies (inline or modal)
                                replies = self._scrape_replies(sec)
                                if replies:
                                    matching_comment['replies'] = replies
                                    page_replies += len(replies)
                                    replies_extracted += len(replies)
                                    
                            except Exception as click_err:
                                # If login required, stop trying more comments
                                if "Login required" in str(click_err):
                                    raise
                                # Otherwise just skip this comment
                                continue
                                
                        except Exception as comment_err:
                            if "Login required" in str(comment_err):
                                raise
                            continue
                    
                    if page_replies > 0:
                        safe_print(f"      ✅ Extracted {page_replies} replies from page {page_num}")
                    
                    # Navigate to next page
                    if page_num < min(detected_pages, 2):
                        try:
                            next_page_link = self.page.locator(f"a.ui-page[data-page='{page_num + 1}']").first
                            if next_page_link.count() > 0:
                                next_page_link.click(timeout=5000)
                                self._random_sleep(2, 3)
                        except:
                            break
                            
                except Exception as page_err:
                    if "Login required" in str(page_err):
                        safe_print(f"   ⚠️  Login required to view replies - stopping extraction")
                        break
                    safe_print(f"   ⚠️  Error on page {page_num}: {page_err}")
                    break
            
            if replies_extracted > 0:
                safe_print(f"   ✅ Successfully extracted {replies_extracted} total replies")
            else:
                safe_print(f"   ℹ️  No replies extracted (may require authentication)")
            
            safe_print(f"   ✅ Successfully scraped {len(collected)} book comments")
            
            comments = collected
            safe_print(f"✅ Collected {len(comments)} book comments total\n")
            
            # Remove network listener
            try:
                self.page.remove_listener('response', handle_comment_response)
            except:
                pass
        
        except Exception as e:
            safe_print(f"⚠️  Error scraping book comments: {e}")
            import traceback
            traceback.print_exc()
        
        return comments
    
    def _OLD_REPLY_EXTRACTION_CODE_DISABLED(self):
        """
        OLD CODE - Reply extraction disabled (requires login)
        Kept for reference only
        """
        if False:  # Disabled
                # Extract replies from each page
                for page_num in range(1, 999):
                    try:
                        # Get all comment sections on current page
                        sections = self.page.locator(".m-comment").all()
                        page_replies_count = 0
                        if page_num == 1:
                            safe_print(f"      🔍 Page {page_num}: Found {len(sections)} comment sections")
                        
                        for sec in sections:
                            try:
                                data_ejs = sec.get_attribute('data-ejs')
                                if not data_ejs:
                                    continue
                                
                                parsed = json.loads(data_ejs)
                                raw_id = str(parsed.get('reviewId') or parsed.get('id'))
                                
                                # Find matching comment in our collected list
                                if raw_id not in comment_map:
                                    continue
                                
                                comment = comment_map[raw_id]
                                
                                # Skip if already has replies
                                if comment.get('replies') and len(comment['replies']) > 0:
                                    continue
                                
                                # Look for reply button (use robust selector: a.m-comment-reply-btn)
                                # Note: Webnovel has typo in class name (j_reivew_open, not j_review_open)
                                reply_btn = sec.locator("a.m-comment-reply-btn").first
                                reply_btn_count = reply_btn.count()
                                if page_num == 1 and comment_map.get(raw_id):
                                    safe_print(f"         Comment {raw_id}: reply_btn.count()={reply_btn_count}")
                                if reply_btn_count > 0:
                                    try:
                                        # Check if button is visible (not hidden with .dn class)
                                        btn_classes = reply_btn.get_attribute('class') or ''
                                        if ' dn' in btn_classes or btn_classes.endswith('dn'):
                                            if page_num == 1:
                                                safe_print(f"            → Skipped (hidden): {raw_id}")
                                            continue
                                        
                                        btn_text = reply_btn.inner_text()
                                        if page_num == 1:
                                            safe_print(f"            → Button text: '{btn_text}'")
                                        
                                        reply_match = re.search(r'(\d+)\s*Repl', btn_text, re.I)
                                        if reply_match:
                                            reply_count = int(reply_match.group(1))
                                            if page_num == 1:
                                                safe_print(f"            → Clicking to load {reply_count} replies...")
                                            
                                            # Scroll and click reply button
                                            reply_btn.scroll_into_view_if_needed(timeout=3000)
                                            self._random_sleep(0.3, 0.6)
                                            reply_btn.click(timeout=5000)
                                            self._random_sleep(1.0, 1.5)
                                            
                                            # Wait for replies to load - try multiple selectors
                                            try:
                                                sec.locator(".j_more_replies_body section, .m-comment-reply-item, .m-reply").first.wait_for(timeout=5000)
                                            except:
                                                self._random_sleep(0.5, 1.0)
                                            
                                            # Check if modal opened instead of inline expansion
                                            modal = self.page.locator("#replyDetailModal, .g_mod_wrap._on").first
                                            if modal.count() > 0 and modal.is_visible():
                                                # Modal opened - extract from modal
                                                if page_num == 1:
                                                    safe_print(f"            → Modal opened, waiting for AJAX content...")
                                                
                                                # CRITICAL: Wait for loading spinner to disappear (AJAX loads replies)
                                                loading_spinner = modal.locator(".g_loading._on, .loading._on, span.g_loading")
                                                if loading_spinner.count() > 0:
                                                    try:
                                                        # Wait for spinner to be hidden (max 10 seconds)
                                                        loading_spinner.wait_for(state="hidden", timeout=10000)
                                                        if page_num == 1:
                                                            safe_print(f"            → Content loaded!")
                                                    except:
                                                        if page_num == 1:
                                                            safe_print(f"            → Loading timeout, extracting anyway...")
                                                
                                                self._random_sleep(0.5, 1.0)
                                                replies = self._scrape_replies(modal)
                                                
                                                # Close modal - try multiple methods
                                                modal_closed = False
                                                try:
                                                    # Method 1: Click close button
                                                    close_btn = modal.locator("a.close, button.close, .g_close, a.g_close, [class*='close']").first
                                                    if close_btn.count() > 0:
                                                        close_btn.click(timeout=2000)
                                                        self._random_sleep(0.2, 0.4)
                                                        modal_closed = True
                                                except:
                                                    pass
                                                
                                                if not modal_closed:
                                                    try:
                                                        # Method 2: Press Escape key
                                                        self.page.keyboard.press("Escape")
                                                        self._random_sleep(0.2, 0.4)
                                                    except:
                                                        pass
                                            else:
                                                # Inline expansion
                                                replies = self._scrape_replies(sec)
                                            
                                            comment['replies'] = replies
                                            page_replies_count += len(replies)
                                            total_replies_extracted += len(replies)
                                            
                                            if page_num == 1:
                                                safe_print(f"            → Extracted {len(replies)} replies")
                                        else:
                                            if page_num == 1:
                                                safe_print(f"            → No reply count match in text")
                                    except Exception as click_err:
                                        if page_num == 1:
                                            safe_print(f"            → Error: {str(click_err)[:100]}")
                                        # Try to close any open modal to prevent blocking next clicks
                                        try:
                                            # Try Escape key first
                                            self.page.keyboard.press("Escape")
                                            self._random_sleep(0.3, 0.5)
                                        except:
                                            pass
                                        try:
                                            # Then try close button
                                            modal = self.page.locator("#replyDetailModal, .g_mod_wrap._on").first
                                            if modal.count() > 0 and modal.is_visible():
                                                close_btn = modal.locator("a.close, button.close, .g_close, a.g_close, [class*='close']").first
                                                if close_btn.count() > 0:
                                                    close_btn.click(timeout=1000)
                                                    self._random_sleep(0.2, 0.3)
                                        except:
                                            pass
                            except:
                                continue
                        
                        if page_replies_count > 0:
                            safe_print(f"      📄 Page {page_num}: Extracted {page_replies_count} replies")
                        
                        # Navigate to next page if not last
                        if page_num < detected_pages:
                            try:
                                pagination_cont = self.page.locator("div.ui-page-x").first
                                if pagination_cont.count() > 0:
                                    next_page_link = pagination_cont.locator(f"a.ui-page[data-page='{page_num + 1}']").first
                                    next_page_link.click(timeout=5000)
                                    self.page.wait_for_function(f"() => {{ return document.querySelector('.ui-page-current').textContent.trim() == '{page_num + 1}'; }}", timeout=10000)
                                    self._random_sleep(1, 1.5)
                            except:
                                break
                    except:
                        continue
                
                safe_print(f"   ✅ Extracted {total_replies_extracted} total replies")
    
    def _extract_comments_from_api_response(self, data, internal_book_id, platform_book_id):
        """
        Extract and normalize comments from intercepted API response data
        Handles multiple API response formats from Webnovel
        
        Args:
            data: JSON data from API response
            internal_book_id: Internal book ID
            platform_book_id: Platform book ID
            
        Returns:
            list[dict]: Normalized comment dictionaries
        """
        comments = []
        
        try:
            # Navigate through different possible response structures
            comment_list = []
            
            # Strategy 1: data.data.items or data.data.list or data.data.reviews
            if isinstance(data, dict):
                if 'data' in data and isinstance(data['data'], dict):
                    payload = data['data']
                    # Try common keys
                    for key in ['items', 'list', 'reviews', 'reviewList', 'commentList', 'comments']:
                        if key in payload and isinstance(payload[key], list):
                            comment_list = payload[key]
                            break
                # Strategy 2: Direct list at top level
                elif 'items' in data or 'list' in data or 'reviews' in data:
                    for key in ['items', 'list', 'reviews', 'reviewList', 'commentList']:
                        if key in data and isinstance(data[key], list):
                            comment_list = data[key]
                            break
            elif isinstance(data, list):
                comment_list = data
            
            # Extract each comment
            for item in comment_list:
                try:
                    # Extract user info
                    user_name = 'Anonymous'
                    user_id = None
                    
                    if 'userName' in item:
                        user_name = item['userName']
                    elif 'userInfo' in item and isinstance(item['userInfo'], dict):
                        user_name = item['userInfo'].get('nickName') or item['userInfo'].get('userName') or 'Anonymous'
                        user_id = item['userInfo'].get('userId')
                    elif 'author' in item:
                        if isinstance(item['author'], dict):
                            user_name = item['author'].get('name') or 'Anonymous'
                        else:
                            user_name = item['author']
                    
                    # Extract content
                    content = item.get('content') or item.get('reviewContent') or item.get('body') or item.get('reviewBody') or ''
                    
                    # Extract time
                    time_str = ''
                    if 'createTime' in item:
                        # Unix timestamp in milliseconds
                        try:
                            ts = int(item['createTime'])
                            if ts > 10**12:  # milliseconds
                                ts = ts // 1000
                            from datetime import datetime
                            dt = datetime.fromtimestamp(ts)
                            # Convert to relative time
                            now = datetime.now()
                            diff = now - dt
                            if diff.days > 365:
                                years = diff.days // 365
                                time_str = f"{years} year{'s' if years > 1 else ''}"
                            elif diff.days > 30:
                                months = diff.days // 30
                                time_str = f"{months} month{'s' if months > 1 else ''}"
                            elif diff.days > 0:
                                time_str = f"{diff.days} day{'s' if diff.days > 1 else ''}"
                            elif diff.seconds > 3600:
                                hours = diff.seconds // 3600
                                time_str = f"{hours} hour{'s' if hours > 1 else ''}"
                            else:
                                minutes = diff.seconds // 60
                                time_str = f"{minutes} minute{'s' if minutes > 1 else ''}"
                        except:
                            time_str = item.get('createTime', '')
                    else:
                        time_str = item.get('time') or item.get('date') or item.get('datePublished') or ''
                    
                    # Extract score
                    score = None
                    if 'score' in item:
                        try:
                            score = float(item['score'])
                        except:
                            pass
                    elif 'reviewRating' in item and isinstance(item['reviewRating'], dict):
                        try:
                            score = float(item['reviewRating'].get('ratingValue'))
                        except:
                            pass
                    
                    # Extract raw ID for later use (replies loading)
                    raw_id = item.get('reviewId') or item.get('id') or item.get('commentId')
                    
                    # Extract replies if present in API response
                    replies = []
                    if 'replyList' in item and isinstance(item['replyList'], list):
                        for reply_item in item['replyList']:
                            try:
                                reply_user = 'Anonymous'
                                if 'userName' in reply_item:
                                    reply_user = reply_item['userName']
                                elif 'userInfo' in reply_item and isinstance(reply_item['userInfo'], dict):
                                    reply_user = reply_item['userInfo'].get('nickName') or reply_item['userInfo'].get('userName') or 'Anonymous'
                                
                                reply_content = reply_item.get('content') or reply_item.get('replyContent') or ''
                                reply_time = reply_item.get('time') or reply_item.get('createTime') or ''
                                
                                replies.append({
                                    'reply_id': str(uuid6.uuid7()),
                                    'user_name': reply_user,
                                    'time': reply_time,
                                    'content': reply_content
                                })
                            except:
                                continue
                    
                    # Build normalized comment
                    comment = {
                        'comment_id': str(uuid6.uuid7()),
                        'story_id': internal_book_id,
                        'user_id': user_id or self._make_platform_obf(user_name) if user_name else None,
                        'user_name': user_name,
                        'time': time_str,
                        'content': content,
                        'score': {'overall': score},
                        'replies': replies,
                        '_raw_id': raw_id  # Store for HTML fallback if needed
                    }
                    
                    comments.append(comment)
                    
                except Exception as item_err:
                    safe_print(f"      ⚠️ Failed to parse comment item: {item_err}")
                    continue
                    
        except Exception as e:
            safe_print(f"   ⚠️ Error extracting comments from API data: {e}")
        
        return comments

    def _fetch_book_comments_via_api(self, book_id_numeric, page_num):
        """
        Try multiple known API endpoint patterns to fetch book comments for a given page.
        Returns a list of normalized comment dicts or empty list.
        """
        results = []
        try:
            # Build candidate endpoints. These are best-effort guesses based on common patterns.
            candidates = [
                f"https://www.webnovel.com/apiajax/comment/getCommentList?bookId={book_id_numeric}&page={page_num}",
                f"https://www.webnovel.com/apiajax/comment/getCommentList?workId={book_id_numeric}&page={page_num}",
                f"https://www.webnovel.com/apiajax/comment/getBookComments?bookId={book_id_numeric}&page={page_num}",
                f"https://www.webnovel.com/go/comment/getCommentList?bookId={book_id_numeric}&page={page_num}",
                f"https://www.webnovel.com/go/pcm/comment/getCommentList?bookId={book_id_numeric}&page={page_num}",
            ]

            # Extract cookies from current Playwright context
            cookies = {}
            try:
                for c in self.page.context.cookies():
                    cookies[c.get('name')] = c.get('value')
            except:
                cookies = {}

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Referer': self.page.url,
                'Origin': 'https://www.webnovel.com',
            }

            with httpx.Client(timeout=15, follow_redirects=True, cookies=cookies) as client:
                for url in candidates:
                    try:
                        resp = client.get(url, headers=headers)
                        if resp.status_code != 200:
                            continue
                        text = resp.text
                        if not text:
                            continue
                        try:
                            data = resp.json()
                        except Exception:
                            # Sometimes API returns HTML fragment - skip
                            continue

                        # Normalize different response shapes
                        comments_raw = []
                        if isinstance(data, dict):
                            # common envelope: { data: { commentList: [...] } }
                            if data.get('data') and isinstance(data.get('data'), dict):
                                d = data.get('data')
                                # check several known keys
                                if d.get('commentList') and isinstance(d.get('commentList'), list):
                                    comments_raw = d.get('commentList')
                                elif d.get('comments') and isinstance(d.get('comments'), list):
                                    comments_raw = d.get('comments')
                                elif d.get('list') and isinstance(d.get('list'), list):
                                    comments_raw = d.get('list')
                                else:
                                    # try top-level list
                                    for v in d.values():
                                        if isinstance(v, list) and v and isinstance(v[0], dict) and ('content' in v[0] or 'body' in v[0] or 'reviewBody' in v[0]):
                                            comments_raw = v
                                            break
                            elif data.get('comments') and isinstance(data.get('comments'), list):
                                comments_raw = data.get('comments')
                            elif isinstance(data.get('data'), list):
                                comments_raw = data.get('data')
                        elif isinstance(data, list):
                            comments_raw = data

                        # Convert comment entries into normalized format used by parser
                        for entry in comments_raw:
                            try:
                                # entry may contain author, content, date, reviewId
                                user_name = None
                                if isinstance(entry.get('author'), dict):
                                    user_name = entry.get('author', {}).get('name')
                                else:
                                    user_name = entry.get('author') or entry.get('userName') or entry.get('nickname')

                                body = entry.get('content') or entry.get('body') or entry.get('reviewBody') or entry.get('description') or ''
                                date = entry.get('date') or entry.get('createTime') or entry.get('time') or entry.get('datePublished') or ''
                                rid = entry.get('reviewId') or entry.get('id') or entry.get('commentId') or entry.get('cid')

                                comment = {
                                    'comment_id': str(uuid6.uuid7()),
                                    'story_id': f"bk_{book_id_numeric}",
                                    'user_id': None,
                                    'user_name': user_name or 'Anonymous',
                                    'time': date,
                                    'content': body,
                                    'score': {'overall': None},
                                    'replies': []
                                }
                                results.append(comment)
                            except Exception:
                                continue

                        if results:
                            return results
                    except Exception:
                        continue
        except Exception:
            pass
        return []
    
    def _parse_book_comments(self, internal_book_id, platform_book_id, return_ids=False):
        """Parse book comments from loaded page. If return_ids=True also returns platform review ids list for deduplication."""
        comments = []
        review_ids = []

        try:
            # Prefer explicit comment sections
            sections = self.page.locator("section.m-comment, .m-comment, div.m-comment").all()
            if not sections:
                # fallback: look for generic comment containers
                sections = self.page.locator(".comment-item, li.comment, div.comment").all()

            for sec in sections:
                try:
                    # get platform review id from data-ejs attribute if present
                    data_ejs = None
                    try:
                        data_ejs = sec.get_attribute('data-ejs') or sec.get_attribute('data-ejs')
                    except:
                        data_ejs = None
                    platform_rev_id = None
                    if data_ejs:
                        try:
                            parsed = json.loads(data_ejs)
                            # may contain 'reviewId' or 'reviewid'
                            platform_rev_id = parsed.get('reviewId') or parsed.get('reviewid') or parsed.get('id') or None
                            # may also include lastTime
                            last_time = parsed.get('lastTime') or parsed.get('time') or None
                        except:
                            platform_rev_id = None
                            last_time = None
                    else:
                        last_time = None

                    comment = self._parse_single_book_comment(sec, internal_book_id, platform_book_id)
                    if comment:
                        # Add raw platform review ID for reply extraction
                        comment['_raw_id'] = str(platform_rev_id) if platform_rev_id else None
                        comments.append(comment)
                        review_ids.append(str(platform_rev_id) if platform_rev_id else None)
                except:
                    continue

        except Exception as e:
            safe_print(f"⚠️  Parse error: {e}")

        if return_ids:
            return comments, review_ids
        return comments
    
    def _parse_comment_replies(self, comment_section, internal_book_id):
        """
        Parse replies for a book comment after clicking "View X Replies"
        
        Args:
            comment_section: Playwright element containing the comment with loaded replies
            internal_book_id: Internal book ID
            
        Returns:
            list[dict]: List of reply objects
        """
        replies = []
        
        try:
            # Find all reply items within this comment section or modal
            # Pattern: <div class="m-reply-item">, <section class="m-comment">, <li class="reply-item">
            # In modals, replies are often in .m-comment or .j_reply_list
            reply_items = comment_section.locator(
                ".m-reply-item, .reply-item, div[class*='reply'], "
                ".j_reply_list .m-comment, .m-comment-reply-item, "
                "section.m-comment:not(:first-child)"
            ).all()
            
            for reply_el in reply_items:
                try:
                    # Extract reply text
                    reply_text = reply_el.inner_text().strip()
                    if not reply_text or len(reply_text) < 3:
                        continue
                    
                    # Extract username - try title attribute first
                    user_name = "Anonymous"
                    try:
                        user_link = reply_el.locator("a[href*='/profile'][rel='nofollow']").first
                        if user_link.count() > 0:
                            user_name = user_link.get_attribute('title') or user_link.inner_text().strip() or user_name
                    except:
                        pass
                    
                    # Extract time - expand format
                    time_str = ""
                    try:
                        time_patterns = [
                            (r'(\d+)\s*y(?:r|ear)?s?', lambda n: f"{n} year{'s' if int(n) > 1 else ''}"),
                            (r'(\d+)\s*m(?:on|nth|onth)?s?', lambda n: f"{n} month{'s' if int(n) > 1 else ''}"),
                            (r'(\d+)\s*w(?:eek)?s?', lambda n: f"{n} week{'s' if int(n) > 1 else ''}"),
                            (r'(\d+)\s*d(?:ay)?s?', lambda n: f"{n} day{'s' if int(n) > 1 else ''}"),
                            (r'(\d+)\s*h(?:r|our)?s?', lambda n: f"{n} hour{'s' if int(n) > 1 else ''}"),
                            (r'(\d+)\s*m(?:in)?s?', lambda n: f"{n} minute{'s' if int(n) > 1 else ''}"),
                            (r'(\d+)\s*s(?:ec)?s?', lambda n: f"{n} second{'s' if int(n) > 1 else ''}"),
                        ]
                        for pattern, formatter in time_patterns:
                            match = re.search(pattern, reply_text, re.I)
                            if match:
                                time_str = formatter(match.group(1))
                                break
                    except:
                        pass
                    
                    # Clean content (remove metadata)
                    lines = reply_text.split('\n')
                    content_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line or len(line) < 3:
                            continue
                        if line == user_name:
                            continue
                        if re.match(r'^\d+(s|m|h|d|w|mth|yr)$', line):
                            continue
                        content_lines.append(line)
                    
                    content = '\n'.join(content_lines)
                    
                    if content:
                        reply = {
                            "comment_id": str(uuid6.uuid7()),  # UUID v7 for reply
                            "source_id": str(uuid6.uuid7()),  # Separate UUID for source_id
                            "story_id": internal_book_id,
                            "user_id": None,
                            "user_name": user_name,
                            "time": time_str,
                            "content": content,
                            "score": {"overall": None},
                            "replies": []
                        }
                        replies.append(reply)
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            safe_print(f"      ⚠️  Error parsing replies: {e}")
        
        return replies

    def _scrape_replies(self, comment_element):
        """Click reply trigger and extract replies for a comment element.
        
        This method handles BOTH Book Reviews and Chapter Comments.
        It uses broad selectors to handle Webnovel's varying DOM structures.

        Returns:
            list[dict]: [{reply_id, user_name, content, time, _raw_id}]
        """
        out = []
        try:
            # Check for reply count / trigger - broader selectors
            trigger_selectors = [
                ".j_reply_trigger",
                ".reply-cnt",
                "a.m-comment-reply-btn",
                "button:has-text('View')",
                "a:has-text('Reply')",
                "a:has-text('Replies')",
                ".j_reply_btn"
            ]

            reply_btn = None
            for sel in trigger_selectors:
                try:
                    btn = comment_element.locator(sel).first
                    if btn.count() > 0:
                        reply_btn = btn
                        break
                except:
                    continue

            # If no button found, return []
            if not reply_btn:
                return []

            # Try to read reply count quickly
            try:
                btn_text = reply_btn.inner_text().strip()
                m = re.search(r"(\d+)", btn_text)
                if m and int(m.group(1)) == 0:
                    return []
            except:
                pass

            # Click to reveal replies (inline or modal)
            try:
                reply_btn.scroll_into_view_if_needed(timeout=3000)
                self._random_sleep(0.2, 0.5)
                reply_btn.click(timeout=5000)
                self._random_sleep(1.5, 2.5)  # Longer wait for animation/load
            except Exception as click_err:
                safe_print(f"   ⚠️  Reply button click failed: {click_err}")
                return []

            # CRITICAL: Find reply container - check BOTH inline and modal locations
            container_selectors = [
                '.j_reply_list',
                '.j_more_replies_body',
                '.sub-comm-item',
                '.m-reply-list',
                '.reply-list',
                'div[class*="reply-list"]',
                '.j_reply_body'
            ]
            
            containers = []
            # Strategy 1: First try inside the comment element (inline replies)
            for sel in container_selectors:
                try:
                    loc = comment_element.locator(sel).first
                    if loc.count() > 0:
                        # Don't wait for visible - just check if it exists
                        containers.append(loc)
                        safe_print(f"   ✓ Found inline reply container: {sel}")
                        break
                except:
                    continue
            
            # Strategy 2: If none found inside, check for modal (global page context)
            if not containers:
                try:
                    # Wait briefly for modal to appear
                    self._random_sleep(0.5, 1)
                    modal_selectors = ['#replyDetailModal', '.g_mod_wrap._on', '.reply-modal', '.g_mod_reply']
                    for modal_sel in modal_selectors:
                        try:
                            modal = self.page.locator(modal_sel).first
                            if modal.count() > 0 and modal.is_visible():
                                safe_print(f"   ✓ Found reply modal: {modal_sel}")
                                for sel in container_selectors:
                                    try:
                                        loc = modal.locator(sel).first
                                        if loc.count() > 0:
                                            containers.append(loc)
                                            safe_print(f"   ✓ Found modal reply container: {sel}")
                                            break
                                    except:
                                        continue
                                if containers:
                                    break
                        except:
                            continue
                except:
                    pass

            if not containers:
                safe_print(f"   ⚠️  No reply container found after click")
                return []

            # Collect reply items with BROAD selectors
            reply_item_selectors = [
                '.m-reply-item',
                '.reply-item',
                '.sub-comm-item',
                '.m-comment-reply-item',
                '.j_reply_item',
                'div[class*="reply-item"]',
                'section.m-comment'
            ]
            
            reply_items = []
            for container in containers:
                for sel in reply_item_selectors:
                    try:
                        items = container.locator(sel).all()
                        if items:
                            reply_items.extend(items)
                            break  # Stop after first successful selector
                    except:
                        continue

            # Debug print
            safe_print(f"   -> Found {len(reply_items)} reply items after clicking")

            # Parse each reply item with BROAD selectors
            for item in reply_items:
                try:
                    # raw id candidates - broader search
                    raw_id = (item.get_attribute('data-id') or 
                             item.get_attribute('data-ejs') or 
                             item.get_attribute('data-reply-id') or 
                             item.get_attribute('id') or None)

                    # user name - multiple strategies
                    user_name = 'Anonymous'
                    user_selectors = [
                        ".j_user_name",
                        "a[href*='/profile']",
                        ".user-name",
                        ".name",
                        ".author",
                        ".reply-author"
                    ]
                    for u_sel in user_selectors:
                        try:
                            u = item.locator(u_sel).first
                            if u.count() > 0:
                                user_name = u.get_attribute('title') or u.inner_text().strip() or user_name
                                if user_name != 'Anonymous':
                                    break
                        except:
                            continue

                    # content - multiple strategies
                    content = ''
                    content_selectors = [
                        '.j_content',
                        '.comm-txt',
                        '.reply-content',
                        '.m-reply-cont',
                        '.m-reply-body',
                        '.content',
                        'p'
                    ]
                    for c_sel in content_selectors:
                        try:
                            c_el = item.locator(c_sel).first
                            if c_el.count() > 0:
                                content = c_el.inner_text().strip()
                                if content:
                                    break
                        except:
                            continue
                    
                    # Fallback to full item text if no content found
                    if not content:
                        try:
                            content = item.inner_text().strip()
                        except:
                            content = ''

                    # time
                    time_text = ''
                    time_selectors = ['time', '.time', 'small', '.j_time', '.reply-time', '.date']
                    for t_sel in time_selectors:
                        try:
                            t = item.locator(t_sel).first
                            if t.count() > 0:
                                time_text = t.inner_text().strip()
                                if time_text:
                                    break
                        except:
                            continue
                    
                    # Fallback: regex search for time pattern
                    if not time_text:
                        try:
                            m = re.search(r"(\d+\s*(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s*ago)", item.inner_text(), re.I)
                            if m:
                                time_text = m.group(1)
                        except:
                            pass

                    if not content:
                        continue

                    reply_obj = {
                        'reply_id': str(uuid6.uuid7()),
                        'user_name': user_name,
                        'content': content,
                        'time': time_text,
                        '_raw_id': str(raw_id) if raw_id else None
                    }
                    out.append(reply_obj)
                except Exception as parse_err:
                    safe_print(f"   ⚠️  Failed to parse reply item: {parse_err}")
                    continue

        except Exception as e:
            safe_print(f"   ⚠️  _scrape_replies error: {e}")

        return out
    
    def _parse_single_book_comment(self, element, internal_book_id, platform_book_id):
        """
        Parse single book comment
        
        Returns:
            CommentOnBook: {comment_id, story_id, user_id, user_name, time, content, score, replies}
        """
        try:
            # CRITICAL FIX: Click all "Reveal Spoiler" buttons BEFORE extracting text
            try:
                spoiler_buttons = element.locator("button:has-text('Reveal Spoiler'), a:has-text('Reveal Spoiler'), span:has-text('Reveal Spoiler')").all()
                for btn in spoiler_buttons:
                    try:
                        if btn.is_visible():
                            btn.click(timeout=2000)
                            time.sleep(0.3)  # Wait for content to reveal
                    except:
                        continue
            except:
                pass
            
            full_text = element.inner_text().strip()
            if not full_text or len(full_text) < 5:
                return None
            
            # Extract username and profile link - try multiple selectors
            user_name = "Anonymous"
            user_profile = None
            
            # Method 1: Try data-ejs JSON (most reliable)
            try:
                data_ejs = element.get_attribute('data-ejs')
                if data_ejs:
                    ejs_data = json.loads(data_ejs)
                    user_name = ejs_data.get('userName') or user_name
            except:
                pass
            
            # Method 2: Try DOM selector for username link
            if user_name == "Anonymous":
                try:
                    # Selector based on HTML structure: .m-comment-hd a[href*='/profile'][rel='nofollow']
                    user_link = element.locator(".m-comment-hd a[href*='/profile'][rel='nofollow']").first
                    if user_link.count() > 0:
                        # Get username from title attribute first (most reliable)
                        user_name = user_link.get_attribute('title') or user_link.inner_text().strip() or user_name
                        try:
                            user_profile = user_link.get_attribute('href')
                        except:
                            pass
                except:
                    pass
            
            # Extract ONLY comment content (filter out ALL metadata/navigation)
            lines = full_text.split('\n')
            content_lines = []
            skip_keywords = [
                'webnovel.com', 'browse', 'rankings', 'create', 'contest', 'library', 'sign in',
                'original', 'chapters', 'views', 'author:', 'add to library', 'report story',
                'about', 'table of contents', 'synopsis', 'general audiences', 'tags',
                'fans', 'see all', 'contributed', 'weekly power', 'ranking', 'power stone', 'vote',
                'you may also like', 'reviews', 'writing quality', 'stability', 'story development',
                'character design', 'world background', 'share your thoughts', 'write a review',
                'liked', 'newest', 'view', 'replies', 'prev', 'next', 'cloudary holdings',
                'teams', 'contacts', 'resources', 'download', 'help center', 'privacy policy',
                'terms of service', 'affiliate', 'via email', 'app store', 'google play',
                'gif:', 'http', '©', '#', 'anime & comics', 'rating'
            ]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Skip metadata patterns
                if re.match(r'^LV\s+\d+', line):
                    continue
                if line == user_name:
                    continue
                if re.match(r'^\d+(s|m|h|d|w|mth|yr)$', line):
                    continue
                # Skip lines containing keywords (case-insensitive)
                if any(keyword in line.lower() for keyword in skip_keywords):
                    continue
                # Skip very short lines (likely UI elements)
                if len(line) < 3:
                    continue
                # Skip numbers only
                if line.replace('.', '').replace(',', '').isdigit():
                    continue
                
                content_lines.append(line)
            
            content = '\n'.join(content_lines)
            
            # If content is still too long (>500 chars), it's likely wrong - skip
            if len(content) > 500:
                return None
            
            # Extract GIF URLs
            try:
                gif_imgs = element.locator("img[src*='.gif']").all()
                for gif_img in gif_imgs:
                    gif_url = gif_img.get_attribute("src")
                    if gif_url and not gif_url.startswith("http"):
                        gif_url = "https:" + gif_url
                    content += f"\n[GIF: {gif_url}]"
            except:
                pass
            
            # Extract time - expand to full format
            time_str = ""
            try:
                # Find time patterns from data-ejs or text
                # Try data-ejs lastTime first
                try:
                    data_ejs = element.get_attribute('data-ejs')
                    if data_ejs:
                        ejs_data = json.loads(data_ejs)
                        last_time = ejs_data.get('lastTime')
                        if last_time:
                            # Convert milliseconds timestamp to readable format
                            from datetime import datetime, timezone
                            dt = datetime.fromtimestamp(last_time / 1000, tz=timezone.utc)
                            now = datetime.now(timezone.utc)
                            diff = now - dt
                            
                            if diff.days >= 365:
                                years = diff.days // 365
                                time_str = f"{years} year{'s' if years > 1 else ''}"
                            elif diff.days >= 30:
                                months = diff.days // 30
                                time_str = f"{months} month{'s' if months > 1 else ''}"
                            elif diff.days > 0:
                                time_str = f"{diff.days} day{'s' if diff.days > 1 else ''}"
                            elif diff.seconds >= 3600:
                                hours = diff.seconds // 3600
                                time_str = f"{hours} hour{'s' if hours > 1 else ''}"
                            elif diff.seconds >= 60:
                                minutes = diff.seconds // 60
                                time_str = f"{minutes} minute{'s' if minutes > 1 else ''}"
                            else:
                                time_str = f"{diff.seconds} second{'s' if diff.seconds != 1 else ''}"
                except:
                    pass
                
                # Fallback: parse from text and expand
                if not time_str:
                    time_patterns = [
                        (r'(\d+)\s*y(?:r|ear)?s?', lambda n: f"{n} year{'s' if int(n) > 1 else ''}"),
                        (r'(\d+)\s*m(?:on|nth|onth)?s?', lambda n: f"{n} month{'s' if int(n) > 1 else ''}"),
                        (r'(\d+)\s*w(?:eek)?s?', lambda n: f"{n} week{'s' if int(n) > 1 else ''}"),
                        (r'(\d+)\s*d(?:ay)?s?', lambda n: f"{n} day{'s' if int(n) > 1 else ''}"),
                        (r'(\d+)\s*h(?:r|our)?s?', lambda n: f"{n} hour{'s' if int(n) > 1 else ''}"),
                        (r'(\d+)\s*m(?:in)?s?', lambda n: f"{n} minute{'s' if int(n) > 1 else ''}"),
                        (r'(\d+)\s*s(?:ec)?s?', lambda n: f"{n} second{'s' if int(n) > 1 else ''}"),
                    ]
                    for pattern, formatter in time_patterns:
                        match = re.search(pattern, full_text, re.I)
                        if match:
                            time_str = formatter(match.group(1))
                            break
            except:
                pass
            
            # Generate UUID v7 for comment_id (primary)
            comment_id = str(uuid6.uuid7())
            user_id = None
            if user_profile:
                user_id = self._make_platform_obf(user_profile)
            
            # Extract score from stars (svg.g_star._on from F12)
            score = {"overall": None}
            try:
                # Count filled stars: <svg class="g_star _on">
                stars_on = element.locator("svg.g_star._on, span.g_star svg._on").count()
                if stars_on > 0:
                    score["overall"] = float(stars_on)
            except:
                pass
            
            return {
                "comment_id": comment_id,  # UUID v7
                "source_id": comment_id,  # Store same as comment_id for now
                "story_id": internal_book_id,
                "user_id": user_id,
                "user_name": user_name,
                "time": time_str,
                "content": content,
                "score": score,
                "replies": []
            }
            
        except Exception as e:
            safe_print(f"⚠️  Error parsing comment: {e}")
            return None
    
    # ==================== CHAPTER SCRAPERS ====================
    
    def _parse_toc_chapters(self, book_id_numeric):
        """Parse chapters from Table of Contents with full metadata
        
        Returns:
            list[dict]: [{"url": str, "order": int, "name": str, "published_time": str}]
        """
        chapters = []
        
        try:
            # Find all chapter links in TOC area
            # Strategy 1: Find all links in TOC that match book ID pattern
            safe_print(f"   🔍 Searching for chapter links in TOC...")
            
            # Try to find TOC container first
            toc_containers = [
                "#j_catalog_content",
                ".catalog-content",
                ".j_catalog_content",
                "[class*='catalog']",
                ".volume-content"
            ]
            
            container = None
            for container_sel in toc_containers:
                try:
                    count = self.page.locator(container_sel).count()
                    if count > 0:
                        container = self.page.locator(container_sel).first
                        safe_print(f"   ✅ Found TOC container: {container_sel}")
                        break
                except:
                    continue
            
            # If no container found, search whole page
            if not container:
                safe_print(f"   ⚠️  No specific TOC container found, searching whole page")
                container = self.page.locator("body").first
            
            # Find all chapter list items in TOC
            # Pattern from screenshot: <li class="g_col__6"> contains <a>, <strong>, <small>
            chapter_items = container.locator("li.g_col__6, li[class*='g_col']").all()
            
            if not chapter_items:
                # Fallback: find by link pattern
                safe_print(f"   ⚠️  No li.g_col__6 found, falling back to link search")
                chapter_links = container.locator(f"a[href*='/book/{book_id_numeric}/']").all()
            else:
                safe_print(f"   📊 Found {len(chapter_items)} chapter list items")
                chapter_links = []
                for item in chapter_items:
                    try:
                        link = item.locator("a").first
                        if link.count() > 0:
                            chapter_links.append((item, link))
                    except:
                        continue
            
            order = 0
            for entry in chapter_links:
                try:
                    # Handle both (item, link) tuple and bare link
                    if isinstance(entry, tuple):
                        parent, link = entry
                    else:
                        link = entry
                        parent = link.locator('xpath=..').first
                    
                    href = link.get_attribute('href')
                    if not href or '/catalog' in href:
                        continue
                    
                    if not href.startswith('http'):
                        href = 'https://www.webnovel.com' + href
                    
                    # Extract chapter name from <strong> tag
                    # Pattern: <strong class="db mb8 fs16 lh24 c_l ell">Chapter name</strong>
                    name = ""
                    try:
                        # Search in parent li element first (more accurate)
                        strong_elem = parent.locator("strong.ell, strong.db, strong[class*='c_l'], strong").first
                        if strong_elem.count() > 0:
                            name = strong_elem.inner_text().strip()
                        
                        # Fallback: get link text
                        if not name:
                            name = link.inner_text().strip()
                            name = ' '.join(name.split())  # Clean whitespace
                    except:
                        name = link.inner_text().strip()
                    
                    # Extract published time from <small> tag
                    # Pattern: <small class="db fs12 lh16 c_s">18 days ago</small>
                    published_time = ""
                    try:
                        # Search in parent li element
                        small_elem = parent.locator("small.db, small.fs12, small.lh16, small[class*='c_s'], small").first
                        if small_elem.count() > 0:
                            published_time = small_elem.inner_text().strip()
                    except:
                        pass
                    
                    # Only add if we have at least a name
                    if name:
                        order += 1
                        chapters.append({
                            "url": href,
                            "order": order,
                            "name": name,
                            "published_time": published_time
                        })
                        
                        # Debug: print first few chapters to verify
                        if order <= 3:
                            safe_print(f"      Ch{order}: {name[:50]}... | {published_time}")
                    
                except Exception as e:
                    continue
            
            safe_print(f"   ✅ Successfully parsed {len(chapters)} chapters with metadata")
            return chapters
            
        except Exception as e:
            safe_print(f"   ⚠️  Error parsing TOC chapters: {e}")
            import traceback
            safe_print(traceback.format_exc())
            return []
    
    def _get_chapter_urls(self, book_url, book_id):
        """Get list of all chapter URLs with metadata (order, name, published_time)"""
        safe_print("\n📖 Finding chapter URLs with metadata...")
        chapter_urls = []
        
        try:
            # Extract numeric ID
            book_id_numeric = book_id.replace('wn_', '') if book_id.startswith('wn_') else book_id
            
            # Strategy 1: Use authenticated API with browser cookies
            safe_print("🔍 Strategy 1: Fetching chapters via authenticated API...")
            
            api_chapters = []
            try:
                # Get cookies from current browser session
                cookies = self.page.context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                
                # Prepare headers with all browser info
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': book_url,
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Origin': 'https://www.webnovel.com',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                }
                
                # Try multiple API endpoints
                api_endpoints = [
                    f"https://www.webnovel.com/go/pcm/chapterList/getChapterList?bookId={book_id_numeric}&_csrfToken=",
                    f"https://www.webnovel.com/apiajax/chapter/GetChapterList?_csrfToken=&bookId={book_id_numeric}",
                    f"https://www.webnovel.com/book/{book_id_numeric}/_catalog",
                ]
                
                with httpx.Client(timeout=30, follow_redirects=True, cookies=cookie_dict) as client:
                    for api_url in api_endpoints:
                        try:
                            safe_print(f"   🌐 Trying: {api_url.split('?')[0]}")
                            response = client.get(api_url, headers=headers)
                            
                            if response.status_code == 200:
                                try:
                                    data = response.json()
                                    safe_print(f"   📊 API response keys: {list(data.keys())[:5]}")
                                    
                                    # Try different data structures
                                    if 'data' in data:
                                        data_obj = data['data']
                                        
                                        # Structure 1: volumeItems with nested chapterItems
                                        if 'volumeItems' in data_obj:
                                            for volume in data_obj['volumeItems']:
                                                for chapter in volume.get('chapterItems', []):
                                                    chapter_id = chapter.get('chapterId', '') or chapter.get('id', '')
                                                    if chapter_id:
                                                        chapter_url = f"https://www.webnovel.com/book/{book_id_numeric}/{chapter_id}"
                                                        if chapter_url not in api_chapters:
                                                            api_chapters.append(chapter_url)
                                        
                                        # Structure 2: direct chapterItems
                                        elif 'chapterItems' in data_obj:
                                            for chapter in data_obj['chapterItems']:
                                                chapter_id = chapter.get('chapterId', '') or chapter.get('id', '')
                                                if chapter_id:
                                                    chapter_url = f"https://www.webnovel.com/book/{book_id_numeric}/{chapter_id}"
                                                    if chapter_url not in api_chapters:
                                                        api_chapters.append(chapter_url)
                                        
                                        # Structure 3: chapterList array
                                        elif 'chapterList' in data_obj:
                                            for chapter in data_obj['chapterList']:
                                                chapter_id = chapter.get('chapterId', '') or chapter.get('id', '')
                                                if chapter_id:
                                                    chapter_url = f"https://www.webnovel.com/book/{book_id_numeric}/{chapter_id}"
                                                    if chapter_url not in api_chapters:
                                                        api_chapters.append(chapter_url)
                                    
                                    if api_chapters:
                                        safe_print(f"   ✅ API returned {len(api_chapters)} chapters")
                                        break
                                        
                                except ValueError:
                                    safe_print(f"   ⚠️  Response is not JSON")
                                    # Save response for debugging
                                    with open("data/debug_api_response.txt", "w", encoding="utf-8") as f:
                                        f.write(response.text[:5000])
                                    safe_print(f"   📄 Response saved to debug_api_response.txt")
                        except Exception as endpoint_err:
                            safe_print(f"   ⚠️  Endpoint failed: {endpoint_err}")
                            continue
                            
            except Exception as api_err:
                safe_print(f"   ⚠️  API approach failed: {api_err}")
            
            if api_chapters:
                chapter_urls = api_chapters
                safe_print(f"✅ Found {len(chapter_urls)} chapter URLs via API\n")
                return chapter_urls

            # Strategy 0 (unauthenticated): Try fetching the catalog HTML directly using slug + id
            safe_print("🔍 Strategy 0: Trying unauthenticated catalog HTML fetch...")
            try:
                slug = self._extract_book_slug(book_url) or ''
                possible_catalog_urls = []
                if slug:
                    possible_catalog_urls.append(f"https://www.webnovel.com/book/{slug}_{book_id_numeric}/catalog")
                    possible_catalog_urls.append(f"https://www.webnovel.com/book/{slug}_{book_id_numeric}/_catalog")
                possible_catalog_urls.append(f"https://www.webnovel.com/book/{book_id_numeric}/catalog")
                possible_catalog_urls.append(f"https://www.webnovel.com/book/{book_id_numeric}/_catalog")

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': book_url,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
                for c_url in possible_catalog_urls:
                    try:
                        safe_print(f"   🌐 Trying catalog URL: {c_url}")
                        # Add extra headers (Referer/Origin/Accept-Language) to mimic browser requests
                        headers.update({
                            'Referer': book_url,
                            'Origin': 'https://www.webnovel.com',
                            'Accept-Language': 'en-US,en;q=0.9'
                        })
                        r = httpx.get(c_url, headers=headers, timeout=15)
                        safe_print(f"   ↳ Status: {r.status_code}, bytes: {len(r.text)}")
                        # Save HTTP debug when 403 or Cloudflare block
                        os.makedirs(config.DEBUG_OUTPUT_DIR, exist_ok=True)
                        http_dbg = os.path.join(config.DEBUG_OUTPUT_DIR, 'catalog_http.html')
                        hdr_dbg = os.path.join(config.DEBUG_OUTPUT_DIR, 'catalog_http_headers.txt')
                        try:
                            with open(http_dbg, 'w', encoding='utf-8') as f:
                                f.write(r.text or '')
                            with open(hdr_dbg, 'w', encoding='utf-8') as f:
                                f.write(str(r.status_code) + '\n')
                                for k, v in r.headers.items():
                                    f.write(f"{k}: {v}\n")
                        except Exception:
                            pass

                        blocked = False
                        if r.status_code == 403:
                            blocked = True
                        else:
                            body_l = (r.text or '').lower()
                            if 'please unblock challenges.cloudflare.com' in body_l or 'just a moment' in body_l or 'checking your browser' in body_l or 'cloudflare' in body_l or 'turnstile' in body_l:
                                blocked = True

                        if blocked and config.USE_PLAYWRIGHT_FALLBACK and render_with_playwright is not None:
                            safe_print("   ⚠️  Catalog appears blocked — using Playwright-rendered fallback")
                            pw_html = render_with_playwright(c_url, storage_state_path=config.PLAYWRIGHT_STORAGE_STATE, timeout=config.PLAYWRIGHT_TIMEOUT_MS, screenshot_path=os.path.join(config.DEBUG_OUTPUT_DIR, 'catalog_playwright.png'), har_path=os.path.join(config.DEBUG_OUTPUT_DIR, 'catalog_network.har'), debug_dir=config.DEBUG_OUTPUT_DIR)
                            if pw_html:
                                # Save Playwright HTML
                                try:
                                    with open(os.path.join(config.DEBUG_OUTPUT_DIR, 'catalog_playwright.html'), 'w', encoding='utf-8') as f:
                                        f.write(pw_html)
                                except Exception:
                                    pass
                                # Try to extract chapter links from the rendered HTML using simple regex
                                hrefs = re.findall(r'href\s*=\s*"([^\"]+)"', pw_html)
                                found = []
                                for href in hrefs:
                                    if '/book/' in href and book_id_numeric in href:
                                        if not href.startswith('http'):
                                            href = 'https://www.webnovel.com' + href
                                        if href not in found:
                                            found.append(href)
                                if found:
                                    safe_print(f"   ✅ Playwright-rendered catalog provided {len(found)} chapter links")
                                    return found
                            else:
                                safe_print("   ⚠️  Playwright-rendered fallback returned no HTML")
                        if r.status_code == 200 and r.text and 'Failed to load chapters' not in r.text:
                            # Find chapter hrefs in HTML
                            hrefs = re.findall(r'href\s*=\s*"([^"]+)"', r.text)
                            for href in hrefs:
                                if '/book/' in href and book_id_numeric in href:
                                    if not href.startswith('http'):
                                        href = 'https://www.webnovel.com' + href
                                    if href not in chapter_urls:
                                        chapter_urls.append(href)
                            if chapter_urls:
                                safe_print(f"   ✅ Extracted {len(chapter_urls)} chapters from catalog HTML")
                                return chapter_urls
                    except Exception as e:
                        safe_print(f"   ⚠️  Catalog fetch failed: {e}")
                        continue
            except Exception:
                pass
            
            # Strategy 2: Extract chapter data from JavaScript window object
            safe_print("🔍 Strategy 2: Extracting chapters from page JavaScript data...")
            try:
                # Go back to book page to ensure we're on the right page
                if self.page.url != book_url:
                    self.page.goto(book_url, timeout=config.TIMEOUT, wait_until='domcontentloaded')
                    self._close_popups()
                    self._random_sleep(2, 3)
                
                # Try extracting from common Webnovel JS variables
                js_chapters = self.page.evaluate("""
                    () => {
                        const chapters = [];
                        
                        // Try window.g_data or window._feData
                        if (window.g_data && window.g_data.book) {
                            const book = window.g_data.book;
                            if (book.chapterList) {
                                book.chapterList.forEach(ch => {
                                    if (ch.id || ch.chapterId) {
                                        chapters.push(ch.id || ch.chapterId);
                                    }
                                });
                            }
                            if (book.volumeItems) {
                                book.volumeItems.forEach(vol => {
                                    if (vol.chapterItems) {
                                        vol.chapterItems.forEach(ch => {
                                            if (ch.id || ch.chapterId) {
                                                chapters.push(ch.id || ch.chapterId);
                                            }
                                        });
                                    }
                                });
                            }
                        }
                        
                        // Try __NUXT__ or __NEXT_DATA__
                        if (window.__NUXT__) {
                            const data = window.__NUXT__;
                            // Search for chapter data in the object
                            const findChapters = (obj) => {
                                if (obj && typeof obj === 'object') {
                                    if (obj.chapterId || obj.chapterList) {
                                        if (obj.chapterId) chapters.push(obj.chapterId);
                                        if (obj.chapterList && Array.isArray(obj.chapterList)) {
                                            obj.chapterList.forEach(ch => {
                                                if (ch.id || ch.chapterId) chapters.push(ch.id || ch.chapterId);
                                            });
                                        }
                                    }
                                    for (let key in obj) {
                                        findChapters(obj[key]);
                                    }
                                }
                            };
                            findChapters(data);
                        }
                        
                        return chapters;
                    }
                """)
                
                if js_chapters and len(js_chapters) > 0:
                    # Convert to full URLs
                    for chapter_id in js_chapters:
                        chapter_url = f"https://www.webnovel.com/book/{book_id_numeric}/{chapter_id}"
                        if chapter_url not in chapter_urls:
                            chapter_urls.append(chapter_url)
                    safe_print(f"   ✅ Extracted {len(chapter_urls)} chapters from JavaScript data")
                    
                if chapter_urls:
                    safe_print(f"✅ Found {len(chapter_urls)} chapter URLs via JavaScript\n")
                    return chapter_urls
                else:
                    safe_print(f"   ⚠️  No chapters found in JavaScript data")
                    
            except Exception as js_err:
                safe_print(f"   ⚠️  JavaScript extraction failed: {js_err}")
            
            # Strategy 3: Use Playwright browser's API intercept to get chapter data
            safe_print("🔍 Strategy 3: Intercepting API calls for chapter data...")
            try:
                captured_chapters = []
                
                def handle_route(route, request):
                    """Intercept API responses"""
                    try:
                        response = route.fetch()
                        url = request.url.lower()
                        
                        # Check if this is a chapter list API call
                        if 'chapterlist' in url or 'getchapterlist' in url:
                            try:
                                body = response.text()
                                data = json.loads(body)
                                safe_print(f"   ✅ Intercepted chapter API: {request.url[:80]}...")
                                
                                # Parse chapter data from API response
                                if 'data' in data:
                                    data_obj = data['data']
                                    
                                    # Structure 1: volumeItems with nested chapterItems
                                    if 'volumeItems' in data_obj:
                                        order = 0
                                        for volume in data_obj['volumeItems']:
                                            for chapter in volume.get('chapterItems', []):
                                                order += 1
                                                chapter_id = chapter.get('chapterId', '') or chapter.get('id', '')
                                                if chapter_id:
                                                    captured_chapters.append({
                                                        'url': f"https://www.webnovel.com/book/{book_id_numeric}/{chapter_id}",
                                                        'order': order,
                                                        'name': chapter.get('chapterName', '') or chapter.get('name', ''),
                                                        'published_time': chapter.get('updateTime', '') or chapter.get('publishTime', '')
                                                    })
                                    
                                    # Structure 2: direct chapterItems
                                    elif 'chapterItems' in data_obj:
                                        order = 0
                                        for chapter in data_obj['chapterItems']:
                                            order += 1
                                            chapter_id = chapter.get('chapterId', '') or chapter.get('id', '')
                                            if chapter_id:
                                                captured_chapters.append({
                                                    'url': f"https://www.webnovel.com/book/{book_id_numeric}/{chapter_id}",
                                                    'order': order,
                                                    'name': chapter.get('chapterName', '') or chapter.get('name', ''),
                                                    'published_time': chapter.get('updateTime', '') or chapter.get('publishTime', '')
                                                })
                                
                                safe_print(f"   📊 Captured {len(captured_chapters)} chapters from API")
                            except:
                                pass
                        
                        route.fulfill(response=response)
                    except Exception as e:
                        route.continue_()
                
                # Enable route interception (DISABLED - causing route conflicts)
                # try:
                #     self.page.route("**/*", handle_route)
                #     safe_print("   🛰️  API interception enabled")
                # except:
                #     pass
                
                # Now click Table of Contents to trigger API call
                safe_print("   🔍 Clicking Table of Contents to trigger API...")
                toc_clicked = False
                for selector in ["a:has-text('Table of Contents')", "a:has-text('Contents')", "button:has-text('Contents')"]:
                    try:
                        tab = self.page.locator(selector).first
                        if tab.count() > 0:
                            tab.click(force=True, timeout=5000)
                            safe_print(f"   ✅ Clicked TOC tab")
                            toc_clicked = True
                            break
                    except:
                        continue
                
                if toc_clicked:
                    # Wait for API response
                    safe_print("   ⏳ Waiting for chapter data...")
                    self._random_sleep(1, 1.5)
                    
                    if captured_chapters:
                        safe_print(f"✅ Found {len(captured_chapters)} chapters via API interception\n")
                        # Disable route interception
                        try:
                            self.page.unroute("**/*")
                        except:
                            pass
                        return captured_chapters
                
                # Disable route interception
                try:
                    self.page.unroute("**/*")
                except:
                    pass
                    
            except Exception as e:
                safe_print(f"   ⚠️  API interception failed: {e}")
                    
            except Exception as toc_err:
                safe_print(f"   ⚠️  Table of Contents parsing failed: {toc_err}")
            
            # Strategy 4: Click Contents tab AGAIN (previous strategies may have already clicked it)
            safe_print("🔍 Strategy 4: Re-clicking Contents tab and checking DOM...")
            
            contents_clicked = False
            try:
                # Try different tab selectors
                tab_selectors = [
                    "li:has-text('Contents')",
                    "a:has-text('Contents')",
                    "button:has-text('Contents')",
                    "[data-tab='contents']",
                    ".j_catalog_wrap",
                    "#j_catalog"
                ]
                
                for selector in tab_selectors:
                    try:
                        tabs = self.page.locator(selector).all()
                        if tabs:
                            safe_print(f"   ✅ Found {len(tabs)} element(s): {selector}")
                            # Try clicking first one
                            tab = tabs[0]
                            tab.scroll_into_view_if_needed()
                            self._random_sleep()
                            tab.click(force=True, timeout=3000)
                            safe_print(f"   ✅ Clicked tab")
                            self._random_sleep(2, 3)  # Wait for content load
                            contents_clicked = True
                            break
                    except Exception as click_err:
                        continue
                
                # Wait for chapter elements to appear (not just spinner to disappear)
                safe_print("   ⏳ Waiting for chapter list to load after tab click...")
                
                # Try waiting for different chapter-related elements
                chapter_loaded = False
                wait_selectors = [
                    "li[class*='chapter']",
                    "div[class*='chapter']",
                    "a[href*='/book/'][href*='/34078380808505505/']",
                    ".volume-item",
                    ".catalog-volume"
                ]
                
                for wait_sel in wait_selectors:
                    try:
                        self.page.wait_for_selector(wait_sel, timeout=3000)
                        safe_print(f"   ✅ Chapter elements found: {wait_sel}")
                        chapter_loaded = True
                        break
                    except:
                        continue
                
                if not chapter_loaded:
                    safe_print("   ⚠️  No chapter elements detected after wait, will continue anyway")
                
                self._random_sleep(2, 3)
                
                # Try multiple chapter container selectors
                chapter_containers = [
                    "#j_catalog_content",
                    ".catalog-content",
                    ".j_catalog_content",
                    "[class*='catalog']",
                    ".volume-content",
                    "[id*='catalog']",
                    ".chapter-list",
                    "ol[class*='chapter']",
                    "ul[class*='chapter']"
                ]
                
                # Now look for chapter containers
                container_found = None
                for container_sel in chapter_containers:
                    try:
                        count = self.page.locator(container_sel).count()
                        if count > 0:
                            safe_print(f"   ✅ Found {count} chapter container(s): {container_sel}")
                            container_found = container_sel
                            break
                    except:
                        continue
                
                # Debug: Save screenshot and HTML AFTER loading complete
                try:
                    self.page.screenshot(path="data/debug_after_contents_click.png", full_page=True)
                    safe_print(f"   📸 Full page screenshot saved")
                    
                    # Get and save HTML of catalog container
                    if container_found:
                        catalog_html = self.page.locator(container_found).first.inner_html()
                        # Also count links inside
                        links_in_catalog = self.page.locator(f"{container_found} a").count()
                        safe_print(f"   📊 Links found in catalog container: {links_in_catalog}")
                        with open("data/debug_catalog.html", "w", encoding="utf-8") as f:
                            f.write(catalog_html)
                        safe_print(f"   📄 Catalog HTML saved (length: {len(catalog_html)} chars)")
                except Exception as debug_err:
                    safe_print(f"   ⚠️  Debug save failed: {debug_err}")
                
                # CRITICAL FIX: Aggressive scrolling to load all chapters
                safe_print("   📜 AGGRESSIVE SCROLLING to load all chapters (Fix for 277-chapter bug)...")
                
                # First, try to find the Contents/catalog container to scroll
                catalog_container = None
                for container_sel in ["#j_catalog_content", ".catalog-content", ".j_catalog_content", "[class*='catalog']"]:
                    try:
                        elem = self.page.locator(container_sel).first
                        if elem.count() > 0:
                            catalog_container = elem
                            safe_print(f"   ✅ Found catalog container: {container_sel}")
                            break
                    except:
                        continue
                
                # Strategy 1: Keyboard "End" key for maximum scroll efficiency
                if catalog_container:
                    try:
                        # Click inside catalog container to focus it
                        catalog_container.click(timeout=2000)
                        safe_print("   🎯 Focused catalog container")
                        
                        # Press End key repeatedly (at least 20 times as per requirement)
                        for i in range(25):
                            try:
                                self.page.keyboard.press("End")
                                time.sleep(0.4)  # Wait for lazy load
                                if i % 5 == 0:
                                    safe_print(f"   ⬇️  End key pressed {i+1}/25 times...")
                            except:
                                break
                        safe_print("   ✅ Aggressive keyboard scrolling complete")
                    except Exception as kbd_err:
                        safe_print(f"   ⚠️  Keyboard scroll failed: {kbd_err}, falling back to JS scroll")
                
                # Strategy 2: JavaScript scrolling fallback (if keyboard fails)
                if catalog_container:
                    try:
                        # Scroll to bottom of container multiple times
                        for i in range(30):
                            catalog_container.evaluate("el => el.scrollTop = el.scrollHeight")
                            time.sleep(0.3)
                            if i % 5 == 0:
                                safe_print(f"   📜 JS scroll iteration {i+1}/30...")
                    except Exception as js_err:
                        safe_print(f"   ⚠️  JS container scroll failed: {js_err}")
                
                # Strategy 3: Window-level scrolling as additional measure
                try:
                    for i in range(20):
                        self.page.evaluate("window.scrollBy(0, 800)")
                        time.sleep(0.3)
                except:
                    pass
                
                safe_print("   ✅ All scrolling strategies completed")
                
                # Wait for final render
                time.sleep(2)
            except Exception as e:
                safe_print(f"   ⚠️  Tab click and wait failed: {e}")
            
            # Strategy 3: Find chapter list containers (look INSIDE catalog container)
            safe_print("🔍 Strategy 3: Searching for chapter list containers...")
            
            chapter_container_selectors = [
                "#j_catalog_content a",  # Links inside catalog content
                ".catalog-content a",
                ".j_catalog_content a",
                "[class*='catalog'] a",
                "div.volume-item a",
                "div.chapter-item a",
                "li.chapter-item a",
                "ul.chapter-list a",
                "ol[class*='chapter'] li a",
                ".content-list a",
                "[class*='chapter-list'] a"
            ]
            
            found_container = False
            all_chapter_links = []
            
            for container_sel in chapter_container_selectors:
                try:
                    links = self.page.locator(container_sel).all()
                    if links:
                        safe_print(f"✅ Found {len(links)} links in: {container_sel}")
                        all_chapter_links = links
                        found_container = True
                        break
                except:
                    continue
            
            # Strategy 3.5: Parse TOC with full metadata (order, name, published_time)
            book_id_numeric = book_id.replace('wn_', '') if book_id.startswith('wn_') else book_id
            if found_container or all_chapter_links:
                safe_print("🔍 Strategy 3.5: Parsing TOC chapters with metadata...")
                try:
                    toc_chapters = self._parse_toc_chapters(book_id_numeric)
                    if toc_chapters:
                        # CRITICAL CHECK: Verify chapter count matches expected total
                        expected_total = self._scrape_total_chapters()
                        extracted_count = len(toc_chapters)
                        
                        safe_print(f"   📊 Expected: {expected_total} chapters, Extracted: {extracted_count}")
                        
                        # If we got significantly fewer chapters than expected, use Walk-Next fallback
                        if expected_total > 0 and extracted_count < expected_total * 0.9:  # Allow 10% tolerance
                            safe_print(f"   ⚠️  INCOMPLETE CHAPTER LIST DETECTED!")
                            safe_print(f"   🔄 Switching to WALK-NEXT strategy (slower but 100% accurate)...")
                            # Don't return yet - fall through to Walk-Next strategy below
                        else:
                            safe_print(f"   ✅ Chapter count verified! Parsed {len(toc_chapters)} chapters with metadata from TOC")
                            return toc_chapters  # Return with full metadata
                except Exception as toc_err:
                    safe_print(f"   ⚠️  TOC parsing failed: {toc_err}")
            
            # Strategy 4: Look for chapter links directly by book ID pattern
            if not found_container:
                safe_print("🔍 Strategy 4: Searching for chapter links by book ID pattern...")
                try:
                    # Find links that contain the book ID in their href
                    chapter_link_selector = f"a[href*='/book/'][href*='/{book_id_numeric}/']"
                    all_chapter_links = self.page.locator(chapter_link_selector).all()
                    safe_print(f"   Found {len(all_chapter_links)} links matching book ID")
                    if all_chapter_links:
                        found_container = True
                except:
                    all_chapter_links = []
            
            # Strategy 5: Scan ALL links as last resort
            if not found_container:
                safe_print("🔍 Strategy 5: Scanning all links on page...")
                try:
                    all_chapter_links = self.page.locator("a[href]").all()
                    safe_print(f"   Found {len(all_chapter_links)} total links")
                except:
                    all_chapter_links = []
            
            # Now parse all collected links
            safe_print(f"🔍 Parsing {len(all_chapter_links)} links for chapter URLs...")
            
            chapter_count_webnovel = 0
            chapter_count_external = 0
            seen_urls = set()
            
            # Debug: Print first 10 link hrefs to see pattern
            if all_chapter_links:
                safe_print(f"   📊 Sample links (first 10):")
                for i, link in enumerate(all_chapter_links[:10]):
                    try:
                        href = link.get_attribute("href") or ""
                        text = link.inner_text().strip()[:40]
                        safe_print(f"      {i+1}. {text} -> {href}")
                    except:
                        pass
            
            for link in all_chapter_links:
                try:
                    href = link.get_attribute("href")
                    text = link.inner_text().strip()
                    
                    if not href:
                        continue
                    
                    # Build full URL first
                    if not href.startswith("http"):
                        href = "https://www.webnovel.com" + href
                    
                    # CRITICAL: Filter out external domains first
                    if "webnovel.com" not in href:
                        chapter_count_external += 1
                        continue
                    
                    # Extract numeric book ID for pattern matching
                    book_id_numeric = book_id.replace('wn_', '') if book_id.startswith('wn_') else book_id
                    
                    # Check if this looks like a chapter link
                    is_chapter = False
                    
                    # Pattern 1: /book/{book_id}/{chapter_id} (most reliable for Webnovel)
                    if re.search(rf'/book/{book_id_numeric}/\d+', href):
                        is_chapter = True
                    
                    # Pattern 2: /book/any_id/numeric_chapter_id
                    elif re.search(r'/book/[\w-]+/\d{10,}', href):  # Webnovel uses long numeric IDs
                        is_chapter = True
                    
                    # Pattern 3: href contains 'chapter' (but not 'chapters' plural)
                    elif re.search(r'[/-]chapter[/-]', href.lower()):
                        is_chapter = True
                    
                    # Pattern 4: text looks like chapter title pattern
                    elif text and (re.match(r'^(?:Chapter|Ch\.?)\s*\d+', text, re.I) or
                                   re.match(r'^\d+\.\s+\w', text) or  # "1. Title"
                                   re.match(r'^Chương\s*\d+', text, re.I)):  # Vietnamese
                        is_chapter = True
                    
                    if is_chapter and href not in seen_urls and href != book_url:
                        chapter_urls.append(href)
                        seen_urls.add(href)
                        chapter_count_webnovel += 1
                        # Print first few for debugging
                        if chapter_count_webnovel <= 3:
                            safe_print(f"   ✅ Chapter {chapter_count_webnovel}: {text[:50]} -> {href}")
                except Exception as e:
                    continue
            
            safe_print(f"📊 Webnovel chapters: {chapter_count_webnovel}, External redirects (filtered): {chapter_count_external}")
            
            # Strategy 6 (LAST RESORT): Find Chapter 1 from TOC or READ button
            if not chapter_urls:
                safe_print("🔍 Strategy 6: Finding Chapter 1 (not latest chapter)...")
                try:
                    # Go back to book page
                    if self.page.url != book_url:
                        self.page.goto(book_url, timeout=config.TIMEOUT, wait_until='domcontentloaded')
                        self._close_popups()
                        self._random_sleep()
                    
                    book_id_numeric = book_id.replace('wn_', '') if book_id.startswith('wn_') else book_id
                    first_chapter_url = None
                    
                    # PRIORITY: Look for "Chapter 1" link in TOC/Catalog
                    safe_print("   🔍 Priority: Searching for 'Chapter 1' link in catalog...")
                    try:
                        # Click Contents tab first to reveal catalog
                        for tab_sel in ["a:has-text('Contents')", "button:has-text('Contents')", "li:has-text('Contents')"]:
                            try:
                                tab = self.page.locator(tab_sel).first
                                if tab.count() > 0:
                                    tab.click(timeout=3000)
                                    self._random_sleep(1, 2)
                                    break
                            except:
                                continue
                        
                        # Look for Chapter 1 specifically
                        chapter1_selectors = [
                            "a:has-text('Chapter 1')",
                            "a:has-text('Ch 1')",
                            "a:has-text('Ch. 1')",
                            "a:has-text('1.')"
                        ]
                        
                        for ch1_sel in chapter1_selectors:
                            try:
                                ch1_links = self.page.locator(ch1_sel).all()
                                for link in ch1_links:
                                    href = link.get_attribute('href')
                                    if href and '/book/' in href and book_id_numeric in href:
                                        if not href.startswith('http'):
                                            href = 'https://www.webnovel.com' + href
                                        first_chapter_url = href
                                        safe_print(f"   ✅ Found Chapter 1 in catalog: {href}")
                                        break
                                if first_chapter_url:
                                    break
                            except:
                                continue
                        
                        # Try getting first item from catalog list
                        if not first_chapter_url:
                            try:
                                catalog_links = self.page.locator(f"#j_catalog_content a[href*='/book/{book_id_numeric}/'], .catalog-content a[href*='/book/{book_id_numeric}/']").all()
                                if catalog_links:
                                    first_href = catalog_links[0].get_attribute('href')
                                    if first_href:
                                        if not first_href.startswith('http'):
                                            first_href = 'https://www.webnovel.com' + first_href
                                        first_chapter_url = first_href
                                        safe_print(f"   ✅ Found first chapter from catalog list: {first_href}")
                            except:
                                pass
                    except:
                        pass
                    
                    # FALLBACK: Use READ button but verify it's Chapter 1
                    if not first_chapter_url:
                        safe_print("   ⚠️  Chapter 1 not found in catalog, trying READ button...")
                        read_selectors = ["a:has-text('READ')", "button:has-text('READ')", "a.j_show_content"]
                        
                        for read_sel in read_selectors:
                            try:
                                read_btn = self.page.locator(read_sel).first
                                if read_btn.count() > 0:
                                    href = read_btn.get_attribute('href')
                                    if href and not href.startswith('http'):
                                        href = 'https://www.webnovel.com' + href
                                    
                                    if href and 'webnovel.com' in href and '/book/' in href:
                                        # Check if URL contains high chapter numbers
                                        high_chapter_match = re.search(r'chapter[-_]?([56789]\d|\d{3,})', href, re.I)
                                        if high_chapter_match:
                                            safe_print(f"   ⚠️  READ button links to Chapter {high_chapter_match.group(1)}, not Chapter 1!")
                                            safe_print(f"   🔄 Attempting to construct Chapter 1 URL...")
                                            # Try to construct Chapter 1 by replacing chapter number in URL
                                            # This is risky but better than starting from Chapter 61
                                        else:
                                            first_chapter_url = href
                                            safe_print(f"   ✅ READ button appears to link to early chapter: {href}")
                                        break
                            except:
                                continue
                    
                    if first_chapter_url:
                        chapter_urls.append(first_chapter_url)
                        
                        # Navigate to chapter and look for more
                        try:
                            self.page.goto(first_chapter_url, timeout=config.TIMEOUT, wait_until='domcontentloaded')
                            self._close_popups()
                            self._random_sleep()
                            
                            # Find all chapter links on this page
                            nav_links = self.page.locator(f"a[href*='/book/{book_id_numeric}/']").all()
                            for nav_link in nav_links[:10]:
                                try:
                                    nav_href = nav_link.get_attribute('href') or ""
                                    if not nav_href.startswith('http'):
                                        nav_href = 'https://www.webnovel.com' + nav_href
                                    if '/catalog' not in nav_href and nav_href not in chapter_urls:
                                        chapter_urls.append(nav_href)
                                except:
                                    continue
                            
                            safe_print(f"   📊 Total chapters found: {len(chapter_urls)}")
                        except:
                            pass
                        
                except Exception as read_err:
                    safe_print(f"   ⚠️  READ strategy failed: {read_err}")
            
            safe_print(f"✅ Found {len(chapter_urls)} chapter URLs (webnovel.com only)\n")
            
            # CRITICAL CHECK: Verify chapter count for walk-next fallback
            expected_total = self._scrape_total_chapters()
            should_use_walk_next = False
            
            if expected_total > 0 and len(chapter_urls) > 0:
                extracted_count = len(chapter_urls)
                if extracted_count < expected_total * 0.9:  # Less than 90% of expected
                    safe_print(f"⚠️  INCOMPLETE CHAPTER LIST: Expected {expected_total}, got {extracted_count}")
                    safe_print(f"🔄 Will use WALK-NEXT fallback strategy for 100% accuracy...")
                    should_use_walk_next = True
            
            # Strategy 7 (fallback): Follow prefetch/read target -> walk next links to enumerate chapters
            if not chapter_urls or should_use_walk_next:
                safe_print("🔍 Strategy 7: Following prefetch/read link and walking next-> to enumerate chapters...")
                try:
                    # Find prefetch link for first chapter
                    prefetch = None
                    try:
                        prefetch = None
                        links = self.page.locator('link').all()
                        for ln in links:
                            try:
                                rel = (ln.get_attribute('rel') or '').lower()
                                href = ln.get_attribute('href')
                                if href and '/book/' in href and ('prefetch' in rel or 'preload' in rel or 'next' in rel):
                                    prefetch = href
                                    break
                            except:
                                continue
                    except:
                        prefetch = None

                    # Also inspect JSON-LD potentialAction->target urlTemplate
                    if not prefetch:
                        try:
                            scripts = self.page.locator("script[type='application/ld+json']").all()
                            for s in scripts:
                                try:
                                    data = json.loads(s.inner_text())
                                except:
                                    continue
                                if isinstance(data, list):
                                    objs = data
                                else:
                                    objs = [data]
                                for obj in objs:
                                    pa = obj.get('potentialAction')
                                    if pa and isinstance(pa, dict):
                                        target = pa.get('target', {})
                                        urlt = target.get('urlTemplate') if isinstance(target, dict) else None
                                        if urlt and '/book/' in urlt:
                                            prefetch = urlt
                                            break
                                if prefetch:
                                    break
                        except:
                            pass

                    # If no prefetch found, construct first chapter URL from book URL
                    if not prefetch:
                        safe_print("   ⚠️  No prefetch link found, constructing from READ button or book URL...")
                        try:
                            # Try clicking READ button and getting resulting URL
                            read_btn = self.page.locator("a:has-text('READ'), a.g_button:has-text('READ'), a._go_detail").first
                            if read_btn.count() > 0:
                                href = read_btn.get_attribute('href')
                                if href and '/book/' in href:
                                    prefetch = href
                                    safe_print(f"   ✓ Found first chapter from READ button: {prefetch}")
                        except:
                            pass
                    
                    if prefetch:
                        if not prefetch.startswith('http'):
                            prefetch = 'https://www.webnovel.com' + prefetch
                        
                        # CRITICAL CHECK: Verify this is Chapter 1, not a later chapter
                        high_chapter_match = re.search(r'chapter[-_]?(\d+)', prefetch, re.I)
                        if high_chapter_match:
                            chapter_num = int(high_chapter_match.group(1))
                            if chapter_num > 5:
                                safe_print(f"   ⚠️  WARNING: Prefetch URL appears to be Chapter {chapter_num}, not Chapter 1!")
                                safe_print(f"   ⚠️  This will result in incomplete scraping. Consider re-running with force.")
                        
                        safe_print(f"   ↳ Starting from: {prefetch}")
                    else:
                        safe_print("   ❌ Could not find starting chapter URL for Strategy 7")
                        
                    if prefetch:
                        # Walk next links and collect metadata using Cloudscraper (bypass Cloudflare)
                        visited = set()
                        to_visit = [prefetch]
                        # CRITICAL FIX: Use actual total chapters from page (e.g., 277) instead of limiting to 100
                        expected_total = self._scrape_total_chapters() or 300  # Default to 300 if unknown
                        max_walk = expected_total + 10  # Add buffer for safety
                        safe_print(f"   📊 Will walk up to {max_walk} chapters (expected: {expected_total})")
                        order = 0
                        
                        # Setup cloudscraper session with browser fingerprint (same as chapter scraping)
                        import cloudscraper
                        from bs4 import BeautifulSoup
                        
                        cs = cloudscraper.create_scraper(browser={'browser':'chrome', 'platform':'windows', 'desktop': True})
                        
                        # Load cookies from cookies.json (same as chapter scraping)
                        if os.path.exists('cookies.json'):
                            try:
                                with open('cookies.json', 'r', encoding='utf-8') as cf:
                                    cookie_list = json.load(cf)
                                loaded = 0
                                for c in cookie_list:
                                    n = c.get('name')
                                    v = c.get('value')
                                    dom = c.get('domain')
                                    path = c.get('path', '/')
                                    if n and v:
                                        try:
                                            cs.cookies.set(n, v, domain=dom, path=path)
                                        except:
                                            try:
                                                cs.cookies.set(n, v)
                                            except:
                                                continue
                                        loaded += 1
                                safe_print(f"   🔑 Loaded {loaded} cookies into cloudscraper")
                            except:
                                pass
                        
                        while to_visit and order < max_walk:
                            cur = to_visit.pop(0)
                            if cur in visited:
                                continue
                            try:
                                # Set browser-like headers
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                    'Accept-Language': 'en-US,en;q=0.9',
                                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                    'Referer': 'https://www.webnovel.com/',
                                    'Origin': 'https://www.webnovel.com'
                                }
                                
                                # Try desktop URL first
                                resp = cs.get(cur, headers=headers, timeout=30)
                                if resp.status_code != 200 or len(resp.text or '') < 200:
                                    # Try mobile URL as fallback
                                    mobile_url = cur.replace('www.webnovel.com', 'm.webnovel.com')
                                    resp = cs.get(mobile_url, headers=headers, timeout=30)
                                    if resp.status_code != 200:
                                        safe_print(f"   ⚠️  HTTP {resp.status_code} for {cur}")
                                        continue
                                
                                soup = BeautifulSoup(resp.text, 'html.parser')
                                self._random_sleep()  # Fast default
                                visited.add(cur)
                                canonical = cur
                                
                                # Find canonical link
                                try:
                                    can = soup.find('link', {'rel': 'canonical'})
                                    if can and can.get('href'):
                                        canonical = can['href']
                                except:
                                    pass
                                
                                # Extract chapter metadata from HTML
                                order += 1
                                name = ""
                                published_time = ""
                                
                                try:
                                    # Get chapter name from h1 or title
                                    title_tag = soup.select_one('h1, h2.cha-tit, .cha-title, .cha-tit h3')
                                    if title_tag:
                                        name = title_tag.get_text(strip=True)
                                except:
                                    pass
                                
                                try:
                                    # Get published time from embedded JSON (chapInfo)
                                    # Webnovel stores chapter metadata in "var chapInfo={...}"
                                    # There are multiple publishTime fields - we want the LAST one (chapterInfo.publishTime)
                                    # Note: re and datetime are already imported at module level
                                    
                                    script_tags = soup.find_all('script', string=re.compile(r'var chapInfo='))
                                    for script in script_tags:
                                        script_text = script.string
                                        # Find ALL publishTime occurrences, take the last one
                                        all_matches = list(re.finditer(r'"publishTime":(\d+)', script_text))
                                        if all_matches:
                                            # Last publishTime is chapterInfo.publishTime
                                            last_match = all_matches[-1]
                                            timestamp_ms = int(last_match.group(1))
                                            dt = datetime.fromtimestamp(timestamp_ms / 1000)
                                            published_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                                            break
                                except:
                                    pass
                                
                                # Check if already in list (by URL)
                                already_added = False
                                for ch in chapter_urls:
                                    if isinstance(ch, dict) and ch.get('url') == canonical:
                                        already_added = True
                                        break
                                
                                if not already_added:
                                    chapter_urls.append({
                                        'url': canonical,
                                        'order': order,
                                        'name': name,
                                        'published_time': published_time
                                    })
                                    
                                    # Print progress more frequently for user feedback
                                    if order == 1:
                                        safe_print(f"   ✅ Chapter 1: {name[:50] if name else canonical[:50]}")
                                    elif order % 20 == 0:
                                        safe_print(f"   📚 Walked {order}/{expected_total} chapters... ({int(order/expected_total*100)}% complete)")
                                    elif order == expected_total:
                                        safe_print(f"   🎉 Reached expected total: {order} chapters!")
                                # find next chapter link using several strategies
                                next_found = None
                                
                                # Strategy A: Check <link rel="next"> in HTML head (PRIMARY - Webnovel standard)
                                try:
                                    next_tag = soup.find('link', {'rel': 'next'})
                                    if next_tag and next_tag.get('href'):
                                        next_href = next_tag['href']
                                        if not next_href.startswith('http'):
                                            next_href = 'https://www.webnovel.com' + next_href
                                        if next_href not in visited and '/book/' in next_href:
                                            next_found = next_href
                                            if order % 10 == 0:  # Log every 10 chapters
                                                safe_print(f"   ✓ Found next chapter #{order+1} via <link rel='next'>")
                                except Exception as e:
                                    logger.debug(f"link[rel='next'] exception: {e}")
                                
                                # Strategy B: Look for "Next Chapter" button/link (fallback)
                                if not next_found:
                                    try:
                                        next_selectors = [
                                            "a.j_bottom_next",  # Webnovel specific button
                                            "a[title*='Next']",
                                            "a:has-text('Next Chapter')",
                                            "a:has-text('Next')",
                                            "a.next-chapter"
                                        ]
                                        for sel in next_selectors:
                                            try:
                                                el = self.page.locator(sel).first
                                                if el.count() > 0 and el.is_visible():
                                                    nh = el.get_attribute('href')
                                                    if nh:
                                                        if not nh.startswith('http'):
                                                            nh = 'https://www.webnovel.com' + nh
                                                        if nh not in visited and '/book/' in nh:
                                                            next_found = nh
                                                            logger.info(f"Found next chapter via {sel}: {nh}")
                                                            break
                                            except:
                                                continue
                                    except:
                                        pass
                                
                                # Strategy B: Try JavaScript window.g_data
                                if not next_found:
                                    try:
                                        js_next = self.page.evaluate("""() => { 
                                            try { 
                                                if (window.g_data && window.g_data.nextChapterId) {
                                                    return window.g_data.nextChapterId;
                                                }
                                                if (window.__NUXT__ && window.__NUXT__.data) {
                                                    const data = Array.isArray(window.__NUXT__.data) ? window.__NUXT__.data[0] : window.__NUXT__.data;
                                                    if (data && data.nextChapterId) return data.nextChapterId;
                                                }
                                                return null;
                                            } catch(e) { 
                                                return null; 
                                            } 
                                        }""")
                                        if js_next:
                                            candidate = f"https://www.webnovel.com/book/{book_id_numeric}/{js_next}"
                                            if candidate not in visited:
                                                next_found = candidate
                                    except:
                                        pass

                                # Strategy C: Parse chapter nav buttons area
                                if not next_found:
                                    try:
                                        # Look for navigation container and find all chapter links
                                        nav_links = self.page.locator(".cha-nav a, .chapter-nav a, [class*='nav'] a").all()
                                        for link in nav_links:
                                            try:
                                                href = link.get_attribute('href')
                                                if href and '/book/' in href and href not in visited:
                                                    if not href.startswith('http'):
                                                        href = 'https://www.webnovel.com' + href
                                                    # Check if this is likely a "next" link (not prev/catalog)
                                                    text = link.inner_text().lower()
                                                    if 'next' in text or '›' in text or '>' in text:
                                                        next_found = href
                                                        break
                                            except:
                                                continue
                                    except:
                                        pass

                                if next_found:
                                    to_visit.append(next_found)
                                else:
                                    # No next found - we've reached the end
                                    safe_print(f"   ℹ️  No more chapters found at chapter {order}")
                            except Exception as e:
                                safe_print(f"   ⚠️  Walk error at {cur}: {e}")
                                continue
                        safe_print(f"   ✅ Walked and found {len(chapter_urls)} chapter URLs via next-links")
                        return chapter_urls
                except Exception as e:
                    safe_print(f"   ⚠️  Prefetch/read walk failed: {e}")
        except Exception as e:
            safe_print(f"⚠️  Error finding chapters: {e}")
        
        return chapter_urls
    
    def _collect_chapter_urls_from_nav(self):
        """Collect chapter URLs from chapter navigation dropdown"""
        urls = []
        try:
            # Find chapter dropdown or list
            chapter_links = self.page.locator("a[href*='/chapter/']").all()
            for link in chapter_links:
                href = link.get_attribute("href")
                if href and '/chapter/' in href:
                    if not href.startswith("http"):
                        href = "https://www.webnovel.com" + href
                    if href not in urls:
                        urls.append(href)
        except:
            pass
        return urls

    def _fetch_catalog_via_playwright(self, book_url, book_id_numeric):
        """Fallback: render the book page in Playwright and extract chapter links by pattern.

        Returns list of chapter URLs or None
        """
        safe_print("   🔁 Falling back to Playwright-rendered catalog fetch...")
        try:
            # Navigate with extended timeout
            try:
                # Use DOMContentLoaded to avoid long networkidle hangs; we already increased global timeout
                self.page.goto(book_url, timeout=min(config.TIMEOUT, 60000), wait_until='domcontentloaded')
            except Exception:
                safe_print("   ⚠️ Playwright navigation to catalog timed out or failed; continuing to parse available DOM")

            # Try clicking Contents/TOC tabs to reveal chapters
            try:
                tab_selectors = ["a:has-text('Contents')", "button:has-text('Contents')", "a:has-text('Table of Contents')", "button:has-text('Table of Contents')"]
                for sel in tab_selectors:
                    try:
                        el = self.page.locator(sel).first
                        if el.count() > 0:
                            el.scroll_into_view_if_needed()
                            el.click(force=True, timeout=5000)
                            time.sleep(2)
                            break
                    except:
                        continue
            except:
                pass

            # Scroll to load lazy content
            for _ in range(8):
                try:
                    self.page.evaluate('window.scrollBy(0, 800)')
                    time.sleep(0.5)
                except:
                    break

            # Collect links that look like chapter URLs
            links = self.page.locator("a[href]").all()
            found = []
            seen = set()
            for a in links:
                try:
                    href = a.get_attribute('href') or ''
                    if not href:
                        continue
                    if not href.startswith('http'):
                        href = urljoin(book_url, href)
                    # Match /book/{book_id}/{chapter_id} patterns
                    if re.search(rf'/book/{book_id_numeric}/\d+', href):
                        if href not in seen:
                            seen.add(href)
                            found.append(href)
                except:
                    continue

            safe_print(f"   🔍 Playwright fallback found {len(found)} chapter links")
            return found if found else None
        except Exception as e:
            safe_print(f"   ⚠️ Playwright catalog fallback error: {e}")
            return None
    
    def _scrape_chapter(self, chapter_url, internal_book_id, platform_book_id, order, toc_name=None, toc_published=None):
        """
        Scrape single chapter with comments
        
        Args:
            chapter_url: Chapter URL
            book_id: Parent book ID
            order: Chapter order (1, 2, 3...)
        
        Returns:
            Chapter: {id, book_id, order, name, url, content, published_time, comments}
        """
        safe_print(f"\n📄 Scraping Chapter {order}: {chapter_url}")
        
        try:
            # Navigate to chapter (Playwright attempt first)
            self.page.goto(chapter_url, timeout=config.TIMEOUT, wait_until='domcontentloaded')
            
            # Wait for Cloudflare to complete (detect and wait for "Just a moment..." to disappear)
            try:
                # Wait up to 10 seconds for Cloudflare challenge to disappear
                self.page.wait_for_function(
                    """() => {
                        const body = document.body.innerText.toLowerCase();
                        return !body.includes('just a moment') && 
                               !body.includes('checking your browser') &&
                               !body.includes('cloudflare');
                    }""",
                    timeout=10000
                )
                safe_print("   ✅ Cloudflare bypass successful")
            except Exception:
                # If timeout, check if content is actually available anyway
                body_text = self.page.locator('body').inner_text().lower()
                if 'just a moment' in body_text or 'checking your browser' in body_text:
                    safe_print("   ⚠️ Cloudflare challenge still present")
                else:
                    safe_print("   ✅ Page loaded (no Cloudflare detected)")
            
            # Small delay to ensure content renders
            time.sleep(random.uniform(1.5, 2.5))
            
            # Generate UUID v7 for chapter ID
            internal_chapter_id = str(uuid6.uuid7())
            
            # Extract platform chapter ID for source_id
            platform_chapter_id = None
            try:
                m = re.search(r"/book/.+?/([\w\-]+_?\d+)$", chapter_url)
                if m:
                    platform_chapter_id = self._make_platform_obf(m.group(1))
            except:
                platform_chapter_id = None
            
            # Scrape chapter data
            # Prefer TOC-supplied metadata when available
            chapter_name = toc_name if toc_name else self._scrape_chapter_name()
            published_time = toc_published if toc_published else self._scrape_chapter_published_time()

            # Try to get content via Playwright (now that Cloudflare is bypassed)
            content = self._scrape_chapter_content()

            # Check if content extraction failed and log appropriately
            if not content or len(content.strip()) < 50:
                safe_print(f"   ⚠️ Warning: Chapter {order} content is too short or empty ({len(content or '')} chars)")
                # Save debug HTML for inspection
                try:
                    os.makedirs('data/debug', exist_ok=True)
                    debug_html = self.page.content()
                    dbg_path = os.path.join('data/debug', f'chapter_{order}_failed.html')
                    with open(dbg_path, 'w', encoding='utf-8') as df:
                        df.write(debug_html)
                    safe_print(f"   📄 Saved debug HTML to {dbg_path}")
                except Exception as e:
                    safe_print(f"   ⚠️ Failed to save debug HTML: {e}")
            
            # Legacy cloudscraper fallback (now deprecated in favor of Playwright with Cloudflare wait)
            # Keeping this code commented for reference, but it should not be needed anymore
            need_cloudscraper = False
            if need_cloudscraper and cloudscraper is not None and BeautifulSoup is not None:
                try:
                    safe_print("   ⚙️  Content seems blocked or empty — attempting cloudscraper fetch...")
                    # Create a fresh scraper session to solve JS challenge and get cookies
                    # Use browser-like fingerprint to improve success
                    scraper = cloudscraper.create_scraper(browser={ 'browser':'chrome', 'platform':'windows', 'desktop': True })
                    # If cookies.json exists (exported from interactive login), load cookies into the cloudscraper session
                    if os.path.exists('cookies.json'):
                        try:
                            with open('cookies.json', 'r', encoding='utf-8') as cf:
                                cookie_list = json.load(cf)
                            if isinstance(cookie_list, list):
                                loaded = 0
                                for c in cookie_list:
                                    n = c.get('name')
                                    v = c.get('value')
                                    dom = c.get('domain')
                                    path = c.get('path', '/')
                                    if n and v:
                                        try:
                                            scraper.cookies.set(n, v, domain=dom, path=path)
                                        except Exception:
                                            try:
                                                scraper.cookies.set(n, v)
                                            except Exception:
                                                continue
                                        loaded += 1
                                safe_print(f"   🔑 Loaded {loaded} cookies into cloudscraper session")
                        except Exception as e:
                            safe_print(f"   ⚠️ Failed loading cookies into cloudscraper: {e}")
                    # Set headers similar to browser
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Referer': chapter_url,
                        'Origin': 'https://www.webnovel.com'
                    }
                    # Try desktop URL first, then mobile if needed
                    resp = scraper.get(chapter_url, headers=headers, timeout=30)
                    if resp is None or resp.status_code != 200 or len(resp.text or '') < 200:
                        # Try mobile variant which sometimes contains simpler HTML
                        m_url = chapter_url.replace('www.webnovel.com', 'm.webnovel.com')
                        safe_print(f"   ↳ Trying mobile URL: {m_url}")
                        resp = scraper.get(m_url, headers=headers, timeout=30)

                    html = resp.text if resp is not None else ''
                    # Save debug HTML for inspection
                    try:
                        os.makedirs('data', exist_ok=True)
                        dbg_path = os.path.join('data', f'debug_chapter_{order}.html')
                        with open(dbg_path, 'w', encoding='utf-8') as df:
                            df.write(html or '')
                        safe_print(f"   📄 Saved cloudscraper HTML to {dbg_path}")
                    except:
                        pass

                    # Parse HTML to extract content from div.cha-content or div.cha-words
                    soup = BeautifulSoup(html or '', 'html.parser')
                    content_container = soup.find('div', class_=re.compile(r'cha-content|chapter-content|cha-words'))
                    if not content_container:
                        # try multiple strategies: look for div with class containing 'cha-words'
                        content_container = soup.find('div', class_=re.compile(r'cha-words'))

                    if content_container:
                        # Extract paragraphs
                        paras = []
                        for p in content_container.find_all(['p', 'div']):
                            text = p.get_text(separator=' ', strip=True)
                            if text:
                                paras.append(text)
                        if not paras:
                            # fallback: full text of container
                            content = content_container.get_text(separator='\n', strip=True)
                        else:
                            content = '\n\n'.join(paras)

                        # Extract GIF URLs inside container and append markers
                        gifs = []
                        for img in content_container.find_all('img'):
                            src = img.get('src') or img.get('data-src') or ''
                            if src and '.gif' in src:
                                if not src.startswith('http'):
                                    src = 'https:' + src
                                gifs.append(src)
                        if gifs:
                            content += '\n' + '\n'.join([f'[GIF: {g}]' for g in gifs])
                    else:
                        # If still nothing, fallback to naive body text
                        content = soup.get_text(separator='\n', strip=True)[:20000]

                    # small delay to avoid rapid retries
                    time.sleep(random.uniform(1.0, 2.5))
                except Exception as cs_e:
                    safe_print(f"   ⚠️  cloudscraper fetch failed: {cs_e}")
                    # leave content as-is (could be empty)
            # If cloudscraper couldn't retrieve useful content, try Playwright-rendered chapter
            if (not content or len(content.strip()) < 50) and config.USE_PLAYWRIGHT_FALLBACK and render_with_playwright is not None:
                try:
                    safe_print("   ⚠️  Falling back to Playwright-rendered chapter fetch")
                    pw_html = render_with_playwright(chapter_url, storage_state_path=config.PLAYWRIGHT_STORAGE_STATE, timeout=config.PLAYWRIGHT_TIMEOUT_MS, screenshot_path=os.path.join(config.DEBUG_OUTPUT_DIR, f'chapter{order}_playwright.png'), har_path=os.path.join(config.DEBUG_OUTPUT_DIR, f'chapter{order}_network.har'), debug_dir=config.DEBUG_OUTPUT_DIR)
                    if pw_html:
                        try:
                            ch_dbg = os.path.join(config.DEBUG_OUTPUT_DIR, f'chapter{order}_playwright.html')
                            with open(ch_dbg, 'w', encoding='utf-8') as f:
                                f.write(pw_html)
                        except Exception:
                            pass
                        # parse with BeautifulSoup
                        try:
                            soup = BeautifulSoup(pw_html, 'html.parser')
                            content_container = soup.find('div', class_=re.compile(r'cha-content|chapter-content|cha-words'))
                            if content_container:
                                paras = [p.get_text(separator=' ', strip=True) for p in content_container.find_all(['p', 'div']) if p.get_text(strip=True)]
                                content = '\n\n'.join(paras) if paras else content_container.get_text(separator='\n', strip=True)
                            else:
                                content = soup.get_text(separator='\n', strip=True)[:20000]
                        except Exception:
                            pass
                except Exception as e:
                    safe_print(f"   ⚠️ Playwright chapter fallback failed: {e}")
            else:
                if need_cloudscraper and cloudscraper is None:
                    safe_print("   ⚠️  cloudscraper not installed — cannot attempt JS-challenge fetch")
                if need_cloudscraper and BeautifulSoup is None:
                    safe_print("   ⚠️  BeautifulSoup (bs4) not installed — cannot parse fetched HTML")
            comments = self._scrape_chapter_comments(internal_chapter_id)

            return {
                "id": internal_chapter_id,
                "book_id": internal_book_id,
                "order": order,
                "name": chapter_name,
                "url": chapter_url,
                "content": content,
                "published_time": published_time,
                "comments": comments
            }
            
        except Exception as e:
            safe_print(f"❌ Error scraping chapter {order}: {e}")
            return None
    
    def _scrape_chapter_name(self):
        """Scrape chapter title"""
        try:
            title_el = self.page.locator("h1").first
            if title_el.count() > 0:
                return title_el.inner_text().strip()
        except:
            pass
        return "Untitled Chapter"
    
    def _scrape_chapter_content(self):
        """
        Scrape chapter content text with robust multi-strategy fallback.
        Tries specific selectors first, then generic patterns, then text-based extraction.
        """
        safe_print("   ⏳ Waiting for chapter content to render...")
        
        # ============================================================================
        # PRIORITY 1: Try specific known Webnovel selectors with wait
        # ============================================================================
        specific_selectors = [
            "div.cha-words",
            "div.j_chapterContent", 
            "div.cha-content",
            "div.chapter-content"
        ]
        
        for selector in specific_selectors:
            try:
                # Try to wait for this specific selector (15s timeout)
                self.page.wait_for_selector(selector, timeout=15000, state='visible')
                self._random_sleep(1, 1.5)
                
                # Extract text content
                content_el = self.page.locator(selector).first
                if content_el.count() > 0:
                    text = content_el.inner_text().strip()
                    if text and len(text) > 200:  # Valid chapter content should be substantial
                        safe_print(f"   ✅ Content found via selector '{selector}' ({len(text)} chars)")
                        return text
                    elif text and len(text) > 50:
                        safe_print(f"   ⚠️  Short content via '{selector}' ({len(text)} chars) - trying next...")
            except Exception as e:
                # Timeout or not found - continue to next selector
                continue
        
        safe_print("   ⚠️  Specific selectors failed - trying generic patterns...")
        
        # ============================================================================
        # PRIORITY 2: Try generic content patterns (any div with "content" in class)
        # ============================================================================
        try:
            generic_selector = 'div[class*="content"]'
            self.page.wait_for_selector(generic_selector, timeout=10000, state='visible')
            self._random_sleep(0.5, 1)
            
            # Find all matching divs and get the one with most paragraph content
            content = self.page.evaluate("""() => {
                const contentDivs = Array.from(document.querySelectorAll('div[class*="content"]'));
                let bestContent = '';
                let maxParagraphs = 0;
                
                for (const div of contentDivs) {
                    const paragraphs = div.querySelectorAll('p');
                    if (paragraphs.length > maxParagraphs) {
                        const text = Array.from(paragraphs)
                            .map(p => p.innerText.trim())
                            .filter(t => t.length > 20)
                            .join('\\n\\n');
                        
                        if (text.length > 200) {
                            maxParagraphs = paragraphs.length;
                            bestContent = text;
                        }
                    }
                }
                return bestContent;
            }""")
            
            if content and len(content.strip()) > 200:
                safe_print(f"   ✅ Content found via generic pattern ({len(content)} chars, paragraphs detected)")
                return content.strip()
                
        except Exception as e:
            safe_print(f"   ⚠️  Generic pattern failed: {str(e)[:100]}")
        
        # ============================================================================
        # PRIORITY 3: Text-based fallback - find largest block of story-like text
        # ============================================================================
        safe_print("   ⚠️  All CSS selectors failed - using text-based extraction fallback...")
        
        try:
            content = self.page.evaluate("""() => {
                // Strategy: Find the container with the most <p> tags that looks like story content
                const allContainers = Array.from(document.querySelectorAll('div, article, section, main'));
                
                let bestCandidate = null;
                let maxScore = 0;
                
                for (const container of allContainers) {
                    // Count paragraphs in this container
                    const paragraphs = container.querySelectorAll('p');
                    const pCount = paragraphs.length;
                    
                    // Skip containers with too few paragraphs (likely not story content)
                    if (pCount < 5) continue;
                    
                    // Calculate total text length in paragraphs
                    let totalLength = 0;
                    const texts = [];
                    for (const p of paragraphs) {
                        const text = p.innerText.trim();
                        if (text.length > 20) {  // Skip very short paragraphs (UI elements)
                            texts.push(text);
                            totalLength += text.length;
                        }
                    }
                    
                    // Skip if not enough text
                    if (totalLength < 500) continue;
                    
                    // Score: prioritize containers with many long paragraphs
                    const score = pCount * 10 + totalLength / 100;
                    
                    if (score > maxScore) {
                        maxScore = score;
                        bestCandidate = texts.join('\\n\\n');
                    }
                }
                
                // If we found a good candidate, return it
                if (bestCandidate && bestCandidate.length > 200) {
                    return bestCandidate;
                }
                
                // Last resort: get all <p> tags on page (might include navigation/UI text)
                const allParagraphs = Array.from(document.querySelectorAll('p'));
                const allText = allParagraphs
                    .map(p => p.innerText.trim())
                    .filter(t => t.length > 20)
                    .join('\\n\\n');
                
                return allText.length > 200 ? allText : '';
            }""")
            
            if content and len(content.strip()) > 200:
                safe_print(f"   ✅ Content extracted via text-based fallback ({len(content)} chars)")
                return content.strip()
            else:
                safe_print(f"   ❌ Text-based fallback insufficient ({len(content or '')} chars)")
                
        except Exception as e:
            safe_print(f"   ❌ Text-based extraction failed: {e}")
        
        # ============================================================================
        # COMPLETE FAILURE: No content found
        # ============================================================================
        safe_print("   ❌ ALL extraction strategies failed - content unavailable")
        return ""
    
    def _scrape_chapter_published_time(self):
        """Scrape chapter publish time (ISO datetime)"""
        try:
            # Look for time element or date text
            time_el = self.page.locator("time, span[class*='date'], span[class*='time']").first
            if time_el.count() > 0:
                time_str = time_el.get_attribute("datetime") or time_el.inner_text()
                # Convert to ISO if needed
                return time_str
        except:
            pass
        return ""
    
    def _scrape_chapter_comments(self, chapter_id):
        """
        Scrape ALL comments on chapter by clicking comment button and waiting for drawer/panel
        
        Returns:
            list[CommentOnChapter]: All comments with replies
        """
        safe_print(f"  💬 Scraping chapter comments...")
        comments = []
        
        try:
            # STEP 1: Scroll to bottom to make comment button visible
            safe_print(f"  📜 Scrolling to make comment button visible...")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)  # Brief pause for content to load
            
            # STEP 2: Find comment button FAST (5 second timeout total)
            safe_print(f"  🔍 Looking for comment button (5s timeout)...")
            comment_btn = None
            comment_count = None
            btn_text = ""
            
            try:
                # Quick check: CSS selector first (fastest)
                try:
                    btn_locator = self.page.locator(".j_bottom_comments, a[href*='#comment']").first
                    if btn_locator.count() > 0:
                        comment_btn = btn_locator
                        btn_text = btn_locator.inner_text(timeout=2000).strip()
                        try:
                            comment_count = btn_locator.get_attribute('data-reply-amount')
                        except:
                            pass
                        safe_print(f"  ✅ Found by CSS: '{btn_text}'")
                except:
                    pass
                
                # Fallback: Text search
                if not comment_btn:
                    try:
                        text_btn = self.page.get_by_text("Comment", exact=False).first
                        if text_btn.is_visible(timeout=3000):
                            comment_btn = text_btn
                            btn_text = text_btn.inner_text().strip()
                            safe_print(f"  ✅ Found by text: '{btn_text}'")
                            
                            # Extract count from text
                            import re
                            match = re.search(r'(\d+)', btn_text)
                            if match:
                                comment_count = match.group(1)
                    except:
                        pass
                
                # If no button found, skip this chapter
                if not comment_btn:
                    safe_print(f"  ⚠️  Comment button not found/clickable. Skipping.")
                    return []
                    
            except Exception as find_err:
                safe_print(f"  ⚠️  Comment button search timed out: {find_err}. Skipping.")
                return []
            
            # STEP 3: CLICK THE BUTTON (fast, single attempt)
            safe_print(f"  👆 Clicking comment button...")
            try:
                comment_btn.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.5)
                comment_btn.click(timeout=5000)
                safe_print(f"  ✅ Comment button clicked!")
            except Exception as click_err:
                safe_print(f"  ⚠️  Click failed: {click_err}. Skipping.")
                return []
            
            # STEP 4: Wait for drawer to open (3 seconds)
            safe_print(f"  ⏳ Waiting for drawer (3s)...")
            time.sleep(3)
            
            # STEP 5: Quick check for comment items (5 second timeout)
            safe_print(f"  🔍 Checking for comment items (5s timeout)...")
            comment_appeared = False
            
            try:
                # Fast wait for comment items
                self.page.wait_for_selector(
                    ".m-comment-item, .j_comment_list li, section.m-comment, div[class*='comment-item'], li[class*='comment']",
                    timeout=5000,
                    state='attached'
                )
                safe_print(f"  ✅ Comment items detected!")
                comment_appeared = True
                time.sleep(1)  # Brief render wait
                
            except Exception as wait_err:
                safe_print(f"  ⚠️  No comment items found after 5s")
            
            # STEP 6: One quick retry if no comments found
            if not comment_appeared:
                safe_print(f"  🔄 Quick retry: Scrolling drawer...")
                try:
                    # Try to find drawer and scroll
                    drawer = self.page.locator(".drawer._on, .j_comment_list, .g_drawer._on").first
                    if drawer.count() > 0:
                        drawer.evaluate("el => el.scrollTop = 100")
                        time.sleep(1)
                        
                        # Check again
                        self.page.wait_for_selector(
                            ".m-comment-item, .j_comment_list li",
                            timeout=3000,
                            state='attached'
                        )
                        safe_print(f"  ✅ Comments appeared after retry!")
                        comment_appeared = True
                except:
                    safe_print(f"  ⚠️  Retry failed")
            
            # STEP 7: If still no comments, give up quickly
            if not comment_appeared:
                safe_print(f"  ⚠️  No comments detected. Skipping chapter.")
                return []
            
            # STEP 8: Scroll to load all comments (fast)
            safe_print(f"  📜 Scrolling to load all comments...")
            try:
                container = self.page.locator(".j_comment_list, .drawer._on").first
                if container.count() > 0:
                    # Quick scroll to trigger lazy loading
                    for i in range(3):
                        container.evaluate(f"el => el.scrollTop = {(i + 1) * 300}")
                        time.sleep(0.3)
            except:
                pass
            
            # STEP 10: Parse comments with multiple selector strategies
            comments = self._parse_chapter_comments(chapter_id)
            
            # STEP 11: RETRY PARSE if we got 0 comments but button said there should be some
            if not comments and comment_count and str(comment_count).isdigit() and int(comment_count) > 0:
                safe_print(f"  🔄 Retry #2: Expected {comment_count} comments but got 0, waiting 2s and trying again...")
                time.sleep(2)
                # Try clicking button again (sometimes drawer needs double trigger)
                try:
                    comment_btn.click(timeout=3000)
                    safe_print(f"     👆 Re-clicked comment button")
                    time.sleep(3)
                except:
                    pass
                # Try parsing again
                comments = self._parse_chapter_comments(chapter_id)
                if comments:
                    safe_print(f"     ✅ Retry successful! Got {len(comments)} comments")
            
            if comments:
                safe_print(f"  ✅ Successfully scraped {len(comments)} chapter comments")
            else:
                safe_print(f"  ℹ️  No comments found (might be 0 comments or wrong selector)")
                # Debug: Save HTML for analysis
                try:
                    debug_dir = "data/debug"
                    os.makedirs(debug_dir, exist_ok=True)
                    debug_html = self.page.content()
                    debug_path = f"{debug_dir}/chapter_{chapter_id}_after_click.html"
                    with open(debug_path, 'w', encoding='utf-8') as f:
                        f.write(debug_html)
                    safe_print(f"  🐛 Saved debug HTML: {debug_path}")
                except:
                    pass
            
        except Exception as e:
            safe_print(f"  ⚠️  Error scraping chapter comments: {e}")
        
        return comments
    
    def _parse_chapter_comments_inner(self, chapter_id):
        """Inner parser after clicking Reveal Spoiler buttons"""
    
    def _parse_chapter_comments(self, chapter_id):
        """Parse chapter comments - wrapper that clicks Reveal Spoiler first"""
        # CRITICAL FIX: Click all Reveal Spoiler buttons before parsing
        try:
            spoiler_buttons = self.page.locator("button:has-text('Reveal Spoiler'), a:has-text('Reveal Spoiler'), span:has-text('Reveal Spoiler')").all()
            if spoiler_buttons:
                safe_print(f"  🔓 Found {len(spoiler_buttons)} spoiler buttons, clicking all...")
                for btn in spoiler_buttons:
                    try:
                        if btn.is_visible():
                            btn.click(timeout=2000)
                            time.sleep(0.2)
                    except:
                        continue
                safe_print(f"  ✅ All spoiler content revealed")
        except:
            pass
        
        # Now call the actual parser
        return self._parse_chapter_comments_inner(chapter_id)
    
    def _parse_chapter_comments_inner(self, chapter_id):
        """
        Parse chapter comments using multiple selector strategies.
        After clicking button, comments appear in drawer/panel with various possible selectors.
        """
        comments = []
        
        try:
            # Strategy 1: Try standard selectors first
            comment_sections = self.page.locator("section.m-comment").all()
            
            # Strategy 2: Try .m-comment-item class (common in drawers)
            if len(comment_sections) == 0:
                safe_print(f"  🔍 Trying .m-comment-item selector...")
                comment_sections = self.page.locator(".m-comment-item").all()
                if len(comment_sections) > 0:
                    safe_print(f"  ✅ Found {len(comment_sections)} comments using .m-comment-item")
            
            # Strategy 3: Try broader patterns
            if len(comment_sections) == 0:
                safe_print(f"  🔍 Standard selectors failed, trying broader patterns...")
                selectors_to_try = [
                    ".j_comment_list > li",
                    ".j_comment_list > div",
                    "div[class*='comment-item']",
                    "li[class*='comment-item']",
                    "div[class*='comment'][class*='item']",
                    "[data-comment-id]",
                    "[data-ejs*='review']",
                ]
                
                for selector in selectors_to_try:
                    comment_sections = self.page.locator(selector).all()
                    if len(comment_sections) > 0:
                        safe_print(f"  ✅ Found {len(comment_sections)} comments using: {selector}")
                        break
            
            # Strategy 4: VERY BROAD - Find elements with level badges (reliable comment indicator)
            if len(comment_sections) == 0:
                safe_print(f"  🔍 All selectors failed, trying broad search with 'LV' and 'Level' indicators...")
                try:
                    # Strategy 4a: Look for elements with "LV" (user level badges like "LV 5")
                    lv_candidates = self.page.locator("div, li").filter(has_text="LV").all()
                    safe_print(f"     🔍 Found {len(lv_candidates)} elements with 'LV' text")
                    
                    for candidate in lv_candidates:
                        try:
                            text = candidate.inner_text().strip()
                            # Validate: should have reasonable comment size and contain "LV" + content
                            if len(text) > 30 and len(text) < 5000 and ("LV" in text):
                                comment_sections.append(candidate)
                        except:
                            continue
                    
                    # Strategy 4b: Also try "Level" if "LV" didn't find enough
                    if len(comment_sections) < 3:
                        level_candidates = self.page.locator("div, li").filter(has_text="Level").all()
                        safe_print(f"     🔍 Found {len(level_candidates)} elements with 'Level' text")
                        
                        for candidate in level_candidates:
                            try:
                                text = candidate.inner_text().strip()
                                if len(text) > 30 and len(text) < 5000 and ("Level" in text):
                                    # Avoid duplicates
                                    if candidate not in comment_sections:
                                        comment_sections.append(candidate)
                            except:
                                continue
                    
                    if len(comment_sections) > 0:
                        safe_print(f"  ✅ Found {len(comment_sections)} potential comments via level badge search")
                
                except Exception as lv_err:
                    safe_print(f"  ⚠️  Level badge search error: {lv_err}")
            
            # Strategy 5: FALLBACK - Find elements with "Reply" text
            if len(comment_sections) == 0:
                safe_print(f"  🔍 Last resort: Looking for elements with 'Reply' text...")
                try:
                    reply_candidates = self.page.locator("div, li").filter(has_text="Reply").all()
                    safe_print(f"     🔍 Found {len(reply_candidates)} elements with 'Reply' text")
                    
                    for candidate in reply_candidates:
                        try:
                            text = candidate.inner_text().strip()
                            if len(text) > 20 and len(text) < 5000:
                                comment_sections.append(candidate)
                        except:
                            continue
                    
                    if len(comment_sections) > 0:
                        safe_print(f"  ✅ Found {len(comment_sections)} potential comments via 'Reply' search")
                
                except Exception as reply_err:
                    safe_print(f"  ⚠️  Reply search error: {reply_err}")
            
            # Log final selector used
            if len(comment_sections) == 0:
                safe_print(f"  ℹ️  No comment elements found with any selector")
            else:
                safe_print(f"  📝 Parsing {len(comment_sections)} comment element(s)...")
            
            # Parse each comment
            for comment_section in comment_sections:
                comment = self._parse_single_chapter_comment(comment_section, chapter_id)
                if comment:
                    comments.append(comment)
                    
        except Exception as e:
            safe_print(f"  ⚠️  Error parsing chapter comments: {e}")
        
        return comments
    
    def _parse_single_chapter_comment(self, element, chapter_id):
        """
        Parse single chapter comment - FIXED username and replies extraction
        
        Returns:
            CommentOnChapter: {comment_id, chapter_id, parent_id, user_id, user_name, time, content, replies}
        """
        try:
            comment_id = str(uuid6.uuid7())
            user_name = "Anonymous"
            user_id = None
            time_str = ""
            
            # ===== FIX BUG A: Extract USERNAME properly =====
            # CRITICAL: Try the MOST SPECIFIC selector first
            # Priority 1: Try data-ejs (most reliable for chapter comments)
            try:
                data_ejs = element.get_attribute('data-ejs')
                if data_ejs:
                    ejs_data = json.loads(data_ejs)
                    username_from_ejs = ejs_data.get('userName') or ejs_data.get('user') or ejs_data.get('name')
                    if username_from_ejs and username_from_ejs.strip():
                        user_name = username_from_ejs.strip()
                        # Also get user ID if available
                        user_id_from_ejs = ejs_data.get('userId') or ejs_data.get('uid')
                        if user_id_from_ejs:
                            user_id = f"wn_{user_id_from_ejs}"
            except:
                pass
            
            # Priority 2: Try .m-comment-hd a selector (MOST SPECIFIC - prevents content capture)
            if user_name == "Anonymous":
                try:
                    # CRITICAL: Use .m-comment-hd a to target ONLY the header link (NOT content)
                    user_link = element.locator(".m-comment-hd a").first
                    
                    # Filter to ensure it's a profile link
                    if user_link.count() > 0:
                        href = user_link.get_attribute('href')
                        if href and '/profile/' in href:
                            # Get username from title attribute (most reliable)
                            user_name = user_link.get_attribute('title')
                            
                            # If no title, try inner text
                            if not user_name or not user_name.strip():
                                user_name = user_link.inner_text().strip()
                            
                            # Validate it's a username (not content fragment)
                            if user_name and len(user_name) < 50 and '\n' not in user_name:
                                # Get user ID from href
                                user_id = self._make_platform_obf(href)
                            else:
                                user_name = "Anonymous"  # Reset if invalid
                except:
                    pass
            
            # Priority 3: Fallback to any profile link if header search failed
            if user_name == "Anonymous":
                try:
                    user_link = element.locator("a[href*='/profile/']").first
                    if user_link.count() > 0:
                        user_name = user_link.get_attribute('title') or user_link.inner_text().strip()
                        if user_name and len(user_name) < 50 and '\n' not in user_name:
                            href = user_link.get_attribute('href')
                            if href:
                                user_id = self._make_platform_obf(href)
                        else:
                            user_name = "Anonymous"
                except:
                    pass
            
            # Note: Removed .g_txt_over selector as it's too generic and captures content
            
            # ===== Extract TIMESTAMP =====
            # Priority 1: Try data-ejs timestamp
            try:
                data_ejs = element.get_attribute('data-ejs')
                if data_ejs:
                    ejs_data = json.loads(data_ejs)
                    last_time = ejs_data.get('lastTime')
                    if last_time:
                        from datetime import datetime, timezone
                        dt = datetime.fromtimestamp(last_time / 1000, tz=timezone.utc)
                        now = datetime.now(timezone.utc)
                        diff = now - dt
                        
                        years = diff.days // 365
                        months = diff.days // 30
                        weeks = diff.days // 7
                        days = diff.days
                        hours = diff.seconds // 3600
                        minutes = (diff.seconds % 3600) // 60
                        
                        if years > 0:
                            time_str = f"{years}y"
                        elif months > 0:
                            time_str = f"{months}mth"
                        elif weeks > 0:
                            time_str = f"{weeks}w"
                        elif days > 0:
                            time_str = f"{days}d"
                        elif hours > 0:
                            time_str = f"{hours}h"
                        elif minutes > 0:
                            time_str = f"{minutes}m"
                        else:
                            time_str = "Just now"
            except:
                pass
            
            # Priority 2: Parse from visible text
            if not time_str:
                try:
                    full_text = element.inner_text()
                    # Match patterns like "2d", "5h", "1mth", "Just now"
                    match = re.search(r'\b(\d+(?:mth|[ywdhms])|Just now)\b', full_text, re.IGNORECASE)
                    if match:
                        time_str = match.group(1)
                except:
                    pass
            
            # ===== Extract CONTENT (NOT username!) =====
            content = ""
            try:
                # Strategy 1: Look for .m-comment-bd or .db class
                content_selectors = [".m-comment-bd", ".db", ".comment-content", ".content"]
                for sel in content_selectors:
                    try:
                        content_el = element.locator(sel).first
                        if content_el.count() > 0:
                            content = content_el.inner_text().strip()
                            if content:
                                break
                    except:
                        continue
                
                # Strategy 2: Fallback to text parsing (remove username/metadata)
                if not content:
                    full_text = element.inner_text().strip()
                    lines = full_text.split('\n')
                    content_lines = []
                    skip_patterns = [
                        user_name,  # Skip username line
                        r'^LV\s+\d+$',  # Skip level badge
                        r'^\d+(?:mth|[ywdhms])$',  # Skip timestamp line
                        r'^Just now$',  # Skip "Just now"
                        r'^\d+$',  # Skip lone numbers (likes/votes)
                    ]
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Check if line should be skipped
                        should_skip = False
                        for pattern in skip_patterns:
                            if isinstance(pattern, str):
                                if line == pattern:
                                    should_skip = True
                                    break
                            else:  # regex pattern
                                if re.match(pattern, line):
                                    should_skip = True
                                    break
                        
                        if not should_skip:
                            content_lines.append(line)
                    
                    content = '\n'.join(content_lines)
            except:
                pass
            
            # ===== FIX BUG B: Extract REPLIES using unified helper =====
            replies = []
            try:
                replies = self._scrape_replies(element)
            except Exception as e:
                safe_print(f"         ⚠️ Failed to extract replies: {e}")
            
            return {
                "comment_id": comment_id,
                "chapter_id": chapter_id,
                "parent_id": None,
                "user_id": user_id,
                "user_name": user_name,
                "time": time_str,
                "content": content,
                "replies": replies
            }
            
        except Exception as e:
            return None
    
    def _parse_single_reply(self, element, parent_comment_id):
        """
        Parse a single reply (sub-comment) within a chapter comment
        
        Returns:
            dict: {comment_id, chapter_id, parent_id, user_id, user_name, time, content, replies}
        """
        try:
            reply_id = str(uuid6.uuid7())
            user_name = "Anonymous"
            user_id = None
            time_str = ""
            content = ""
            
            # Extract username - try data-ejs first
            try:
                data_ejs = element.get_attribute('data-ejs')
                if data_ejs:
                    ejs_data = json.loads(data_ejs)
                    user_name = ejs_data.get('userName') or ejs_data.get('user') or ejs_data.get('name') or user_name
                    user_id_raw = ejs_data.get('userId') or ejs_data.get('uid')
                    if user_id_raw:
                        user_id = f"wn_{user_id_raw}"
            except:
                pass
            
            # Fallback: profile link
            if user_name == "Anonymous":
                user_selectors = ["a[href*='/profile/']", ".g_txt_over", "h4", ".reply-user", ".user-name"]
                for selector in user_selectors:
                    try:
                        user_el = element.locator(selector).first
                        if user_el.count() > 0:
                            name = user_el.get_attribute('title') or user_el.inner_text().strip()
                            # Validate it's a username (not content)
                            if name and len(name) < 50 and '\n' not in name:
                                user_name = name
                                # Get user ID
                                href = user_el.get_attribute('href')
                                if href and '/profile/' in href:
                                    user_id = self._make_platform_obf(href)
                                break
                    except:
                        continue
            
            # Extract timestamp
            try:
                full_text = element.inner_text()
                match = re.search(r'\b(\d+(?:mth|[ywdhms])|Just now)\b', full_text, re.IGNORECASE)
                if match:
                    time_str = match.group(1)
            except:
                pass
            
            # Extract content - be VERY careful to not include username
            try:
                # Try specific content selectors first
                content_selectors = [".reply-content", ".m-comment-bd", ".db", ".content", "[class*='content']"]
                for sel in content_selectors:
                    try:
                        content_el = element.locator(sel).first
                        if content_el.count() > 0:
                            text = content_el.inner_text().strip()
                            # Make sure it's not just the username
                            if text and text != user_name and len(text) > 1:
                                content = text
                                break
                    except:
                        continue
                
                # Fallback: parse from full text (remove metadata)
                if not content:
                    full_text = element.inner_text().strip()
                    lines = full_text.split('\n')
                    content_lines = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Skip username
                        if line == user_name:
                            continue
                        # Skip timestamp patterns
                        if re.match(r'^\d+(?:mth|[ywdhms])$', line):
                            continue
                        if line.lower() == 'just now':
                            continue
                        # Skip level badges
                        if re.match(r'^LV\s+\d+$', line):
                            continue
                        # Skip very short lines that are likely UI elements
                        if len(line) < 3:
                            continue
                        
                        content_lines.append(line)
                    
                    content = '\n'.join(content_lines)
            except:
                pass
            
            # Only return if we have actual content
            if content and content.strip():
                return {
                    "comment_id": reply_id,
                    "parent_id": parent_comment_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "time": time_str,
                    "content": content,
                    "replies": []  # Nested replies not supported for now
                }
            return None
        except:
            return None
    
    # ==================== SAVE TO FILE ====================
    
    def _save_book_to_json(self, book_data):
        """Save book data to JSON file"""
        output_dir = self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        # Sanitize book name for filename (remove illegal Windows characters)
        raw_name = book_data.get('name') or ''
        # remove characters that are illegal in Windows filenames: <>:"/\|?* and control chars
        safe_name = re.sub(r'[<>:\\"/\\|?*\n\r]+', '', raw_name)
        safe_name = safe_name.strip().replace(' ', '_')
        if not safe_name:
            safe_name = book_data.get('id', 'book')

        # Limit filename length to avoid OS issues
        safe_name = safe_name[:100]

        filename = f"{book_data['id']}_{safe_name}"
        if not filename.lower().endswith('.json'):
            filename = filename + '.json'

        filepath = os.path.join(output_dir, filename)

        # Write atomically: write to a temp file then replace
        temp_path = filepath + '.tmp'
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(book_data, f, indent=4, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    # Not critical if fsync not available
                    pass
            os.replace(temp_path, filepath)
            safe_print(f"\n💾 Saved to: {filepath}")
        except Exception as e:
            # Cleanup temp file if exists
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
            safe_print(f"⚠️  Failed to save JSON file: {e}")
