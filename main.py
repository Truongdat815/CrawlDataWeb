from src.scraper_engine import ScribbleHubScraper
from src.utils import safe_print
from src import config

def main():
    # ===== Cào 10 bộ truyện từ trang ranking =====
    # URL ranking: https://www.scribblehub.com/series-ranking/
    # Có thể thay đổi page bằng cách thêm ?pg=X (ví dụ: ?pg=1, ?pg=2, ...)
    ranking_url = "https://www.scribblehub.com/series-ranking/"
    
    # Số lượng bộ truyện muốn cào
    num_stories = 10
    
    # Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên)
    start_from = 0
    # ==================================================
    
    # Khởi tạo bot
    bot = ScribbleHubScraper()
    
    try:
        bot.start()
        
        safe_print("=" * 80)
        safe_print(f"🚀 BẮT ĐẦU CÀO {num_stories} BỘ TRUYỆN")
        safe_print("=" * 80)
        safe_print(f"📄 Ranking URL: {ranking_url}")
        safe_print(f"📚 Số lượng: {num_stories} bộ truyện")
        safe_print(f"📍 Bắt đầu từ: Vị trí {start_from + 1}")
        safe_print("=" * 80)
        safe_print("")
        
        # Cào các bộ truyện từ ranking
        # Hàm này sẽ:
        # 1. Lấy danh sách URL từ ranking page
        # 2. Cào từng bộ truyện với đầy đủ:
        #    - Story metadata (title, author, description, tags, etc.)
        #    - Tất cả chapters (toàn bộ, không giới hạn)
        #    - Chapter contents (full text)
        #    - Comments
        #    - Reviews
        #    - Rankings
        #    - User info
        #    - Glossary (nếu có)
        bot.scrape_best_rated_stories(
            ranking_url=ranking_url,
            num_stories=num_stories,
            start_from=start_from
        )
        
        safe_print("")
        safe_print("=" * 80)
        safe_print(f"✅ ĐÃ HOÀN THÀNH CÀO {num_stories} BỘ TRUYỆN!")
        safe_print("=" * 80)
        safe_print("📁 Dữ liệu đã được lưu vào:")
        safe_print(f"   - MongoDB: {config.MONGODB_DB_NAME}")
        safe_print(f"   - JSON files: {config.JSON_DIR}")
        
    except Exception as e:
        safe_print(f"❌ Lỗi chương trình: {e}")
        import traceback
        safe_print(traceback.format_exc())
    finally:
        bot.stop()

if __name__ == "__main__":
    main()