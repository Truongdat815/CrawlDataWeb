"""
Test Chapter Comments Fix - Verify the username/reply fixes work
Tests on a single chapter before running full refetch

Usage:
    python test_chapter_comments_fix.py <chapter_url>
    
Example:
    python test_chapter_comments_fix.py "https://www.webnovel.com/book/avatar-tlab-tai-lung_34078380808505505/chapter-1-a-new-beginning_91653802867374764"
"""

import sys
import os
import json

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


def test_chapter_comments(chapter_url):
    """Test chapter comment scraping with fixed logic"""
    safe_print("\n" + "="*80)
    safe_print("🧪 TEST CHAPTER COMMENTS FIX")
    safe_print("="*80)
    safe_print(f"URL: {chapter_url}")
    safe_print("="*80 + "\n")
    
    # Check for cookies
    if not os.path.exists('cookies.json'):
        safe_print("⚠️  WARNING: cookies.json not found!")
        safe_print("   Run setup_login.py first for authenticated scraping")
        safe_print()
    
    # Initialize scraper
    scraper = WebnovelScraper(
        headless=False,  # Visual mode
        block_resources=False
    )
    
    scraper.start()
    
    try:
        # Navigate to chapter
        safe_print("🌐 Loading chapter page...")
        scraper.page.goto(chapter_url, timeout=60000)
        scraper.page.wait_for_load_state("networkidle", timeout=30000)
        safe_print("✅ Page loaded\n")
        
        # Scrape comments
        safe_print("💬 Scraping comments with FIXED logic...\n")
        comments = scraper._scrape_chapter_comments("test_ch_001")
        
        # Display results
        safe_print("\n" + "="*80)
        safe_print("📊 RESULTS")
        safe_print("="*80)
        safe_print(f"Total Comments: {len(comments)}\n")
        
        if comments:
            safe_print("First 3 comments:\n")
            for i, comment in enumerate(comments[:3], 1):
                safe_print(f"Comment {i}:")
                safe_print(f"  👤 Username: {comment.get('user_name')}")
                safe_print(f"  🕒 Time: {comment.get('time')}")
                safe_print(f"  💬 Content: {comment.get('content')[:80]}...")
                safe_print(f"  💭 Replies: {len(comment.get('replies', []))}")
                
                # Show first reply if exists
                if comment.get('replies'):
                    reply = comment['replies'][0]
                    safe_print(f"     └─ Reply by {reply.get('user_name')}: {reply.get('content')[:50]}...")
                
                safe_print()
            
            # Validation checks
            safe_print("="*80)
            safe_print("✅ VALIDATION CHECKS")
            safe_print("="*80)
            
            # Check 1: Username != Content
            username_equals_content = sum(1 for c in comments if c.get('user_name') == c.get('content'))
            safe_print(f"❌ Usernames matching content: {username_equals_content}/{len(comments)}")
            
            if username_equals_content > 0:
                safe_print("   ⚠️  BUG STILL EXISTS! Usernames are still wrong.")
            else:
                safe_print("   ✅ Usernames look correct!")
            
            # Check 2: Replies found
            comments_with_replies = sum(1 for c in comments if c.get('replies'))
            safe_print(f"💭 Comments with replies: {comments_with_replies}/{len(comments)}")
            
            if comments_with_replies > 0:
                safe_print("   ✅ Reply extraction working!")
            else:
                safe_print("   ⚠️  No replies found (may be normal if chapter has no replies)")
            
            # Check 3: Valid usernames (short, no newlines)
            invalid_usernames = sum(1 for c in comments 
                                  if len(c.get('user_name', '')) > 50 or '\n' in c.get('user_name', ''))
            safe_print(f"⚠️  Invalid usernames: {invalid_usernames}/{len(comments)}")
            
            if invalid_usernames == 0:
                safe_print("   ✅ All usernames valid!")
            else:
                safe_print("   ⚠️  Some usernames look suspicious (too long or multiline)")
            
            safe_print("="*80)
            
            # Save to test output
            output_file = "test_chapter_comments_output.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(comments, f, indent=2, ensure_ascii=False)
            safe_print(f"\n💾 Saved to: {output_file}")
            safe_print("   Review this file to verify the fixes\n")
        
        else:
            safe_print("⚠️  No comments found")
            safe_print("   This could mean:")
            safe_print("   - Chapter has no comments")
            safe_print("   - Selectors are still wrong")
            safe_print("   - Login required (check cookies.json)")
        
    except Exception as e:
        safe_print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        scraper.stop()
    
    safe_print("\n" + "="*80)
    safe_print("🧪 Test Complete")
    safe_print("="*80 + "\n")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        safe_print("❌ Usage: python test_chapter_comments_fix.py <chapter_url>")
        safe_print()
        safe_print("Example:")
        safe_print('   python test_chapter_comments_fix.py "https://www.webnovel.com/book/avatar-tlab-tai-lung_34078380808505505/chapter-1-a-new-beginning_91653802867374764"')
        sys.exit(1)
    
    chapter_url = sys.argv[1]
    test_chapter_comments(chapter_url)


if __name__ == '__main__':
    main()
