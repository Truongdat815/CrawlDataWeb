"""
Chapter Sync Worker
Sync chapters dựa trên hash content để phát hiện thay đổi.
Chỉ crawl lại chapter khi hash khác → cực nhanh và hiệu quả.
"""
import time
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
from src import config, utils

# Helper function để print an toàn với encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

class ChapterSyncWorker:
    """
    Worker để sync chapters đã crawl.
    Sử dụng hash để phát hiện thay đổi content → chỉ crawl lại chapter bị sửa.
    """
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.mongo_client = None
        self.mongo_db = None
        self.mongo_collection = None
        
        # Kết nối MongoDB
        if config.MONGODB_ENABLED:
            try:
                self.mongo_client = MongoClient(config.MONGODB_URI)
                self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                self.mongo_collection = self.mongo_db[config.MONGODB_COLLECTION_FICTIONS]
                safe_print("✅ Đã kết nối MongoDB")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                self.mongo_client = None
    
    def start(self):
        """Khởi động trình duyệt"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=config.HEADLESS)
        self.page = self.browser.new_page()
        safe_print("✅ Chapter Sync Worker đã khởi động!")
    
    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.mongo_client:
            self.mongo_client.close()
        safe_print("✅ Chapter Sync Worker đã tắt.")
    
    def fetch_chapter_metadata_list(self, fiction_url):
        """
        Lấy danh sách metadata của tất cả chapters (không crawl content).
        Rất nhẹ, chỉ lấy: chapter_id, title, url, updated_at (nếu có).
        
        Returns:
            list: Danh sách chapter metadata
        """
        try:
            self.page.goto(fiction_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Lấy chapters từ trang đầu tiên
            chapter_urls = []
            chapter_rows = self.page.locator("table#chapters tbody tr").all()
            
            for row in chapter_rows:
                try:
                    link_el = row.locator("td").first.locator("a")
                    if link_el.count() > 0:
                        url = link_el.get_attribute("href")
                        title = link_el.inner_text()
                        if url:
                            if url.startswith("/"):
                                full_url = config.BASE_URL + url
                            elif url.startswith("http"):
                                full_url = url
                            else:
                                full_url = config.BASE_URL + "/" + url
                            
                            # Extract chapter_id từ URL
                            chapter_id = None
                            try:
                                url_parts = full_url.split("/chapter/")
                                if len(url_parts) > 1:
                                    chapter_id = url_parts[1].split("/")[0]
                            except:
                                pass
                            
                            chapter_urls.append({
                                "chapter_id": chapter_id,
                                "title": title,
                                "url": full_url
                            })
                except:
                    continue
            
            # TODO: Có thể mở rộng để lấy từ pagination nếu cần
            # Nhưng để đơn giản, chỉ lấy từ trang đầu tiên
            
            return chapter_urls
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi fetch chapter list: {e}")
            return []
    
    def fetch_chapter_content(self, chapter_url):
        """
        Crawl content của một chapter.
        
        Returns:
            dict: Chapter data với content hoặc None nếu lỗi
        """
        try:
            self.page.goto(chapter_url, timeout=config.TIMEOUT)
            self.page.wait_for_selector(".chapter-inner", timeout=10000)
            time.sleep(1)
            
            title = self.page.locator("h1").first.inner_text()
            
            # Lấy content
            content = ""
            try:
                from src.scraper_engine import RoyalRoadScraper
                # Tạo instance tạm để dùng hàm helper
                temp_scraper = RoyalRoadScraper()
                content_container = self.page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content = temp_scraper._convert_html_to_formatted_text(html_content)
                else:
                    content = self.page.locator(".chapter-inner").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy content: {e}")
                content = self.page.locator(".chapter-inner").inner_text()
            
            # Extract chapter_id
            chapter_id = None
            try:
                url_parts = chapter_url.split("/chapter/")
                if len(url_parts) > 1:
                    chapter_id = url_parts[1].split("/")[0]
            except:
                pass
            
            # Tính hash
            content_hash = utils.hash_content(content)
            current_time = utils.get_current_timestamp()
            
            return {
                "chapter_id": chapter_id,
                "url": chapter_url,
                "title": title,
                "content_text": content,
                "content_hash": content_hash,
                "content_length": len(content),
                "updated_at": current_time,
                "last_synced_at": current_time
            }
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi fetch chapter content: {e}")
            return None
    
    def sync_chapter(self, fiction_id, chapter_data_from_db, chapter_url):
        """
        Sync một chapter bằng cách so sánh hash.
        
        Args:
            fiction_id: ID của fiction
            chapter_data_from_db: Chapter data từ DB (có thể None nếu chapter mới)
            chapter_url: URL của chapter cần sync
        
        Returns:
            dict: Chapter data mới hoặc None nếu không thay đổi
        """
        try:
            # Fetch content mới
            new_chapter_data = self.fetch_chapter_content(chapter_url)
            if not new_chapter_data:
                return None
            
            # Nếu chưa có chapter trong DB → đây là chapter mới
            if not chapter_data_from_db:
                safe_print(f"      ➕ Chapter mới: {new_chapter_data.get('title', 'N/A')}")
                return new_chapter_data
            
            # So sánh hash
            old_hash = chapter_data_from_db.get("content_hash", "")
            new_hash = new_chapter_data["content_hash"]
            
            if old_hash == new_hash:
                # Không thay đổi
                safe_print(f"      ✅ Chapter không thay đổi: {new_chapter_data.get('title', 'N/A')}")
                # Chỉ cập nhật last_synced_at
                return {
                    **chapter_data_from_db,
                    "last_synced_at": utils.get_current_timestamp()
                }
            else:
                # Có thay đổi → Update
                safe_print(f"      🔄 Chapter đã thay đổi: {new_chapter_data.get('title', 'N/A')}")
                safe_print(f"         Hash cũ: {old_hash[:16]}...")
                safe_print(f"         Hash mới: {new_hash[:16]}...")
                return new_chapter_data
                
        except Exception as e:
            safe_print(f"      ❌ Lỗi khi sync chapter: {e}")
            return None
    
    def sync_fiction_chapters(self, fiction_id, fiction_url, max_chapters=20):
        """
        Sync chapters của một fiction.
        Chỉ sync những chapter có khả năng thay đổi (dựa trên metadata hoặc random check).
        
        Args:
            fiction_id: ID của fiction
            fiction_url: URL của fiction
            max_chapters: Số lượng chapter tối đa để sync mỗi lần
        """
        if not self.mongo_collection:
            safe_print("❌ Không có kết nối MongoDB")
            return
        
        try:
            # Lấy fiction từ DB
            fiction = self.mongo_collection.find_one({"id": fiction_id})
            if not fiction:
                safe_print(f"      ⚠️ Fiction {fiction_id} không tồn tại trong DB")
                return
            
            # Lấy danh sách chapters từ DB
            chapters_from_db = fiction.get("chapters", [])
            
            # Tạo map: chapter_id hoặc url → chapter data
            chapter_map = {}
            for chap in chapters_from_db:
                key = chap.get("chapter_id") or chap.get("url")
                if key:
                    chapter_map[key] = chap
            
            # Fetch danh sách chapters từ web (metadata only)
            safe_print(f"      📄 Đang lấy danh sách chapters từ web...")
            chapter_list_web = self.fetch_chapter_metadata_list(fiction_url)
            
            if not chapter_list_web:
                safe_print(f"      ⚠️ Không lấy được danh sách chapters")
                return
            
            # Giới hạn số lượng chapters để sync
            chapters_to_sync = chapter_list_web[:max_chapters]
            
            safe_print(f"      🔄 Bắt đầu sync {len(chapters_to_sync)} chapters...")
            
            updated_chapters = []
            new_chapters = []
            unchanged_chapters = []
            
            for chapter_meta in chapters_to_sync:
                chapter_url = chapter_meta["url"]
                chapter_id = chapter_meta.get("chapter_id")
                
                # Tìm chapter trong DB
                chapter_from_db = None
                if chapter_id and chapter_id in chapter_map:
                    chapter_from_db = chapter_map[chapter_id]
                elif chapter_url in chapter_map:
                    chapter_from_db = chapter_map[chapter_url]
                
                # Sync chapter
                synced_chapter = self.sync_chapter(fiction_id, chapter_from_db, chapter_url)
                
                if synced_chapter:
                    if not chapter_from_db:
                        new_chapters.append(synced_chapter)
                    elif synced_chapter.get("content_hash") != chapter_from_db.get("content_hash"):
                        updated_chapters.append(synced_chapter)
                    else:
                        unchanged_chapters.append(synced_chapter)
                
                # Delay giữa các chapters
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Cập nhật DB
            if updated_chapters or new_chapters:
                # Merge chapters: giữ chapters cũ, update/chèn chapters mới
                all_chapters = list(chapters_from_db)
                
                # Update chapters đã thay đổi
                for updated_chap in updated_chapters:
                    updated_id = updated_chap.get("chapter_id") or updated_chap.get("url")
                    found = False
                    for i, old_chap in enumerate(all_chapters):
                        old_id = old_chap.get("chapter_id") or old_chap.get("url")
                        if old_id == updated_id:
                            all_chapters[i] = updated_chap
                            found = True
                            break
                    if not found:
                        all_chapters.append(updated_chap)
                
                # Thêm chapters mới
                for new_chap in new_chapters:
                    new_id = new_chap.get("chapter_id") or new_chap.get("url")
                    # Kiểm tra xem đã có chưa
                    exists = False
                    for old_chap in all_chapters:
                        old_id = old_chap.get("chapter_id") or old_chap.get("url")
                        if old_id == new_id:
                            exists = True
                            break
                    if not exists:
                        all_chapters.append(new_chap)
                
                # Cập nhật DB
                self.mongo_collection.update_one(
                    {"id": fiction_id},
                    {
                        "$set": {
                            "chapters": all_chapters,
                            "updated_at": utils.get_current_timestamp()
                        }
                    }
                )
                
                safe_print(f"      ✅ Đã cập nhật: {len(updated_chapters)} chapters thay đổi, {len(new_chapters)} chapters mới")
            else:
                safe_print(f"      ✅ Không có chapter nào thay đổi")
            
        except Exception as e:
            safe_print(f"      ❌ Lỗi khi sync chapters Fiction {fiction_id}: {e}")
    
    def sync_batch(self, num_fictions=5, max_chapters_per_fiction=10):
        """
        Sync chapters của một batch fictions.
        
        Args:
            num_fictions: Số lượng fiction cần sync
            max_chapters_per_fiction: Số chapter tối đa sync mỗi fiction
        """
        if not self.mongo_collection:
            safe_print("❌ Không có kết nối MongoDB")
            return
        
        try:
            # Lấy danh sách fiction
            fictions = list(self.mongo_collection.find().limit(num_fictions))
            
            if not fictions:
                safe_print("📭 Không có fiction nào trong DB")
                return
            
            safe_print(f"🔄 Bắt đầu sync chapters cho {len(fictions)} fiction...")
            
            for fiction in fictions:
                fiction_id = fiction.get("id")
                fiction_url = fiction.get("fiction_url")
                
                if not fiction_url:
                    fiction_url = f"{config.BASE_URL}/fiction/{fiction_id}"
                
                safe_print(f"\n📖 Đang sync Fiction {fiction_id}...")
                self.sync_fiction_chapters(fiction_id, fiction_url, max_chapters_per_fiction)
                
                # Delay giữa các fiction
                time.sleep(config.DELAY_BETWEEN_CHAPTERS * 2)
            
            safe_print(f"\n✅ Hoàn thành sync chapters!")
            
        except Exception as e:
            safe_print(f"❌ Lỗi khi sync batch: {e}")

def main():
    """Chạy chapter sync worker"""
    worker = ChapterSyncWorker()
    
    try:
        worker.start()
        # Sync 5 fiction, mỗi fiction 10 chapters
        worker.sync_batch(num_fictions=5, max_chapters_per_fiction=10)
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
    finally:
        worker.stop()

if __name__ == "__main__":
    main()

