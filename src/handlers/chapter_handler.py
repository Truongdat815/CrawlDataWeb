"""
Chapter handler - xử lý chapter content scraping
"""
import time
import re
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
            
            # Lấy web_chapter_id từ URL (Ví dụ: từ https://www.scribblehub.com/read/123456-story-name/chapter/789012/ lấy 789012)
            web_chapter_id = ""
            try:
                # Tìm pattern /chapter/789012
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    # Fallback: split theo /chapter/
                    url_parts = url.split("/chapter/")
                    if len(url_parts) > 1:
                        web_chapter_id = url_parts[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy web_chapter_id từ URL: {e}")
                web_chapter_id = ""
            
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"      ⏭️  Thread-{index}: Bỏ qua chapter {web_chapter_id} (đã có trong DB)")
                existing_chapter = self.mongo.get_chapter_by_web_id(web_chapter_id)
                existing_chapter_id = existing_chapter.get("id") if existing_chapter else None
                if existing_chapter_id:
                    comments_list = self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", existing_chapter_id)
                    total_comments = len(comments_list) if comments_list else 0
                    # Cập nhật total_comments cho chapter đã có
                    if existing_chapter:
                        self.mongo.mongo_collection_chapters.update_one(
                            {"id": existing_chapter_id},
                            {"$set": {"total_comments": str(total_comments)}}
                        )
                return None
            
            chapter_id = generate_id()
            
            safe_print(f"      💬 Thread-{index}: Đang lấy comments cho chương")
            comments_list = self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", chapter_id)
            total_comments = len(comments_list) if comments_list else 0
            
            time.sleep(config.DELAY_BETWEEN_CHAPTERS)
            
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
                else:
                    safe_print(f"      ⏭️  Thread-{index}: Bỏ qua content chapter {web_chapter_id} (đã có trong DB)")
            
            # Lấy views và voted từ chapter page
            views = ""
            voted = ""
            try:
                # Tìm views từ các selector có thể có
                views_selectors = [
                    ".chapter-stats .views",
                    ".stats .views",
                    "[class*='view']",
                    ".chapter-meta [class*='view']"
                ]
                for selector in views_selectors:
                    try:
                        views_elem = worker_page.locator(selector).first
                        if views_elem.count() > 0:
                            views_text = views_elem.inner_text().strip()
                            # Extract số từ text (có thể có format như "1.2k", "500", etc.)
                            numbers = re.findall(r'[\d.]+[kmKM]?', views_text)
                            if numbers:
                                views = numbers[0].replace(",", "")
                            break
                    except:
                        continue
                
                # Tìm voted từ các selector có thể có
                voted_selectors = [
                    ".chapter-stats .votes",
                    ".stats .votes",
                    "[class*='vote']",
                    ".chapter-meta [class*='vote']"
                ]
                for selector in voted_selectors:
                    try:
                        voted_elem = worker_page.locator(selector).first
                        if voted_elem.count() > 0:
                            voted_text = voted_elem.inner_text().strip()
                            # Extract số từ text
                            numbers = re.findall(r'[\d.]+[kmKM]?', voted_text)
                            if numbers:
                                voted = numbers[0].replace(",", "")
                            break
                    except:
                        continue
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy views/voted: {e}")
            
            chapter_data = {
                "id": chapter_id,
                "web_chapter_id": web_chapter_id,
                "order": order,
                "name": title,
                "url": url,
                "published_time": published_time,
                "story_id": story_id,
                "voted": voted,
                "views": views,
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

