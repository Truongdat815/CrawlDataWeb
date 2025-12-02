import sys

# Helper function để print an toàn với encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

from src.webnovel_scraper import WebnovelScraper

def main():
    # URL của bộ truyện Webnovel cần cào
    book_url = "https://www.webnovel.com/book/avatar-tlab-tai-lung_34078380808505505"
    
    # Khởi tạo scraper
    scraper = WebnovelScraper()
    
    try:
        scraper.start()

        # Command-line flag: --export-cookies -> open browser, let user login, then save cookies.json
        if '--export-cookies' in sys.argv:
            scraper.export_cookies_interactive(target_url=book_url, save_path='cookies.json')
        else:
            # Cào book without manual login (no interactive steps)
            scraper.scrape_book(book_url, max_chapters=None, wait_for_login=False)
    except Exception as e:
        safe_print(f"❌ Error: {e}")
        import traceback
        safe_print(traceback.format_exc())
    finally:
        scraper.stop()

if __name__ == "__main__":
    main()