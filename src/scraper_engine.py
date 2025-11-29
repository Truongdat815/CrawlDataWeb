import time
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from src import config, utils

# Import MongoDB
try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

# Helper function để print an toàn với encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        # Thử print bình thường
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Nếu lỗi encoding, encode lại thành ASCII-safe
        message = ' '.join(str(arg) for arg in args)
        # Thay thế emoji và ký tự đặc biệt
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

class RoyalRoadScraper:
    def __init__(self, max_workers=None):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Khởi tạo MongoDB client nếu được bật
        self.mongo_client = None
        self.mongo_db = None
        self.mongo_collection_stories = None
        self.mongo_collection_chapters = None
        self.mongo_collection_comments = None
        self.mongo_collection_reviews = None
        self.mongo_collection_users = None
        self.mongo_collection_scores = None
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                self.mongo_client = MongoClient(config.MONGODB_URI)
                self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                self.mongo_collection_stories = self.mongo_db[config.MONGODB_COLLECTION_STORIES]
                self.mongo_collection_chapters = self.mongo_db["chapters"]
                self.mongo_collection_comments = self.mongo_db["comments"]
                self.mongo_collection_reviews = self.mongo_db["reviews"]
                self.mongo_collection_users = self.mongo_db["users"]
                self.mongo_collection_scores = self.mongo_db["scores"]
                safe_print("✅ Đã kết nối MongoDB với 6 collections")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

    def start(self):
        """Khởi động trình duyệt"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=config.HEADLESS)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        safe_print("✅ Bot đã khởi động!")

    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.mongo_client:
            self.mongo_client.close()
            safe_print("✅ Đã đóng kết nối MongoDB")
        safe_print("zzz Bot đã tắt.")

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
        story_urls = self._get_story_urls_from_best_rated(num_stories, start_from)
        
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

    def _get_story_urls_from_best_rated(self, num_stories=10, start_from=0):
        """
        Lấy danh sách URL của các bộ truyện từ trang best-rated
        Selector: h2.fiction-title a
        Args:
            num_stories: Số lượng bộ truyện muốn lấy
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên)
        """
        story_urls = []
        
        try:
            # Scroll xuống để load thêm nội dung nếu cần
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Lấy tất cả các link truyện từ thẻ h2.fiction-title a
            fiction_links = self.page.locator("h2.fiction-title a").all()
            
            # Tính toán vị trí bắt đầu và kết thúc
            start_index = start_from
            end_index = start_from + num_stories
            
            # Lấy các link từ vị trí start_from đến end_index
            for link in fiction_links[start_index:end_index]:
                try:
                    href = link.get_attribute("href")
                    if href:
                        # Tạo full URL
                        if href.startswith("/"):
                            full_url = config.BASE_URL + href
                        elif href.startswith("http"):
                            full_url = href
                        else:
                            full_url = config.BASE_URL + "/" + href
                        
                        if full_url not in story_urls:
                            story_urls.append(full_url)
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi lấy URL truyện: {e}")
                    continue
            
            return story_urls
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy danh sách truyện từ best-rated: {e}")
            return []

    def scrape_story(self, story_url):
        """
        Hàm chính để cào toàn bộ 1 bộ truyện.
        Luồng đi: Vào trang truyện -> Lấy Info -> Lấy List Chapter -> Vào từng Chapter -> Lấy Content.
        """
        safe_print(f"🌍 Đang truy cập truyện: {story_url}")
        self.page.goto(story_url, timeout=config.TIMEOUT)

        # 1. Lấy ID truyện từ URL (Ví dụ: 21220)
        story_id = story_url.split("/")[4]

        # 2. Lấy thông tin tổng quan (Metadata)
        safe_print("... Đang lấy thông tin chung")
        
        # Lấy title
        title = self.page.locator("h1").first.inner_text()
        
        # Lấy URL ảnh bìa rồi tải về luôn
        img_url_raw = self.page.locator(".cover-art-container img").get_attribute("src")
        local_img_path = utils.download_image(img_url_raw, story_id)

        # Lấy author (user_id từ profile URL)
        author_id = self.page.locator(".fic-title h4 a").first.get_attribute("href").split("/")[2]
        author_name = self.page.locator(".fic-title h4 a").first.inner_text()
        
        # Lưu user (author) ngay vào MongoDB
        if author_id and author_name:
            self._save_user_to_mongo(author_id, author_name)

        # Lấy category
        category = self.page.locator(".fiction-info span").first.inner_text()

        # Lấy status
        status = self.page.locator(".fiction-info span:nth-child(2)").first.inner_text()

        #Lấy tags
        tags = self.page.locator(".tags a").all_inner_texts()

        #Lấy description - giữ nguyên định dạng như trong UI
        description = ""
        try:
            desc_container = self.page.locator(".description").first
            if desc_container.count() > 0:
                # Lấy HTML để giữ định dạng
                html_content = desc_container.inner_html()
                # Chuyển HTML sang text với định dạng đúng
                description = self._convert_html_to_formatted_text(html_content)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
            description = ""

        #Lấy stats
        # stats = self.page.locator(".stats-content .list-item").all()
        # Container chính: .stats-content ul.list-unstyled
        base_locator = ".stats-content ul.list-unstyled li:nth-child({}) span"

        # 1. Overall Score (Nằm ở vị trí con thứ 2)
        overall_score = self.page.locator(base_locator.format(2)).inner_text()

        # 2. Style Score (Vị trí con thứ 4)
        style_score = self.page.locator(base_locator.format(4)).inner_text()

        # 3. Story Score (Vị trí con thứ 6)
        story_score = self.page.locator(base_locator.format(6)).inner_text()

        # 4. Grammar Score (Vị trí con thứ 8)
        grammar_score = self.page.locator(base_locator.format(8)).inner_text()

        # 5. Character Score (Vị trí con thứ 10)
        character_score = self.page.locator(base_locator.format(10)).inner_text()

        # 1. Định vị tất cả các thẻ <li> chứa GIÁ TRỊ số liệu
        # Sử dụng class đặc trưng (.font-red-sunglo) và giới hạn trong khối stats bên phải (.col-sm-6)
        stats_values_locator = self.page.locator("div.col-sm-6 li.font-red-sunglo")
        
        # 2. Lấy giá trị bằng cách dùng chỉ mục (index)
        
        # Lấy total_views (Index 0)
        total_views = stats_values_locator.nth(0).inner_text()
        
        # Lấy average_views (Index 1)
        average_views = stats_values_locator.nth(1).inner_text()
        
        # Lấy followers (Index 2)
        followers = stats_values_locator.nth(2).inner_text()
        
        # Lấy favorites (Index 3)
        favorites = stats_values_locator.nth(3).inner_text()
        
        # Lấy ratings (Index 4)
        ratings = stats_values_locator.nth(4).inner_text()
        
        # Lấy pages/words (Index 5 - Giá trị cuối cùng)
        pages = stats_values_locator.nth(5).inner_text()

        # Tạo cấu trúc dữ liệu tổng quan theo schema
        # Schema: story id, story name, story url, cover image, category, status, tags, description, 
        # total views, average views, followers, favorites, ratings, page views
        # Score: overall_score, style_score, story_score, grammar_score, character_score
        story_data = {
            "id": story_id,  # Schema: story id
            "name": title,  # Schema: story name
            "url": story_url,  # Schema: story url
            "cover_image": local_img_path,  # Schema: cover image
            "category": category,  # Schema: category
            "status": status,  # Schema: status
            "tags": tags,  # Schema: tags
            "description": description,  # Schema: description
            "total_views": total_views,  # Schema: total views
            "average_views": average_views,  # Schema: average views
            "followers": followers,  # Schema: followers
            "favorites": favorites,  # Schema: favorites
            "ratings": ratings,  # Schema: ratings
            "page_views": pages,  # Schema: page views
            "overall_score": overall_score,  # Schema: overall score
            "style_score": style_score,  # Schema: style score
            "story_score": story_score,  # Schema: story score
            "grammar_score": grammar_score,  # Schema: grammar score
            "character_score": character_score,  # Schema: character score
            "reviews": [],  # Sẽ được điền sau
            "chapters": []     # Chuẩn bị cái mảng rỗng để chứa các chương
        }
        
        # Lưu score vào collection scores (từ story)
        score_id = f"{story_id}_score"
        self._save_score_to_mongo(score_id, overall_score, style_score, story_score, grammar_score, character_score)
        
        # Lưu story ngay khi cào xong metadata (chưa có chapters và reviews)
        self._save_story_to_mongo(story_data)

        # 3. Lấy danh sách link chương từ TẤT CẢ các trang phân trang
        safe_print("... Đang lấy danh sách chương từ tất cả các trang")
        chapter_urls = self._get_all_chapters_from_pagination(story_url)
        
        safe_print(f"--> Tổng cộng tìm thấy {len(chapter_urls)} chương từ tất cả các trang.")

        # 3.5. Lấy reviews cho toàn bộ truyện
        safe_print("... Đang lấy reviews cho toàn bộ truyện")
        reviews = self._scrape_reviews(story_url, story_id)
        story_data["reviews"] = reviews
        safe_print(f"✅ Đã lấy được {len(reviews)} reviews")

        # 4. Cào các chương song song với ThreadPoolExecutor (GIỮ ĐÚNG THỨ TỰ)
        safe_print(f"🚀 Bắt đầu cào {len(chapter_urls)} chương với {self.max_workers} thread...")
        
        # Tạo list kết quả cố định theo index - mỗi index = 1 chương
        chapter_results = [None] * len(chapter_urls)
        
        # Dictionary để map future -> index để biết chương nào
        future_to_index = {}
        
        # Sử dụng ThreadPoolExecutor - NÓ TỰ ĐỘNG PHÂN PHỐI công việc!
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit TẤT CẢ chapters vào pool - mỗi chương chỉ submit 1 LẦN
            for index, chap_url in enumerate(chapter_urls):
                future = executor.submit(self._scrape_single_chapter_worker, chap_url, index, story_id)
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
                    safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_urls)} (đã xong {completed}/{len(chapter_urls)})")
                except Exception as e:
                    safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                    chapter_results[index] = None

        # SAU KHI TẤT CẢ XONG: Thêm vào story_data THEO ĐÚNG THỨ TỰ
        safe_print(f"📝 Sắp xếp kết quả theo đúng thứ tự...")
        for index in range(len(chapter_results)):
            chapter_data = chapter_results[index]
            if chapter_data:
                story_data["chapters"].append(chapter_data)
            else:
                safe_print(f"    ⚠️ Bỏ qua chương {index + 1} (lỗi hoặc không có dữ liệu)")

        safe_print(f"✅ Đã hoàn thành {len(story_data['chapters'])}/{len(chapter_urls)} chương (theo đúng thứ tự)")

        # 5. Cập nhật story trong MongoDB với đầy đủ chapters và reviews
        self._save_story_to_mongo(story_data)
        
        # 6. Lưu kết quả ra JSON (backup)
        self._save_to_json(story_data)

    def _get_all_chapters_from_pagination(self, story_url):
        """
        Lấy tất cả chapters từ tất cả các trang phân trang
        Pagination sử dụng JavaScript (AJAX), không đổi URL
        Trả về danh sách URL của tất cả chapters
        """
        all_chapter_urls = []
        
        try:
            # Trang đầu tiên: Lấy từ trang story chính
            safe_print(f"    📄 Đang lấy chapters từ trang 1 (trang story chính)...")
            self.page.goto(story_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Lấy chapters từ trang story chính
            page_chapters = self._get_chapters_from_current_page()
            all_chapter_urls.extend(page_chapters)
            safe_print(f"    ✅ Trang 1: Lấy được {len(page_chapters)} chapters")
            
            # Tìm số trang tối đa cho chapters từ pagination trên trang story chính
            max_page = self._get_max_chapter_page()
            
            # Nếu chỉ có 1 trang, return luôn
            if max_page <= 1:
                safe_print(f"    📚 Chỉ có 1 trang chapters")
                return all_chapter_urls
            
            safe_print(f"    📚 Tìm thấy {max_page} trang chapters (trang 1 đã lấy, còn {max_page - 1} trang nữa)")
            
            # Loop qua từng trang còn lại (từ trang 2 trở đi)
            # Sử dụng click vào pagination để load thêm chapters (AJAX, không đổi URL)
            for page_num in range(2, max_page + 1):
                safe_print(f"    📄 Đang lấy chapters từ trang {page_num}/{max_page}...")
                
                # Click vào nút pagination để chuyển trang (AJAX load, không đổi URL)
                if not self._go_to_chapter_page(page_num):
                    safe_print(f"    ⚠️ Không thể chuyển đến trang {page_num}, dừng lại")
                    break
                
                # Đợi AJAX load xong
                time.sleep(2)
                
                # Lấy chapters từ trang hiện tại
                page_chapters = self._get_chapters_from_current_page()
                all_chapter_urls.extend(page_chapters)
                
                safe_print(f"    ✅ Trang {page_num}: Lấy được {len(page_chapters)} chapters")
                
                # Delay giữa các trang
                if page_num < max_page:
                    time.sleep(1)
            
            return all_chapter_urls
            
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi lấy chapters từ pagination: {e}")
            # Fallback: Lấy từ trang đầu tiên (trang story chính)
            try:
                self.page.goto(story_url, timeout=config.TIMEOUT)
                time.sleep(2)
                return self._get_chapters_from_current_page()
            except:
                return []

    def _get_max_chapter_page(self):
        """Lấy số trang chapters tối đa từ pagination"""
        try:
            # Scroll xuống để load pagination
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1  # Mặc định là 1 trang
            
            # Tìm pagination element - có thể là pagination-small hoặc pagination
            pagination_selectors = [
                "ul.pagination-small",
                "ul.pagination",
                ".pagination-small",
                ".pagination"
            ]
            
            pagination = None
            for selector in pagination_selectors:
                try:
                    pagination = self.page.locator(selector).first
                    if pagination.count() > 0:
                        break
                except:
                    continue
            
            if pagination and pagination.count() > 0:
                # Lấy tất cả các link có data-page attribute
                page_links = pagination.locator("a[data-page]").all()
                
                page_numbers = []
                for link in page_links:
                    try:
                        page_num_str = link.get_attribute("data-page")
                        if page_num_str:
                            page_num = int(page_num_str)
                            page_numbers.append(page_num)
                    except:
                        continue
                
                # Nếu không có data-page, thử lấy từ text content
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                # Bỏ qua các nút navigation (Next, Previous) và icon
                                if link_text.isdigit():
                                    page_num = int(link_text)
                                    page_numbers.append(page_num)
                            except:
                                continue
                    except:
                        pass
                
                if page_numbers:
                    max_page = max(page_numbers)
                    safe_print(f"        📄 Tìm thấy {max_page} trang chapters")
                else:
                    # Nếu không tìm thấy số trang, có thể chỉ có 1 trang
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang chapters: {e}")
            return 1

    def _get_chapter_page_urls(self, base_url, max_page):
        """Lấy tất cả URL của các trang chapters từ pagination"""
        page_urls = [base_url]  # Trang 1 là base_url
        
        try:
            # Tìm pagination
            pagination_selectors = [
                "ul.pagination-small",
                "ul.pagination",
                ".pagination-small",
                ".pagination"
            ]
            
            pagination = None
            for selector in pagination_selectors:
                try:
                    pagination = self.page.locator(selector).first
                    if pagination.count() > 0:
                        break
                except:
                    continue
            
            if pagination and pagination.count() > 0:
                # Lấy tất cả các link có data-page attribute
                page_links = pagination.locator("a[data-page]").all()
                
                url_map = {}  # {page_num: url}
                for link in page_links:
                    try:
                        page_num_str = link.get_attribute("data-page")
                        if page_num_str:
                            page_num = int(page_num_str)
                            href = link.get_attribute("href")
                            if href:
                                # Tạo full URL
                                if href.startswith("/"):
                                    full_url = config.BASE_URL + href
                                elif href.startswith("http"):
                                    full_url = href
                                else:
                                    full_url = config.BASE_URL + "/" + href
                                url_map[page_num] = full_url
                    except:
                        continue
                
                # Sắp xếp và thêm vào list
                for page_num in sorted(url_map.keys()):
                    if page_num <= max_page:
                        page_urls.append(url_map[page_num])
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy URLs từ pagination: {e}")
        
        return page_urls

    def _go_to_chapter_page(self, page_num):
        """
        Chuyển đến trang chapters cụ thể bằng cách click vào link hoặc nút Next
        Trả về True nếu thành công, False nếu thất bại
        """
        try:
            # Tìm pagination
            pagination_selectors = [
                "ul.pagination-small",
                "ul.pagination",
                ".pagination-small",
                ".pagination"
            ]
            
            pagination = None
            for selector in pagination_selectors:
                try:
                    pagination = self.page.locator(selector).first
                    if pagination.count() > 0:
                        break
                except:
                    continue
            
            if not pagination or pagination.count() == 0:
                return False
            
            # Cách 1: Thử tìm link có data-page = page_num
            try:
                page_link = pagination.locator(f'a[data-page="{page_num}"]').first
                if page_link.count() > 0:
                    page_link.click()
                    time.sleep(2)
                    return True
            except:
                pass
            
            # Cách 2: Nếu không có data-page, thử tìm link có text = page_num
            # Lấy tất cả các link trong pagination và tìm link có text = page_num
            try:
                all_links = pagination.locator("a").all()
                for link in all_links:
                    try:
                        link_text = link.inner_text().strip()
                        # Kiểm tra xem text có phải là số và bằng page_num không
                        if link_text.isdigit() and int(link_text) == page_num:
                            # Kiểm tra xem không phải là nút navigation (không có class nav-arrow)
                            parent_class = link.evaluate("el => el.closest('li')?.className || ''")
                            if "nav-arrow" not in parent_class:
                                link.click()
                                time.sleep(2)
                                return True
                    except:
                        continue
            except:
                pass
            
            # Cách 3: Click nút "Next" nhiều lần (chỉ dùng nếu page_num nhỏ)
            # Tìm nút Next (có class nav-arrow hoặc chứa icon chevron-right)
            if page_num <= 10:  # Giới hạn để tránh click quá nhiều
                # Tìm trang hiện tại
                current_page = 1
                try:
                    active_page = pagination.locator("li.page-active a").first
                    if active_page.count() > 0:
                        active_text = active_page.inner_text().strip()
                        if active_text.isdigit():
                            current_page = int(active_text)
                except:
                    pass
                
                # Click Next cho đến khi đến trang cần
                while current_page < page_num:
                    # Tìm nút Next (có thể là .nav-arrow với icon chevron-right)
                    next_selectors = [
                        'a.pagination-button:has(i.fa-chevron-right)',
                        '.nav-arrow a:has(i.fa-chevron-right)',
                        'a:has(i.fa-chevron-right)',
                        '.nav-arrow a',
                        'a.pagination-button'
                    ]
                    
                    next_button = None
                    for selector in next_selectors:
                        try:
                            next_button = pagination.locator(selector).last  # Lấy nút cuối (Next)
                            if next_button.count() > 0:
                                # Kiểm tra xem có phải nút Next không (không phải Previous)
                                href = next_button.get_attribute("href") or ""
                                if "page" in href.lower() or "next" in href.lower() or not href:
                                    break
                        except:
                            continue
                    
                    if next_button and next_button.count() > 0:
                        try:
                            next_button.click()
                            time.sleep(2)
                            current_page += 1
                        except:
                            return False
                    else:
                        return False
                
                return True
            
            return False
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi chuyển đến trang {page_num}: {e}")
            return False

    def _get_chapters_from_current_page(self):
        """Lấy danh sách chapters từ trang hiện tại"""
        chapter_urls = []
        
        try:
            # Lấy tất cả các rows trong table chapters
            chapter_rows = self.page.locator("table#chapters tbody tr").all()
            
            for row in chapter_rows:
                try:
                    link_el = row.locator("td").first.locator("a")
                    if link_el.count() > 0:
                        url = link_el.get_attribute("href")
                        if url:
                            # Tạo full URL
                            if url.startswith("/"):
                                full_url = config.BASE_URL + url
                            elif url.startswith("http"):
                                full_url = url
                            else:
                                full_url = config.BASE_URL + "/" + url
                            
                            # Tránh duplicate
                            if full_url not in chapter_urls:
                                chapter_urls.append(full_url)
                except:
                    continue
            
            return chapter_urls
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapters từ trang hiện tại: {e}")
            return []

    def _convert_html_to_formatted_text(self, html_content):
        """
        Chuyển đổi HTML sang text với định dạng đúng (giữ nguyên xuống dòng như trong UI)
        - Mỗi thẻ <p> = một đoạn văn, các đoạn cách nhau bằng một dòng trống
        - Thẻ <br> = xuống dòng
        - Giữ nguyên cấu trúc như trong UI
        """
        if not html_content:
            return ""
        
        import html as html_module
        
        # Decode HTML entities trước
        html_content = html_module.unescape(html_content)
        
        # Xử lý theo thứ tự để đảm bảo định dạng đúng
        text = html_content
        
        # 1. Xử lý <br> và <br/> trước - xuống dòng ngay lập tức
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        # 2. Xử lý các thẻ block: <p> - mỗi đoạn văn cách nhau 1 dòng trống
        # Thay thế </p> thành dấu phân cách đoạn (2 dòng xuống)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        # Xóa thẻ mở <p>
        text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)
        
        # 3. Xử lý các thẻ block khác: <div> - xuống dòng
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<div[^>]*>', '', text, flags=re.IGNORECASE)
        
        # 4. Xử lý các thẻ heading (h1, h2, h3, ...) - xuống dòng trước và sau
        text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
        
        # 5. Xóa tất cả các thẻ HTML còn lại (giữ lại text)
        text = re.sub(r'<[^>]+>', '', text)
        
        # 6. Làm sạch: xử lý các dòng trống và khoảng trắng thừa
        lines = text.split('\n')
        cleaned_lines = []
        
        prev_empty = False
        for line in lines:
            # Strip cả 2 bên để loại bỏ khoảng trắng thừa (từ HTML indentation)
            stripped_line = line.strip()
            
            # Xử lý dòng trống
            if not stripped_line:
                # Chỉ thêm 1 dòng trống giữa các đoạn (không thêm nhiều dòng trống liên tiếp)
                if not prev_empty:
                    cleaned_lines.append('')
                prev_empty = True
            else:
                # Giữ nguyên dòng có nội dung (đã strip khoảng trắng thừa)
                cleaned_lines.append(stripped_line)
                prev_empty = False
        
        # Loại bỏ dòng trống ở đầu và cuối (nhưng giữ dòng trống giữa các đoạn)
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        result = '\n'.join(cleaned_lines)
        
        # Loại bỏ khoảng trắng thừa ở đầu và cuối toàn bộ text
        # Nhưng vẫn giữ nguyên cấu trúc bên trong (các dòng trống giữa đoạn)
        result = result.strip()
        
        # Đảm bảo không có khoảng trắng thừa ở đầu mỗi dòng (từ HTML indentation)
        # Normalize lại để chắc chắn
        if result:
            lines = result.split('\n')
            final_lines = []
            for line in lines:
                # Strip từng dòng để loại bỏ khoảng trắng thừa
                clean_line = line.strip()
                # Giữ dòng trống nếu là dòng trống thật
                if not clean_line:
                    final_lines.append('')
                else:
                    final_lines.append(clean_line)
            result = '\n'.join(final_lines).strip()
        
        return result

    def _scrape_single_chapter(self, url):
        """Hàm con: Chỉ chịu trách nhiệm vào 1 link chương và trả về cục data của chương đó"""
        try:
            self.page.goto(url, timeout=config.TIMEOUT)
            self.page.wait_for_selector(".chapter-inner", timeout=10000)

            title = self.page.locator("h1").first.inner_text()
            
            # Lấy content với định dạng đúng (giữ nguyên xuống dòng như trong UI)
            content = ""
            try:
                content_container = self.page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    # Lấy HTML để giữ định dạng
                    html_content = content_container.inner_html()
                    # Chuyển HTML sang text với định dạng đúng
                    content = self._convert_html_to_formatted_text(html_content)
                else:
                    # Fallback: dùng inner_text nếu không tìm thấy
                    content = self.page.locator(".chapter-inner").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy content: {e}")
                content = self.page.locator(".chapter-inner").inner_text()

            # Lấy published_time
            published_time = ""
            try:
                time_elem = self.page.locator("time, .timestamp, [class*='time'], [class*='date'], [datetime]").first
                if time_elem.count() > 0:
                    published_time = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # Lấy chapter_id từ URL (ví dụ: /chapter/123456/ -> 123456)
            chapter_id = ""
            try:
                url_parts = url.split("/chapter/")
                if len(url_parts) > 1:
                    chapter_id = url_parts[1].split("/")[0]
            except:
                chapter_id = ""
            
            # Lấy comments cho chapter này
            safe_print(f"      ... Đang lấy comments cho chương")
            chapter_comments = self._scrape_comments(url, "chapter", chapter_id)

            return {
                "id": chapter_id,  # Schema: chapter id
                "name": title,  # Schema: chapter name
                "url": url,  # Schema: chapter url
                "content": content,  # Schema: content
                "published_time": published_time,  # Schema: published time
                "story_id": "",  # Sẽ được điền sau nếu cần
                "comments": chapter_comments
            }
        except Exception as e:
            safe_print(f"⚠️ Lỗi cào chương {url}: {e}")
            return None

    def _scrape_single_chapter_worker(self, url, index, story_id):
        """
        Worker function để cào MỘT chương - mỗi worker có browser instance riêng
        Thread-safe: Mỗi worker có browser instance riêng
        
        Args:
            url: URL của chương cần cào (DUY NHẤT - không trùng lặp)
            index: Thứ tự chương trong list (DUY NHẤT - không trùng lặp)
            story_id: ID của story (FK)
        """
        worker_playwright = None
        worker_browser = None
        
        try:
            # Delay để stagger các thread - tránh tất cả thread bắt đầu cùng lúc
            time.sleep(index * config.DELAY_THREAD_START)
            
            # Tạo browser instance riêng cho worker này
            worker_playwright = sync_playwright().start()
            worker_browser = worker_playwright.chromium.launch(headless=config.HEADLESS)
            worker_context = worker_browser.new_context()
            worker_page = worker_context.new_page()
            
            safe_print(f"    🔄 Thread-{index}: Đang cào chương {index + 1}")
            
            # Delay trước khi request để tránh ban IP
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Cào chương
            worker_page.goto(url, timeout=config.TIMEOUT)
            worker_page.wait_for_selector(".chapter-inner", timeout=10000)
            
            # Delay sau khi load page
            time.sleep(config.DELAY_BETWEEN_REQUESTS)

            title = worker_page.locator("h1").first.inner_text()
            
            # Lấy published_time
            published_time = ""
            try:
                time_elem = worker_page.locator("time, .timestamp, [class*='time'], [class*='date'], [datetime]").first
                if time_elem.count() > 0:
                    published_time = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # Lấy content với định dạng đúng
            content = ""
            try:
                content_container = worker_page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content = self._convert_html_to_formatted_text(html_content)
                else:
                    content = worker_page.locator(".chapter-inner").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy content: {e}")
                content = worker_page.locator(".chapter-inner").inner_text()

            # Delay trước khi lấy comments
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Lấy chapter_id từ URL (ví dụ: /chapter/123456/ -> 123456)
            chapter_id = ""
            try:
                url_parts = url.split("/chapter/")
                if len(url_parts) > 1:
                    chapter_id = url_parts[1].split("/")[0]
            except:
                chapter_id = ""
            
            # Lấy comments cho chapter này (cần chapter_id để thêm vào mỗi comment)
            safe_print(f"      💬 Thread-{index}: Đang lấy comments cho chương")
            chapter_comments = self._scrape_comments_worker(worker_page, url, "chapter", chapter_id)

            # Delay sau khi hoàn thành chương
            time.sleep(config.DELAY_BETWEEN_CHAPTERS)

            chapter_data = {
                "id": chapter_id,  # Schema: chapter id
                "name": title,  # Schema: chapter name
                "url": url,  # Schema: chapter url
                "content": content,  # Schema: content
                "published_time": published_time,  # Schema: published time
                "story_id": story_id,  # Schema: story id (FK)
                "comments": chapter_comments
            }
            
            # Lưu chapter ngay vào MongoDB (sau khi đã cào xong chapter và comments)
            self._save_chapter_to_mongo(chapter_data)
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"⚠️ Thread-{index}: Lỗi cào chương {index + 1}: {e}")
            return None
        finally:
            # Đóng browser của worker
            if worker_browser:
                worker_browser.close()
            if worker_playwright:
                worker_playwright.stop()

    def _get_max_comment_page(self, url):
        """Lấy số trang comments tối đa từ pagination"""
        try:
            # Đảm bảo đang ở đúng trang (trang 1 - không có query comments)
            base_url = url.split('?')[0]
            current_url = self.page.url.split('?')[0]
            
            if base_url not in current_url:
                self.page.goto(base_url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            # Scroll xuống để load pagination
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1  # Mặc định là 1 trang
            
            # Tìm pagination element - có thể trong .chapter-nav hoặc trực tiếp
            pagination_selectors = [
                "ul.pagination",
                ".chapter-nav ul.pagination",
                ".pagination"
            ]
            
            pagination = None
            for selector in pagination_selectors:
                try:
                    pagination = self.page.locator(selector).first
                    if pagination.count() > 0:
                        break
                except:
                    continue
            
            if pagination and pagination.count() > 0:
                # Lấy tất cả các link có data-page attribute
                page_links = pagination.locator("a[data-page]").all()
                
                page_numbers = []
                for link in page_links:
                    try:
                        page_num_str = link.get_attribute("data-page")
                        if page_num_str:
                            page_num = int(page_num_str)
                            page_numbers.append(page_num)
                    except:
                        continue
                
                # Cũng thử lấy từ text content (nếu không có data-page)
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                # Thử parse số từ text (ví dụ: "31", "Next >" sẽ bị skip)
                                if link_text.isdigit():
                                    page_num = int(link_text)
                                    page_numbers.append(page_num)
                            except:
                                continue
                    except:
                        pass
                
                if page_numbers:
                    max_page = max(page_numbers)
                    safe_print(f"        📄 Tìm thấy {max_page} trang comments")
                else:
                    # Nếu không tìm thấy số trang, có thể chỉ có 1 trang hoặc chưa load
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang: {e}")
            return 1  # Nếu lỗi, mặc định chỉ có 1 trang

    def _scrape_comments_from_page(self, page_url, chapter_id=""):
        """Lấy comments từ một trang cụ thể, trả về danh sách phẳng (flat)"""
        comments = []
        
        try:
            self.page.goto(page_url, timeout=config.TIMEOUT)
            time.sleep(2)  # Chờ page load
            
            # Scroll xuống để load comments (lazy load)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Lấy tất cả div.comment và filter những cái không nằm trong ul.subcomments
            all_comments = self.page.locator("div.comment").all()
            
            for comment_elem in all_comments:
                try:
                    # Kiểm tra xem comment này có nằm trong ul.subcomments không
                    is_in_subcomments = comment_elem.evaluate("""
                        el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.tagName === 'UL' && parent.classList.contains('subcomments')) {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        }
                    """)
                    
                    # Nếu nằm trong subcomments thì skip (đây là reply, sẽ được lấy đệ quy)
                    if is_in_subcomments:
                        continue
                    
                    # Đây là comment gốc, lấy nó và tất cả replies (flatten)
                    comment_list = self._scrape_single_comment_recursive(comment_elem, chapter_id, parent_id=None)
                    if comment_list:
                        comments.extend(comment_list)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []

    def _scrape_comments(self, url, comment_type="chapter", chapter_id=""):
        """
        Lấy tất cả comments từ TẤT CẢ các trang phân trang
        Trả về danh sách comments phẳng (flat) với parent_id thay vì nested
        """
        try:
            # Đảm bảo đang ở đúng trang để kiểm tra pagination
            current_url = self.page.url
            if url not in current_url:
                self.page.goto(url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            # Bước 1: Tìm số trang tối đa
            max_page = self._get_max_comment_page(url)
            
            all_comments = []
            
            # Bước 2: Lấy comments từ tất cả các trang
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang {page_num}/{max_page}...")
                
                # Tạo URL cho trang này
                if page_num == 1:
                    # Trang 1: Loại bỏ query parameter comments nếu có
                    base_url = url.split('?')[0]  # Lấy URL gốc không có query
                    page_url = base_url
                else:
                    # Trang khác: Thêm query parameter comments=N
                    base_url = url.split('?')[0]  # Lấy URL gốc
                    # Tìm các query parameter hiện có (trừ comments)
                    if '?' in url:
                        existing_params = url.split('?', 1)[1]
                        # Loại bỏ comments parameter nếu có
                        params_list = []
                        for param in existing_params.split('&'):
                            if not param.startswith('comments='):
                                params_list.append(param)
                        if params_list:
                            other_params = '&'.join(params_list)
                            page_url = f"{base_url}?{other_params}&comments={page_num}"
                        else:
                            page_url = f"{base_url}?comments={page_num}"
                    else:
                        page_url = f"{base_url}?comments={page_num}"
                
                # Lấy comments từ trang này
                page_comments = self._scrape_comments_from_page(page_url, chapter_id)
                all_comments.extend(page_comments)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_comments)} comments")
                
                # Delay giữa các trang để tránh bị ban
                if page_num < max_page:
                    time.sleep(1)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_comments)} comments từ {max_page} trang ({comment_type}-level)")
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []

    def _scrape_comments_worker(self, page, url, comment_type="chapter", chapter_id=""):
        """
        Worker function để lấy comments - dùng page từ worker thay vì self.page
        """
        try:
            current_url = page.url
            if url not in current_url:
                # Delay trước khi request comments
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
                page.goto(url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            # Delay trước khi lấy số trang
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Tìm số trang tối đa
            max_page = self._get_max_comment_page_worker(page, url)
            
            all_comments = []
            
            # Lấy comments từ tất cả các trang
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang {page_num}/{max_page}...")
                
                # Tạo URL cho trang này
                if page_num == 1:
                    base_url = url.split('?')[0]
                    page_url = base_url
                else:
                    base_url = url.split('?')[0]
                    if '?' in url:
                        existing_params = url.split('?', 1)[1]
                        params_list = []
                        for param in existing_params.split('&'):
                            if not param.startswith('comments='):
                                params_list.append(param)
                        if params_list:
                            other_params = '&'.join(params_list)
                            page_url = f"{base_url}?{other_params}&comments={page_num}"
                        else:
                            page_url = f"{base_url}?comments={page_num}"
                    else:
                        page_url = f"{base_url}?comments={page_num}"
                
                # Delay trước khi request trang comments
                if page_num > 1:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                
                # Lấy comments từ trang này
                page_comments = self._scrape_comments_from_page_worker(page, page_url, chapter_id)
                all_comments.extend(page_comments)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_comments)} comments")
                
                # Delay giữa các trang comments
                if page_num < max_page:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_comments)} comments từ {max_page} trang ({comment_type}-level)")
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []

    def _get_max_comment_page_worker(self, page, url):
        """Lấy số trang comments tối đa từ pagination - dùng page từ worker"""
        try:
            base_url = url.split('?')[0]
            current_url = page.url.split('?')[0]
            
            if base_url not in current_url:
                page.goto(base_url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1
            
            pagination_selectors = [
                "ul.pagination",
                ".chapter-nav ul.pagination",
                ".pagination"
            ]
            
            pagination = None
            for selector in pagination_selectors:
                try:
                    pagination = page.locator(selector).first
                    if pagination.count() > 0:
                        break
                except:
                    continue
            
            if pagination and pagination.count() > 0:
                page_links = pagination.locator("a[data-page]").all()
                
                page_numbers = []
                for link in page_links:
                    try:
                        page_num_str = link.get_attribute("data-page")
                        if page_num_str:
                            page_num = int(page_num_str)
                            page_numbers.append(page_num)
                    except:
                        continue
                
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                if link_text.isdigit():
                                    page_num = int(link_text)
                                    page_numbers.append(page_num)
                            except:
                                continue
                    except:
                        pass
                
                if page_numbers:
                    max_page = max(page_numbers)
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang: {e}")
            return 1

    def _scrape_comments_from_page_worker(self, page, page_url, chapter_id=""):
        """Lấy comments từ một trang cụ thể - dùng page từ worker, trả về danh sách phẳng"""
        comments = []
        
        try:
            # Delay trước khi request
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            page.goto(page_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            all_comments = page.locator("div.comment").all()
            
            for comment_elem in all_comments:
                try:
                    is_in_subcomments = comment_elem.evaluate("""
                        el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.tagName === 'UL' && parent.classList.contains('subcomments')) {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        }
                    """)
                    
                    if is_in_subcomments:
                        continue
                    
                    comment_list = self._scrape_single_comment_recursive(comment_elem, chapter_id, parent_id=None)
                    if comment_list:
                        comments.extend(comment_list)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []

    def _scrape_single_comment_recursive(self, comment_elem, chapter_id="", parent_id=None):
        """
        Hàm đệ quy để lấy một comment và tất cả replies của nó, trả về danh sách phẳng (flat)
        Schema: comment id, comment text, time, chapter id (FK), parent id (recursive FK), user id (FK)
        """
        result_list = []
        
        try:
            # Lấy comment container (div.media.media-v2)
            media_elem = comment_elem.locator("div.media.media-v2").first
            if media_elem.count() == 0:
                return []
            
            # Lấy comment ID từ id attribute
            comment_id = media_elem.get_attribute("id") or ""
            if comment_id.startswith("comment-container-"):
                comment_id = comment_id.replace("comment-container-", "")
            
            # Lấy user_id từ profile URL
            user_id = ""
            username = ""
            try:
                # Cấu trúc: h4.media-heading > span.name > a[href*='/profile/']
                username_selectors = [
                    "h4.media-heading span.name a",
                    "h4.media-heading .name a",
                    ".media-heading span.name a",
                    ".media-heading .name a[href*='/profile/']",
                    "h4.media-heading a[href*='/profile/']",
                    ".media-heading a[href*='/profile/']"
                ]
                
                for selector in username_selectors:
                    try:
                        username_elem = media_elem.locator(selector).first
                        if username_elem.count() > 0:
                            username = username_elem.inner_text().strip()
                            # Lấy user_id từ href
                            href = username_elem.get_attribute("href") or ""
                            if "/profile/" in href:
                                user_id = href.split("/profile/")[1].split("/")[0] if "/profile/" in href else ""
                            if username:
                                break
                    except:
                        continue
                
                # Nếu vẫn không tìm thấy, thử lấy từ bất kỳ link profile nào trong media-heading
                if not username:
                    try:
                        username_elem = media_elem.locator(".media-heading a[href*='/profile/']").first
                        if username_elem.count() > 0:
                            username = username_elem.inner_text().strip()
                            href = username_elem.get_attribute("href") or ""
                            if "/profile/" in href:
                                user_id = href.split("/profile/")[1].split("/")[0] if "/profile/" in href else ""
                    except:
                        pass
                        
                if not username:
                    username = "[Unknown]"
            except:
                username = "[Unknown]"
            
            # Lấy comment text/content - lấy tất cả các đoạn văn để giữ format
            comment_text = ""
            try:
                media_body = media_elem.locator(".media-body").first
                if media_body.count() > 0:
                    # Lấy tất cả các đoạn văn trong comment
                    paragraphs = media_body.locator("p").all()
                    
                    if paragraphs:
                        # Nếu có nhiều đoạn văn, nối lại với xuống dòng
                        text_parts = []
                        for para in paragraphs:
                            try:
                                para_text = para.inner_text().strip()
                                if para_text:
                                    text_parts.append(para_text)
                            except:
                                continue
                        comment_text = "\n\n".join(text_parts)
                    else:
                        # Nếu không có thẻ p, lấy toàn bộ text từ media-body
                        full_text = media_body.inner_text().strip()
                        
                        # Loại bỏ username nếu có ở đầu
                        if username and full_text.startswith(username):
                            comment_text = full_text[len(username):].strip()
                        else:
                            comment_text = full_text
                        
                        # Loại bỏ các phần không phải nội dung (như timestamp, rep count)
                        # Các phần này thường ở cuối, có thể có format như "7 years ago" hoặc "Rep (63)"
                        lines = comment_text.split('\n')
                        cleaned_lines = []
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            # Bỏ qua dòng chứa "years ago", "Rep (", "Reply", "Report"
                            if any(x in line.lower() for x in ['years ago', 'months ago', 'days ago', 'hours ago', 
                                                                'rep (', 'reply', 'report']):
                                continue
                            cleaned_lines.append(line)
                        comment_text = '\n'.join(cleaned_lines).strip()
            except Exception as e:
                comment_text = ""
            
            # Lấy timestamp
            timestamp = ""
            try:
                time_elem = media_elem.locator("time, .timestamp, [class*='time'], [class*='date']").first
                if time_elem.count() > 0:
                    timestamp = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # Tạo cấu trúc comment theo schema (flat structure)
            comment_data = {
                "comment_id": comment_id,  # Schema: comment id
                "comment_text": comment_text,  # Schema: comment text
                "time": timestamp,  # Schema: time
                "chapter_id": chapter_id,  # Schema: chapter id (FK)
                "parent_id": parent_id,  # Schema: parent id (recursive FK, None nếu là comment gốc)
                "user_id": user_id  # Schema: user id (FK)
            }
            
            # Lưu user nếu có user_id và username
            if user_id and username:
                self._save_user_to_mongo(user_id, username)
            
            # Lưu comment ngay vào MongoDB (từ cấp thấp nhất)
            self._save_comment_to_mongo(comment_data)
            
            # Thêm comment này vào danh sách
            result_list.append(comment_data)
            
            # Lấy replies (subcomments) - ĐỆ QUY (flatten)
            try:
                subcomments_list = comment_elem.locator("ul.subcomments").first
                if subcomments_list.count() > 0:
                    # Lấy tất cả các comment con trong ul.subcomments
                    reply_comments = subcomments_list.locator("div.comment").all()
                    
                    for reply_elem in reply_comments:
                        # Gọi đệ quy với parent_id = comment_id của comment hiện tại
                        reply_list = self._scrape_single_comment_recursive(reply_elem, chapter_id, parent_id=comment_id)
                        if reply_list:
                            result_list.extend(reply_list)
            except Exception as e:
                # Không có replies hoặc lỗi khi lấy
                pass
            
            return result_list
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse comment: {e}")
            return []

    def _scrape_reviews(self, story_url, story_id):
        """
        Lấy tất cả reviews từ trang story
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        reviews = []
        try:
            safe_print("      📝 Đang lấy reviews từ trang story...")
            
            # Đảm bảo đang ở trang story
            self.page.goto(story_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Scroll xuống để load reviews section
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Tìm reviews section - có thể là tab "Reviews" hoặc section riêng
            # Thử tìm các selector phổ biến cho reviews
            review_selectors = [
                ".review",
                ".review-item",
                ".review-container",
                "[class*='review']",
                ".rating-review"
            ]
            
            review_elements = []
            for selector in review_selectors:
                try:
                    elements = self.page.locator(selector).all()
                    if elements:
                        review_elements = elements
                        safe_print(f"      ✅ Tìm thấy {len(elements)} reviews với selector: {selector}")
                        break
                except:
                    continue
            
            # Nếu không tìm thấy với selector thông thường, thử tìm trong tabs
            if not review_elements:
                try:
                    # Thử click vào tab "Reviews" nếu có
                    reviews_tab = self.page.locator("a[href*='reviews'], button:has-text('Reviews'), .nav-tabs a:has-text('Reviews')").first
                    if reviews_tab.count() > 0:
                        reviews_tab.click()
                        time.sleep(3)
                        # Thử lại với các selector
                        for selector in review_selectors:
                            try:
                                elements = self.page.locator(selector).all()
                                if elements:
                                    review_elements = elements
                                    break
                            except:
                                continue
                except:
                    pass
            
            # Parse từng review và lưu ngay
            for review_elem in review_elements:
                try:
                    review_data = self._parse_single_review(review_elem, story_id)
                    if review_data:
                        reviews.append(review_data)
                        # Lưu review ngay vào MongoDB
                        self._save_review_to_mongo(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    continue
            
            safe_print(f"      ✅ Đã lấy được {len(reviews)} reviews")
            return reviews
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy reviews: {e}")
            return []

    def _parse_single_review(self, review_elem, story_id):
        """
        Parse một review element thành dictionary theo schema
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        try:
            # Lấy review ID
            review_id = ""
            try:
                review_id = review_elem.get_attribute("id") or review_elem.get_attribute("data-id") or ""
                if review_id.startswith("review-"):
                    review_id = review_id.replace("review-", "")
            except:
                pass
            
            # Lấy title
            title = ""
            try:
                title_elem = review_elem.locator("h3, h4, .review-title, [class*='title']").first
                if title_elem.count() > 0:
                    title = title_elem.inner_text().strip()
            except:
                pass
            
            # Lấy user_id từ profile URL
            user_id = ""
            try:
                username_elem = review_elem.locator("a[href*='/profile/'], .username, .reviewer-name, [class*='username']").first
                if username_elem.count() > 0:
                    href = username_elem.get_attribute("href") or ""
                    if "/profile/" in href:
                        user_id = href.split("/profile/")[1].split("/")[0] if "/profile/" in href else ""
            except:
                pass
            
            # Lấy chapter_id từ chapter link
            chapter_id = ""
            try:
                chapter_elem = review_elem.locator("a[href*='/chapter/'], .chapter-link, [class*='chapter']").first
                if chapter_elem.count() > 0:
                    href = chapter_elem.get_attribute("href") or ""
                    if "/chapter/" in href:
                        chapter_id = href.split("/chapter/")[1].split("/")[0]
            except:
                pass
            
            # Lấy time
            time_str = ""
            try:
                time_elem = review_elem.locator("time, .timestamp, [class*='time'], [class*='date']").first
                if time_elem.count() > 0:
                    time_str = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # Lấy content
            content = ""
            try:
                content_elem = review_elem.locator(".review-content, .review-text, [class*='content'], [class*='text']").first
                if content_elem.count() > 0:
                    content = content_elem.inner_text().strip()
            except:
                pass
            
            # Lấy scores để tạo score_id (tạo unique ID từ scores)
            scores = {
                "overall_score": "",
                "style_score": "",
                "story_score": "",
                "grammar_score": "",
                "character_score": ""
            }
            
            try:
                # Tìm các score elements
                score_elements = review_elem.locator(".score, .rating, [class*='score'], [class*='rating']").all()
                for score_elem in score_elements:
                    try:
                        score_text = score_elem.inner_text().strip()
                        score_label = score_elem.get_attribute("data-label") or ""
                        # Có thể parse từ text hoặc từ data attributes
                        if "overall" in score_label.lower() or "overall" in score_text.lower():
                            scores["overall_score"] = score_text
                        elif "style" in score_label.lower() or "style" in score_text.lower():
                            scores["style_score"] = score_text
                        elif "story" in score_label.lower() or "story" in score_text.lower():
                            scores["story_score"] = score_text
                        elif "grammar" in score_label.lower() or "grammar" in score_text.lower():
                            scores["grammar_score"] = score_text
                        elif "character" in score_label.lower() or "character" in score_text.lower():
                            scores["character_score"] = score_text
                    except:
                        continue
            except:
                pass
            
            # Tạo score_id từ scores (hash hoặc unique identifier)
            score_id = f"{review_id}_score" if review_id else ""
            
            # Tạo review data theo schema
            review_data = {
                "review_id": review_id,  # Schema: review id
                "title": title,  # Schema: title
                "time": time_str,  # Schema: time
                "content": content,  # Schema: content
                "user_id": user_id,  # Schema: user id (FK)
                "chapter_id": chapter_id,  # Schema: chapter id (FK)
                "story_id": story_id,  # Schema: story id (FK)
                "score_id": score_id  # Schema: score id (FK)
            }
            
            # Lưu score vào collection scores (từ review)
            if score_id and any(scores.values()):
                self._save_score_to_mongo(
                    score_id,
                    scores.get("overall_score", ""),
                    scores.get("style_score", ""),
                    scores.get("story_score", ""),
                    scores.get("grammar_score", ""),
                    scores.get("character_score", "")
                )
            
            # Lưu user nếu có user_id
            if user_id:
                # Username có thể lấy từ review element nếu cần
                username_elem = review_elem.locator("a[href*='/profile/'], .username, .reviewer-name, [class*='username']").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
                    if username:
                        self._save_user_to_mongo(user_id, username)
            
            # Note: Review sẽ được lưu trong _scrape_reviews sau khi parse
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None

    def _save_comment_to_mongo(self, comment_data):
        """Lưu comment vào MongoDB ngay khi cào xong"""
        if not comment_data or not self.mongo_collection_comments:
            return
        
        try:
            existing = self.mongo_collection_comments.find_one({"comment_id": comment_data.get("comment_id")})
            if existing:
                self.mongo_collection_comments.update_one(
                    {"comment_id": comment_data.get("comment_id")},
                    {"$set": comment_data}
                )
            else:
                self.mongo_collection_comments.insert_one(comment_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu comment vào MongoDB: {e}")
    
    def _save_chapter_to_mongo(self, chapter_data):
        """Lưu chapter vào MongoDB ngay khi cào xong chapter và comments"""
        if not chapter_data or not self.mongo_collection_chapters:
            return
        
        try:
            existing = self.mongo_collection_chapters.find_one({"id": chapter_data.get("id")})
            if existing:
                self.mongo_collection_chapters.update_one(
                    {"id": chapter_data.get("id")},
                    {"$set": chapter_data}
                )
                safe_print(f"      🔄 Đã cập nhật chapter {chapter_data.get('id')} trong MongoDB")
            else:
                self.mongo_collection_chapters.insert_one(chapter_data)
                safe_print(f"      ✅ Đã lưu chapter {chapter_data.get('id')} vào MongoDB")
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lưu chapter vào MongoDB: {e}")
    
    def _save_review_to_mongo(self, review_data):
        """Lưu review vào MongoDB ngay khi cào xong"""
        if not review_data or not self.mongo_collection_reviews:
            return
        
        try:
            existing = self.mongo_collection_reviews.find_one({"review_id": review_data.get("review_id")})
            if existing:
                self.mongo_collection_reviews.update_one(
                    {"review_id": review_data.get("review_id")},
                    {"$set": review_data}
                )
            else:
                self.mongo_collection_reviews.insert_one(review_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu review vào MongoDB: {e}")
    
    def _save_user_to_mongo(self, user_id, username):
        """Lưu user vào MongoDB ngay khi gặp user_id và username"""
        if not user_id or not username or not self.mongo_collection_users:
            return
        
        try:
            existing = self.mongo_collection_users.find_one({"user_id": user_id})
            if existing:
                # Update nếu username thay đổi
                if existing.get("username") != username:
                    self.mongo_collection_users.update_one(
                        {"user_id": user_id},
                        {"$set": {"username": username}}
                    )
            else:
                user_data = {
                    "user_id": user_id,  # Schema: user id
                    "username": username  # Schema: username
                }
                self.mongo_collection_users.insert_one(user_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu user vào MongoDB: {e}")
    
    def _save_score_to_mongo(self, score_id, overall_score, style_score, story_score, grammar_score, character_score):
        """Lưu score vào MongoDB"""
        if not score_id or not self.mongo_collection_scores:
            return
        
        try:
            score_data = {
                "score_id": score_id,  # Schema: score id
                "overall_score": overall_score,  # Schema: overall score
                "style_score": style_score,  # Schema: style score
                "story_score": story_score,  # Schema: story score
                "grammar_score": grammar_score,  # Schema: grammar score
                "character_score": character_score  # Schema: character score
            }
            
            existing = self.mongo_collection_scores.find_one({"score_id": score_id})
            if existing:
                self.mongo_collection_scores.update_one(
                    {"score_id": score_id},
                    {"$set": score_data}
                )
            else:
                self.mongo_collection_scores.insert_one(score_data)
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu score vào MongoDB: {e}")
    
    def _save_story_to_mongo(self, story_data):
        """Lưu story vào MongoDB (có thể update nhiều lần khi có thêm chapters/reviews)"""
        if not story_data or not self.mongo_collection_stories:
            return
        
        try:
            existing = self.mongo_collection_stories.find_one({"id": story_data.get("id")})
            if existing:
                self.mongo_collection_stories.update_one(
                    {"id": story_data.get("id")},
                    {"$set": story_data}
                )
            else:
                self.mongo_collection_stories.insert_one(story_data)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu story vào MongoDB: {e}")
    
    def _save_to_json(self, data):
        """
        Lưu dữ liệu vào file JSON (MongoDB đã được lưu từng phần riêng)
        """
        filename = f"{data['id']}_{utils.clean_text(data.get('name', data.get('title', 'unknown')))}.json"
        save_path = os.path.join(config.JSON_DIR, filename)
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        safe_print(f"💾 Đã lưu dữ liệu vào file: {save_path}")