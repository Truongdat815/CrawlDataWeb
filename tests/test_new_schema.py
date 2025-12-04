"""
Test script to verify new schema and collections
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper_engine import WattpadScraper
from src import config

# Set limits for quick test
config.MAX_CHAPTERS_PER_STORY = 2
config.MAX_COMMENTS_PER_CHAPTER = 5

print("🔍 Testing new schema implementation...")
print("=" * 60)

scraper = WattpadScraper()
scraper.start()

# Test with a known story
story_id = "374284891"  # The Perfect Run
print(f"\n📚 Testing story ID: {story_id}")

try:
    result = scraper.scrape_story(story_id, fetch_chapters=True, fetch_comments=True)
    
    print("\n" + "=" * 60)
    print("✅ SCRAPING COMPLETED!")
    print("=" * 60)
    
    # Check what was saved
    if scraper.mongo_db is not None:
        print("\n📊 Database Collections:")
        collections = scraper.mongo_db.list_collection_names()
        for coll in collections:
            count = scraper.mongo_db[coll].count_documents({})
            print(f"   - {coll}: {count} documents")
        
        print("\n📄 Sample Story Document:")
        story = scraper.mongo_db["stories"].find_one({})
        if story:
            print(f"   Fields: {list(story.keys())}")
        
        print("\n📈 Sample Story Info Document:")
        story_info = scraper.mongo_db["story_info"].find_one({})
        if story_info:
            print(f"   Fields: {list(story_info.keys())}")
        
        print("\n📖 Sample Chapter Document:")
        chapter = scraper.mongo_db["chapters"].find_one({})
        if chapter:
            print(f"   Fields: {list(chapter.keys())}")
        
        print("\n💬 Sample Comment Document:")
        comment = scraper.mongo_db["comments"].find_one({})
        if comment:
            print(f"   Fields: {list(comment.keys())}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    scraper.stop()
    print("\n✅ Test completed")
