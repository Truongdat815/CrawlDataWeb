"""
Base handler với browser management và các utilities cơ bản
"""
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print

class BaseHandler:
    """Base class cho tất cả handlers với browser management"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
    
    def start_browser(self):
        """Khởi động trình duyệt"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=config.HEADLESS)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        safe_print("✅ Bot đã khởi động!")
    
    def stop_browser(self):
        """Đóng trình duyệt"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        safe_print("zzz Bot đã tắt.")

