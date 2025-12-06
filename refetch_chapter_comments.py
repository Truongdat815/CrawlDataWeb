"""
Refetch Chapter Comments - Fix corrupted chapter comments in existing JSON
Re-scrapes all chapter comments with FIXED logic and overwrites the old data

This script:
1. Loads an existing book JSON file
2. Uses authenticated cookies (cookies.json) 
3. Re-scrapes comments for each chapter using fixed selectors
4. Overwrites the old 'comments' arrays with correct data
5. Saves after each chapter to prevent data loss

Usage:
    python refetch_chapter_comments.py path/to/book.json
    
Example:
    python refetch_chapter_comments.py "data/json/bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json"
"""

import sys
import os
import json
import time
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from webnovel_scraper import WebnovelScraper


def safe_print(*args, **kwargs):
    """Print with UTF-8 encoding safety for Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)


def load_book_json(filepath):
    """Load book JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        safe_print(f"✅ Loaded: {filepath}")
        return data
    except Exception as e:
        safe_print(f"❌ Failed to load JSON: {e}")
        return None


def save_book_json(filepath, data):
    """Save book JSON file (atomic write)"""
    try:
        # Write to temp file first
        temp_path = filepath + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Create backup of original
        backup_path = filepath + '.backup'
        if os.path.exists(filepath):
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(filepath, backup_path)
        
        # Move temp to final location
        os.rename(temp_path, filepath)
        
        safe_print(f"💾 Saved: {filepath}")
        return True
    except Exception as e:
        safe_print(f"❌ Failed to save JSON: {e}")
        return False


def refetch_chapter_comments(json_path):
    """
    Re-scrape all chapter comments for a book
    
    Args:
        json_path: Path to the book JSON file
    """
    safe_print("\n" + "="*80)
    safe_print("🔄 REFETCH CHAPTER COMMENTS")
    safe_print("="*80)
    safe_print(f"File: {json_path}")
    safe_print("="*80 + "\n")
    
    # Load book data
    book_data = load_book_json(json_path)
    if not book_data:
        return False
    
    book_name = book_data.get('name', 'Unknown')
    chapters = book_data.get('chapters', [])
    
    if not chapters:
        safe_print("⚠️  No chapters found in JSON")
        return False
    
    safe_print(f"📖 Book: {book_name}")
    safe_print(f"📚 Total Chapters: {len(chapters)}")
    safe_print()
    
    # Check for cookies.json
    if not os.path.exists('cookies.json'):
        safe_print("⚠️  WARNING: cookies.json not found!")
        safe_print("   Comments may be hidden for guests. Run setup_login.py first.")
        safe_print()
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        if confirm != 'y':
            safe_print("❌ Cancelled")
            return False
    else:
        safe_print("✅ Found cookies.json (will use for authentication)")
    
    safe_print()
    confirm = input(f"Re-scrape comments for {len(chapters)} chapters? [Y/n]: ").strip().lower()
    if confirm == 'n':
        safe_print("❌ Cancelled")
        return False
    
    safe_print()
    safe_print("="*80)
    safe_print("🚀 Starting refetch process...")
    safe_print("="*80)
    safe_print()
    
    # MUST match setup_login.py settings: Visual Mode + Load All Resources
    # This ensures cookies work correctly (same browser fingerprint as login)
    scraper = WebnovelScraper(
        headless=False,       # Changed from True: Show browser (matches login environment)
        block_resources=False # Changed from True: Load scripts/CSS (comment drawer needs JS)
    )
    
    safe_print("👁️  Visual mode: Browser will be visible")
    safe_print("📦 Loading all resources: Scripts/CSS enabled for comment drawer")
    safe_print()
    
    scraper.start()
    
    # Stats
    success_count = 0
    error_count = 0
    total_new_comments = 0
    
    try:
        for idx, chapter in enumerate(chapters, 1):
            chapter_url = chapter.get('url')
            chapter_name = chapter.get('name', f'Chapter {idx}')
            chapter_id = chapter.get('id')
            old_comment_count = len(chapter.get('comments', []))
            
            safe_print(f"\n[{idx}/{len(chapters)}] {chapter_name}")
            safe_print(f"   URL: {chapter_url}")
            safe_print(f"   Old comments: {old_comment_count}")
            
            if not chapter_url:
                safe_print(f"   ⚠️  No URL - skipping")
                error_count += 1
                continue
            
            try:
                # Navigate to chapter page (OPTIMIZED: domcontentloaded avoids waiting for ads/images)
                safe_print(f"   🌐 Loading chapter page...")
                scraper.page.goto(chapter_url, timeout=60000, wait_until='domcontentloaded')
                safe_print(f"   ⚡ Page DOM loaded (skipped waiting for ads/images)")
                time.sleep(1)  # Brief pause for JS initialization
                
                # Scrape comments with FIXED logic
                safe_print(f"   💬 Scraping comments...")
                new_comments = scraper._scrape_chapter_comments(chapter_id)
                
                # Update chapter data
                chapter['comments'] = new_comments
                new_comment_count = len(new_comments)
                
                safe_print(f"   ✅ New comments: {new_comment_count}")
                
                # Count replies
                total_replies = sum(len(c.get('replies', [])) for c in new_comments)
                if total_replies > 0:
                    safe_print(f"   💬 Total replies: {total_replies}")
                
                success_count += 1
                total_new_comments += new_comment_count
                
                # Save after each chapter (incremental progress)
                safe_print(f"   💾 Saving progress...")
                if save_book_json(json_path, book_data):
                    safe_print(f"   ✅ Saved")
                else:
                    safe_print(f"   ⚠️  Save failed")
                
                # Small delay between chapters
                time.sleep(2)
                
            except Exception as e:
                safe_print(f"   ❌ Error: {e}")
                error_count += 1
                continue
    
    except KeyboardInterrupt:
        safe_print("\n\n🛑 Interrupted by user")
        safe_print("💾 Saving current progress...")
        save_book_json(json_path, book_data)
    
    finally:
        # Clean up
        scraper.stop()
    
    # Final summary
    safe_print()
    safe_print("="*80)
    safe_print("📊 REFETCH COMPLETE")
    safe_print("="*80)
    safe_print(f"✅ Successful: {success_count}/{len(chapters)}")
    safe_print(f"❌ Failed: {error_count}/{len(chapters)}")
    safe_print(f"💬 Total comments collected: {total_new_comments}")
    safe_print()
    
    if error_count > 0:
        safe_print(f"⚠️  {error_count} chapters failed - review output above")
    
    safe_print(f"💾 Updated file: {json_path}")
    
    # Backup info
    backup_path = json_path + '.backup'
    if os.path.exists(backup_path):
        safe_print(f"🔙 Original backup: {backup_path}")
    
    safe_print("="*80)
    safe_print()
    
    return True


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        safe_print("❌ Usage: python refetch_chapter_comments.py <path_to_book_json>")
        safe_print()
        safe_print("Example:")
        safe_print('   python refetch_chapter_comments.py "data/json/bk_0e01a5eb8d91_Avatar_TLAB_Tai_Lung.json"')
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    if not os.path.exists(json_path):
        safe_print(f"❌ File not found: {json_path}")
        sys.exit(1)
    
    success = refetch_chapter_comments(json_path)
    
    if success:
        safe_print("✅ Done!")
    else:
        safe_print("❌ Refetch failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
