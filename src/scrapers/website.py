# -*- coding: utf-8 -*-
"""
Website Scraper - Quản lý thông tin websites
"""

from src.scrapers.base import BaseScraper, safe_print
import uuid
from datetime import datetime


class WebsiteScraper(BaseScraper):
    """Scraper for website management (multi-source support)"""
    
    # Wattpad website UUID (fixed, sử dụng UUID v7)
    WATTPAD_WEBSITE_ID = "wp_019376f0-0000-7000-8000-000000000001"
    WATTPAD_WEBSITE_NAME = "wattpad"
    
    @staticmethod
    def generate_website_id(prefix="wp"):
        """
        Generate UUID v7 for website
        Format: {prefix}_uuid_v7
        
        Args:
            prefix: Website prefix (default: "wp" for Wattpad)
            
        Returns:
            String: {prefix}_{uuid_v7}
        """
        # UUID v7: timestamp-based UUID (better for database indexing)
        # Python uuid không có v7 native, dùng v1 thay thế (timestamp-based)
        uid = uuid.uuid1()
        return f"{prefix}_{uid}"
    
    @staticmethod
    def generate_story_id(web_story_id, prefix="wp"):
        """
        Generate story UUID v7 (deterministic based on web_story_id)
        Format: {prefix}_{uuid_v5}
        
        Args:
            web_story_id: Original story ID from website
            prefix: Website prefix (default: "wp" for Wattpad)
            
        Returns:
            String: {prefix}_{uuid_v5}
        """
        # UUID v5: deterministic (same input = same output)
        # Sử dụng namespace DNS + web_story_id để tạo UUID deterministic
        namespace = uuid.NAMESPACE_DNS
        uid = uuid.uuid5(namespace, f"{prefix}_{web_story_id}")
        return f"{prefix}_{uid}"
    
    @staticmethod
    def generate_chapter_id(web_chapter_id, prefix="wp"):
        """
        Generate chapter UUID v7 (deterministic based on web_chapter_id)
        Format: {prefix}_{uuid_v5}
        
        Args:
            web_chapter_id: Original chapter ID from website
            prefix: Website prefix (default: "wp" for Wattpad)
            
        Returns:
            String: {prefix}_{uuid_v5}
        """
        namespace = uuid.NAMESPACE_DNS
        uid = uuid.uuid5(namespace, f"{prefix}_chapter_{web_chapter_id}")
        return f"{prefix}_{uid}"
    
    @staticmethod
    def generate_info_id(story_id, prefix="wp"):
        """
        Generate story_info UUID v7 (deterministic based on story_id)
        Format: {prefix}_{uuid_v5}
        Since each story has only one info record, use story_id as seed.
        
        Args:
            story_id: Story ID (wp_uuid_v7 format)
            prefix: Website prefix (default: "wp" for Wattpad)
            
        Returns:
            String: {prefix}_{uuid_v5}
        """
        namespace = uuid.NAMESPACE_DNS
        uid = uuid.uuid5(namespace, f"{prefix}_info_{story_id}")
        return f"{prefix}_{uid}"
    
    @staticmethod
    def generate_comment_id(web_comment_id, prefix="wp"):
        """
        Generate comment UUID v7 (deterministic based on web_comment_id)
        Format: {prefix}_{uuid_v5}
        
        Args:
            web_comment_id: Original comment ID from website
            prefix: Website prefix (default: "wp" for Wattpad)
            
        Returns:
            String: {prefix}_{uuid_v5}
        """
        namespace = uuid.NAMESPACE_DNS
        uid = uuid.uuid5(namespace, f"{prefix}_comment_{web_comment_id}")
        return f"{prefix}_{uid}"
    
    @staticmethod
    def get_or_create_wattpad_website(mongo_collection):
        """
        Get or create Wattpad website entry
        Chỉ tạo 1 lần, sau đó reuse
        
        Args:
            mongo_collection: MongoDB websites collection
            
        Returns:
            dict: Website document with _id, website_id, name
        """
        if mongo_collection is None:
            safe_print("⚠️ MongoDB collection is None, skipping website creation")
            return None
        
        try:
            # Check if Wattpad website exists
            existing = mongo_collection.find_one({"website_id": WebsiteScraper.WATTPAD_WEBSITE_ID})
            
            if existing:
                safe_print(f"✅ Wattpad website already exists: {WebsiteScraper.WATTPAD_WEBSITE_ID}")
                return existing
            
            # Create new Wattpad website entry
            website_doc = {
                "website_id": WebsiteScraper.WATTPAD_WEBSITE_ID,
                "name": WebsiteScraper.WATTPAD_WEBSITE_NAME,
                "display_name": "Wattpad",
                "base_url": "https://www.wattpad.com",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "active",
                "metadata": {
                    "description": "Online storytelling platform",
                    "language": "en",
                    "country": "CA"
                }
            }
            
            result = mongo_collection.insert_one(website_doc)
            website_doc["_id"] = result.inserted_id
            
            safe_print(f"✅ Created Wattpad website: {WebsiteScraper.WATTPAD_WEBSITE_ID}")
            return website_doc
            
        except Exception as e:
            safe_print(f"❌ Error getting/creating Wattpad website: {e}")
            return None
    
    @staticmethod
    def get_website_by_id(mongo_collection, website_id):
        """
        Get website by website_id
        
        Args:
            mongo_collection: MongoDB websites collection
            website_id: Website ID to fetch
            
        Returns:
            dict or None: Website document
        """
        if mongo_collection is None:
            return None
        
        try:
            return mongo_collection.find_one({"website_id": website_id})
        except Exception as e:
            safe_print(f"❌ Error fetching website {website_id}: {e}")
            return None
    
    @staticmethod
    def create_website(mongo_collection, name, base_url, prefix="wp"):
        """
        Create new website entry (for future multi-source support)
        
        Args:
            mongo_collection: MongoDB websites collection
            name: Website name (lowercase, no spaces)
            base_url: Website base URL
            prefix: ID prefix
            
        Returns:
            dict or None: Created website document
        """
        if mongo_collection is None:
            return None
        
        try:
            # Check if exists
            existing = mongo_collection.find_one({"name": name})
            if existing:
                safe_print(f"⚠️ Website {name} already exists")
                return existing
            
            # Generate ID
            website_id = WebsiteScraper.generate_website_id(prefix)
            
            website_doc = {
                "website_id": website_id,
                "name": name,
                "display_name": name.title(),
                "base_url": base_url,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "active",
                "metadata": {}
            }
            
            result = mongo_collection.insert_one(website_doc)
            website_doc["_id"] = result.inserted_id
            
            safe_print(f"✅ Created website {name}: {website_id}")
            return website_doc
            
        except Exception as e:
            safe_print(f"❌ Error creating website {name}: {e}")
            return None
