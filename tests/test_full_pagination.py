"""Test full pagination flow with engine"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scraper_engine import WattpadScraper
from src import config

def test_full_pagination():
    """Test fetching multiple pages through engine"""
    
    chapter_id = "1211987074"
    
    # Temporarily set limit lower to test pagination
    original_limit = config.MAX_COMMENTS_PER_CHAPTER
    config.MAX_COMMENTS_PER_CHAPTER = 15  # Fetch 15 comments (will need multiple pages if limit=5 per page)
    
    print(f"\n{'='*60}")
    print(f"Test Full Pagination Flow")
    print(f"MAX_COMMENTS_PER_CHAPTER: {config.MAX_COMMENTS_PER_CHAPTER}")
    print(f"{'='*60}\n")
    
    bot = WattpadScraper()
    bot.start()
    
    try:
        print(f"📥 Fetching up to {config.MAX_COMMENTS_PER_CHAPTER} comments...")
        comments = bot.fetch_comments_from_api_v5(chapter_id)
        
        print(f"\n✅ Total fetched: {len(comments)} comments")
        
        if len(comments) > 0:
            print(f"\nFirst 5 comments:")
            for i, cmt in enumerate(comments[:5], 1):
                print(f"  {i}. {cmt.get('userName')}: {cmt.get('commentText', '')[:50]}...")
            
            if len(comments) > 5:
                print(f"\nLast comment:")
                print(f"  {len(comments)}. {comments[-1].get('userName')}: {comments[-1].get('commentText', '')[:50]}...")
        
        # Restore original limit
        config.MAX_COMMENTS_PER_CHAPTER = original_limit
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        config.MAX_COMMENTS_PER_CHAPTER = original_limit
    
    finally:
        bot.stop()

if __name__ == "__main__":
    test_full_pagination()
