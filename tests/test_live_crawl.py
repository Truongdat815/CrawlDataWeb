"""
Live test crawl với schema mới
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper_engine import WattpadScraper
from src import config

# Set limits
config.MAX_CHAPTERS_PER_STORY = 3
config.MAX_COMMENTS_PER_CHAPTER = 10

print("🚀 Testing live crawl with new schema...")
print("=" * 70)

scraper = WattpadScraper()
scraper.start()

# Test story - Mother of Learning  
story_id = "21220"
print(f"\n📚 Crawling story ID: {story_id}")
print(f"   Limits: {config.MAX_CHAPTERS_PER_STORY} chapters, {config.MAX_COMMENTS_PER_CHAPTER} comments/chapter")
print("=" * 70)

try:
    result = scraper.scrape_story(story_id, fetch_chapters=True, fetch_comments=True)
    
    if result:
        print("\n" + "=" * 70)
        print("✅ CRAWL COMPLETED!")
        print("=" * 70)
        
        # Show what was saved
        if scraper.mongo_db is not None:
            print("\n📊 Collections after crawl:")
            
            # Stories
            story_doc = scraper.mongo_db["stories"].find_one({"storyId": story_id})
            if story_doc:
                print(f"\n✅ Story saved:")
                print(f"   ID: {story_doc.get('storyId')}")
                print(f"   Name: {story_doc.get('storyName')}")
                print(f"   Fields: {list(story_doc.keys())[:10]}...")
            
            # Story Info
            info_doc = scraper.mongo_db["story_info"].find_one({"storyId": story_id})
            if info_doc:
                print(f"\n✅ Story Info saved:")
                print(f"   Total Views: {info_doc.get('totalViews')}")
                print(f"   Voted: {info_doc.get('voted')}")
                print(f"   Fields: {list(info_doc.keys())[:10]}...")
            else:
                print(f"\n⚠️ Story Info not saved")
            
            # Chapters
            chapter_count = scraper.mongo_db["chapters"].count_documents({"storyId": story_id})
            if chapter_count > 0:
                chapter = scraper.mongo_db["chapters"].find_one({"storyId": story_id})
                print(f"\n✅ Chapters saved: {chapter_count}")
                print(f"   Sample fields: {list(chapter.keys())[:10]}...")
            
            # Comments
            comment_count = scraper.mongo_db["comments"].count_documents({})
            if comment_count > 0:
                comment = scraper.mongo_db["comments"].find_one()
                print(f"\n✅ Comments saved: {comment_count}")
                print(f"   Sample fields: {list(comment.keys())[:10]}...")
    else:
        print("\n❌ No result returned")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    scraper.stop()
    print("\n" + "=" * 70)
    print("✅ Test completed")
    print("=" * 70)
