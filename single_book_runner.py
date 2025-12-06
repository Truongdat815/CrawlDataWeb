"""
Single Book Runner - Scrape one book with fresh browser process
Used by batch_runner.py to avoid async/memory/Cloudflare issues

Usage:
    python single_book_runner.py <book_url> [--chapters N]
"""
import sys
import argparse
from src.webnovel_scraper import WebnovelScraper


def main():
    parser = argparse.ArgumentParser(description='Scrape a single Webnovel book')
    parser.add_argument('url', help='Book URL to scrape')
    parser.add_argument('--chapters', type=int, default=None, help='Max chapters to scrape (default: None = ALL)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--fast', action='store_true', help='Enable fast mode (block resources)')
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"📖 SINGLE BOOK SCRAPER")
    print(f"{'='*70}")
    print(f"   URL: {args.url}")
    print(f"   Chapter Limit: {args.chapters}")
    print(f"   Headless: {args.headless}")
    print(f"   Fast Mode: {args.fast}")
    print(f"{'='*70}\n")

    # Initialize scraper with optimal settings for Cloudflare bypass
    # Visual mode + load resources = best success rate
    scraper = WebnovelScraper(
        headless=args.headless,
        block_resources=args.fast
    )

    try:
        scraper.start()
        print("✅ Browser started successfully\n")

        # Scrape the book with chapter limit
        book_data = scraper.scrape_book(
            book_url=args.url,
            chapter_limit=args.chapters
        )

        if book_data:
            print(f"\n{'='*70}")
            print(f"✅ SUCCESS!")
            print(f"   Book: {book_data.get('name', 'Unknown')}")
            print(f"   Chapters scraped: {len(book_data.get('chapters', []))}")
            print(f"   Comments scraped: {len(book_data.get('comments', []))}")
            print(f"{'='*70}\n")
            sys.exit(0)
        else:
            print("\n❌ ERROR: scrape_book returned None")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ ERROR during scraping: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        try:
            scraper.stop()
            print("🛑 Browser stopped cleanly\n")
        except Exception as e:
            print(f"⚠️  Error stopping browser: {e}")


if __name__ == '__main__':
    main()
