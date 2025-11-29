"""
Metadata Sync Worker
Sync metadata của fictions (title, stats, tags, description) dựa trên metadata_hash.
Chạy background để cập nhật dữ liệu đã crawl trước đó mà không cần crawl lại toàn bộ.
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

class MetadataSyncWorker:
    """
    Worker để sync metadata của fictions đã crawl.
    Chỉ crawl metadata (rất nhẹ) → so sánh hash → update nếu khác.
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
        safe_print("✅ Metadata Sync Worker đã khởi động!")
    
    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.mongo_client:
            self.mongo_client.close()
        safe_print("✅ Metadata Sync Worker đã tắt.")
    
    def fetch_fiction_metadata(self, fiction_url):
        """
        Chỉ crawl metadata của fiction (không crawl chapters).
        Rất nhẹ và nhanh.
        
        Returns:
            dict: Metadata dict hoặc None nếu lỗi
        """
        try:
            self.page.goto(fiction_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Lấy các metadata giống như scraper chính
            title = self.page.locator("h1").first.inner_text()
            author = self.page.locator(".fic-title h4 a").first.inner_text()
            category = self.page.locator(".fiction-info span").first.inner_text()
            status = self.page.locator(".fiction-info span:nth-child(2)").first.inner_text()
            tags = self.page.locator(".tags a").all_inner_texts()
            
            # Description
            description = ""
            try:
                desc_container = self.page.locator(".description").first
                if desc_container.count() > 0:
                    html_content = desc_container.inner_html()
                    # Sử dụng hàm từ scraper_engine
                    from src.scraper_engine import RoyalRoadScraper
                    # Tạo instance tạm để dùng hàm helper
                    temp_scraper = RoyalRoadScraper()
                    description = temp_scraper._convert_html_to_formatted_text(html_content)
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy description: {e}")
            
            # Stats
            base_locator = ".stats-content ul.list-unstyled li:nth-child({}) span"
            overall_score = self.page.locator(base_locator.format(2)).inner_text()
            style_score = self.page.locator(base_locator.format(4)).inner_text()
            story_score = self.page.locator(base_locator.format(6)).inner_text()
            grammar_score = self.page.locator(base_locator.format(8)).inner_text()
            character_score = self.page.locator(base_locator.format(10)).inner_text()
            
            stats_values_locator = self.page.locator("div.col-sm-6 li.font-red-sunglo")
            total_views = stats_values_locator.nth(0).inner_text()
            average_views = stats_values_locator.nth(1).inner_text()
            followers = stats_values_locator.nth(2).inner_text()
            favorites = stats_values_locator.nth(3).inner_text()
            ratings = stats_values_locator.nth(4).inner_text()
            pages = stats_values_locator.nth(5).inner_text()
            
            # Tạo metadata dict
            metadata_dict = {
                "title": title,
                "author": author,
                "category": category,
                "status": status,
                "tags": sorted(tags) if tags else [],
                "description": description,
                "stats": {
                    "score": {
                        "overall_score": overall_score,
                        "style_score": style_score,
                        "story_score": story_score,
                        "grammar_score": grammar_score,
                        "character_score": character_score,
                    },
                    "views": {
                        "total_views": total_views,
                        "average_views": average_views,
                        "followers": followers,
                        "favorites": favorites,
                        "ratings": ratings,
                        "page_views": pages,
                    }
                }
            }
            
            return metadata_dict
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi fetch metadata: {e}")
            return None
    
    def sync_fiction_metadata(self, fiction_id, fiction_url):
        """
        Sync metadata của một fiction.
        
        Returns:
            bool: True nếu có thay đổi và đã update, False nếu không thay đổi
        """
        try:
            # Lấy fiction từ DB
            existing = self.mongo_collection.find_one({"id": fiction_id})
            if not existing:
                safe_print(f"      ⚠️ Fiction {fiction_id} không tồn tại trong DB")
                return False
            
            # Fetch metadata mới từ web
            new_metadata = self.fetch_fiction_metadata(fiction_url)
            if not new_metadata:
                return False
            
            # Tính hash metadata mới
            new_metadata_hash = utils.hash_metadata(new_metadata)
            old_metadata_hash = existing.get("metadata_hash", "")
            
            # So sánh hash
            if old_metadata_hash == new_metadata_hash:
                # Không thay đổi
                safe_print(f"      ✅ Fiction {fiction_id}: Metadata không thay đổi")
                # Cập nhật last_synced_at
                self.mongo_collection.update_one(
                    {"id": fiction_id},
                    {"$set": {"last_synced_at": utils.get_current_timestamp()}}
                )
                return False
            else:
                # Có thay đổi → Update
                safe_print(f"      🔄 Fiction {fiction_id}: Metadata đã thay đổi → Đang cập nhật...")
                
                # Cập nhật metadata
                update_data = {
                    "title": new_metadata["title"],
                    "author": new_metadata["author"],
                    "category": new_metadata["category"],
                    "status": new_metadata["status"],
                    "tags": new_metadata["tags"],
                    "description": new_metadata["description"],
                    "stats": new_metadata["stats"],
                    "metadata_hash": new_metadata_hash,
                    "updated_at": utils.get_current_timestamp(),
                    "last_synced_at": utils.get_current_timestamp()
                }
                
                self.mongo_collection.update_one(
                    {"id": fiction_id},
                    {"$set": update_data}
                )
                
                safe_print(f"      ✅ Đã cập nhật metadata cho Fiction {fiction_id}")
                return True
                
        except Exception as e:
            safe_print(f"      ❌ Lỗi khi sync metadata Fiction {fiction_id}: {e}")
            return False
    
    def sync_batch(self, num_fictions=10, max_age_hours=24):
        """
        Sync metadata của một batch fictions.
        Ưu tiên sync những fiction lâu chưa được sync.
        
        Args:
            num_fictions: Số lượng fiction cần sync
            max_age_hours: Chỉ sync fiction chưa sync trong X giờ
        """
        if not self.mongo_collection:
            safe_print("❌ Không có kết nối MongoDB")
            return
        
        try:
            # Tính thời gian cutoff
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            cutoff_iso = cutoff_time.isoformat()
            
            # Lấy danh sách fiction cần sync
            # Ưu tiên: last_synced_at cũ nhất hoặc chưa có last_synced_at
            query = {
                "$or": [
                    {"last_synced_at": {"$exists": False}},
                    {"last_synced_at": {"$lt": cutoff_iso}},
                    {"last_synced_at": None}
                ]
            }
            
            fictions = list(self.mongo_collection.find(query).limit(num_fictions))
            
            if not fictions:
                safe_print("📭 Không có fiction nào cần sync metadata")
                return
            
            safe_print(f"🔄 Bắt đầu sync metadata cho {len(fictions)} fiction...")
            
            updated_count = 0
            for fiction in fictions:
                fiction_id = fiction.get("id")
                fiction_url = fiction.get("fiction_url")
                
                if not fiction_url:
                    # Tạo URL từ ID
                    fiction_url = f"{config.BASE_URL}/fiction/{fiction_id}"
                
                if self.sync_fiction_metadata(fiction_id, fiction_url):
                    updated_count += 1
                
                # Delay giữa các fiction
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            safe_print(f"\n✅ Hoàn thành sync metadata: {updated_count}/{len(fictions)} fiction được cập nhật")
            
        except Exception as e:
            safe_print(f"❌ Lỗi khi sync batch: {e}")

def main():
    """Chạy metadata sync worker"""
    worker = MetadataSyncWorker()
    
    try:
        worker.start()
        # Sync 10 fiction mỗi lần
        worker.sync_batch(num_fictions=10, max_age_hours=24)
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
    finally:
        worker.stop()

if __name__ == "__main__":
    main()

