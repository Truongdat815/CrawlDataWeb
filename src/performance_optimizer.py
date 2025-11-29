"""
Performance Optimizer - Các tối ưu để tăng tốc độ crawl/sync
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import UpdateOne
from src import config

class BrowserPool:
    """
    Browser Pool để tái sử dụng browser instances
    Giảm thời gian khởi động browser
    """
    def __init__(self, pool_size=4):
        self.pool_size = pool_size
        self.pool = []
        self.lock = None
        self.playwright = None
        
    def initialize(self):
        """Khởi tạo pool"""
        from threading import Lock
        from playwright.sync_api import sync_playwright
        
        self.lock = Lock()
        self.playwright = sync_playwright().start()
        
        # Tạo pool browsers
        for _ in range(self.pool_size):
            browser = self.playwright.chromium.launch(headless=config.HEADLESS)
            self.pool.append(browser)
    
    def get_browser(self):
        """Lấy browser từ pool"""
        if not self.pool:
            # Nếu pool rỗng, tạo mới
            return self.playwright.chromium.launch(headless=config.HEADLESS)
        return self.pool.pop()
    
    def return_browser(self, browser):
        """Trả browser về pool"""
        if len(self.pool) < self.pool_size:
            self.pool.append(browser)
        else:
            browser.close()
    
    def close_all(self):
        """Đóng tất cả browsers"""
        for browser in self.pool:
            browser.close()
        if self.playwright:
            self.playwright.stop()

class BulkMongoWriter:
    """
    Bulk writer cho MongoDB để tăng tốc độ ghi
    """
    def __init__(self, collection, batch_size=100):
        self.collection = collection
        self.batch_size = batch_size
        self.buffer = []
    
    def add_update(self, filter_dict, update_dict):
        """Thêm update vào buffer"""
        self.buffer.append(
            UpdateOne(filter_dict, {"$set": update_dict}, upsert=True)
        )
        
        if len(self.buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        """Ghi buffer vào MongoDB"""
        if not self.buffer:
            return
        
        try:
            self.collection.bulk_write(self.buffer, ordered=False)
            self.buffer = []
        except Exception as e:
            print(f"⚠️ Lỗi bulk write: {e}")
            self.buffer = []
    
    def close(self):
        """Đóng writer và flush buffer"""
        self.flush()

def parallel_sync_fictions(sync_func, fictions, max_workers=5):
    """
    Sync nhiều fictions song song
    
    Args:
        sync_func: Function để sync một fiction
        fictions: List fictions cần sync
        max_workers: Số workers song song
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tất cả tasks
        future_to_fiction = {
            executor.submit(sync_func, fiction): fiction 
            for fiction in fictions
        }
        
        # Thu thập kết quả
        for future in as_completed(future_to_fiction):
            fiction = future_to_fiction[future]
            try:
                result = future.result()
                results.append((fiction, result))
            except Exception as e:
                print(f"❌ Lỗi sync fiction {fiction.get('id', 'N/A')}: {e}")
                results.append((fiction, None))
    
    return results

def smart_delay(base_delay, success_count=0, error_count=0):
    """
    Smart delay: Giảm delay nếu không có lỗi, tăng nếu có lỗi
    
    Args:
        base_delay: Delay cơ bản
        success_count: Số request thành công liên tiếp
        error_count: Số request lỗi liên tiếp
    
    Returns:
        float: Delay thực tế
    """
    if error_count > 0:
        # Có lỗi → tăng delay
        return base_delay * (1 + error_count * 0.5)
    elif success_count > 10:
        # Nhiều request thành công → giảm delay
        return max(base_delay * 0.5, 0.1)
    else:
        return base_delay

def optimize_page_load(page):
    """
    Tối ưu page load bằng cách:
    - Block images/CSS không cần thiết
    - Chỉ load resources cần thiết
    """
    # Block images và CSS để tăng tốc (nếu không cần)
    # page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
    
    # Hoặc chỉ block images
    page.route("**/*.{png,jpg,jpeg,gif,svg}", lambda route: route.abort())
    
    return page

def batch_process(items, batch_size, process_func, *args, **kwargs):
    """
    Xử lý items theo batch
    
    Args:
        items: List items cần xử lý
        batch_size: Kích thước batch
        process_func: Function xử lý một batch
    """
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = process_func(batch, *args, **kwargs)
        results.extend(batch_results)
    
    return results

