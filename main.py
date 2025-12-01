# -*- coding: utf-8 -*-
import sys
import re
import traceback
from src import config

# Helper function de print an toan voi encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toan voi encoding UTF-8 tren Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

from src.scraper_engine import WattpadScraper

def extract_story_id_from_url(url):
    """Extract story ID from Wattpad URL
    
    Examples:
    - https://www.wattpad.com/story/83744060-15-days-with-the-possessive-billionaire
    - https://www.wattpad.com/83744060-15-days-with-the-possessive-billionaire
    - 83744060
    
    Returns: story_id or None if invalid
    """
    # If it's just a number, return it
    if url.isdigit():
        return url
    
    # Try to extract from URL
    match = re.search(r'/(?:story/)?(\d+)', url)
    if match:
        return match.group(1)
    
    return None

def main():
    # ========== DOC STORY URLs TU FILE ==========
    try:
        with open('story_urls.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        safe_print("Loi: Khong tim thay file story_urls.txt")
        safe_print("Tao file story_urls.txt va dan URLs vao")
        return
    
    # Filter va clean URLs (bo comment va blank lines)
    urls = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)
    
    if not urls:
        safe_print("Loi: Khong co URL nao trong story_urls.txt")
        safe_print("Vui long dan URLs vao file")
        return
    
    safe_print(f"\nTim thay {len(urls)} story URL(s)")
    
    # ========== TUY CHINH SO LUONG CHAPTERS VA COMMENTS ==========
    # Uncomment de custom (None = lay tat ca):
    # config.MAX_CHAPTERS_PER_STORY = 5  # Lay toi da 5 chapters
    # config.MAX_COMMENTS_PER_CHAPTER = 20  # Lay toi da 20 comments moi chapter
    
    safe_print("\n" + "="*60)
    safe_print("Cau hinh hien tai:")
    safe_print(f"  Max chapters/story: {config.MAX_CHAPTERS_PER_STORY or 'Unlimited'}")
    safe_print(f"  Max comments/chapter: {config.MAX_COMMENTS_PER_CHAPTER or 'Unlimited'}")
    safe_print(f"  Rate limit: {config.MAX_REQUESTS_PER_MINUTE} requests/minute")
    safe_print(f"  Max retries: {config.MAX_RETRIES}")
    safe_print("="*60 + "\n")
    
    # Khoi tao bot
    bot = WattpadScraper()
    
    try:
        bot.start()
        
        # Scrape tung story
        for idx, story_url in enumerate(urls, 1):
            safe_print(f"\n[{idx}/{len(urls)}] Xu ly: {story_url}")
            
            # Extract story ID from URL
            story_id = extract_story_id_from_url(story_url)
            if not story_id:
                safe_print(f"  Loi: Khong the extract story ID tu URL")
                continue
            
            safe_print(f"  Story ID: {story_id}")
            
            # Scrape story
            result = bot.scrape_story(
                story_id=story_id,
                story_url=story_url,
                fetch_chapters=True,
                fetch_comments=True
            )
            
            if result:
                safe_print(f"  {result.get('storyName')}")
                safe_print(f"  Author: {result.get('userId')}")
                if "chapters" in result:
                    safe_print(f"  Chapters: {len(result['chapters'])}")
                if "comments" in result:
                    safe_print(f"  Comments: {len(result['comments'])}")
            else:
                safe_print(f"  Cao that bai")
        
        safe_print(f"\n{'='*60}")
        safe_print(f"Xong cao {len(urls)} story")
        safe_print(f"{'='*60}")
            
    except Exception as e:
        safe_print(f"\nLoi chuong trinh: {e}")
        traceback.print_exc()
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
