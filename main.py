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

from src.scraper_engine import RoyalRoadScraper

def main():
    # URL trang complete
    best_rated_url = "https://www.royalroad.com/fictions/complete"
    
    # Khởi tạo bot
    bot = RoyalRoadScraper()
    
    try:
        bot.start()
        # Cào 2 bộ truyện đầu tiên từ trang best-rated
        bot.scrape_best_rated_fictions(best_rated_url, num_fictions=2)
    except Exception as e:
        safe_print(f"Lỗi chương trình: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()