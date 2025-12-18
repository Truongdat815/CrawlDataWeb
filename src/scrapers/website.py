# -*- coding: utf-8 -*-
"""
Website Scraper - Quản lý thông tin websites
"""

from .base import BaseScraper, safe_print
from ..utils import uuid_v7
from datetime import datetime


class WebsiteScraper(BaseScraper):
    """Scraper for website management (multi-source support)"""
    
    # Wattpad website UUID (fixed, sử dụng UUID v7)
    WATTPAD_WEBSITE_ID = "wp_019376f0000070008000000000000001"
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
        # Use our uuid_v7 implementation to generate time-ordered ids
        return uuid_v7.prefixed(prefix)
    
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
        # Generate a non-deterministic, timestamp-first id (uuid7)
        # Stories should get a generated id rather than deterministic uuid5
        return uuid_v7.prefixed(prefix)
    
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
        # Generate a non-deterministic uuid7 for each chapter
        return uuid_v7.prefixed(prefix)
    
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
        # Use UUID v7 (non-deterministic, timestamp-first) without hyphens
        return uuid_v7.prefixed(prefix)
    
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
        # Generate a non-deterministic uuid7 for comments
        return uuid_v7.prefixed(prefix)
    
    @staticmethod
    def generate_user_id(username, prefix="wp"):
        """
        Generate user UUID v7 (deterministic based on username)
        Format: {prefix}_{uuid_v5}
        
        Args:
            username: Username from website
            prefix: Website prefix (default: "wp" for Wattpad)
            
        Returns:
            String: {prefix}_{uuid_v5}
        """
        # Use UUID v7 (non-deterministic, timestamp-first) without hyphens
        return uuid_v7.prefixed(prefix)

    @staticmethod
    def generate_chapter_content_id(chapter_id, prefix="wp"):
        """Generate a UUIDv7-based content id for a chapter.

        Format: {prefix}_{uuidv7}
        """
        return uuid_v7.prefixed(prefix)
    
    @staticmethod
    def get_or_create_wattpad_website(mongo_collection):
        """
        Get or create Wattpad website entry
        Chỉ tạo 1 lần, sau đó reuse
        
        Args:
            mongo_collection: MongoDB websites collection
            
        Returns:
            dict: Website document with websiteId and websiteName
        """
        if mongo_collection is None:
            safe_print("⚠️ MongoDB collection is None, skipping website creation")
            return None
        
        try:
            # Use upsert to prevent race conditions in parallel crawler
            website_doc = {
                "websiteId": WebsiteScraper.WATTPAD_WEBSITE_ID,
                "websiteName": WebsiteScraper.WATTPAD_WEBSITE_NAME
            }
            
            result = mongo_collection.update_one(
                {"websiteId": WebsiteScraper.WATTPAD_WEBSITE_ID},
                {"$setOnInsert": website_doc},
                upsert=True
            )
            
            # Retrieve the document (either existing or newly created)
            existing = mongo_collection.find_one({"websiteId": WebsiteScraper.WATTPAD_WEBSITE_ID})
            
            if result.upserted_id:
                safe_print(f"✅ Created Wattpad website: {WebsiteScraper.WATTPAD_WEBSITE_ID}")
            else:
                safe_print(f"✅ Wattpad website already exists: {WebsiteScraper.WATTPAD_WEBSITE_ID}")
            
            return existing
            
        except Exception as e:
            safe_print(f"❌ Error getting/creating Wattpad website: {e}")
            return None
    
    @staticmethod
    def get_website_by_id(mongo_collection, website_id):
        """
        Get website by websiteId
        
        Args:
            mongo_collection: MongoDB websites collection
            website_id: Website ID to fetch
            
        Returns:
            dict or None: Website document
        """
        if mongo_collection is None:
            return None
        
        try:
            return mongo_collection.find_one({"websiteId": website_id})
        except Exception as e:
            safe_print(f"❌ Error fetching website {website_id}: {e}")
            return None
    
    @staticmethod
    def create_website(mongo_collection, name, base_url=None, prefix="wp"):
        """
        Create new website entry (for future multi-source support)
        
        Args:
            mongo_collection: MongoDB websites collection
            name: Website name (lowercase, no spaces)
            base_url: Website base URL (deprecated, not stored)
            prefix: ID prefix
            
        Returns:
            dict or None: Created website document
        """
        if mongo_collection is None:
            return None
        
        try:
            # Check if exists
            existing = mongo_collection.find_one({"websiteName": name})
            if existing:
                safe_print(f"⚠️ Website {name} already exists")
                return existing
            
            # Generate ID
            website_id = WebsiteScraper.generate_website_id(prefix)
            
            # Chỉ 2 fields theo schema
            website_doc = {
                "websiteId": website_id,
                "websiteName": name
            }
            
            result = mongo_collection.insert_one(website_doc)
            website_doc["_id"] = result.inserted_id
            
            safe_print(f"✅ Created website {name}: {website_id}")
            return website_doc
            
        except Exception as e:
            safe_print(f"❌ Error creating website {name}: {e}")
            return None
