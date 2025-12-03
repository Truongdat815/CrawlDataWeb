from src.scraper_engine import ScribbleHubScraper
from src.utils import safe_print

def main():
    # ===== PHẦN CŨ: Lấy danh sách URL từ series-ranking =====
    ranking_url = "https://www.scribblehub.com/series-ranking/?pg=50"
    # ===================================================================
    
    # ===== PHẦN MỚI: Cào trực tiếp một URL truyện (ĐÃ COMMENT) =====
    # story_url = "https://www.scribblehub.com/read/1709446-fractured-i-became-hersouls-game--vrmmo--litrpg/"
    # bot.scrape_story(story_url)
    # ==================================================
    
    # Khởi tạo bot
    bot = ScribbleHubScraper()
    
    try:
        bot.start()
        # Cào từ trang series-ranking
        bot.scrape_best_rated_stories(ranking_url, num_stories=10, start_from=0)
    except Exception as e:
        safe_print(f"Lỗi chương trình: {e}")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()