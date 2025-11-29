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
    best_rated_url = "https://www.royalroad.com/fictions/best-rated"
    
    # Khởi tạo bot
    bot = RoyalRoadScraper()
    
    try:
        bot.start()
        # Cào 5 bộ truyện tiếp theo (bắt đầu từ vị trí thứ 6, tức là bỏ qua 5 bộ đầu)
        # start_from=5 nghĩa là bỏ qua 5 bộ đầu tiên (vị trí 0-4), bắt đầu từ vị trí 5 (bộ thứ 6)
        bot.scrape_best_rated_fictions(best_rated_url, num_fictions=5, start_from=5)
    except Exception as e:
        safe_print(f"Lỗi chương trình: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()