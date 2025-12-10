"""
Chapter handler - xử lý chapter content scraping
"""
import time
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text, goto_with_retry, wait_for_selector_with_retry


class ChapterHandler:
    """Handler cho chapter content scraping"""
    
    def __init__(self, mongo_handler, comment_handler):
        """
        Args:
            mongo_handler: MongoHandler instance
            comment_handler: CommentHandler instance
        """
        self.mongo = mongo_handler
        self.comment_handler = comment_handler
    
    def scrape_single_chapter_worker(self, url, index, story_id, order, published_time_from_table):
        """
        Worker function để cào MỘT chương - mỗi worker có browser instance riêng
        Thread-safe: Mỗi worker có browser instance riêng
        
        Args:
            url: URL của chương cần cào
            index: Thứ tự chương trong list
            story_id: ID của story (FK)
            order: Số thứ tự của chapter (từ 1)
            published_time_from_table: published_time lấy từ table row
        """
        worker_playwright = None
        worker_browser = None
        
        try:
            time.sleep(index * config.DELAY_THREAD_START)
            
            worker_playwright = sync_playwright().start()
            worker_browser = worker_playwright.chromium.launch(headless=config.HEADLESS)
            worker_context = worker_browser.new_context()
            worker_page = worker_context.new_page()
            
            safe_print(f"    🔄 Thread-{index}: Đang cào chương {index + 1}")
            
            # Kiểm tra chapter đã có trong DB chưa theo URL - nếu có rồi thì chỉ scrape comments
            if url and self.mongo.is_chapter_scraped(url):
                safe_print(f"      ⏭️  Thread-{index}: Chapter với URL {url} đã có trong DB, chỉ scrape comments")
                existing_chapter = self.mongo.get_chapter_by_url(url)
                existing_chapter_id = existing_chapter.get("chapterId") if existing_chapter else None
                if existing_chapter_id:
                    # Navigate đến chapter URL để scrape comments
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                    goto_with_retry(worker_page, url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name=f"Thread-{index}")
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                    # Chỉ scrape comments, không scrape chapter content
                    self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", existing_chapter_id)
                return None
            
            # Lấy web_chapter_id từ URL để lưu vào chapter_data
            web_chapter_id = None
            try:
                url_parts = url.split("/chapter/")
                if len(url_parts) > 1:
                    web_chapter_id = url_parts[1].split("/")[0]
            except:
                web_chapter_id = None
            
            # Chapter chưa có trong DB, scrape chapter content
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            goto_with_retry(worker_page, url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name=f"Thread-{index}")
            wait_for_selector_with_retry(worker_page, ".chapter-inner", 10000, max_retries=3, retry_delay=2, context_name=f"Thread-{index}")
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            title = worker_page.locator("h1").first.inner_text()
            
            published_time = published_time_from_table
            # Nếu published_time_from_table chưa được format (có thể là ISO format), format lại
            if published_time and ("T" in published_time or published_time.endswith("Z")):
                try:
                    from src.utils import parse_and_format_datetime
                    published_time = parse_and_format_datetime(published_time)
                except:
                    pass
            
            if not published_time:
                try:
                    time_elem = worker_page.locator("time").first
                    if time_elem.count() > 0:
                        datetime_attr = time_elem.get_attribute("datetime")
                        if datetime_attr:
                            from src.utils import parse_and_format_datetime
                            published_time = parse_and_format_datetime(datetime_attr)
                except:
                    pass
            
            content = None
            try:
                content_container = worker_page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content_value = convert_html_to_formatted_text(html_content)
                    content = content_value if content_value else None
                else:
                    content_value = worker_page.locator(".chapter-inner").inner_text()
                    content = content_value if content_value else None
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy content: {e}")
                content = worker_page.locator(".chapter-inner").inner_text()
            
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            chapter_id = generate_id()
            
            # Lưu chapter content trước
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
                else:
                    safe_print(f"      ⏭️  Thread-{index}: Bỏ qua content chapter {web_chapter_id} (đã có trong DB)")
            
            # Tạo và lưu chapter_data vào DB TRƯỚC khi scrape comments
            chapter_data = {
                "chapterId": chapter_id,
                "webChapterId": web_chapter_id,
                "order": order,
                "chapterName": title,
                "chapterUrl": url,
                "publishedTime": published_time,
                "storyId": story_id,
                "voted": None,
                "views": None,
                "totalComments": None
            }
            
            self.mongo.save_chapter(chapter_data)
            safe_print(f"      ✅ Thread-{index}: Đã lưu chapter với URL {url} vào DB")
            
            # Sau khi lưu chapter vào DB, mới scrape comments
            safe_print(f"      💬 Thread-{index}: Đang lấy comments cho chương")
            self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", chapter_id)
            
            time.sleep(config.DELAY_BETWEEN_CHAPTERS)
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"⚠️ Thread-{index}: Lỗi cào chương {index + 1}: {e}")
            return None
        finally:
            if worker_browser:
                worker_browser.close()
            if worker_playwright:
                worker_playwright.stop()

