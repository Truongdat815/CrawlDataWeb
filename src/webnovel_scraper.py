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
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.net_logs = []
        # ID helpers
        self._id_prefix_book = 'bk'
        self._id_prefix_chapter = 'ch'
        self._id_prefix_comment = 'cmt'
        self._id_prefix_reply = 'rep'
        self._platform_prefix = 'wn'

    def _make_internal_id(self, prefix='id'):
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

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
        self.playwright = sync_playwright().start()
        
        # Launch with realistic settings to avoid Cloudflare detection
        self.browser = self.playwright.chromium.launch(
            headless=False,  # Non-headless to avoid detection
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context with realistic browser fingerprint
        context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
                self.page.goto(target_url, timeout=config.TIMEOUT)
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
    
    def scrape_book(self, book_url, max_chapters=None, wait_for_login=False):
        """
        Scrape complete book with all data
        
        Args:
            book_url: URL of the book to scrape
            max_chapters: Maximum number of chapters to scrape (None = all)
            wait_for_login: If True, pause and wait for manual login before scraping
        
        Args:
            book_url: URL of book page (e.g., https://www.webnovel.com/book/xxx_123)
            max_chapters: Max chapters to scrape (None = all)
        
        Returns:
            dict: Complete book data following schema
        """
        safe_print(f"\n{'='*60}")
        safe_print(f"📖 SCRAPING BOOK: {book_url}")
        safe_print(f"{'='*60}\n")
        
        # Navigate to book page with random delay
        try:
            self.page.goto(book_url, timeout=config.TIMEOUT)
            try:
                # Wait for network to settle, but don't fail the whole run if it hangs
                self.page.wait_for_load_state("networkidle", timeout=config.TIMEOUT)
            except Exception:
                safe_print("⚠️ networkidle wait timed out; continuing anyway")
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

        # Create internal primary book id (not predictable) and include platform id separately
        internal_book_id = f"bk_{uuid.uuid4().hex[:12]}"
        
        # Scrape book metadata
        book_data = {
            "id": internal_book_id,
            "platform_id": platform_book_id,
            "platform": "webnovel",
            "name": self._scrape_book_name(),
            "url": book_url,
            "cover_image": self._scrape_cover_image(internal_book_id),
            "author": self._scrape_author(),
            "category": self._scrape_category(),
            "status": None,  # Status removed as per user request
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
        
        # Scrape chapters
        chapter_list = self._get_chapter_urls(book_url, platform_book_id)
        if chapter_list:
            if max_chapters:
                chapter_list = chapter_list[:max_chapters]
            safe_print(f"\n📚 Found {len(chapter_list)} chapters to scrape\n")

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
        """Scrape category from page"""
        try:
            selectors = [
                "span._ml a",
                "a[href*='/category/']",
                ".det-info a"
            ]
            for selector in selectors:
                el = self.page.locator(selector).first
                if el.count() > 0:
                    category = el.inner_text().strip()
                    if category and len(category) > 2 and not category.isdigit():
                        safe_print(f"📂 Category: {category}")
                        return category
        except:
            pass
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
        
        safe_print("📖 Status: Unknown")
        return "Unknown"
    
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
            page_text = self.page.locator("body").inner_text()
            
            # Parse overall rating and count
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
            
            safe_print(f"⭐ Ratings: {ratings['overall_score']} ({ratings['total_ratings']} ratings)")
        except:
            pass
        
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
        Scrape ALL comments on book page with infinite scroll
        
        Returns:
            list[CommentOnBook]: All comments with replies
        """
        safe_print("\n💬 Scraping book comments...")
        comments = []
        
        try:
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

            # Click Reviews tab if exists and wait for content to load
            try:
                review_tab = self.page.locator("button:has-text('Review'), a:has-text('Review'), a:has-text('Comments'), button:has-text('Comments'), a:has-text('About'), button:has-text('About')").first
                if review_tab.count() > 0:
                    review_tab.click()
                    self._random_sleep(2, 3)  # Wait for comments and pagination to load
            except:
                pass

            safe_print("📜 Collecting book comments with replies...")
            collected = []
            seen_reviews = set()
            
            # Parse pagination from HTML to get total pages (must be done AFTER clicking review tab)
            max_pages = 1
            try:
                self._random_sleep(1, 1.5)  # Extra wait for pagination to render
                pagination_container = self.page.locator("div.ui-page-x").first
                if pagination_container.count() > 0:
                    # Find all numbered page links: <a data-page="2">2</a>, <a data-page="3">3</a>, etc.
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
                        max_pages = max(page_numbers)
                        safe_print(f"   📄 Found {max_pages} pages of comments")
            except Exception as e:
                safe_print(f"   ⚠️  Could not detect pagination: {e}")
            
            current_page = 1
            
            while current_page <= max_pages:
                safe_print(f"   📄 Page {current_page}...")
                self._random_sleep()  # Use default fast timing
                
                # Parse comments on current page
                page_comments, page_review_ids = self._parse_book_comments(internal_book_id, platform_book_id, return_ids=True)
                
                # For each comment, check if it has replies and extract them
                for i, (comment, rid) in enumerate(zip(page_comments, page_review_ids)):
                    # Skip duplicates
                    if rid and rid in seen_reviews:
                        continue
                    if rid:
                        seen_reviews.add(rid)
                    
                    # Skip reply extraction for speed (TODO: fix reply button detection)
                    if False and rid:  # Disabled for performance
                        # Check for "View X Replies" button
                        # Pattern: <a data-rid="..." data-rc="26">View 26 Replies</a>
                        try:
                            # Find the comment section by data-ejs containing this reviewId
                            # Use escaped quotes for JSON search
                            sections = self.page.locator(f"section.m-comment").all()
                            
                            comment_section = None
                            for sec in sections:
                                try:
                                    data_ejs = sec.get_attribute('data-ejs')
                                    if data_ejs and rid in data_ejs:
                                        comment_section = sec
                                        break
                                except:
                                    continue
                            
                            if comment_section:
                                # Look for reply button: a.m-comment-reply-btn or a.j_reivew_open._book
                                reply_btns = comment_section.locator("a.m-comment-reply-btn, a.j_reivew_open._book, a[data-rc]").all()
                                
                                for reply_btn in reply_btns:
                                    try:
                                        # Check if this button has reply count
                                        reply_count_attr = reply_btn.get_attribute('data-rc')
                                        if not reply_count_attr:
                                            continue
                                            
                                        reply_count = int(reply_count_attr)
                                        if reply_count == 0:
                                            continue
                                        
                                        # Get button text to verify it's "View Replies"
                                        btn_text = reply_btn.inner_text().lower()
                                        if 'repl' not in btn_text and 'view' not in btn_text:
                                            continue
                                        
                                        safe_print(f"      💬 Comment has {reply_count} replies, loading...")
                                        
                                        # Click to load replies
                                        try:
                                            reply_btn.scroll_into_view_if_needed(timeout=3000)
                                            self._random_sleep(0.5, 1)
                                            reply_btn.click(force=True, timeout=3000)
                                            self._random_sleep(2, 3)
                                            
                                            # Wait for replies to load - check within comment section
                                            comment_section.locator(".m-reply-item, .reply-item, div[class*='reply']").first.wait_for(timeout=5000)
                                            
                                            # Extract replies
                                            replies = self._parse_comment_replies(comment_section, internal_book_id)
                                            comment['replies'] = replies
                                            safe_print(f"      ✅ Extracted {len(replies)} replies")
                                            break  # Only process first reply button
                                            
                                        except Exception as reply_err:
                                            safe_print(f"      ⚠️  Failed to load replies: {reply_err}")
                                            
                                    except Exception as btn_err:
                                        continue
                                        
                        except Exception as e:
                            pass
                    
                    # Always append comment to collected (after reply extraction attempt)
                    collected.append(comment)
                
                safe_print(f"   ✅ Page {current_page}: {len(page_comments)} comments")
                
                # Check if we've reached max_pages limit
                if current_page >= max_pages:
                    safe_print(f"   ✅ Reached max pages limit ({max_pages})")
                    break
                
                # Try to find and click next page button
                # Pattern: <a class="ui-page ui-page-next" data-page="2">Next</a>
                try:
                    # Find pagination container
                    pagination = self.page.locator("div.ui-page-x").first
                    if pagination.count() == 0:
                        safe_print(f"   ✅ No pagination found (single page)")
                        break
                    
                    # Check if we're on the last page (Next button disabled or missing)
                    # Look for numbered page button for next page
                    next_page_num = current_page + 1
                    next_page_link = pagination.locator(f"a.ui-page[data-page='{next_page_num}']").first
                    
                    if next_page_link.count() > 0:
                        safe_print(f"   ➡️  Moving to page {next_page_num}...")
                        try:
                            # Get first comment data-ejs before click to verify change
                            old_first_rid = None
                            try:
                                first_comment = self.page.locator("section.m-comment").first
                                if first_comment.count() > 0:
                                    old_data = first_comment.get_attribute('data-ejs')
                                    if old_data:
                                        old_first_rid = json.loads(old_data).get('reviewId')
                            except:
                                pass
                            
                            next_page_link.scroll_into_view_if_needed(timeout=3000)
                            self._random_sleep()
                            
                            # Use JavaScript to trigger click with event dispatching
                            self.page.evaluate(f"""
                                (pageNum) => {{
                                    const link = document.querySelector('a.ui-page[data-page="' + pageNum + '"]');
                                    if (link) {{
                                        link.click();
                                        // Dispatch events to trigger any handlers
                                        link.dispatchEvent(new Event('click', {{bubbles: true, cancelable: true}}));
                                    }}
                                }}
                            """, next_page_num)
                            
                            # Wait for page indicator to update
                            indicator_updated = False
                            try:
                                self.page.wait_for_function(f"""
                                    () => {{
                                        const currentPage = document.querySelector('.ui-page-current');
                                        return currentPage && currentPage.textContent.trim() === '{next_page_num}';
                                    }}
                                """, timeout=5000)
                                indicator_updated = True
                            except:
                                pass
                            
                            # Wait for network activity to complete
                            try:
                                self.page.wait_for_load_state('networkidle', timeout=5000)
                            except:
                                pass
                            
                            # Additional wait for content to render
                            self._random_sleep(1, 2)
                            
                            # Verify first comment changed
                            new_first_rid = None
                            try:
                                first_comment = self.page.locator("section.m-comment").first
                                if first_comment.count() > 0:
                                    new_data = first_comment.get_attribute('data-ejs')
                                    if new_data:
                                        new_first_rid = json.loads(new_data).get('reviewId')
                            except:
                                pass
                            
                            if indicator_updated and new_first_rid and new_first_rid != old_first_rid:
                                safe_print(f"      ✅ Successfully loaded page {next_page_num}")
                            elif indicator_updated:
                                safe_print(f"      ⚠️  Page indicator updated but content may be same")
                            else:
                                safe_print(f"      ⚠️  Page did not change properly")
                            
                            current_page = next_page_num
                            continue
                            
                        except Exception as click_err:
                            safe_print(f"      ⚠️  Pagination failed: {click_err}")
                            break
                    
                    # No more pages
                    safe_print(f"   ✅ No more pages found")
                    break
                    
                except Exception as page_err:
                    safe_print(f"   ⚠️  Pagination error: {page_err}")
                    break

            comments = collected
            safe_print(f"✅ Collected {len(comments)} book comments with replies\n")
            
        except Exception as e:
            safe_print(f"⚠️  Error scraping book comments: {e}")
        
        return comments
    
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
            # Find all reply items within this comment section
            # Pattern: <div class="m-reply-item"> or <li class="reply-item">
            reply_items = comment_section.locator(".m-reply-item, .reply-item, div[class*='reply']").all()
            
            for reply_el in reply_items:
                try:
                    # Extract reply text
                    reply_text = reply_el.inner_text().strip()
                    if not reply_text or len(reply_text) < 3:
                        continue
                    
                    # Extract username
                    user_name = "Anonymous"
                    try:
                        user_link = reply_el.locator("a[href*='/profile'], a[href*='/user']").first
                        if user_link.count() > 0:
                            user_name = user_link.inner_text().strip() or user_name
                    except:
                        pass
                    
                    # Extract time
                    time_str = ""
                    try:
                        time_patterns = [
                            (r'(\d+)\s*s(?:ec)?', 's'),
                            (r'(\d+)\s*m(?:in)?', 'm'),
                            (r'(\d+)\s*h(?:r|our)?', 'h'),
                            (r'(\d+)\s*d(?:ay)?', 'd'),
                            (r'(\d+)\s*w(?:eek)?', 'w'),
                            (r'(\d+)\s*m(?:on|nth|onth)?', 'mth'),
                            (r'(\d+)\s*y(?:r|ear)?', 'yr')
                        ]
                        for pattern, suffix in time_patterns:
                            match = re.search(pattern, reply_text, re.I)
                            if match:
                                time_str = match.group(1) + suffix
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
                            "comment_id": self._make_internal_id(self._id_prefix_comment),
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
    
    def _parse_single_book_comment(self, element, internal_book_id, platform_book_id):
        """
        Parse single book comment
        
        Returns:
            CommentOnBook: {comment_id, story_id, user_id, user_name, time, content, score, replies}
        """
        try:
            full_text = element.inner_text().strip()
            if not full_text or len(full_text) < 5:
                return None
            
            # Extract username and profile link
            user_name = "Anonymous"
            user_profile = None
            try:
                user_links = element.locator("a[href*='/profile'], a[href*='/user']").all()
                if user_links:
                    user_el = user_links[0]
                    user_name = user_el.inner_text().strip() or user_name
                    try:
                        user_profile = user_el.get_attribute('href')
                    except:
                        user_profile = None
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
            
            # Extract time - normalize format (22d, 1mth, 5yr)
            time_str = ""
            try:
                # Find time patterns and normalize
                time_patterns = [
                    (r'(\d+)\s*s(?:ec)?', 's'),
                    (r'(\d+)\s*m(?:in)?', 'm'),  
                    (r'(\d+)\s*h(?:r|our)?', 'h'),
                    (r'(\d+)\s*d(?:ay)?', 'd'),
                    (r'(\d+)\s*w(?:eek)?', 'w'),
                    (r'(\d+)\s*m(?:on|nth|onth)?', 'mth'),
                    (r'(\d+)\s*y(?:r|ear)?', 'yr')
                ]
                for pattern, suffix in time_patterns:
                    match = re.search(pattern, full_text, re.I)
                    if match:
                        time_str = match.group(1) + suffix
                        break
            except:
                pass
            
            # Generate internal comment_id (primary) and obfuscated platform user id
            comment_id = self._make_internal_id(self._id_prefix_comment)
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
                "comment_id": comment_id,
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
                    self.page.goto(book_url, timeout=config.TIMEOUT)
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
                
                # Scroll to load all lazy-loaded chapters
                safe_print("   📜 Scrolling to load all chapters...")
                for i in range(15):
                    try:
                        self.page.evaluate("window.scrollBy(0, 600)")
                        self._random_sleep(0.6, 1.2)
                    except:
                        break
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
                        safe_print(f"   ✅ Parsed {len(toc_chapters)} chapters with metadata from TOC")
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
            
            # Strategy 6 (LAST RESORT): Try READ button to get first chapter
            if not chapter_urls:
                safe_print("🔍 Strategy 6: Trying READ button to access first chapter...")
                try:
                    # Go back to book page
                    if self.page.url != book_url:
                        self.page.goto(book_url, timeout=config.TIMEOUT)
                        self._close_popups()
                        self._random_sleep()
                    
                    # Find READ button
                    read_selectors = ["a:has-text('READ')", "button:has-text('READ')", "a.j_show_content"]
                    book_id_numeric = book_id.replace('wn_', '') if book_id.startswith('wn_') else book_id
                    
                    for read_sel in read_selectors:
                        try:
                            read_btn = self.page.locator(read_sel).first
                            if read_btn.count() > 0:
                                href = read_btn.get_attribute('href')
                                if href and not href.startswith('http'):
                                    href = 'https://www.webnovel.com' + href
                                
                                if href and 'webnovel.com' in href and '/book/' in href:
                                    safe_print(f"   ✅ Found first chapter via READ: {href}")
                                    chapter_urls.append(href)
                                    
                                    # Navigate to chapter and look for more
                                    try:
                                        self.page.goto(href, timeout=config.TIMEOUT)
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
                                    break
                        except:
                            continue
                except Exception as read_err:
                    safe_print(f"   ⚠️  READ strategy failed: {read_err}")
            
            safe_print(f"✅ Found {len(chapter_urls)} chapter URLs (webnovel.com only)\n")
            
            # Strategy 7 (fallback): Follow prefetch/read target -> walk next links to enumerate chapters
            if not chapter_urls:
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
                        safe_print(f"   ↳ Starting from: {prefetch}")
                    else:
                        safe_print("   ❌ Could not find starting chapter URL for Strategy 7")
                        
                    if prefetch:
                        # Walk next links and collect metadata using Cloudscraper (bypass Cloudflare)
                        visited = set()
                        to_visit = [prefetch]
                        max_walk = min(int(self._scrape_total_chapters() or 100), 100)  # Limit to 100 for speed
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
                                    import re
                                    from datetime import datetime
                                    
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
                                    
                                    # Print progress every 10 chapters
                                    if order % 10 == 0:
                                        safe_print(f"   📚 Walked {order} chapters...")
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
            self.page.goto(chapter_url, timeout=config.TIMEOUT)
            self._random_sleep()  # Fast default
            
            # Generate internal chapter ID and attempt to derive platform chapter id
            internal_chapter_id = self._make_internal_id(self._id_prefix_chapter)
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

            # Try to get content via Playwright first
            content = self._scrape_chapter_content()

            # Detect Cloudflare / block patterns in fetched content
            blocked_indicators = ['just a moment', 'checking your browser', 'cloudflare', 'you are being redirected']
            content_lower = (content or '').lower()
            need_cloudscraper = False
            if not content or len(content.strip()) < 50:
                need_cloudscraper = True
            else:
                for ind in blocked_indicators:
                    if ind in content_lower:
                        need_cloudscraper = True
                        break

            # If blocked or content missing, try cloudscraper (fresh session) to fetch chapter HTML directly
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
        """Scrape chapter content text"""
        try:
            content_el = self.page.locator(".chapter-inner, .chapter-content, div[class*='content']").first
            if content_el.count() > 0:
                return content_el.inner_text().strip()
        except:
            pass
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
        Scrape ALL comments on chapter with infinite scroll
        
        Returns:
            list[CommentOnChapter]: All comments with replies
        """
        safe_print(f"  💬 Scraping chapter comments...")
        comments = []
        
        try:
            # Find and click comment button
            comment_btn_selectors = [
                "button:has-text('Comment')",
                "a:has-text('Comment')",
                "button[class*='comment']"
            ]
            
            for selector in comment_btn_selectors:
                btn = self.page.locator(selector).first
                if btn.count() > 0:
                    btn.scroll_into_view_if_needed()
                    time.sleep(1)
                    btn.click()
                    time.sleep(3)
                    break
            
            # Infinite scroll to load all comments
            previous_height = 0
            no_change_count = 0
            max_scrolls = 30
            
            for scroll in range(max_scrolls):
                self.page.evaluate("window.scrollBy(0, 500)")
                time.sleep(1)
                
                current_height = self.page.evaluate("document.body.scrollHeight")
                if current_height == previous_height:
                    no_change_count += 1
                    if no_change_count >= 3:
                        break
                else:
                    no_change_count = 0
                    previous_height = current_height
            
            # Parse comments
            comments = self._parse_chapter_comments(chapter_id)
            safe_print(f"  ✅ Found {len(comments)} chapter comments")
            
        except Exception as e:
            safe_print(f"  ⚠️  Error scraping chapter comments: {e}")
        
        return comments
    
    def _parse_chapter_comments(self, chapter_id):
        """Parse chapter comments from loaded page"""
        comments = []
        
        try:
            # Find comment containers
            comment_selectors = [
                "div[class*='comment']",
                "li[class*='comment']",
                ".comment-item"
            ]
            
            for selector in comment_selectors:
                elements = self.page.locator(selector).all()
                if elements:
                    for el in elements:
                        comment = self._parse_single_chapter_comment(el, chapter_id)
                        if comment:
                            comments.append(comment)
                    break
        except:
            pass
        
        return comments
    
    def _parse_single_chapter_comment(self, element, chapter_id):
        """
        Parse single chapter comment
        
        Returns:
            CommentOnChapter: {comment_id, chapter_id, parent_id, user_id, user_name, time, content, replies}
        """
        try:
            full_text = element.inner_text().strip()
            if not full_text or len(full_text) < 5:
                return None
            
            # Extract username and profile link
            user_name = "Anonymous"
            user_profile = None
            try:
                user_links = element.locator("a[href*='/profile'], a[href*='/user']").all()
                if user_links:
                    user_el = user_links[0]
                    user_name = user_el.inner_text().strip() or user_name
                    try:
                        user_profile = user_el.get_attribute('href')
                    except:
                        user_profile = None
            except:
                pass
            
            # Extract content
            lines = full_text.split('\n')
            content_lines = []
            for line in lines:
                line = line.strip()
                if not line or line == user_name:
                    continue
                if re.match(r'^LV\s+\d+', line) or re.match(r'^\d+(s|m|h|d|w|mth|yr)$', line):
                    continue
                content_lines.append(line)
            
            content = '\n'.join(content_lines)
            
            # Extract GIFs (append to content)
            try:
                gifs = element.locator("img[src*='.gif']").all()
                for gif in gifs:
                    url = gif.get_attribute("src")
                    if url and not url.startswith("http"):
                        url = "https:" + url
                    content += f"\n[GIF: {url}]"
            except:
                pass
            
            # Extract time
            time_str = ""
            patterns = [r'\d+s', r'\d+m', r'\d+h', r'\d+d', r'\d+w', r'\d+mth', r'\d+yr']
            for pattern in patterns:
                matches = re.findall(pattern, full_text)
                if matches:
                    time_str = matches[0]
                    break
            
            # Normalize time format
            time_patterns = [
                (r'(\d+)\s*s(?:ec)?', 's'),
                (r'(\d+)\s*m(?:in)?', 'm'),
                (r'(\d+)\s*h(?:r)?', 'h'),
                (r'(\d+)\s*d(?:ay)?', 'd'),
                (r'(\d+)\s*w(?:eek)?', 'w'),
                (r'(\d+)\s*m(?:on|nth)?', 'mth'),
                (r'(\d+)\s*y(?:r)?', 'yr')
            ]
            for pattern, suffix in time_patterns:
                match = re.search(pattern, full_text, re.I)
                if match:
                    time_str = match.group(1) + suffix
                    break
            
            # Generate internal comment id and obfuscated user id
            comment_id = self._make_internal_id(self._id_prefix_comment)
            user_id = None
            if user_profile:
                user_id = self._make_platform_obf(user_profile)

            return {
                "comment_id": comment_id,
                "chapter_id": chapter_id,
                "parent_id": None,
                "user_id": user_id,
                "user_name": user_name,
                "time": time_str,
                "content": content,
                "replies": []
            }
            
        except:
            return None
    
    # ==================== SAVE TO FILE ====================
    
    def _save_book_to_json(self, book_data):
        """Save book data to JSON file"""
        output_dir = "data/json"
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
