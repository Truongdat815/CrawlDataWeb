from src.scraper_engine import ScribbleHubScraper
from src.utils import safe_print
from src import config

def main():
    # ===== Cào story cụ thể =====
    story_url = "https://www.scribblehub.com/series/1077902/conquest/"
    # Chỉ cào 2 chapter đầu tiên (đã set trong scraper_engine.py)
    # ==================================================
    
    # Khởi tạo bot
    bot = ScribbleHubScraper()
    
    try:
        bot.start()
        
        safe_print("=" * 80)
        safe_print("🚀 BẮT ĐẦU CÀO STORY")
        safe_print("=" * 80)
        safe_print(f"📄 Story URL: {story_url}")
        safe_print(f"📚 Số lượng: 2 chapters đầu tiên")
        safe_print("=" * 80)
        safe_print("")
        
        # Cào story cụ thể
        # Hàm này sẽ:
        # 1. Cào story metadata (title, author, description, tags, etc.)
        # 2. Cào 2 chapters đầu tiên
        #    - Chapter contents (full text)
        #    - Comments
        #    - Reviews
        #    - Rankings
        #    - User info
        #    - Glossary (nếu có)
        bot.scrape_story(story_url)
        
        safe_print("")
        safe_print("=" * 80)
        safe_print("✅ ĐÃ HOÀN THÀNH CÀO STORY!")
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