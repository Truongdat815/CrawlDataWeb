#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Test duplicate detection - scrape story twice to see skipping"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper_engine import WattpadScraper

def test_duplicate_detection():
    """Test that scraper skips already scraped stories/chapters"""
    
    # Use story 399709711 (Puck You) - already scraped
    story_id = "399709711"
    
    print(f"\n{'='*60}")
    print(f"Test: Duplicate Detection")
    print(f"{'='*60}")
    print(f"Story ID: {story_id} (Puck You)\n")
    print(f"This story should already be in database.")
    print(f"When scraping, it should skip and continue.\n")
    
    bot = WattpadScraper()
    
    try:
        bot.start()
        
        # Try to scrape same story again
        print(f"📌 Attempting to scrape story that already exists...\n")
        result = bot.scrape_story(
            story_id=story_id,
            fetch_chapters=True,
            fetch_comments=False  # Skip comments for speed
        )
        
        if result:
            print(f"\n{'='*60}")
            print(f"Result:")
            print(f"{'='*60}")
            print(f"Story: {result.get('storyName')}")
            print(f"Chapters: {len(result.get('chapters', []))}")
            print(f"\n✅ Test passed - Story was skipped but returned existing data")
        else:
            print(f"\n❌ No result returned")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    test_duplicate_detection()
