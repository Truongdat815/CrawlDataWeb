"""
ScribbleHub Scraper Engine - Main orchestrator
Sử dụng các handlers để thực hiện scraping
"""
import time
import random
from src import config
from src.utils import safe_print

# Import handlers
from src.handlers.base_handler import BaseHandler
from src.handlers.mongo_handler import MongoHandler
from src.handlers.story_handler import StoryHandler
from src.handlers.chapter_handler import ChapterHandler
from src.handlers.comment_handler import CommentHandler
from src.handlers.review_handler import ReviewHandler


class ScribbleHubScraper(BaseHandler):
    """Main scraper class - orchestrator cho tất cả handlers"""
    
    def __init__(self, max_workers=None):
        # Gọi __init__ của BaseHandler để khởi tạo browser attributes
        super().__init__()
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Khởi tạo MongoDB handler
        self.mongo = MongoHandler()
        
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
        self.comment_handler = CommentHandler(self.page, self.mongo)
        self.review_handler = ReviewHandler(self.page, self.mongo)
        self.story_handler = StoryHandler(self.page, self.mongo)
        # Truyền context vào ChapterHandler để dùng cho requests
        self.chapter_handler = ChapterHandler(self.mongo, self.comment_handler, self.context)

    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        # Sử dụng method từ BaseHandler để đóng browser
        self.stop_browser()
        
        # Đóng MongoDB connection
        if self.mongo:
            self.mongo.close()

    def scrape_best_rated_stories(self, best_rated_url, num_stories=10, start_from=0):
        """
        Cào nhiều bộ truyện từ trang series-ranking của ScribbleHub
        Args:
            best_rated_url: URL trang series-ranking (ví dụ: https://www.scribblehub.com/series-ranking/?pg=50)
            num_stories: Số lượng bộ truyện muốn cào (mặc định 10)
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên, 5 = bỏ qua 5 bộ đầu)
        """
        safe_print(f"📚 Đang truy cập trang series-ranking: {best_rated_url}")
        self.page.goto(best_rated_url, timeout=config.TIMEOUT)
        time.sleep(2)
        
        # Lấy danh sách các bộ truyện từ trang series-ranking
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
                    delay = config.get_delay_between_chapters() * 2
                    safe_print(f"⏳ Nghỉ {delay} giây trước khi cào bộ tiếp theo...")
                    time.sleep(delay)
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🎉 Đã hoàn thành cào {len(story_urls)} bộ truyện!")
        safe_print(f"{'='*60}")

    def scrape_story(self, story_url):
        """
        Hàm chính để cào toàn bộ 1 bộ truyện.
        Luồng đi: Vào trang truyện -> Lấy Info -> Lấy List Chapter -> Vào từng Chapter -> Lấy Content.
        """
        safe_print(f"🌍 Đang truy cập truyện: {story_url}")
        
        # Goto với wait_until="domcontentloaded" - KHÔNG dùng networkidle vì Cloudflare sẽ block
        safe_print("      🌐 Đang truy cập URL...")
        try:
            self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
        except:
            # Nếu lỗi, thử lại với load
            try:
                self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="load")
            except:
                # Cuối cùng thử với commit
                self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="commit")
        
        # Delay để đợi Cloudflare challenge bắt đầu
        check_delay = getattr(config, 'CLOUDFLARE_CHECK_DELAY', 5)
        time.sleep(check_delay)
        
        # Kiểm tra Cloudflare challenge
        safe_print("\n" + "="*60)
        safe_print("      🔒 KIỂM TRA CLOUDFLARE CHALLENGE")
        safe_print("="*60)
        
        # Kiểm tra ngay xem có challenge không
        page_content = self.page.content().lower()
        has_challenge = any(x in page_content for x in [
            "challenges.cloudflare.com",
            "please unblock",
            "checking your browser",
            "just a moment",
            "verifying you are human"
        ])
        
        if has_challenge:
            safe_print("      ⚠️ PHÁT HIỆN CLOUDFLARE CHALLENGE!")
            safe_print("\n      📋 HƯỚNG DẪN:")
            safe_print("         1. Nhìn vào browser window")
            safe_print("         2. Verify Cloudflare challenge (tick checkbox)")
            safe_print("         3. Đợi challenge hoàn thành (thường 5-15 giây)")
            safe_print("         4. Khi thấy page load xong (có title, có content)")
            safe_print("         5. Bấm ENTER trong terminal này để tiếp tục")
            safe_print("\n      ⏳ Code sẽ đợi bạn verify và bấm ENTER...")
            safe_print("      💡 Hoặc code sẽ tự động detect khi challenge pass (tối đa 5 phút)")
            
            # ✅ CHẾ ĐỘ MANUAL VERIFY: Đợi user verify và bấm Enter
            enable_manual = getattr(config, 'ENABLE_MANUAL_VERIFY', True)
            
            if enable_manual and not config.HEADLESS:
                safe_print("\n      ⌨️  BẤM ENTER KHI ĐÃ VERIFY XONG...")
                try:
                    max_wait_manual = 300  # 5 phút
                    start_time = time.time()
                    check_count = 0
                    
                    while time.time() - start_time < max_wait_manual:
                        check_count += 1
                        elapsed = int(time.time() - start_time)
                        
                        # In log mỗi 10 giây
                        if check_count % 10 == 0:
                            safe_print(f"      ⏳ Đang đợi... ({elapsed}s) - Bấm ENTER khi đã verify xong")
                        
                        # Kiểm tra xem challenge đã pass chưa
                        try:
                            page_content_check = self.page.content().lower()
                            has_challenge_check = any(x in page_content_check for x in [
                                "challenges.cloudflare.com",
                                "please unblock",
                                "checking your browser",
                                "just a moment",
                                "verifying you are human"
                            ])
                            
                            if not has_challenge_check:
                                # Kiểm tra xem có content không
                                try:
                                    fic_title = self.page.locator(".fic_title").first
                                    if fic_title.count() > 0:
                                        safe_print(f"      ✅ Đã detect challenge pass tự động! (sau {elapsed}s)")
                                        break
                                except:
                                    pass
                        except:
                            pass
                        
                        # Kiểm tra xem user đã bấm Enter chưa (Windows)
                        if HAS_MSVCRT:
                            try:
                                if msvcrt.kbhit():
                                    key = msvcrt.getch()
                                    if key == b'\r' or key == b'\n':  # Enter key
                                        safe_print(f"      ✅ Bạn đã bấm ENTER (sau {elapsed}s), tiếp tục...")
                                        time.sleep(5)  # Đợi thêm 5 giây để đảm bảo
                                        break
                            except:
                                pass
                        
                        time.sleep(1)
                except:
                    # Fallback: đợi bình thường
                    safe_print("      ⏳ Đang đợi tự động...")
                    max_wait = getattr(config, 'CLOUDFLARE_MAX_WAIT', 300)
                    self.wait_for_cloudflare_challenge(self.page, max_wait=max_wait)
            else:
                # Tự động đợi
                max_wait = getattr(config, 'CLOUDFLARE_MAX_WAIT', 300)
                challenge_passed = self.wait_for_cloudflare_challenge(self.page, max_wait=max_wait)
        else:
            safe_print("      ✅ Không phát hiện Cloudflare challenge, tiếp tục...")
            challenge_passed = True
        
        # Đợi thêm để đảm bảo page ổn định
        verify_wait = getattr(config, 'CLOUDFLARE_VERIFY_WAIT', 10)
        safe_print(f"      ⏳ Đợi thêm {verify_wait} giây để đảm bảo page ổn định...")
        time.sleep(verify_wait)
        
        # ✅ CÁCH 2: Lưu cookies sau khi verify (luôn luôn lưu để đảm bảo)
        if config.ENABLE_COOKIE_PERSISTENCE and self.context:
            from src.utils.cookie_manager import save_cookies
            if save_cookies(self.context):
                safe_print("      💾 Đã lưu cookies - lần sau không cần verify lại!")
        
        safe_print("="*60)

        # Giả lập hành vi người dùng nếu được bật
        if config.ENABLE_HUMAN_BEHAVIOR:
            self.simulate_human_behavior(self.page)
            time.sleep(2)
            
        # 1. Lấy web_story_id từ URL (Ví dụ: từ https://www.scribblehub.com/series/123456-story-name/ lấy 123456)
        web_story_id = ""
        try:
            import re
            # Tìm pattern /series/123456-... hoặc /read/123456-...
            match = re.search(r'/(?:series|read)/(\d+)', story_url)
            if match:
                web_story_id = match.group(1)
            else:
                # Fallback: lấy số từ URL
                numbers = re.findall(r'\d+', story_url)
                if numbers:
                    web_story_id = numbers[0]
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy web_story_id từ URL: {e}")
            web_story_id = ""
        
        # 2. Cào metadata của story (hoặc lấy story_id nếu đã có)
        story_data, story_id = self.story_handler.scrape_story_metadata(story_url, web_story_id)
        
        # Nếu story_data là None, nghĩa là story đã có trong DB
        if story_data is None:
            # Lấy story_id từ DB
            existing_story = self.mongo.get_story_by_web_id(web_story_id)
            if existing_story:
                story_id = existing_story.get("story_id")  # Đổi từ "id" thành "story_id"
            else:
                from src.utils import generate_id
                story_id = generate_id()

        # 3. Lấy danh sách link chương từ TẤT CẢ các trang phân trang
        safe_print("... Đang lấy danh sách chương từ tất cả các trang")
        chapter_info_list = self.story_handler.get_all_chapters_from_pagination(story_url)
        
        safe_print(f"--> Tổng cộng tìm thấy {len(chapter_info_list)} chương từ tất cả các trang.")

        # 3.5. Lấy reviews cho toàn bộ truyện (chỉ nếu có reviews)
        # Kiểm tra total_reviews từ story_info_data trước
        total_reviews_str = ""
        try:
            reviews_section = self.page.locator(".wi_novel_title.tags.pedit_body.nreview").first
            if reviews_section.count() > 0:
                cnt_toc = reviews_section.locator(".cnt_toc").first
                if cnt_toc.count() > 0:
                    total_reviews_str = cnt_toc.inner_text().strip()
        except:
            pass
        
        # Chỉ scrape reviews nếu có reviews (total_reviews > 0)
        reviews = []
        try:
            total_reviews_num = int(total_reviews_str) if total_reviews_str and total_reviews_str.isdigit() else 0
            if total_reviews_num > 0:
                safe_print(f"... Đang lấy reviews cho toàn bộ truyện (có {total_reviews_num} reviews)")
                reviews = self.review_handler.scrape_reviews(story_url, story_id)
                safe_print(f"✅ Đã lấy được {len(reviews)} reviews")
            else:
                safe_print(f"... Bỏ qua reviews (không có reviews: {total_reviews_str})")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi kiểm tra/scrape reviews: {e}")
            # Nếu lỗi, vẫn thử scrape (fallback)
            reviews = self.review_handler.scrape_reviews(story_url, story_id)
            if reviews:
                safe_print(f"✅ Đã lấy được {len(reviews)} reviews (fallback)")

        # 4. Cào các chương song song với ThreadPoolExecutor (GIỮ ĐÚNG THỨ TỰ)
        # Lọc ra các chapters chưa được cào (để tránh cào trùng)
        chapters_to_scrape = []
        for index, chapter_info in enumerate(chapter_info_list):
            chap_url = chapter_info["url"]
            # Lấy web_chapter_id từ URL (Ví dụ: từ https://www.scribblehub.com/read/123456-story-name/chapter/789012/ lấy 789012)
            web_chapter_id = ""
            try:
                import re
                # Tìm pattern /chapter/789012
                match = re.search(r'/chapter/(\d+)', chap_url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    # Fallback: split theo /chapter/
                    url_parts = chap_url.split("/chapter/")
                    if len(url_parts) > 1:
                        web_chapter_id = url_parts[1].split("/")[0]
            except Exception as e:
                safe_print(f"    ⚠️ Lỗi khi lấy web_chapter_id từ URL: {e}")
                web_chapter_id = ""
            
            # Kiểm tra chapter đã có chưa (check theo web_chapter_id)
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"    ⏭️  Bỏ qua chapter {index + 1} (đã có trong DB): {web_chapter_id}")
            else:
                chapters_to_scrape.append((index, chapter_info))
        
        # ✅ CÁCH TỐI ƯU: Dùng browser chính (đã vượt Cloudflare) thay vì requests hoặc tạo browser mới
        # → Không bị 403 Forbidden (vì dùng browser đã verify)
        # → Không bị lỗi Playwright Sync API (vì không tạo browser mới)
        # → Ổn định nhất, reliable nhất
        
        safe_print(f"🚀 Bắt đầu cào {len(chapters_to_scrape)}/{len(chapter_info_list)} chương bằng Browser Chính (Sequential)...")
        safe_print("   ✅ Dùng browser chính → không bị 403 Forbidden")
        safe_print("   ✅ Không tạo browser mới → không bị lỗi Playwright Sync API")
        safe_print("   ✅ Scrape tuần tự → tránh bị flag bot")
        
        chapter_results = [None] * len(chapter_info_list)
        completed = 0
        
        for index, chapter_info in chapters_to_scrape:
            order = chapter_info.get("order", "")
            if not order:
                order = str(index + 1)
            chap_url = chapter_info["url"]
            published_time_from_table = chapter_info.get("published_time", "")
            
            try:
                # ✅ GỌI HÀM MỚI, TRUYỀN self.page VÀO (browser chính đã mở)
                chapter_data = self.chapter_handler.scrape_single_chapter_using_browser(
                    self.page,  # <--- QUAN TRỌNG: Dùng lại page đã mở (đã vượt Cloudflare)
                    chap_url, 
                    index, 
                    story_id, 
                    order, 
                    published_time_from_table
                )
                
                chapter_results[index] = chapter_data
                if chapter_data:
                    completed += 1
                    status = "✅"
                else:
                    status = "⚠️"
                safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_info_list)} (đã xong {completed}/{len(chapters_to_scrape)})")
                
                # Delay nhẹ giữa các chương để không bị ban
                import random
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                chapter_results[index] = None
        
        safe_print(f"✅ Đã hoàn thành cào {completed}/{len(chapters_to_scrape)} chương!")
        
        # SAU KHI TẤT CẢ XONG: Đếm số chapters đã cào thành công
        safe_print(f"📝 Đang kiểm tra kết quả...")
        successful_chapters = sum(1 for ch in chapter_results if ch is not None)
        safe_print(f"✅ Đã hoàn thành {successful_chapters}/{len(chapter_info_list)} chương (theo đúng thứ tự)")
        
        # 5. Cập nhật story trong MongoDB (chapters và reviews đã được lưu vào collections riêng)
        if story_data:
            self.mongo.save_story(story_data)
