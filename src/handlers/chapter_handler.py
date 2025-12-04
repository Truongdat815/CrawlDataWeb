"""
Chapter handler - xử lý chapter content scraping
"""
import time
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text


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
            
            # Lấy web_chapter_id từ URL TRƯỚC để kiểm tra chapter đã có chưa
            web_chapter_id = ""
            try:
                url_parts = url.split("/chapter/")
                if len(url_parts) > 1:
                    web_chapter_id = url_parts[1].split("/")[0]
            except:
                web_chapter_id = ""
            
            # Kiểm tra chapter đã có trong DB chưa - nếu có rồi thì chỉ scrape comments
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"      ⏭️  Thread-{index}: Chapter {web_chapter_id} đã có trong DB, chỉ scrape comments")
                existing_chapter = self.mongo.get_chapter_by_web_id(web_chapter_id)
                existing_chapter_id = existing_chapter.get("chapter_id") if existing_chapter else None
                if existing_chapter_id:
                    # Navigate đến chapter URL để scrape comments
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                    worker_page.goto(url, timeout=config.TIMEOUT)
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                    # Chỉ scrape comments, không scrape chapter content
                    self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", existing_chapter_id)
                return None
            
            # Chapter chưa có trong DB, scrape chapter content
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            worker_page.goto(url, timeout=config.TIMEOUT)
            worker_page.wait_for_selector(".chapter-inner", timeout=10000)
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
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
                content_container = worker_page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content = convert_html_to_formatted_text(html_content)
                else:
                    content = worker_page.locator(".chapter-inner").inner_text()
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
                "chapter_id": chapter_id,
                "web_chapter_id": web_chapter_id,
                "order": order,
                "chapter_name": title,
                "chapter_url": url,
                "published_time": published_time,
                "story_id": story_id,
                "voted": "",
                "views": "",
                "total_comments": ""
            }
            
            self.mongo.save_chapter(chapter_data)
            safe_print(f"      ✅ Thread-{index}: Đã lưu chapter {web_chapter_id} vào DB")
            
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

