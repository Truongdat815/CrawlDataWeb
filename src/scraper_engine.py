import time
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
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

class ScribbleHubScraper:
    def __init__(self, max_workers=None):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Khởi tạo MongoDB client nếu được bật
        self.mongo_client = None
        self.mongo_db = None
        # Khởi tạo các collections riêng biệt
        self.mongo_collections = {}
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                self.mongo_client = MongoClient(config.MONGODB_URI)
                self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                # Khởi tạo tất cả các collections
                self.mongo_collections = {
                    "stories": self.mongo_db[config.MONGODB_COLLECTION_STORIES],
                    "chapters": self.mongo_db[config.MONGODB_COLLECTION_CHAPTERS],
                    "comments": self.mongo_db[config.MONGODB_COLLECTION_COMMENTS],
                    "reviews": self.mongo_db[config.MONGODB_COLLECTION_REVIEWS],
                    "scores": self.mongo_db[config.MONGODB_COLLECTION_SCORES],
                    "users": self.mongo_db[config.MONGODB_COLLECTION_USERS],
                }
                # Giữ lại collection cũ để tương thích
                self.mongo_collection = self.mongo_db[config.MONGODB_COLLECTION_FICTIONS]
                safe_print("✅ Đã kết nối MongoDB với các collections: stories, chapters, comments, reviews, scores, users")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

    def start(self):
        """Khởi động trình duyệt"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=['--disable-blink-features=AutomationControlled']  # Ẩn automation flags
        )
        
        # Tạo context với user agent và headers thật để tránh bot detection
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
        )
        self.page = self.context.new_page()
        
        # Ẩn webdriver property để tránh bot detection
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
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

    def scrape_best_rated_fictions(self, best_rated_url, num_fictions=10, start_from=0):
        """
        Cào nhiều bộ truyện từ trang best-rated
        Args:
            best_rated_url: URL trang best-rated
            num_fictions: Số lượng bộ truyện muốn cào (mặc định 10)
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên, 5 = bỏ qua 5 bộ đầu)
        """
        safe_print(f"📚 Đang truy cập trang best-rated: {best_rated_url}")
        self.page.goto(best_rated_url, timeout=config.TIMEOUT)
        
        # Đợi page load hoàn toàn (quan trọng cho ScribbleHub)
        try:
            self.page.wait_for_load_state("networkidle", timeout=30000)
            safe_print("   ✅ Page đã load xong (networkidle)")
        except:
            # Nếu networkidle timeout, đợi domcontentloaded
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                safe_print("   ✅ Page đã load xong (domcontentloaded)")
            except:
                safe_print("   ⚠️ Page load timeout, tiếp tục...")
        
        time.sleep(3)  # Đợi thêm để JavaScript render xong
        
        # Lấy danh sách các bộ truyện từ trang best-rated
        if start_from > 0:
            safe_print(f"🔍 Đang lấy danh sách {num_fictions} bộ truyện (bắt đầu từ vị trí {start_from + 1})...")
        else:
            safe_print(f"🔍 Đang lấy danh sách {num_fictions} bộ truyện đầu tiên...")
        fiction_urls = self._get_fiction_urls_from_best_rated(num_fictions, start_from)
        
        if not fiction_urls:
            safe_print("❌ Không tìm thấy bộ truyện nào!")
            return
        
        safe_print(f"✅ Đã tìm thấy {len(fiction_urls)} bộ truyện:")
        for i, url in enumerate(fiction_urls, 1):
            safe_print(f"   {i}. {url}")
        
        # Cào từng bộ truyện tuần tự
        for index, fiction_url in enumerate(fiction_urls, 1):
            safe_print(f"\n{'='*60}")
            safe_print(f"📖 Bắt đầu cào bộ truyện {index}/{len(fiction_urls)}")
            safe_print(f"{'='*60}")
            try:
                self.scrape_fiction(fiction_url)
                safe_print(f"✅ Hoàn thành bộ truyện {index}/{len(fiction_urls)}")
            except Exception as e:
                safe_print(f"❌ Lỗi khi cào bộ truyện {index}: {e}")
                continue
            
            # Delay giữa các bộ truyện
            if index < len(fiction_urls):
                safe_print(f"⏳ Nghỉ {config.DELAY_BETWEEN_CHAPTERS * 2} giây trước khi cào bộ tiếp theo...")
                time.sleep(config.DELAY_BETWEEN_CHAPTERS * 2)
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🎉 Đã hoàn thành cào {len(fiction_urls)} bộ truyện!")
        safe_print(f"{'='*60}")

    def _get_fiction_urls_from_best_rated(self, num_fictions=10, start_from=0):
        """
        Lấy danh sách URL của các bộ truyện từ trang best-rated (ScribbleHub)
        Selector: div.search_main_box .search_title a
        Args:
            num_fictions: Số lượng bộ truyện muốn lấy
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên)
        """
        fiction_urls = []
        
        try:
            self.page.wait_for_load_state("networkidle", timeout=20000)
            
            # Lấy tất cả các link truyện từ ScribbleHub ranking page
            cards = self.page.locator("div.search_main_box .search_title a").all()
            
            if not cards:
                safe_print("⚠️ Không tìm thấy link truyện nào với selector div.search_main_box .search_title a")
                return []
            
            safe_print(f"✅ Tìm thấy {len(cards)} links truyện")
            
            # Lấy URLs và cắt theo start_from, num_fictions
            for a in cards:
                href = a.get_attribute("href")
                if href and href not in fiction_urls:
                    # Chuẩn hóa URL
                    if href.startswith("/"):
                        full_url = config.BASE_URL + href
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        full_url = config.BASE_URL + "/" + href
                    fiction_urls.append(full_url)
            
            # Cắt theo start_from và num_fictions
            start_index = start_from
            end_index = start_from + num_fictions
            selected_urls = fiction_urls[start_index:end_index]
            
            return selected_urls
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy danh sách truyện từ best-rated: {e}")
            import traceback
            safe_print(traceback.format_exc())
            return []

    def scrape_fiction(self, fiction_url):
        """
        Hàm chính để cào toàn bộ 1 bộ truyện.
        Luồng đi: Vào trang truyện -> Lấy Info -> Lấy List Chapter -> Vào từng Chapter -> Lấy Content.
        """
        safe_print(f"🌍 Đang truy cập truyện: {fiction_url}")
        self.page.goto(fiction_url, timeout=config.TIMEOUT)
        
        # Đợi page load hoàn toàn
        try:
            self.page.wait_for_load_state("networkidle", timeout=30000)
        except:
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass
        
        time.sleep(3)  # Đợi thêm để JavaScript render xong

        # 1. Lấy ID truyện từ URL (ScribbleHub format: /series/ID/title/)
        # Ví dụ: https://www.scribblehub.com/series/664073/rebirth-of-the-nephilim/
        try:
            url_parts = fiction_url.rstrip('/').split('/')
            # Tìm phần số ID (thường là phần thứ 4 sau /series/)
            fiction_id = ""
            for i, part in enumerate(url_parts):
                if part == "series" and i + 1 < len(url_parts):
                    fiction_id = url_parts[i + 1]
                    break
            if not fiction_id:
                # Fallback: lấy từ cuối URL
                fiction_id = url_parts[-1] if url_parts else ""
        except:
            fiction_id = fiction_url.split("/")[-2] if "/" in fiction_url else ""

        # 2. Lấy thông tin tổng quan (Metadata) - ScribbleHub
        safe_print("... Đang lấy thông tin chung")
        
        # Lấy title - ScribbleHub thường dùng h1.fic_title hoặc .fic_title
        title = ""
        try:
            title_selectors = ["h1.fic_title", ".fic_title", "h1", ".wi_fic_title"]
            for selector in title_selectors:
                try:
                    title_elem = self.page.locator(selector).first
                    if title_elem.count() > 0:
                        title = title_elem.inner_text().strip()
                        break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy title: {e}")
        
        # Lấy URL ảnh bìa rồi tải về luôn - ScribbleHub
        img_url_raw = ""
        try:
            cover_selectors = [".fic_image img", ".cover img", ".nov_cover img", "img[src*='cover']"]
            for selector in cover_selectors:
                try:
                    img_elem = self.page.locator(selector).first
                    if img_elem.count() > 0:
                        img_url_raw = img_elem.get_attribute("src")
                        if img_url_raw:
                            break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy cover image: {e}")
        
        local_img_path = utils.download_image(img_url_raw, fiction_id) if img_url_raw else None

        # Lấy author - ScribbleHub
        author = ""
        try:
            author_selectors = [".auth_name_fic a", ".fic_author a", ".auth_name a", "a[href*='/profile/']"]
            for selector in author_selectors:
                try:
                    author_elem = self.page.locator(selector).first
                    if author_elem.count() > 0:
                        author = author_elem.inner_text().strip()
                        if author:
                            break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy author: {e}")

        # Lấy category/genre - ScribbleHub
        category = ""
        try:
            category_selectors = [".fic_genre", ".genre", ".search_genre a"]
            for selector in category_selectors:
                try:
                    category_elems = self.page.locator(selector).all()
                    if category_elems:
                        categories = [elem.inner_text().strip() for elem in category_elems[:3]]  # Lấy 3 đầu tiên
                        category = ", ".join(categories) if categories else ""
                        if category:
                            break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy category: {e}")

        # Lấy status - ScribbleHub
        status = ""
        try:
            status_selectors = [".fic_status", ".status", "[class*='status']"]
            for selector in status_selectors:
                try:
                    status_elem = self.page.locator(selector).first
                    if status_elem.count() > 0:
                        status = status_elem.inner_text().strip()
                        if status:
                            break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy status: {e}")

        # Lấy tags/genres - ScribbleHub
        tags = []
        try:
            tag_selectors = [".fic_genre", ".genre", ".search_genre a", ".tags a"]
            for selector in tag_selectors:
                try:
                    tag_elems = self.page.locator(selector).all()
                    if tag_elems:
                        tags = [elem.inner_text().strip() for elem in tag_elems]
                        if tags:
                            break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy tags: {e}")

        # Lấy description - ScribbleHub (trang chi tiết)
        description = ""
        try:
            # Scroll để đảm bảo description được load (có thể có "more>>" cần expand)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            desc_selectors = [
                ".wi_fic_description",  # With wrapper description
                ".fic_description",  # Fiction description
                ".description",  # Generic description
                ".novel_description",  # Novel description
                "[class*='description']",  # Bất kỳ class nào có 'description'
            ]
            
            for selector in desc_selectors:
                try:
                    desc_container = self.page.locator(selector).first
                    if desc_container.count() > 0:
                        # Thử click "more>>" nếu có để expand description
                        try:
                            more_link = desc_container.locator(".morelink, [onclick*='showtext']").first
                            if more_link.count() > 0:
                                more_link.click()
                                time.sleep(1)
                        except:
                            pass
                        
                        # Lấy HTML để giữ định dạng
                        html_content = desc_container.inner_html()
                        # Chuyển HTML sang text với định dạng đúng
                        description = self._convert_html_to_formatted_text(html_content)
                        if description:
                            safe_print(f"   ✅ Tìm thấy description với selector: {selector}")
                            break
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
            description = ""

        # Lấy stats - ScribbleHub (trang chi tiết)
        # Cấu trúc: .fic_stats > .st_item
        overall_score = ""
        style_score = ""
        story_score = ""
        grammar_score = ""
        character_score = ""
        
        total_views = ""
        average_views = ""
        followers = ""
        favorites = ""
        ratings = ""
        pages = ""
        
        try:
            # Scroll để đảm bảo stats được load
            self.page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
            
            # Tìm stats container
            stats_container = self.page.locator(".fic_stats").first
            if stats_container.count() > 0:
                # Lấy tất cả các stat items
                stat_items = stats_container.locator(".st_item").all()
                
                for stat_item in stat_items:
                    try:
                        stat_text = stat_item.inner_text().strip()
                        stat_lower = stat_text.lower()
                        
                        # Parse các stats
                        if "view" in stat_lower and not total_views:
                            match = re.search(r'([\d.]+[KMkm]?)\s*views?', stat_lower)
                            if match:
                                total_views = match.group(1)
                        
                        if "favorite" in stat_lower and not favorites:
                            match = re.search(r'([\d,]+)\s*favorites?', stat_lower)
                            if match:
                                favorites = match.group(1)
                        
                        if "chapter" in stat_lower and "week" not in stat_lower and not pages:
                            match = re.search(r'([\d,]+)\s*chapters?', stat_lower)
                            if match:
                                pages = match.group(1) + " Chapters"
                        
                        if "reader" in stat_lower and not followers:
                            match = re.search(r'([\d,]+)\s*readers?', stat_lower)
                            if match:
                                followers = match.group(1)
                    except:
                        continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy stats: {e}")

        # Tạo cấu trúc dữ liệu tổng quan sau khi đã lấy hết các biến
        # Theo scheme: fiction id, fiction name, fiction url, cover image, author, category, status, tags, description
        fiction_data = {
            "id": fiction_id,
            "name": title,  # Scheme: fiction name
            "url": fiction_url,  # Scheme: fiction url
            "cover_image": local_img_path,  # Scheme: cover image
            "author": author,
            "category": category,
            "status": status,
            "tags": tags,
            "description": description,
            "stats": {
                "score": {
                    "overall_score": overall_score,
                    "style_score": style_score,
                    "story_score": story_score,
                    "grammar_score": grammar_score,
                    "character_score": character_score,
                },
                "views": {
                    "total_views": total_views,
                    "average_views": average_views,
                    "followers": followers,
                    "favorites": favorites,
                    "ratings": ratings,
                    "page_views": pages,
                }
            },
            "reviews": [],  # Sẽ được điền sau
            "chapters": []     # Chuẩn bị cái mảng rỗng để chứa các chương
        }

        # 3. Lấy danh sách link chương từ TẤT CẢ các trang TOC
        safe_print("... Đang lấy danh sách chương từ tất cả các trang TOC")
        chapter_urls = self._get_all_chapters_for_story(fiction_url)
        
        safe_print(f"--> Tổng cộng tìm thấy {len(chapter_urls)} chương từ tất cả các trang.")

        # 3.5. Lấy reviews cho toàn bộ truyện
        safe_print("... Đang lấy reviews cho toàn bộ truyện")
        reviews = self._scrape_reviews(fiction_url)
        fiction_data["reviews"] = reviews
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
                future = executor.submit(self._scrape_single_chapter_worker, chap_url, index)
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

        # SAU KHI TẤT CẢ XONG: Thêm vào fiction_data THEO ĐÚNG THỨ TỰ
        safe_print(f"📝 Sắp xếp kết quả theo đúng thứ tự...")
        for index in range(len(chapter_results)):
            chapter_data = chapter_results[index]
            if chapter_data:
                fiction_data["chapters"].append(chapter_data)
            else:
                safe_print(f"    ⚠️ Bỏ qua chương {index + 1} (lỗi hoặc không có dữ liệu)")

        safe_print(f"✅ Đã hoàn thành {len(fiction_data['chapters'])}/{len(chapter_urls)} chương (theo đúng thứ tự)")

        # 5. Lưu kết quả ra JSON
        self._save_to_json(fiction_data)

    def _get_all_chapters_for_story(self, story_url):
        """
        Vào truyện, duyệt toàn bộ TOC pages, trả list chapter URLs.
        Chỉ cào khi thật sự có ol.toc_ol trong HTML.
        """
        all_chapters = []
        
        try:
            # TOC page 1
            toc_url = story_url.rstrip("/") + "/?toc=1#content1"
            safe_print(f"    🔗 Vào TOC: {toc_url}")
            self.page.goto(toc_url, timeout=config.TIMEOUT)
            
            # Đợi page load
            try:
                self.page.wait_for_load_state("networkidle", timeout=20000)
            except:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Đợi thêm để JavaScript render TOC
            time.sleep(3)
            
            # Scroll xuống để trigger lazy load và đảm bảo TOC được render
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            self.page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
            
            # Debug: Kiểm tra URL và HTML
            safe_print(f"    Debug: Đang ở URL: {self.page.url}")
            page_content = self.page.content()
            has_toc_ol = "toc_ol" in page_content
            safe_print(f"    Debug: Có 'toc_ol' trong HTML: {has_toc_ol}")
            
            page_chapters = self._get_chapters_from_current_page()
            all_chapters.extend(page_chapters)
            safe_print(f"    ✅ Trang 1: Lấy được {len(page_chapters)} chapters")
            
            # Nếu không tìm thấy chapters ở URL ?toc=1, thử vào trang chính
            if len(page_chapters) == 0:
                safe_print("    ⚠️ Không tìm thấy chapters ở URL ?toc=1, thử vào trang chính...")
                self.page.goto(story_url, timeout=config.TIMEOUT)
                time.sleep(3)
                self.page.wait_for_load_state("networkidle", timeout=20000)
                # Scroll xuống đến phần TOC
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                page_chapters = self._get_chapters_from_current_page()
                if page_chapters:
                    safe_print(f"    ✅ Tìm thấy {len(page_chapters)} chapters từ trang chính")
                    all_chapters.extend(page_chapters)
            
            # Các trang TOC tiếp theo (2,3,4...)
            pag_links = self.page.locator("#pagination-mesh-toc a.page-link").all()
            seen = set()
            
            for a in pag_links:
                href = a.get_attribute("href")
                if not href:
                    continue
                
                full = urljoin(toc_url, href)
                if full in seen:
                    continue
                seen.add(full)
                
                safe_print(f"    🔗 Vào TOC page: {full}")
                self.page.goto(full, timeout=config.TIMEOUT)
                
                # Đợi page load
                try:
                    self.page.wait_for_load_state("networkidle", timeout=20000)
                except:
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                
                # Đợi thêm để JavaScript render
                time.sleep(3)
                
                # Scroll để trigger render
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                all_chapters.extend(self._get_chapters_from_current_page())
            
            safe_print(f"    ✅ Tổng cộng {len(all_chapters)} chapter URLs")
            return all_chapters
            
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi lấy chapters từ TOC: {e}")
            import traceback
            safe_print(traceback.format_exc())
            return []

    def _get_max_chapter_page(self):
        """Lấy số trang chapters tối đa từ pagination (ScribbleHub: ul#pagination-mesh-toc)"""
        try:
            # Scroll xuống để load pagination
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1  # Mặc định là 1 trang
            
            # ScribbleHub dùng: ul#pagination-mesh-toc với các link a.page-link
            pagination_selectors = [
                "ul#pagination-mesh-toc",  # ScribbleHub TOC pagination
                "#pagination-mesh-toc",  # Alternative
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
                # Lấy tất cả các link page (a.page-link cho ScribbleHub)
                page_links = pagination.locator("a.page-link, a[href*='?toc=']").all()
                
                page_numbers = []
                for link in page_links:
                    try:
                        # ScribbleHub: href="?toc=2#content1" -> extract số 2
                        href = link.get_attribute("href") or ""
                        if "?toc=" in href:
                            # Extract số từ ?toc=N
                            import re
                            match = re.search(r'\?toc=(\d+)', href)
                            if match:
                                page_num = int(match.group(1))
                                page_numbers.append(page_num)
                        
                        # Fallback: lấy từ text nếu là số
                        link_text = link.inner_text().strip()
                        if link_text.isdigit():
                            page_num = int(link_text)
                            page_numbers.append(page_num)
                    except:
                        continue
                
                # Nếu không có, thử lấy từ data-page attribute
                if not page_numbers:
                    try:
                        page_links = pagination.locator("a[data-page]").all()
                        for link in page_links:
                            try:
                                page_num_str = link.get_attribute("data-page")
                                if page_num_str:
                                    page_num = int(page_num_str)
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
        Chuyển đến trang chapters cụ thể (ScribbleHub: dùng URL ?toc=N#content1)
        Trả về True nếu thành công, False nếu thất bại
        """
        try:
            # ScribbleHub dùng URL pattern: ?toc=N#content1
            # Lấy base URL (bỏ query params hiện tại)
            base_url = self.page.url.split('?')[0].split('#')[0]
            toc_url = f"{base_url}?toc={page_num}#content1"
            
            # Goto URL mới (ScribbleHub sẽ load AJAX)
            self.page.goto(toc_url, timeout=config.TIMEOUT)
            time.sleep(3)
            
            # Đợi page load
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass
            
            # Đợi TOC container xuất hiện - dùng selector cụ thể cho ScribbleHub
            try:
                self.page.wait_for_selector("ol.toc_ol li.toc_w", timeout=10000)
                return True
            except:
                # Fallback: thử click pagination link
                try:
                    pagination = self.page.locator("ul#pagination-mesh-toc").first
                    if pagination.count() > 0:
                        # Tìm link có href chứa ?toc=page_num
                        page_link = pagination.locator(f'a[href*="?toc={page_num}"]').first
                        if page_link.count() > 0:
                            page_link.click()
                            time.sleep(3)
                            return True
                except:
                    pass
                return False
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi chuyển đến trang {page_num}: {e}")
            return False

    def _get_chapters_from_current_page(self):
        """
        Lấy danh sách chapter URLs từ trang TOC hiện tại (layout có ol.toc_ol).
        Chỉ cào khi thật sự có ol.toc_ol trong HTML.
        """
        chapter_urls = []
        
        try:
            # Đảm bảo page đã load
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Scroll để đảm bảo TOC được render
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            html = self.page.content()
            
            # Nếu không có toc_ol thì coi như layout khác -> bỏ qua
            if "toc_ol" not in html:
                safe_print("        ⚠️ Trang này không có TOC kiểu ol.toc_ol -> bỏ qua")
                safe_print(f"        Debug URL: {self.page.url}")
                # Debug: Kiểm tra các element liên quan
                try:
                    toc_table = self.page.locator("div.wi_fic_table.toc").count()
                    safe_print(f"        Debug: Tìm thấy {toc_table} div.wi_fic_table.toc")
                    toc_ol = self.page.locator("ol.toc_ol").count()
                    safe_print(f"        Debug: Tìm thấy {toc_ol} ol.toc_ol")
                except:
                    pass
                return []
            
            # Lấy tất cả link chương trong TOC
            self.page.wait_for_selector("ol.toc_ol li.toc_w a.toc_a", timeout=15000)
            links = self.page.locator("ol.toc_ol li.toc_w a.toc_a").all()
            safe_print(f"        ✅ Tìm thấy {len(links)} chapters trên trang TOC hiện tại")
            
            for el in links:
                href = el.get_attribute("href")
                if not href:
                    continue
                
                if href.startswith("http"):
                    full = href
                else:
                    full = urljoin(config.BASE_URL + "/", href.lstrip("/"))
                
                if full not in chapter_urls:
                    chapter_urls.append(full)
            
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
        """Hàm con: Chỉ chịu trách nhiệm vào 1 link chương và trả về cục data của chương đó (ScribbleHub)"""
        try:
            self.page.goto(url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Đợi page load - thử nhiều selector
            content_selectors = [".chapter-inner", ".chp_raw", ".wi_chapter_content", ".chapter_content"]
            content_loaded = False
            for selector in content_selectors:
                try:
                    self.page.wait_for_selector(selector, timeout=5000)
                    content_loaded = True
                    break
                except:
                    continue

            # Lấy title - ScribbleHub
            title = ""
            try:
                title_selectors = ["h1", ".chapter-title", ".chp_title", "h2.chapter-title"]
                for selector in title_selectors:
                    try:
                        title_elem = self.page.locator(selector).first
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            break
                    except:
                        continue
            except:
                pass
            
            # Lấy content với định dạng đúng (ScribbleHub)
            content = ""
            try:
                content_selectors = [".chp_raw", ".wi_chapter_content", ".chapter-inner", ".chapter_content"]
                for selector in content_selectors:
                    try:
                        content_container = self.page.locator(selector).first
                        if content_container.count() > 0:
                            # Lấy HTML để giữ định dạng
                            html_content = content_container.inner_html()
                            # Chuyển HTML sang text với định dạng đúng
                            content = self._convert_html_to_formatted_text(html_content)
                            if content:
                                break
                    except:
                        continue
                
                # Fallback: dùng inner_text nếu không tìm thấy
                if not content:
                    for selector in content_selectors:
                        try:
                            content = self.page.locator(selector).first.inner_text()
                            if content:
                                break
                        except:
                            continue
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy content: {e}")

            # Lấy comments cho chapter này
            safe_print(f"      ... Đang lấy comments cho chương")
            chapter_comments = self._scrape_comments(url, "chapter")
            
            # Lấy chapter_id từ URL (ScribbleHub format: /read/ID/title/chapter/CHAPTER_ID/)
            chapter_id = ""
            try:
                # ScribbleHub: /read/1672529-title/chapter/2013841/
                # Chapter ID là số sau /chapter/
                match = re.search(r'/chapter/(\d+)/', url)
                if match:
                    chapter_id = match.group(1)
            except:
                chapter_id = ""

            return {
                "id": chapter_id,  # Scheme: chapter id
                "name": title,  # Scheme: chapter name
                "url": url,  # Scheme: chapter url
                "content": content,  # Scheme: content
                "comments": chapter_comments
            }
        except Exception as e:
            safe_print(f"⚠️ Lỗi cào chương {url}: {e}")
            return None

    def _scrape_single_chapter_worker(self, url, index):
        """
        Worker function để cào MỘT chương - mỗi worker có browser instance riêng
        Thread-safe: Mỗi worker có browser instance riêng
        
        Args:
            url: URL của chương cần cào (DUY NHẤT - không trùng lặp)
            index: Thứ tự chương trong list (DUY NHẤT - không trùng lặp)
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
            time.sleep(2)
            
            # Đợi page load - thử nhiều selector (ScribbleHub)
            content_selectors = [".chapter-inner", ".chp_raw", ".wi_chapter_content", ".chapter_content"]
            for selector in content_selectors:
                try:
                    worker_page.wait_for_selector(selector, timeout=5000)
                    break
                except:
                    continue
            
            # Delay sau khi load page
            time.sleep(config.DELAY_BETWEEN_REQUESTS)

            # Lấy title - ScribbleHub
            title = ""
            try:
                title_selectors = ["h1", ".chapter-title", ".chp_title", "h2.chapter-title"]
                for selector in title_selectors:
                    try:
                        title_elem = worker_page.locator(selector).first
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            break
                    except:
                        continue
            except:
                pass
            
            # Lấy content với định dạng đúng (ScribbleHub)
            content = ""
            try:
                content_selectors = [".chp_raw", ".wi_chapter_content", ".chapter-inner", ".chapter_content"]
                for selector in content_selectors:
                    try:
                        content_container = worker_page.locator(selector).first
                        if content_container.count() > 0:
                            html_content = content_container.inner_html()
                            content = self._convert_html_to_formatted_text(html_content)
                            if content:
                                break
                    except:
                        continue
                
                # Fallback
                if not content:
                    for selector in content_selectors:
                        try:
                            content = worker_page.locator(selector).first.inner_text()
                            if content:
                                break
                        except:
                            continue
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy content: {e}")

            # Delay trước khi lấy comments
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Lấy comments cho chapter này
            safe_print(f"      💬 Thread-{index}: Đang lấy comments cho chương")
            chapter_comments = self._scrape_comments_worker(worker_page, url, "chapter")

            # Delay sau khi hoàn thành chương
            time.sleep(config.DELAY_BETWEEN_CHAPTERS)
            
            # Lấy chapter_id từ URL (ScribbleHub format: /read/ID/title/chapter/CHAPTER_ID/)
            chapter_id = ""
            try:
                # ScribbleHub: /read/1672529-title/chapter/2013841/
                # Chapter ID là số sau /chapter/
                match = re.search(r'/chapter/(\d+)/', url)
                if match:
                    chapter_id = match.group(1)
            except:
                chapter_id = ""

            return {
                "id": chapter_id,  # Scheme: chapter id
                "name": title,  # Scheme: chapter name
                "url": url,  # Scheme: chapter url
                "content": content,  # Scheme: content
                "comments": chapter_comments
            }
            
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

    def _scrape_comments_from_page(self, page_url):
        """Lấy comments từ một trang cụ thể (ScribbleHub chapter page)"""
        comments = []
        
        try:
            self.page.goto(page_url, timeout=config.TIMEOUT)
            time.sleep(2)  # Chờ page load
            
            # Scroll xuống để load comments (lazy load)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ScribbleHub chapter comments: div#comments.comments-area.chp > ol.comment-list.chapters > li
            # Lấy tất cả các li trong ol.comment-list.chapters (level 1 comments)
            all_comment_lis = self.page.locator("div#comments.comments-area.chp ol.comment-list.chapters > li").all()
            
            # Nếu không tìm thấy với selector mới, thử selector cũ (RoyalRoad)
            if not all_comment_lis:
                all_comment_lis = self.page.locator("div.comment").all()
            
            for comment_li in all_comment_lis:
                try:
                    # Parse comment và replies đệ quy
                    comment_data = self._scrape_single_comment_recursive(comment_li)
                    if comment_data:
                        comments.append(comment_data)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []

    def _scrape_comments(self, url, comment_type="chapter"):
        """
        Lấy tất cả comments từ TẤT CẢ các trang phân trang
        Trả về danh sách comments với threading (comment gốc + replies)
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
                page_comments = self._scrape_comments_from_page(page_url)
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

    def _scrape_comments_worker(self, page, url, comment_type="chapter"):
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
                page_comments = self._scrape_comments_from_page_worker(page, page_url)
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

    def _scrape_comments_from_page_worker(self, page, page_url):
        """Lấy comments từ một trang cụ thể - dùng page từ worker (ScribbleHub chapter)"""
        comments = []
        
        try:
            # Delay trước khi request
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            page.goto(page_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ScribbleHub chapter comments: div#comments.comments-area.chp > ol.comment-list.chapters > li
            all_comment_lis = page.locator("div#comments.comments-area.chp ol.comment-list.chapters > li").all()
            
            # Nếu không tìm thấy với selector mới, thử selector cũ (RoyalRoad)
            if not all_comment_lis:
                all_comment_lis = page.locator("div.comment").all()
            
            for comment_li in all_comment_lis:
                try:
                    comment_data = self._scrape_single_comment_recursive(comment_li)
                    if comment_data:
                        comments.append(comment_data)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []

    def _scrape_single_comment_recursive(self, comment_elem):
        """
        Hàm đệ quy để lấy một comment và tất cả replies của nó
        Hỗ trợ cả ScribbleHub (li#comment-XXX) và RoyalRoad (div.comment)
        """
        try:
            import re
            
            # Kiểm tra xem là ScribbleHub format (li#comment-XXX) hay RoyalRoad format (div.comment)
            li_id = comment_elem.get_attribute("id") or ""
            if li_id.startswith("comment-"):
                # Đây là ScribbleHub format
                return self._parse_scribblehub_comment(comment_elem)
            
            # Thử RoyalRoad format
            media_elem = comment_elem.locator("div.media.media-v2").first
            if media_elem.count() == 0:
                return None
            
            # Lấy comment ID từ id attribute
            comment_id = media_elem.get_attribute("id") or ""
            if comment_id.startswith("comment-container-"):
                comment_id = comment_id.replace("comment-container-", "")
            
            # Lấy username - theo cấu trúc HTML: h4.media-heading > span.name > strong > a
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
            
            # Tạo cấu trúc comment theo scheme
            comment_data = {
                "comment_id": comment_id,
                "username": username,
                "comment_text": comment_text,
                "time": timestamp,  # Scheme: time (đổi từ timestamp)
                "replies": []  # Sẽ được điền đệ quy
            }
            
            # Lấy replies (subcomments) - ĐỆ QUY
            try:
                subcomments_list = comment_elem.locator("ul.subcomments").first
                if subcomments_list.count() > 0:
                    # Lấy tất cả các comment con trong ul.subcomments
                    reply_comments = subcomments_list.locator("div.comment").all()
                    
                    for reply_elem in reply_comments:
                        reply_data = self._scrape_single_comment_recursive(reply_elem)
                        if reply_data:
                            comment_data["replies"].append(reply_data)
            except Exception as e:
                # Không có replies hoặc lỗi khi lấy
                pass
            
            return comment_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse comment: {e}")
            return None
    
    def _parse_scribblehub_comment(self, comment_li):
        """Parse comment theo cấu trúc ScribbleHub chapter comments"""
        try:
            import re
            
            # Comment ID: id="comment-3636791" -> 3636791
            li_id = comment_li.get_attribute("id") or ""
            match = re.search(r'comment-(\d+)', li_id)
            comment_id = match.group(1) if match else ""
            
            # Username: span.fn a
            username = ""
            user_id = ""
            try:
                username_elem = comment_li.locator("span.fn a").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
                    # User ID từ href: /profile/65092/username/ -> 65092
                    user_url = username_elem.get_attribute("href") or ""
                    user_id_match = re.search(r'/profile/(\d+)/', user_url)
                    user_id = user_id_match.group(1) if user_id_match else ""
            except:
                username = "[Unknown]"
                user_id = ""
            
            # Time: span.com_date a với attribute title
            timestamp = ""
            comment_url = ""
            try:
                date_elem = comment_li.locator("span.com_date a").first
                if date_elem.count() > 0:
                    timestamp = date_elem.get_attribute("title") or date_elem.inner_text().strip()
                    comment_url = date_elem.get_attribute("href") or ""
            except:
                pass
            
            # Chapter ID từ comment_url: ?cid=3636791&chapter=1709464 -> 1709464
            chapter_id = ""
            try:
                if "chapter=" in comment_url:
                    match = re.search(r'chapter=(\d+)', comment_url)
                    if match:
                        chapter_id = match.group(1)
            except:
                pass
            
            # Comment text: div.user-comment.comment
            comment_text = ""
            try:
                comment_body = comment_li.locator("div.user-comment.comment").first
                if comment_body.count() > 0:
                    comment_text = comment_body.inner_text().strip()
            except:
                pass
            
            comment_data = {
                "comment_id": comment_id,
                "username": username,
                "user_id": user_id,
                "chapter_id": chapter_id,
                "comment_text": comment_text,
                "time": timestamp,
                "comment_url": comment_url,
                "replies": []
            }
            
            # Lấy replies: ol.children > li
            try:
                children_ol = comment_li.locator("ol.children").first
                if children_ol.count() > 0:
                    reply_lis = children_ol.locator("> li").all()
                    for reply_li in reply_lis:
                        reply_data = self._parse_scribblehub_comment(reply_li)
                        if reply_data:
                            comment_data["replies"].append(reply_data)
            except:
                pass
            
            return comment_data
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse ScribbleHub comment: {e}")
            return None

    def _scrape_reviews(self, fiction_url):
        """
        Lấy tất cả reviews từ trang fiction (ScribbleHub)
        """
        reviews = []
        try:
            safe_print("      📝 Đang lấy reviews từ trang fiction...")
            
            # Đảm bảo đang ở trang fiction
            self.page.goto(fiction_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Scroll xuống để load reviews section
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ScribbleHub dùng: .w-comments-item cho reviews
            review_elements = self.page.locator(".w-comments-item").all()
            
            if not review_elements:
                safe_print("      ⚠️ Không tìm thấy reviews!")
                return []
            
            safe_print(f"      ✅ Tìm thấy {len(review_elements)} reviews")
            
            # Parse từng review
            for review_elem in review_elements:
                try:
                    review_data = self._parse_single_review(review_elem)
                    if review_data:
                        reviews.append(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    continue
            
            safe_print(f"      ✅ Đã lấy được {len(reviews)} reviews")
            return reviews
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy reviews: {e}")
            return []

    def _parse_single_review(self, review_elem):
        """
        Parse một review element thành dictionary theo scheme (ScribbleHub)
        """
        try:
            # Lấy review ID từ id attribute
            review_id = ""
            try:
                review_id = review_elem.get_attribute("id") or ""
                if review_id.startswith("comment-"):
                    review_id = review_id.replace("comment-", "")
            except:
                pass
            
            # Lấy title - ScribbleHub không có title riêng, lấy từ status
            title = ""
            try:
                status_elem = review_elem.locator(".status_cmt .fic_r_stats").first
                if status_elem.count() > 0:
                    title = status_elem.inner_text().strip()
            except:
                pass
            
            # Lấy username
            username = ""
            try:
                username_elem = review_elem.locator(".revname, a[id^='revname']").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
            except:
                username = "[Unknown]"
            
            # Lấy "at chapter"
            at_chapter = ""
            try:
                status_elem = review_elem.locator(".status_cmt .fic_r_stats").first
                if status_elem.count() > 0:
                    at_chapter = status_elem.inner_text().strip()
            except:
                pass
            
            # Lấy time
            time_str = ""
            try:
                time_elem = review_elem.locator(".pro_item_al a").first
                if time_elem.count() > 0:
                    time_str = time_elem.inner_text().strip()
            except:
                pass
            
            # Lấy content
            content = ""
            try:
                content_elem = review_elem.locator(".w-comments-item-text").first
                if content_elem.count() > 0:
                    # Lấy HTML để giữ định dạng
                    html_content = content_elem.inner_html()
                    content = self._convert_html_to_formatted_text(html_content)
            except:
                pass
            
            # Lấy scores từ stars
            scores = {
                "overall": "",
                "style": "",
                "story": "",
                "grammar": "",
                "character": ""
            }
            
            try:
                # Đếm số sao được chọn (filled stars)
                filled_stars = review_elem.locator(".userreview.fa-star").count()
                empty_stars = review_elem.locator(".userreview.fa-star-o").count()
                half_stars = review_elem.locator(".userreview.fa-star-half-o").count()
                
                # Tính overall score
                if filled_stars > 0:
                    overall = filled_stars + (half_stars * 0.5)
                    scores["overall"] = str(overall)
            except:
                pass
            
            # Tạo review data theo scheme
            review_data = {
                "review_id": review_id,
                "title": title,
                "username": username,
                "at_chapter": at_chapter,
                "time": time_str,
                "content": content,
                "score": scores
            }
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None

    def _save_to_json(self, data):
        """
        Lưu dữ liệu vào cả file JSON và MongoDB (nếu được bật)
        Tách dữ liệu thành nhiều collections: stories, chapters, comments, reviews, scores, users
        """
        # 1. Lưu vào file JSON (luôn luôn)
        filename = f"{data['id']}_{utils.clean_text(data.get('name', data.get('title', 'unknown')))}.json"
        save_path = os.path.join(config.JSON_DIR, filename)
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        safe_print(f"💾 Đã lưu dữ liệu vào file: {save_path}")
        
        # 2. Lưu vào MongoDB - tách thành nhiều collections
        if self.mongo_collections:
            try:
                story_id = data['id']
                
                # 2.1. Lưu STORY vào collection "stories"
                story_data = {
                    "id": story_id,
                    "name": data.get("name", ""),
                    "url": data.get("url", ""),
                    "cover_image": data.get("cover_image", ""),
                    "author": data.get("author", ""),
                    "category": data.get("category", ""),
                    "status": data.get("status", ""),
                    "tags": data.get("tags", []),
                    "description": data.get("description", ""),
                    "stats": {
                        "views": data.get("stats", {}).get("views", {})
                    }
                }
                
                stories_col = self.mongo_collections["stories"]
                existing_story = stories_col.find_one({"id": story_id})
                if existing_story:
                    stories_col.update_one({"id": story_id}, {"$set": story_data})
                    safe_print(f"🔄 Đã cập nhật story trong MongoDB (ID: {story_id})")
                else:
                    stories_col.insert_one(story_data)
                    safe_print(f"✅ Đã lưu story vào MongoDB (ID: {story_id})")
                
                # 2.2. Lưu SCORES vào collection "scores"
                if "stats" in data and "score" in data["stats"]:
                    score_data = {
                        "story_id": story_id,
                        "overall_score": data["stats"]["score"].get("overall_score", ""),
                        "style_score": data["stats"]["score"].get("style_score", ""),
                        "story_score": data["stats"]["score"].get("story_score", ""),
                        "grammar_score": data["stats"]["score"].get("grammar_score", ""),
                        "character_score": data["stats"]["score"].get("character_score", "")
                    }
                    
                    scores_col = self.mongo_collections["scores"]
                    existing_score = scores_col.find_one({"story_id": story_id})
                    if existing_score:
                        scores_col.update_one({"story_id": story_id}, {"$set": score_data})
                    else:
                        scores_col.insert_one(score_data)
                    safe_print(f"✅ Đã lưu scores vào MongoDB (story_id: {story_id})")
                
                # 2.3. Lưu CHAPTERS vào collection "chapters"
                chapters_col = self.mongo_collections["chapters"]
                chapters = data.get("chapters", [])
                chapters_saved = 0
                for chapter in chapters:
                    chapter_data = {
                        "id": chapter.get("id", ""),
                        "story_id": story_id,
                        "name": chapter.get("name", ""),
                        "url": chapter.get("url", ""),
                        "content": chapter.get("content", "")
                    }
                    
                    chapter_id = chapter_data["id"]
                    if chapter_id:
                        existing_chapter = chapters_col.find_one({"id": chapter_id, "story_id": story_id})
                        if existing_chapter:
                            chapters_col.update_one(
                                {"id": chapter_id, "story_id": story_id},
                                {"$set": chapter_data}
                            )
                        else:
                            chapters_col.insert_one(chapter_data)
                        chapters_saved += 1
                        
                        # 2.4. Lưu COMMENTS của chapter vào collection "comments"
                        chapter_comments = chapter.get("comments", [])
                        if chapter_comments:
                            self._save_comments_to_mongo(chapter_comments, story_id, chapter_id, "chapter")
                
                safe_print(f"✅ Đã lưu {chapters_saved} chapters vào MongoDB (story_id: {story_id})")
                
                # 2.5. Lưu REVIEWS vào collection "reviews"
                reviews_col = self.mongo_collections["reviews"]
                reviews = data.get("reviews", [])
                reviews_saved = 0
                for review in reviews:
                    review_data = {
                        "review_id": review.get("review_id", ""),
                        "story_id": story_id,
                        "title": review.get("title", ""),
                        "username": review.get("username", ""),
                        "at_chapter": review.get("at_chapter", ""),
                        "time": review.get("time", ""),
                        "content": review.get("content", ""),
                        "score": review.get("score", {})
                    }
                    
                    review_id = review_data["review_id"]
                    if review_id:
                        existing_review = reviews_col.find_one({"review_id": review_id, "story_id": story_id})
                        if existing_review:
                            reviews_col.update_one(
                                {"review_id": review_id, "story_id": story_id},
                                {"$set": review_data}
                            )
                        else:
                            reviews_col.insert_one(review_data)
                        reviews_saved += 1
                        
                        # Lưu user từ review
                        username = review_data.get("username", "")
                        if username:
                            self._save_user_to_mongo(username)
                
                safe_print(f"✅ Đã lưu {reviews_saved} reviews vào MongoDB (story_id: {story_id})")
                
                # 2.6. Lưu vào collection cũ để tương thích (nếu cần)
                if self.mongo_collection:
                    existing = self.mongo_collection.find_one({"id": story_id})
                    if existing:
                        self.mongo_collection.update_one({"id": story_id}, {"$set": data})
                    else:
                        self.mongo_collection.insert_one(data)
                
                safe_print(f"🎉 Đã hoàn thành lưu tất cả dữ liệu vào MongoDB!")
                
            except Exception as e:
                safe_print(f"⚠️ Lỗi khi lưu vào MongoDB: {e}")
                safe_print("   Dữ liệu vẫn được lưu vào file JSON")
                import traceback
                safe_print(traceback.format_exc())
    
    def _save_comments_to_mongo(self, comments, story_id, parent_id, parent_type="chapter"):
        """
        Lưu comments vào MongoDB (đệ quy để lưu cả replies)
        parent_type: "chapter" hoặc "story"
        """
        if not self.mongo_collections:
            return
        
        comments_col = self.mongo_collections["comments"]
        
        for comment in comments:
            comment_data = {
                "comment_id": comment.get("comment_id", ""),
                "story_id": story_id,
                "parent_id": parent_id,
                "parent_type": parent_type,
                "username": comment.get("username", ""),
                "comment_text": comment.get("comment_text", ""),
                "time": comment.get("time", "")
            }
            
            comment_id = comment_data["comment_id"]
            if comment_id:
                # Kiểm tra xem đã có comment này chưa (thêm parent_type để chắc chắn)
                existing = comments_col.find_one({
                    "comment_id": comment_id,
                    "story_id": story_id,
                    "parent_id": parent_id,
                    "parent_type": parent_type
                })
                
                if existing:
                    comments_col.update_one(
                        {"comment_id": comment_id, "story_id": story_id, "parent_id": parent_id, "parent_type": parent_type},
                        {"$set": comment_data}
                    )
                else:
                    comments_col.insert_one(comment_data)
                
                # Lưu user từ comment
                username = comment_data.get("username", "")
                if username:
                    self._save_user_to_mongo(username)
                
                # Lưu replies (đệ quy)
                replies = comment.get("replies", [])
                if replies:
                    self._save_comments_to_mongo(replies, story_id, comment_id, "comment")
    
    def _save_user_to_mongo(self, username):
        """
        Lưu user vào collection "users" (chỉ lưu username, có thể mở rộng sau)
        """
        if not self.mongo_collections or not username or username == "[Unknown]":
            return
        
        users_col = self.mongo_collections["users"]
        
        # Kiểm tra xem user đã tồn tại chưa
        existing_user = users_col.find_one({"username": username})
        if not existing_user:
            user_data = {
                "username": username,
                "created_at": time.time()  # Timestamp khi tạo
            }
            users_col.insert_one(user_data)