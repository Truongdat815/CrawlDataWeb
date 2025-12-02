from src.scraper_engine import RoyalRoadScraper
from src.utils import safe_print

def main():
    # ===== PHẦN CŨ: Lấy danh sách URL từ best-rated (ĐÃ COMMENT) =====
    # URL trang best-rated
    # best_rated_url = "https://www.royalroad.com/fictions/best-rated?page=500"
    # bot.scrape_best_rated_stories(best_rated_url, num_stories=1, start_from=0)
    # ===================================================================
    
    # ===== PHẦN MỚI: Cào trực tiếp một URL truyện =====
    # Đặt URL truyện bạn muốn cào vào đây
    story_url = "https://www.royalroad.com/fiction/120083/the-theogenesis-theorem-litrpg-progression-high"
    # ==================================================
    
    # Khởi tạo bot
    bot = RoyalRoadScraper()
    
    try:
        bot.start()
        # Cào trực tiếp bộ truyện từ URL
        bot.scrape_story(story_url)
    except Exception as e:
        safe_print(f"Lỗi chương trình: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()