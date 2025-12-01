"""
Base classes and utilities for scraper modules.
Contains common functionality shared across all scrapers.
"""

import sys

def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)


class BaseScraper:
    """Base class cho tất cả scrapers - chứa references tới page, db collections, config"""
    
    def __init__(self, page=None, mongo_db=None, config=None):
        """
        Args:
            page: Playwright page object
            mongo_db: MongoDB database object
            config: Configuration module
        """
        self.page = page
        self.mongo_db = mongo_db
        self.config = config
        self.collections = {}
        
    def init_collections(self, collection_names):
        """
        Khởi tạo references tới các MongoDB collections
        
        Args:
            collection_names: dict với {collection_key: collection_name}
            Ví dụ: {"stories": "stories", "chapters": "chapters"}
        """
        if self.mongo_db is None:
            return
        
        for key, name in collection_names.items():
            try:
                self.collections[key] = self.mongo_db[name]
            except Exception as e:
                safe_print(f"⚠️ Lỗi khi khởi tạo collection {name}: {e}")
    
    def get_collection(self, name):
        """Lấy MongoDB collection theo tên"""
        return self.collections.get(name)
    
    def collection_exists(self, name):
        """Kiểm tra collection có tồn tại và initialized hay không"""
        return self.collections.get(name) is not None
