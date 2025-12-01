#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Test scrape story with chapter content storage"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scraper_engine import WattpadScraper
from src import config

def test_scrape_with_content_storage():
    """Test scraping story and saving chapter content to MongoDB"""
    
    # Use working story: Puck You (399709711)
    story_id = "399709711"
    
    print(f"\n{'='*60}")
    print(f"Test Scrape Story with Chapter Content Storage")
    print(f"{'='*60}")
    print(f"Story ID: {story_id}\n")
    
    bot = WattpadScraper()
    
    try:
        bot.start()
        
        # Scrape story with chapters and comments
        result = bot.scrape_story(
            story_id=story_id,
            fetch_chapters=True,
            fetch_comments=True
        )
        
        if result:
            print(f"\n✅ Scraped successfully!")
            print(f"   Story: {result.get('storyName')}")
            print(f"   Chapters scraped: {len(result.get('chapters', []))}")
            
            # Check if chapter content was extracted (not stored in chapter object)
            for i, ch in enumerate(result.get('chapters', [])[:2], 1):
                print(f"\n   Chapter {i}:")
                print(f"     - Name: {ch.get('chapterName')}")
                print(f"     - Has 'content' field: {'content' in ch}")
                print(f"     - Has comments: {len(ch.get('comments', []))} comments")
            
            # Now check MongoDB for chapter_content collection
            print(f"\n📊 Checking MongoDB collections...")
            from pymongo import MongoClient
            client = MongoClient(config.MONGODB_URI)
            db = client[config.MONGODB_DB_NAME]
            
            collections = db.list_collection_names()
            print(f"   Collections: {collections}")
            
            if "chapter_contents" in collections:
                cc_collection = db["chapter_contents"]
                cc_count = cc_collection.count_documents({})
                print(f"\n   ✅ chapter_contents: {cc_count} documents")
                
                if cc_count > 0:
                    sample = cc_collection.find_one()
                    print(f"      Sample:")
                    print(f"      - contentId: {sample.get('contentId')}")
                    print(f"      - chapterId: {sample.get('chapterId')}")
                    print(f"      - content length: {len(sample.get('content', ''))}")
                    print(f"      - createdAt: {sample.get('createdAt')}")
            else:
                print(f"   ❌ chapter_contents collection NOT found")
            
            client.close()
        else:
            print(f"❌ Failed to scrape story")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    test_scrape_with_content_storage()
