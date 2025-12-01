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
    # URL trang best-rated
    best_rated_url = "https://www.royalroad.com/fictions/best-rated?page=500u"
    
    # Khởi tạo bot
    bot = RoyalRoadScraper()
    
    try:
        bot.start()
        # Cào 5 bộ truyện đầu tiên
        # start_from=0 nghĩa là bắt đầu từ vị trí 0 (bộ đầu tiên)
        bot.scrape_best_rated_stories(best_rated_url, num_stories=5, start_from=0)
    except Exception as e:
        safe_print(f"Lỗi chương trình: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()