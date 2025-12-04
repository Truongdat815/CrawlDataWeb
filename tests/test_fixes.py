"""
Test optimizations và fixes
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper_engine import WattpadScraper
from src import config

# Set limits  
config.MAX_CHAPTERS_PER_STORY = 2
config.MAX_COMMENTS_PER_CHAPTER = 5

print("🧪 Testing fixes and optimizations...")
print("=" * 70)

scraper = WattpadScraper()
scraper.start()

# Test new story with replies
story_id = "36735"  # Has replies
print(f"\n📚 Testing story ID: {story_id}")
print("=" * 70)

try:
    result = scraper.scrape_story(story_id, fetch_chapters=True, fetch_comments=True)
    
    if result and scraper.mongo_db is not None:
        print("\n" + "=" * 70)
        print("✅ TESTING RESULTS")
        print("=" * 70)
        
        # Check chapter schema
        chapter = scraper.mongo_db["chapters"].find_one({"storyId": story_id})
        if chapter:
            print("\n📖 Chapter Fields (should match NEW schema):")
            fields = list(chapter.keys())
            print(f"   Total fields: {len(fields)}")
            print(f"   Has 'webChapterId': {'webChapterId' in fields}")
            print(f"   Has 'totalComments': {'totalComments' in fields}")
            print(f"   Has OLD 'wordCount': {'wordCount' in fields}")  # Should be False
            print(f"   Has OLD 'commentCount': {'commentCount' in fields}")  # Should be False
        
        # Check comment user data
        comment = scraper.mongo_db["comments"].find_one({"chapterId": {"$exists": True}})
        if comment:
            print("\n💬 Comment Fields (should have REAL user data):")
            print(f"   userId: {comment.get('userId')}")
            print(f"   Is userId UUID?: {len(str(comment.get('userId', ''))) == 36}")  # Should be False
            print(f"   Has parentId field: {'parentId' in comment}")
            print(f"   parentId value: {comment.get('parentId')}")
        
        # Check for reply comments with parentId
        reply = scraper.mongo_db["comments"].find_one({"parentId": {"$ne": None}})
        if reply:
            print("\n💬 Reply Comment Found:")
            print(f"   commentId: {reply.get('commentId')[:30]}...")
            print(f"   parentId: {reply.get('parentId')[:30] if reply.get('parentId') else None}...")
            print(f"   isRoot: {reply.get('isRoot')}")
        else:
            print("\n⚠️ No reply comments found (may be none in this story)")
            
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    scraper.stop()
    print("\n" + "=" * 70)
    print("✅ Test completed")
