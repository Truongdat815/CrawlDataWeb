"""
RoyalRoad Scraper Engine - Main orchestrator
Sử dụng các handlers để thực hiện scraping
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from src import config
from src.utils import safe_print, goto_with_retry

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
        goto_with_retry(self.page, best_rated_url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name="Scraper")
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
        goto_with_retry(self.page, story_url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name="Scraper")
        
        # 1. Lấy web_story_id từ URL (Ví dụ: 21220)
        web_story_id = story_url.split("/")[4]
        
        # 2. Cào metadata của story (hoặc lấy story_id nếu đã có)
        # Return: (story_data, story_id, match_type)
        # match_type có thể là: "url", "hash", "new"
        result = self.story_handler.scrape_story_metadata(story_url, web_story_id)
        if len(result) == 3:
            story_data, story_id, match_type = result
        else:
            # Fallback cho code cũ (nếu chưa update)
            story_data, story_id = result
            match_type = "new" if story_data else "url"
        
        # 3. Lấy totalChapters từ HTML (từ trang story hiện tại)
        total_web_chapters_str = self.story_handler.get_total_chapters_from_html()
        total_web_chapters = int(total_web_chapters_str) if total_web_chapters_str else 0
        
        # 4. Lấy totalChapters từ DB để so sánh
        db_total_chapters = 0
        if match_type == "url":
            # URL trùng: Lấy story từ DB theo URL
            from src.utils import normalize_url
            normalized_url = normalize_url(story_url)
            existing_story = self.mongo.find_story_by_url(normalized_url)
            if existing_story:
                db_total_chapters_str = existing_story.get("totalChapters")
                if db_total_chapters_str:
                    try:
                        db_total_chapters = int(db_total_chapters_str)
                    except:
                        db_total_chapters = 0
        elif match_type == "hash":
            # Hash trùng: Lấy story từ DB theo story_id
            existing_story = self.mongo.get_story_by_id(story_id)
            if existing_story:
                db_total_chapters_str = existing_story.get("totalChapters")
                if db_total_chapters_str:
                    try:
                        db_total_chapters = int(db_total_chapters_str)
                    except:
                        db_total_chapters = 0
        else:
            # Truyện mới: db_total_chapters = 0
            db_total_chapters = 0
        
        safe_print(f"📊 DB có {db_total_chapters} chapters, Web có {total_web_chapters} chapters (match_type: {match_type})")
        
        # 5. Lấy danh sách link chương từ TẤT CẢ các trang phân trang
        safe_print("... Đang lấy danh sách chương từ tất cả các trang")
        chapter_info_list = self.story_handler.get_all_chapters_from_pagination(story_url)
        
        safe_print(f"--> Tổng cộng tìm thấy {len(chapter_info_list)} chương từ tất cả các trang.")
        
        # 6. Logic: Chỉ cào các chapters còn thiếu
        chapters_to_scrape = []
        
        if match_type == "url":
            # URL trùng: Bỏ qua chapter đã cào, cào tiếp những chapter chưa có
            # Check từng chapter để đảm bảo không bỏ sót
            for index, chapter_info in enumerate(chapter_info_list):
                chap_url = chapter_info["url"]
                
                # Kiểm tra chapter đã có chưa (check theo URL)
                if chap_url and self.mongo.is_chapter_scraped(chap_url):
                    safe_print(f"    ⏭️  Bỏ qua chapter {index + 1} (đã có trong DB): {chap_url}")
                else:
                    chapters_to_scrape.append((index, chapter_info))
            
            if chapters_to_scrape:
                safe_print(f"🚀 Tìm thấy {len(chapters_to_scrape)} chapters chưa có trong DB")
            else:
                safe_print(f"✅ Tất cả chapters đã có trong DB")
        
        elif match_type == "hash":
            # Hash trùng (cùng một bộ truyện từ nền tảng khác): So sánh tổng chapter
            # Chỉ cào chapters mới nếu total_web_chapters > db_total_chapters
            if total_web_chapters > db_total_chapters:
                # Chỉ lấy các chapters từ index db_total_chapters đến cuối
                for index in range(db_total_chapters, len(chapter_info_list)):
                    chapters_to_scrape.append((index, chapter_info_list[index]))
                safe_print(f"🚀 Cần cào {len(chapters_to_scrape)} chapters mới (từ index {db_total_chapters} đến {total_web_chapters - 1})")
            else:
                safe_print(f"✅ Tất cả chapters đã có trong DB (DB: {db_total_chapters}, Web: {total_web_chapters})")
        
        else:
            # Truyện mới: Cào tất cả chapters
            for index, chapter_info in enumerate(chapter_info_list):
                chapters_to_scrape.append((index, chapter_info))
            safe_print(f"🚀 Truyện mới, cần cào {len(chapters_to_scrape)} chapters")
        
        # 7. Cào các chương song song với ThreadPoolExecutor
        if chapters_to_scrape:
            safe_print(f"🚀 Bắt đầu cào {len(chapters_to_scrape)} chương với {self.max_workers} thread...")
        
        # Tạo list kết quả cố định theo index - mỗi index = 1 chương
        chapter_results = [None] * len(chapter_info_list)
        
        # Dictionary để map future -> index để biết chương nào
        future_to_index = {}
        
            # Sử dụng ThreadPoolExecutor
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
            
                # Thu thập kết quả
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    chapter_data = future.result()
                    chapter_results[index] = chapter_data
                    completed += 1
                    status = "✅" if chapter_data else "⚠️"
                    safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_info_list)} (đã xong {completed}/{len(chapters_to_scrape)})")
                except Exception as e:
                    safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                    chapter_results[index] = None
            
            # SAU KHI TẤT CẢ XONG: Đếm số chapters đã cào thành công
            safe_print(f"📝 Đang kiểm tra kết quả...")
            successful_chapters = sum(1 for ch in chapter_results if ch is not None)
            safe_print(f"✅ Đã hoàn thành {successful_chapters}/{len(chapters_to_scrape)} chương")
        
        # 8. Cập nhật totalChapters trong DB (lấy từ HTML) - luôn cập nhật để đảm bảo đồng bộ
        if total_web_chapters_str:
            self.mongo.update_story_total_chapters(story_id, total_web_chapters_str)
        
        # 9. Sau khi lưu tất cả chapters, quay lại URL của truyện để scrape reviews
        safe_print("... Đang quay lại trang truyện để lấy reviews")
        goto_with_retry(self.page, story_url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name="Scraper")
        time.sleep(2)
        
        safe_print("... Đang lấy reviews cho toàn bộ truyện")
        reviews = self.review_handler.scrape_reviews(story_url, story_id)
        safe_print(f"✅ Đã lấy được {len(reviews)} reviews")
        
        # 6. Scrape profile của các users từ comments chưa có đầy đủ thông tin (song song với ThreadPoolExecutor)
        safe_print("\n📋 Đang scrape profile của các users từ comments chưa có đầy đủ thông tin...")
        
        # Lấy tất cả chapterId của story hiện tại
        chapter_ids = [
            ch.get("chapterId") 
            for ch in self.mongo.mongo_collection_chapters.find(
                {"storyId": story_id},
                {"chapterId": 1}
            )
        ]
        safe_print(f"   Tìm thấy {len(chapter_ids)} chapters của story hiện tại")
        
        # Lấy danh sách userId từ comments của các chapters đó (chỉ lấy users từ story này)
        if chapter_ids:
            user_ids_from_comments = self.mongo.mongo_collection_comments.distinct(
                "userId",
                {"chapterId": {"$in": chapter_ids}}
            )
            safe_print(f"   Tìm thấy {len(user_ids_from_comments)} users từ comments của story này")
        else:
            user_ids_from_comments = []
            safe_print(f"   ⏭️  Không có chapters nào, không có users từ comments")
        
        users_to_scrape = []
        if user_ids_from_comments:
            # Chỉ lấy users từ comments chưa có đầy đủ thông tin
            users_to_scrape = list(self.mongo.mongo_collection_users.find({
                "$and": [
                    {"userId": {"$in": user_ids_from_comments}},
                    {
                        "$or": [
                            {"createdDate": None},
                            {"createdDate": {"$exists": False}},
                            {"followers": None},
                            {"followers": {"$exists": False}}
                        ]
                    },
                    {
                        "$or": [
                            {"userUrl": {"$ne": None, "$ne": ""}},
                            {"userUrl": {"$exists": True}}
                        ]
                    }
                ]
            }))
            safe_print(f"   Tìm thấy {len(users_to_scrape)} users từ comments cần scrape profile")
        else:
            safe_print("   ⏭️  Không có users nào từ comments")
        
        if users_to_scrape:
            safe_print(f"   🚀 Bắt đầu scrape với {self.max_workers} thread...")
            
            # Dictionary để map future -> user info
            future_to_user = {}
            
            # Sử dụng ThreadPoolExecutor - mỗi worker có browser instance riêng
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tất cả users cần scrape
                for index, user in enumerate(users_to_scrape):
                    user_url = user.get("userUrl")
                    web_user_id = user.get("webUserId")
                    
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
