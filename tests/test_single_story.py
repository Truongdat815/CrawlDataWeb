#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Test single story scraping"""

import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.scraper_engine import WattpadScraper
from src.scrapers.base import safe_print

# Test single story ID
STORY_ID = "11963741"  # Puck You

def main():
    """Test scraping one story"""
    
    print(f"\n{'='*60}")
    print(f"Test scraping story: {STORY_ID}")
    print(f"{'='*60}\n")
    
    bot = WattpadScraper()
    
    try:
        bot.start()
        
        # Scrape one story
        result = bot.scrape_story(
            story_id=STORY_ID,
            fetch_chapters=True,
            fetch_comments=True
        )
        
        if result:
            print(f"\n✅ Scraped successfully!")
            print(f"   Story: {result.get('storyName')}")
            print(f"   Total chapters: {result.get('totalChapters')}")
            print(f"   Chapters in JSON: {len(result.get('chapters', []))}")
            print(f"   Comments: {len(result.get('comments', []))}")
            
            # Print first chapter
            if result.get('chapters'):
                first_ch = result['chapters'][0]
                print(f"\n   First chapter:")
                print(f"     - ID: {first_ch.get('chapterId')}")
                print(f"     - Name: {first_ch.get('chapterName')}")
                print(f"     - Has content: {'content' in first_ch}")
            
            # Print first comment
            if result.get('comments'):
                first_cmt = result['comments'][0]
                print(f"\n   First comment:")
                print(f"     - Author: {first_cmt.get('author', {}).get('name')}")
                print(f"     - Text: {first_cmt.get('text', '')[:50]}...")
            
            # Save to JSON (in tests/test_data for test artifacts)
            import os
            import json
            test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
            os.makedirs(test_data_dir, exist_ok=True)
            
            story_name = result.get('storyName', 'Unknown')
            safe_name = story_name.replace('/', '_').replace('\\', '_').replace('|', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace(':', '_')[:50]
            filename = f"{result['storyId']}_{safe_name}.json"
            filepath = os.path.join(test_data_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Saved to: {filepath}")

        else:
            print(f"❌ Failed to scrape story")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
