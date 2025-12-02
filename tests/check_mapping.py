"""Check raw API response vs mapped fields"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scraper_engine import WattpadScraper
from src.scrapers.comment import CommentScraper
import json

def check_mapping():
    """Compare raw API response with mapped comment"""
    
    chapter_id = "1211987074"
    
    bot = WattpadScraper()
    bot.start()
    
    try:
        # Fetch raw API response
        data = CommentScraper.fetch_v5_page_via_playwright(
            bot.page, 
            chapter_id, 
            namespace='parts', 
            cursor=None, 
            limit=1
        )
        
        if data and data.get('comments'):
            raw_comment = data['comments'][0]
            
            print("=" * 60)
            print("RAW API RESPONSE (first comment):")
            print("=" * 60)
            print(json.dumps(raw_comment, indent=2))
            
            print("\n" + "=" * 60)
            print("AVAILABLE FIELDS IN RAW API:")
            print("=" * 60)
            print(sorted(raw_comment.keys()))
            
            # Map it
            mapped = CommentScraper.map_v5_comment(raw_comment, chapter_id)
            
            print("\n" + "=" * 60)
            print("MAPPED COMMENT:")
            print("=" * 60)
            print(json.dumps(mapped, indent=2))
            
            print("\n" + "=" * 60)
            print("FIELDS IN MAPPED:")
            print("=" * 60)
            print(sorted(mapped.keys()))
            
            # Check missing fields
            print("\n" + "=" * 60)
            print("FIELD ANALYSIS:")
            print("=" * 60)
            
            api_fields = set(raw_comment.keys())
            mapped_fields = set(mapped.keys())
            
            print(f"\nAPI has {len(api_fields)} fields")
            print(f"Mapped has {len(mapped_fields)} fields")
            
            print("\nFields in API but NOT mapped:")
            not_mapped = api_fields - mapped_fields
            for f in sorted(not_mapped):
                print(f"  - {f}: {raw_comment[f]}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    check_mapping()
