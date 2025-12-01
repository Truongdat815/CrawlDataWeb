#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Test single story scraping"""

import json
import sys
import os
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.scraper_engine import WattpadScraper
from src.scrapers.base import safe_print

# Test URL - chapter URL có comments (link bạn cung cấp)
CHAPTER_URL = "https://www.wattpad.com/1211987074-the-war-general-prologue"
# Test story ID - extract từ URL hoặc dùng trực tiếp
STORY_INPUT = "1211987074"  # The War General  

def test_chapter_url():
    """Test chapter URL - extract chapter comments"""
    print(f"\n{'='*60}")
    print(f"Test Chapter URL Comments")
    print(f"{'='*60}")
    print(f"Chapter URL: {CHAPTER_URL}\n")
    
    # Extract chapter ID từ URL: https://www.wattpad.com/CHAPTERID-chapter-title
    match = re.search(r'wattpad\.com/(\d+)', CHAPTER_URL)
    if not match:
        print(f"❌ Cannot extract chapter ID from URL")
        return
    
    chapter_id = match.group(1)
    print(f"✅ Extracted chapter ID: {chapter_id}\n")
    
    bot = WattpadScraper()
    try:
        bot.start()
        
        # Truy cập chapter URL để lấy HTML với comments
        if bot.page:
            print(f"📖 Accessing chapter URL...")
            try:
                bot.page.goto(CHAPTER_URL, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                print(f"⚠️ Page load timeout: {e}")
                # Continue anyway, might have partial content
            import time
            time.sleep(2)  # Wait for page to fully load
            
            # Click "Hiển thị thêm" buttons từ show-more-btn div
            print(f"💬 Clicking 'Hiển thị thêm' buttons...")
            
            for attempt in range(10):
                # Find button trong div.show-more-btn
                show_more_btn = None
                
                try:
                    show_more_btn = bot.page.query_selector('div.show-more-btn button')
                except:
                    pass
                
                if not show_more_btn:
                    print(f"   ✅ No more 'Hiển thị thêm' buttons found")
                    break
                
                try:
                    show_more_btn.click()
                    time.sleep(0.8)
                    print(f"   ✅ Clicked button {attempt + 1}")
                except Exception as e:
                    print(f"   ⚠️ Error clicking: {e}")
                    break
            
            # Get HTML after clicking
            page_html = bot.page.content()
            
            # Extract comments from HTML
            from src.scrapers.comment import CommentScraper
            comments = CommentScraper.extract_comments_from_html(page_html, chapter_id)
            
            print(f"\n✅ Extracted {len(comments)} comments from chapter HTML:")
            for i, cmt in enumerate(comments, 1):
                print(f"   {i}. {cmt.get('userName', 'Unknown')}: {cmt.get('commentText', '')[:60]}...")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

def main():
    """Test scraping API v5 comments từ chapter ID"""
    
    print(f"\n{'='*60}")
    print(f"Test API v5 Comments for Chapter: {STORY_INPUT}")
    print(f"{'='*60}\n")
    
    bot = WattpadScraper()
    
    try:
        bot.start()
        
        # Fetch comments từ API v5 với chapter ID (không cần story metadata)
        chapter_id = STORY_INPUT
        print(f"📥 Fetching comments from API v5...")
        comments = bot.fetch_comments_from_api_v5(chapter_id)
        
        if comments:
            print(f"\n✅ Lấy được {len(comments)} comments!\n")
            
            # Print first 5 comments
            print(f"First 5 comments:")
            for i, cmt in enumerate(comments[:5], 1):
                print(f"\n{i}. User: {cmt.get('userName', 'Unknown')}")
                print(f"   Text: {cmt.get('commentText', '')[:80]}")
                print(f"   Likes: {cmt.get('react', 0)}")
                print(f"   Created: {cmt.get('createdAt', 'N/A')}")
            
            # Save to JSON
            import os
            import json
            test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
            os.makedirs(test_data_dir, exist_ok=True)
            
            filename = f"comments_{chapter_id}.json"
            filepath = os.path.join(test_data_dir, filename)
            
            # Remove _id field added by MongoDB (nếu có)
            clean_comments = []
            for cmt in comments:
                clean_cmt = {k: v for k, v in cmt.items() if k != '_id'}
                clean_comments.append(clean_cmt)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(clean_comments, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Saved {len(clean_comments)} comments to: {filepath}")

        else:
            print(f"❌ Failed to fetch comments")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

def test_chapter_3_comments():
    """Test chapter 3 comments extraction"""
    print(f"\n{'='*60}")
    print(f"Test Chapter 3 Comments")
    print(f"{'='*60}\n")
    
    # Story 399709711 - Puck You
    # Chapter 3 có comments
    story_id = "399709711"
    
    bot = WattpadScraper()
    try:
        bot.start()
        
        # Get story first để lấy chapters list
        story_data = bot.fetch_story_from_api(story_id)
        if story_data:
            print(f"✅ Story: {story_data.get('title')}")
            print(f"   Total chapters: {story_data.get('numParts')}")
        
        # Scrape full story để lấy chapters
        result = bot.scrape_story(
            story_id=story_id,
            fetch_chapters=True,
            fetch_comments=True
        )
        
        if result and result.get('chapters'):
            # Get chapter 3 (index 2)
            if len(result['chapters']) >= 3:
                ch3 = result['chapters'][2]
                print(f"\n📖 Chapter 3:")
                print(f"   Name: {ch3.get('chapterName')}")
                print(f"   ID: {ch3.get('chapterId')}")
                print(f"   Comments: {len(ch3.get('comments', []))}")
                
                if ch3.get('comments'):
                    print(f"\n   Comments found:")
                    for i, cmt in enumerate(ch3.get('comments', []), 1):
                        print(f"     {i}. {cmt.get('userName', 'Unknown')}: {cmt.get('commentText', '')[:60]}...")
            else:
                print(f"❌ Not enough chapters. Got {len(result['chapters'])}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        bot.stop()

if __name__ == "__main__":
    # Chạy test chính story (dùng API v5 comments)
    main()
    
    # Hoặc chạy test chapter URL (HTML extraction)
    # test_chapter_url()
    
    # Hoặc chạy test chapter 3
    # test_chapter_3_comments()
