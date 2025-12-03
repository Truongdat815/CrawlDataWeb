"""
Test script để scrape một story cụ thể từ ScribbleHub
"""
from src.scraper_engine import ScribbleHubScraper
from src.utils import safe_print

def main():
    # URL story cụ thể để test
    story_url = "https://www.scribblehub.com/series/1266790/dao-of-money-xianxia-business/"
    
    safe_print("=" * 60)
    safe_print("🧪 TEST SCRIBBLEHUB SCRAPER")
    safe_print("=" * 60)
    safe_print(f"📖 URL: {story_url}")
    safe_print("=" * 60)
    
    # Khởi tạo bot
    bot = ScribbleHubScraper()
    
    try:
        bot.start()
        safe_print("\n🚀 Bắt đầu scrape...\n")
        
        # Cào story cụ thể
        bot.scrape_story(story_url)
        
        safe_print("\n" + "=" * 60)
        safe_print("✅ Hoàn thành test!")
        safe_print("=" * 60)
        
    except Exception as e:
        safe_print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bot.stop()

if __name__ == "__main__":
    main()


