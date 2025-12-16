from src.scraper_engine import ScribbleHubScraper
from src.utils import safe_print
from src import config

def main():
    # ===== Cào toàn bộ stories từ ranking page =====
    # Thay đổi ranking_url này thành link ranking page bạn muốn cào
    ranking_url = "https://www.scribblehub.com/series-ranking/"  # Có thể thêm ?pg=1, ?pg=2, etc.
    # Cào tất cả stories trong ranking page (không giới hạn)
    # ==================================================
    
    # Khởi tạo bot
    bot = ScribbleHubScraper()
    
    try:
        bot.start()
        
        safe_print("=" * 80)
        safe_print("🚀 BẮT ĐẦU CÀO TOÀN BỘ STORIES TỪ RANKING PAGE")
        safe_print("=" * 80)
        safe_print(f"📄 Ranking URL: {ranking_url}")
        safe_print(f"📚 Số lượng: TẤT CẢ stories trong ranking page")
        safe_print(f"📖 Chapters: TOÀN BỘ chapters của mỗi story")
        safe_print("=" * 80)
        safe_print("")
        
        # Cào toàn bộ stories từ ranking page
        # Hàm này sẽ:
        # 1. Lấy danh sách tất cả story URLs từ ranking page
        # 2. Với mỗi story:
        #    - Cào story metadata (title, author, description, tags, etc.)
        #    - Cào TOÀN BỘ chapters (không giới hạn)
        #      - Chapter contents (full text)
        #      - Comments
        #      - Reviews
        #      - Rankings
        #      - User info
        bot.scrape_best_rated_stories(ranking_url, num_stories=999999, start_from=0)  # num_stories lớn để lấy tất cả
        
        safe_print("")
        safe_print("=" * 80)
        safe_print("✅ ĐÃ HOÀN THÀNH CÀO TOÀN BỘ STORIES!")
        safe_print("=" * 80)
        safe_print("📁 Dữ liệu đã được lưu vào:")
        safe_print(f"   - MongoDB: {config.MONGODB_DB_NAME} ({config.MONGODB_URI})")
        safe_print(f"   - JSON files: {config.JSON_DIR}")
        
    except Exception as e:
        safe_print(f"❌ Lỗi chương trình: {e}")
        import traceback
        safe_print(traceback.format_exc())
    finally:
        bot.stop()

if __name__ == "__main__":
    main()