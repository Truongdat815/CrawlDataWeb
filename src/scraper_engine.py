"""
RoyalRoad Scraper Engine - Main orchestrator
Sử dụng các handlers để thực hiện scraping
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from src import config
from src.utils import safe_print

# Import handlers
from src.handlers.base_handler import BaseHandler
from src.handlers.mongo_handler import MongoHandler
from src.handlers.user_handler import UserHandler
from src.handlers.story_handler import StoryHandler
from src.handlers.chapter_handler import ChapterHandler
from src.handlers.comment_handler import CommentHandler
from src.handlers.review_handler import ReviewHandler


class RoyalRoadScraper(BaseHandler):
    """Main scraper class - orchestrator cho tất cả handlers"""
    
    def __init__(self, max_workers=None):
        # Gọi __init__ của BaseHandler để khởi tạo browser attributes
        super().__init__()
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Khởi tạo MongoDB handler
        self.mongo = MongoHandler()
        
        # Khởi tạo UserHandler (không cần page)
        self.user_handler = UserHandler(self.mongo)
        
        # Handlers sẽ được khởi tạo sau khi start() được gọi (khi có page)
        self.story_handler = None
        self.chapter_handler = None
        self.comment_handler = None
        self.review_handler = None
    
    def start(self):
        """Khởi động trình duyệt và khởi tạo handlers"""
        # Sử dụng method từ BaseHandler
        self.start_browser()
        
        # Khởi tạo handlers sau khi có page
        self.comment_handler = CommentHandler(self.page, self.mongo, self.user_handler)
        self.review_handler = ReviewHandler(self.page, self.mongo, self.user_handler)
        self.story_handler = StoryHandler(self.page, self.mongo, self.user_handler)
        self.chapter_handler = ChapterHandler(self.mongo, self.comment_handler)
    
    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        # Sử dụng method từ BaseHandler để đóng browser
        self.stop_browser()
        
        # Đóng MongoDB connection
        if self.mongo:
            self.mongo.close()
    
    def scrape_best_rated_stories(self, best_rated_url, num_stories=10, start_from=0):
        """
        Cào nhiều bộ truyện từ trang best-rated
        Args:
            best_rated_url: URL trang best-rated
            num_stories: Số lượng bộ truyện muốn cào (mặc định 10)
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên, 5 = bỏ qua 5 bộ đầu)
        """
        safe_print(f"📚 Đang truy cập trang best-rated: {best_rated_url}")
        self.page.goto(best_rated_url, timeout=config.TIMEOUT)
        time.sleep(2)
        
        # Lấy danh sách các bộ truyện từ trang best-rated
        if start_from > 0:
            safe_print(f"🔍 Đang lấy danh sách {num_stories} bộ truyện (bắt đầu từ vị trí {start_from + 1})...")
        else:
            safe_print(f"🔍 Đang lấy danh sách {num_stories} bộ truyện đầu tiên...")
        story_urls = self.story_handler.get_story_urls_from_best_rated(num_stories, start_from)
        
        if not story_urls:
            safe_print("❌ Không tìm thấy bộ truyện nào!")
            return
        
        safe_print(f"✅ Đã tìm thấy {len(story_urls)} bộ truyện:")
        for i, url in enumerate(story_urls, 1):
            safe_print(f"   {i}. {url}")
        
        # Cào từng bộ truyện tuần tự
        for index, story_url in enumerate(story_urls, 1):
            safe_print(f"\n{'='*60}")
            safe_print(f"📖 Bắt đầu cào bộ truyện {index}/{len(story_urls)}")
            safe_print(f"{'='*60}")
            try:
                self.scrape_story(story_url)
                safe_print(f"✅ Hoàn thành bộ truyện {index}/{len(story_urls)}")
            except Exception as e:
                safe_print(f"❌ Lỗi khi cào bộ truyện {index}: {e}")
                continue
            
            # Delay giữa các bộ truyện
            if index < len(story_urls):
                safe_print(f"⏳ Nghỉ {config.DELAY_BETWEEN_CHAPTERS * 2} giây trước khi cào bộ tiếp theo...")
                time.sleep(config.DELAY_BETWEEN_CHAPTERS * 2)
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🎉 Đã hoàn thành cào {len(story_urls)} bộ truyện!")
        safe_print(f"{'='*60}")
    
    def scrape_story(self, story_url):
        """
        Hàm chính để cào toàn bộ 1 bộ truyện.
        Luồng đi: Vào trang truyện -> Lấy Info -> Lấy List Chapter -> Vào từng Chapter -> Lấy Content.
        """
        safe_print(f"🌍 Đang truy cập truyện: {story_url}")
        self.page.goto(story_url, timeout=config.TIMEOUT)
        
        # 1. Lấy web_story_id từ URL (Ví dụ: 21220)
        web_story_id = story_url.split("/")[4]
        
        # 2. Cào metadata của story (hoặc lấy story_id nếu đã có)
        story_data, story_id = self.story_handler.scrape_story_metadata(story_url, web_story_id)
        
        # Nếu story_data là None, nghĩa là story đã có trong DB
        if story_data is None:
            # Lấy story_id từ DB
            existing_story = self.mongo.get_story_by_web_id(web_story_id)
            if existing_story:
                story_id = existing_story.get("story_id")
            else:
                from src.utils import generate_id
                story_id = generate_id()
        
        # 3. Lấy danh sách link chương từ TẤT CẢ các trang phân trang
        safe_print("... Đang lấy danh sách chương từ tất cả các trang")
        chapter_info_list = self.story_handler.get_all_chapters_from_pagination(story_url)
        
        safe_print(f"--> Tổng cộng tìm thấy {len(chapter_info_list)} chương từ tất cả các trang.")
        
        # 4. Cào các chương song song với ThreadPoolExecutor (GIỮ ĐÚNG THỨ TỰ)
        # Lọc ra các chapters chưa được cào (để tránh cào trùng)
        chapters_to_scrape = []
        for index, chapter_info in enumerate(chapter_info_list):
            chap_url = chapter_info["url"]
            # Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                url_parts = chap_url.split("/chapter/")
                if len(url_parts) > 1:
                    web_chapter_id = url_parts[1].split("/")[0]
            except:
                pass
            
            # Kiểm tra chapter đã có chưa (check theo web_chapter_id)
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"    ⏭️  Bỏ qua chapter {index + 1} (đã có trong DB): {web_chapter_id}")
            else:
                chapters_to_scrape.append((index, chapter_info))
        
        safe_print(f"🚀 Bắt đầu cào {len(chapters_to_scrape)}/{len(chapter_info_list)} chương (đã bỏ qua {len(chapter_info_list) - len(chapters_to_scrape)} chương đã có) với {self.max_workers} thread...")
        
        # Tạo list kết quả cố định theo index - mỗi index = 1 chương
        chapter_results = [None] * len(chapter_info_list)
        
        # Dictionary để map future -> index để biết chương nào
        future_to_index = {}
        
        # Sử dụng ThreadPoolExecutor - NÓ TỰ ĐỘNG PHÂN PHỐI công việc!
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit chỉ các chapters chưa được cào
            for index, chapter_info in chapters_to_scrape:
                # order = index + 1 (số thứ tự bắt đầu từ 1)
                order = index + 1
                chap_url = chapter_info["url"]
                published_time_from_table = chapter_info.get("published_time", "")
                future = executor.submit(
                    self.chapter_handler.scrape_single_chapter_worker,
                    chap_url, index, story_id, order, published_time_from_table
                )
                future_to_index[future] = index
            
            # Thu thập kết quả - các thread có thể hoàn thành bất kỳ lúc nào
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]  # Lấy index của chương này
                try:
                    chapter_data = future.result()
                    # LƯU VÀO ĐÚNG VỊ TRÍ INDEX - không phải append!
                    chapter_results[index] = chapter_data
                    completed += 1
                    status = "✅" if chapter_data else "⚠️"
                    safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_info_list)} (đã xong {completed}/{len(chapter_info_list)})")
                except Exception as e:
                    safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                    chapter_results[index] = None
        
        # SAU KHI TẤT CẢ XONG: Đếm số chapters đã cào thành công
        safe_print(f"📝 Đang kiểm tra kết quả...")
        successful_chapters = sum(1 for ch in chapter_results if ch is not None)
        safe_print(f"✅ Đã hoàn thành {successful_chapters}/{len(chapter_info_list)} chương (theo đúng thứ tự)")
        
        # 5. Sau khi lưu tất cả chapters, quay lại URL của truyện để scrape reviews
        safe_print("... Đang quay lại trang truyện để lấy reviews")
        self.page.goto(story_url, timeout=config.TIMEOUT)
        time.sleep(2)
        
        safe_print("... Đang lấy reviews cho toàn bộ truyện")
        reviews = self.review_handler.scrape_reviews(story_url, story_id)
        safe_print(f"✅ Đã lấy được {len(reviews)} reviews")
        
        # 6. Scrape profile của các users chưa có đầy đủ thông tin (song song với ThreadPoolExecutor)
        safe_print("\n📋 Đang scrape profile của các users chưa có đầy đủ thông tin...")
        users_to_scrape = list(self.mongo.mongo_collection_users.find({
            "$or": [
                {"created_date": ""},
                {"followers": ""}
            ],
            "user_url": {"$ne": ""}
        }))
        
        if users_to_scrape:
            safe_print(f"   Tìm thấy {len(users_to_scrape)} users cần scrape profile")
            safe_print(f"   🚀 Bắt đầu scrape với {self.max_workers} thread...")
            
            # Dictionary để map future -> user info
            future_to_user = {}
            
            # Sử dụng ThreadPoolExecutor - mỗi worker có browser instance riêng
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tất cả users cần scrape
                for index, user in enumerate(users_to_scrape):
                    user_url = user.get("user_url")
                    web_user_id = user.get("web_user_id")
                    
                    if user_url:
                        future = executor.submit(
                            self.user_handler.scrape_user_profile_worker,
                            user_url, web_user_id, index
                        )
                        future_to_user[future] = (web_user_id, index)
                
                # Thu thập kết quả
                completed = 0
                for future in as_completed(future_to_user):
                    web_user_id, index = future_to_user[future]
                    try:
                        user_id = future.result()
                        completed += 1
                        status = "✅" if user_id else "⚠️"
                        safe_print(f"    {status} Hoàn thành user {index + 1}/{len(users_to_scrape)}: {web_user_id} (đã xong {completed}/{len(users_to_scrape)})")
                    except Exception as e:
                        safe_print(f"    ❌ Lỗi khi scrape profile user {web_user_id}: {e}")
            
            safe_print(f"✅ Đã hoàn thành scrape profile của {completed}/{len(users_to_scrape)} users")
        else:
            safe_print("   ✅ Tất cả users đã có đầy đủ thông tin")
        
        # 7. Cập nhật story trong MongoDB (chapters và reviews đã được lưu vào collections riêng)
        if story_data:
            self.mongo.save_story(story_data)
