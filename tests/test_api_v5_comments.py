#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Test API v5 comments endpoint trực tiếp"""

import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scraper_engine import WattpadScraper

def test_api_v5_comments():
    """Test lấy comments từ API v5 với chapter ID"""
    
    chapter_id = "1211987074"  # Chapter ID từ link
    
    print(f"\n{'='*60}")
    print(f"Test API v5 Comments")
    print(f"{'='*60}")
    print(f"Chapter ID: {chapter_id}\n")
    
    bot = WattpadScraper()
    
    try:
        bot.start()
        
        # Call API v5 directly
        comments = bot.fetch_comments_from_api_v5(chapter_id)
        
        print(f"✅ Lấy được {len(comments)} comments\n")
        
        if comments:
            print(f"Comments:")
            for i, cmt in enumerate(comments[:5], 1):  # Show first 5
                print(f"\n{i}. User: {cmt.get('userName', 'Unknown')}")
                print(f"   Text: {cmt.get('commentText', '')[:100]}")
                print(f"   Likes: {cmt.get('react', 0)}")
                print(f"   Created: {cmt.get('createdAt', 'N/A')}")
            
            # Save all to JSON
            filepath = "test_comments_v5.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Saved {len(comments)} comments to: {filepath}")
        else:
            print(f"⚠️ No comments found")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    test_api_v5_comments()
