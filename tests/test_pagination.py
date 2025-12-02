"""Test v5 API pagination with after cursor"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scraper_engine import WattpadScraper
import json

def test_pagination():
    """Test fetching multiple pages of comments"""
    
    chapter_id = "1211987074"
    
    print(f"\n{'='*60}")
    print(f"Test Pagination for Chapter: {chapter_id}")
    print(f"{'='*60}\n")
    
    bot = WattpadScraper()
    bot.start()
    
    try:
        # Fetch first page with limit=5
        print("📥 Fetching page 1 (limit=5)...")
        from src.scrapers.comment import CommentScraper
        
        data = CommentScraper.fetch_v5_page_via_playwright(
            bot.page, 
            chapter_id, 
            namespace='parts', 
            cursor=None, 
            limit=5
        )
        
        if data:
            print(f"✅ Got response!")
            print(f"\nResponse keys: {list(data.keys())}")
            print(f"\nComments count: {len(data.get('comments', []))}")
            
            # Check pagination
            pagination = data.get('pagination', {})
            print(f"\nPagination object: {json.dumps(pagination, indent=2)}")
            
            # Get after cursor
            after = pagination.get('after')
            if after:
                print(f"\n✅ After cursor found: {json.dumps(after, indent=2)}")
                
                # Try fetching page 2
                print(f"\n📥 Fetching page 2 using after cursor...")
                
                # Build after param from cursor
                if isinstance(after, dict):
                    resource_id = after.get('resourceId')
                    if resource_id:
                        data2 = CommentScraper.fetch_v5_page_via_playwright(
                            bot.page,
                            chapter_id,
                            namespace='parts',
                            cursor=resource_id,
                            limit=5
                        )
                        
                        if data2:
                            print(f"✅ Got page 2!")
                            print(f"Comments count: {len(data2.get('comments', []))}")
                            
                            # Show first comment from each page
                            page1_first = data.get('comments', [])[0] if data.get('comments') else None
                            page2_first = data2.get('comments', [])[0] if data2.get('comments') else None
                            
                            if page1_first and page2_first:
                                print(f"\nPage 1 first comment: {page1_first.get('user', {}).get('name')}")
                                print(f"Page 2 first comment: {page2_first.get('user', {}).get('name')}")
            else:
                print("\n⚠️ No 'after' cursor in pagination")
        else:
            print("❌ No data returned")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    test_pagination()
