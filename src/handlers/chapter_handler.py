"""
Chapter handler - xử lý chapter content scraping
✅ CÁCH TỐI ƯU: Dùng browser chính đã mở (đã vượt Cloudflare) thay vì tạo mới
"""
import time
import random
import re
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text
from src.utils.requests_helper import get_session_from_context, scrape_chapter_with_requests


class ChapterHandler:
    """Handler cho chapter content scraping"""
    
    def __init__(self, mongo_handler, comment_handler, context=None):
        """
        Args:
            mongo_handler: MongoHandler instance
            comment_handler: CommentHandler instance
            context: Playwright context (để lấy cookies cho requests)
        """
        self.mongo = mongo_handler
        self.comment_handler = comment_handler
        self.context = context  # Lưu context để dùng cho requests
    
    def scrape_single_chapter_using_browser(self, page, url, index, story_id, order, published_time_from_table):
        """
        ✅ CÁCH TỐI ƯU: Scrape chapter bằng browser chính đã mở (đã vượt Cloudflare)
        → Không bị 403 Forbidden (vì dùng browser đã verify)
        → Không bị lỗi Playwright Sync API (vì không tạo browser mới)
        → Ổn định nhất, reliable nhất
        
        Args:
            page: Playwright page object (browser chính đã mở)
            url: URL của chương cần cào
            index: Thứ tự chương trong list
            story_id: ID của story (FK)
            order: Số thứ tự của chapter (từ 1)
            published_time_from_table: published_time lấy từ table row
        """
        try:
            safe_print(f"    🔄 Đang cào chương {index + 1} bằng Browser chính...")
            
            # 1. Goto URL bằng browser đang mở (đã vượt Cloudflare)
            page.goto(url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            
            # 2. Random delay để giống người thật
            time.sleep(random.uniform(2.0, 4.0))
            
            # 3. Xử lý Cloudflare nếu vô tình gặp lại (Scroll nhẹ)
            page_content = page.content().lower()
            if any(x in page_content for x in ["challenges.cloudflare.com", "please unblock", "checking your browser"]):
                safe_print("      ⚠️ Gặp lại Cloudflare, đợi 5s...")
                time.sleep(5)
            
            # 4. Lấy nội dung từ div.chp_raw (giữ đúng format như UI)
            try:
                # Thử lấy từ #chp_raw hoặc .chp_raw
                page.wait_for_selector("#chp_raw, .chp_raw", timeout=10000)
            except:
                safe_print(f"      ⚠️ Không tìm thấy #chp_raw/.chp_raw (Timeout), thử fallback...")
            
            # Lấy chapter_name từ .chapter-title
            # HTML: <div class="chapter-title">Chapter 77: Instant KO Salamence</div>
            chapter_name = ""
            try:
                title_elem = page.locator(".chapter-title").first
                if title_elem.count() > 0:
                    chapter_name = title_elem.inner_text().strip()
                else:
                    # Fallback: thử h1
                    title_elem = page.locator("h1").first
                    if title_elem.count() > 0:
                        chapter_name = title_elem.inner_text().strip()
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi lấy chapter_name: {e}")
            
            content = ""
            try:
                # ✅ Ưu tiên lấy toàn bộ HTML trong #chp_raw/.chp_raw
                # và loại bỏ phần author notes (.wi_authornotes) bên trong
                content_container = page.locator("#chp_raw, .chp_raw").first
                if content_container.count() > 0:
                    try:
                        # Xóa tất cả .wi_authornotes bên trong chp_raw (Patreon, lời tác giả, v.v.)
                        page.evaluate(
                            """
                            (el) => {
                                if (!el) return;
                                const notes = el.querySelectorAll('.wi_authornotes');
                                notes.forEach(n => n.remove());
                            }
                            """,
                            content_container,
                        )
                    except Exception as _e:
                        # Nếu có lỗi khi evaluate JS thì bỏ qua, tiếp tục dùng HTML hiện tại
                        pass

                    # Lấy lại HTML sau khi đã loại bỏ author notes
                    html_content = content_container.inner_html()
                    content = convert_html_to_formatted_text(html_content)
                    safe_print(f"      ✅ Đã lấy content từ #chp_raw/.chp_raw ({len(content)} ký tự, đã bỏ author notes)")
                else:
                    # Fallback 1: Thử .chapter-inner với helper convert_html_to_formatted_text
                    try:
                        content_container = page.locator(".chapter-inner").first
                        if content_container.count() > 0:
                            html_content = content_container.inner_html()
                            content = convert_html_to_formatted_text(html_content)
                            safe_print("      ⚠️ Dùng fallback .chapter-inner")
                        else:
                            # Fallback 2: Lấy text thô toàn trang
                            content = page.locator("body").inner_text()
                            safe_print("      ⚠️ Dùng fallback body text")
                    except Exception:
                        pass
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi lấy content: {e}")
                try:
                    # Fallback cuối cùng
                    content = page.locator("body").inner_text()
                except Exception:
                    pass
            
            # 5. Lấy published_time nếu chưa có
            published_time = published_time_from_table
            if not published_time:
                try:
                    time_elem = page.locator("time[datetime]").first
                    if time_elem.count() > 0:
                        published_time = time_elem.get_attribute("datetime") or ""
                except:
                    pass
            
            # 6. Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    if "/chapter/" in url:
                        web_chapter_id = url.split("/chapter/")[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy web_chapter_id: {e}")
            
            # 7. Kiểm tra chapter đã có trong DB chưa (có thể chỉ có metadata từ table of contents)
            chapter_id = None
            existing_chapter = None
            if web_chapter_id and self.mongo.mongo_collection_chapters:
                try:
                    existing_chapter = self.mongo.mongo_collection_chapters.find_one({"web_chapter_id": web_chapter_id})
                    if existing_chapter:
                        chapter_id = existing_chapter.get("chapter_id")
                        # Kiểm tra xem đã có content chưa
                        if chapter_id and self.mongo.mongo_collection_chapter_contents:
                            content_doc = self.mongo.mongo_collection_chapter_contents.find_one({"chapter_id": chapter_id})
                            if content_doc and content_doc.get("content"):
                                safe_print(f"      ⏭️  Bỏ qua (Đã có content): {web_chapter_id}")
                                return None
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi kiểm tra chapter trong DB: {e}")
            
            # Nếu chưa có chapter_id, tạo mới
            if not chapter_id:
                chapter_id = generate_id()
            
            # 8. Lưu Content (chỉ nếu chưa có)
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
            
            # 9. Scrape comments (dùng page hiện tại)
            total_comments = 0
            try:
                comments_list = self.comment_handler.scrape_comments_worker(page, url, "chapter", chapter_id)
                total_comments = len(comments_list) if comments_list else 0
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi scrape comments: {e}")
            
            # 10. Lưu/Update Info (update nếu đã có metadata, insert nếu chưa có)
            chapter_data = {
                "chapter_id": chapter_id,
                "web_chapter_id": web_chapter_id,
                "order": order,
                "chapter_name": chapter_name,
                "chapter_url": url,
                "published_time": published_time,
                "story_id": story_id,
                "voted": "",
                "views": "",
                "total_comments": str(total_comments)
            }
            
            self.mongo.save_chapter(chapter_data)
            safe_print(f"      ✅ Đã cào chương {index + 1} bằng Browser chính!")
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"❌ Lỗi cào chương {index + 1}: {e}")
            return None
    
    def scrape_single_chapter_with_requests(self, url, index, story_id, order, published_time_from_table, session=None):
        """
        ✅ CÁCH 5: Scrape chapter bằng requests (không dùng Playwright)
        → Không bị detect như bot headless
        → Nhanh hơn, ổn định hơn
        
        Args:
            url: URL của chương cần cào
            index: Thứ tự chương trong list
            story_id: ID của story (FK)
            order: Số thứ tự của chapter (từ 1)
            published_time_from_table: published_time lấy từ table row
            session: requests.Session (nếu None thì tạo mới từ context)
        """
        try:
            safe_print(f"    📄 Đang cào chương {index + 1} bằng requests...")
            
            # ✅ CÁCH 4: Random delay như người thật
            delay = random.uniform(2.5, 6.0)  # Random 2.5-6 giây
            time.sleep(delay)
            
            # Tạo session từ context nếu chưa có
            if session is None and self.context:
                # Lấy user_agent từ context options (không phải dict)
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                session = get_session_from_context(self.context, user_agent)
            
            if session is None:
                safe_print(f"      ⚠️ Không có session, dùng Playwright fallback...")
                return self.scrape_single_chapter_worker(url, index, story_id, order, published_time_from_table)
            
            # Scrape bằng requests
            chapter_data = scrape_chapter_with_requests(session, url)
            
            if not chapter_data:
                safe_print(f"      ⚠️ Requests failed, dùng Playwright fallback...")
                return self.scrape_single_chapter_worker(url, index, story_id, order, published_time_from_table)
            
            # Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    url_parts = url.split("/chapter/")
                    if len(url_parts) > 1:
                        web_chapter_id = url_parts[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy web_chapter_id: {e}")
            
            # Kiểm tra đã có chưa
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"      ⏭️  Bỏ qua chapter {web_chapter_id} (đã có trong DB)")
                return None
            
            chapter_id = generate_id()
            title = chapter_data.get('title', '')
            content = chapter_data.get('content', '')
            published_time = published_time_from_table or chapter_data.get('published_time', '')
            
            # Lưu content
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
            
            # Comments - vẫn cần Playwright cho comments (có thể cải thiện sau)
            # Tạm thời bỏ qua comments khi dùng requests
            total_comments = 0
            
            # Lấy views và voted từ requests (cần parse HTML)
            views = ""
            voted = ""
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(session.get(url).text, 'html.parser')
                stats_container = soup.select_one(".chapter_stats")
                if stats_container:
                    stats_items = stats_container.select(".chp_stats_feature")
                    for item in stats_items:
                        icon = item.select_one("i")
                        if icon and "fa-eye" in icon.get("class", []):
                            text = item.get_text(strip=True)
                            numbers = re.findall(r'\d+', text)
                            if numbers:
                                views = numbers[0]
                        elif icon and "fa-heart" in icon.get("class", []):
                            heart_cnt = item.select_one("#heart_cnt")
                            if heart_cnt:
                                voted = heart_cnt.get_text(strip=True)
                            else:
                                text = item.get_text(strip=True)
                                numbers = re.findall(r'\d+', text)
                                if numbers:
                                    voted = numbers[0]
            except:
                pass
            
            chapter_data_dict = {
                "chapter_id": chapter_id,  # Khóa chính (không phải "id")
                "web_chapter_id": web_chapter_id,
                "order": order,
                "chapter_name": title,  # Không phải "name"
                "chapter_url": url,  # Không phải "url"
                "published_time": published_time,
                "story_id": story_id,
                "voted": voted,
                "views": views,
                "total_comments": str(total_comments)
            }
            
            self.mongo.save_chapter(chapter_data_dict)
            safe_print(f"      ✅ Đã cào chương {index + 1} bằng requests!")
            
            return chapter_data_dict
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi scrape chapter bằng requests: {e}")
            # Fallback về Playwright
            return self.scrape_single_chapter_worker(url, index, story_id, order, published_time_from_table)
    
    def scrape_single_chapter_worker(self, url, index, story_id, order, published_time_from_table):
        """
        Worker function để cào MỘT chương bằng Playwright (fallback)
        """
        worker_playwright = None
        worker_browser = None
        
        try:
            # ✅ CÁCH 4: Random delay
            delay = random.uniform(2.5, 6.0)
            time.sleep(delay)
            
            worker_playwright = sync_playwright().start()
            worker_browser = worker_playwright.chromium.launch(headless=config.HEADLESS)
            worker_context = worker_browser.new_context()
            worker_page = worker_context.new_page()
            
            safe_print(f"    🔄 Thread-{index}: Đang cào chương {index + 1} (Playwright fallback)")
            
            worker_page.goto(url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            
            # ✅ CÁCH 4: Random delay
            time.sleep(random.uniform(1.0, 3.0))
            
            # ✅ Lấy từ div.chp_raw (giữ đúng format như UI)
            worker_page.wait_for_selector("#chp_raw, .chp_raw", timeout=15000)
            
            title = worker_page.locator("h1").first.inner_text()
            
            published_time = published_time_from_table
            if not published_time:
                try:
                    time_elem = worker_page.locator("time[datetime]").first
                    if time_elem.count() > 0:
                        published_time = time_elem.get_attribute("datetime") or ""
                except:
                    pass
            
            content = ""
            try:
                # ✅ Lấy từ div.chp_raw (có nhiều thẻ p, giữ đúng format như UI)
                content_container = worker_page.locator("#chp_raw, .chp_raw").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content = convert_html_to_formatted_text(html_content)
                else:
                    # Fallback: Thử .chapter-inner
                    try:
                        content_container = worker_page.locator(".chapter-inner").first
                        if content_container.count() > 0:
                            html_content = content_container.inner_html()
                            content = convert_html_to_formatted_text(html_content)
                        else:
                            content = worker_page.locator("body").inner_text()
                    except:
                        content = worker_page.locator("body").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy content: {e}")
                try:
                    content = worker_page.locator("#chp_raw, .chp_raw").inner_text()
                except:
                    content = worker_page.locator("body").inner_text()
            
            # ✅ CÁCH 4: Random delay
            time.sleep(random.uniform(1.0, 3.0))
            
            # Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    url_parts = url.split("/chapter/")
                    if len(url_parts) > 1:
                        web_chapter_id = url_parts[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy web_chapter_id từ URL: {e}")
                web_chapter_id = ""
            
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"      ⏭️  Thread-{index}: Bỏ qua chapter {web_chapter_id} (đã có trong DB)")
                return None
            
            chapter_id = generate_id()
            
            comments_list = self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", chapter_id)
            total_comments = len(comments_list) if comments_list else 0
            
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
            
            chapter_data = {
                "id": chapter_id,
                "web_chapter_id": web_chapter_id,
                "order": order,
                "name": title,
                "url": url,
                "published_time": published_time,
                "story_id": story_id,
                "voted": "",
                "views": "",
                "total_comments": str(total_comments)
            }
            
            self.mongo.save_chapter(chapter_data)
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"⚠️ Thread-{index}: Lỗi cào chương {index + 1}: {e}")
            return None
        finally:
            if worker_browser:
                worker_browser.close()
            if worker_playwright:
                worker_playwright.stop()
