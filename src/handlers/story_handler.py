"""
Story handler - xử lý story metadata và chapter list discovery
"""
import time
import re
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text
from src import utils


class StoryHandler:
    """Handler cho story metadata scraping và chapter list discovery"""
    
    def __init__(self, page, mongo_handler):
        """
        Args:
            page: Playwright page object
            mongo_handler: MongoHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
    
    def get_story_urls_from_best_rated(self, ranking_url, num_stories=10, start_from=0):
        """
        Lấy danh sách URL của các bộ truyện từ trang series-ranking của ScribbleHub
        Args:
            ranking_url: URL của trang ranking (ví dụ: https://www.scribblehub.com/series-ranking/?pg=50)
            num_stories: Số lượng bộ truyện muốn lấy
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên)
        """
        story_urls = []
        
        try:
            # Navigate đến trang ranking
            safe_print(f"🌐 Đang truy cập trang ranking: {ranking_url}")
            try:
                # Thử với networkidle trước
                self.page.goto(ranking_url, timeout=config.TIMEOUT, wait_until="networkidle")
            except Exception as e:
                # Nếu timeout, thử lại với load
                safe_print(f"⚠️ networkidle timeout, thử lại với load: {e}")
                try:
                    self.page.goto(ranking_url, timeout=config.TIMEOUT, wait_until="load")
                except Exception as e2:
                    # Nếu vẫn timeout, thử với domcontentloaded
                    safe_print(f"⚠️ load timeout, thử lại với domcontentloaded: {e2}")
                    self.page.goto(ranking_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Đợi Cloudflare challenge nếu có
            safe_print("... Đang đợi Cloudflare challenge (nếu có)...")
            time.sleep(5)
            
            # Kiểm tra URL hiện tại
            current_url = self.page.url
            safe_print(f"📍 URL hiện tại: {current_url}")
            
            # Đợi trang load xong
            safe_print("... Đang đợi trang load...")
            self.page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(3)
            
            # Kiểm tra xem có body HTML không
            try:
                body_html = self.page.locator("body").inner_html()
                safe_print(f"📄 Độ dài HTML body sau khi load: {len(body_html)}")
                if len(body_html) == 0:
                    safe_print("⚠️ HTML body rỗng! Có thể bị Cloudflare chặn hoặc trang chưa load.")
                    safe_print("... Thử đợi thêm 10 giây...")
                    time.sleep(10)
                    body_html = self.page.locator("body").inner_html()
                    safe_print(f"📄 Độ dài HTML body sau khi đợi thêm: {len(body_html)}")
            except Exception as e:
                safe_print(f"⚠️ Lỗi khi kiểm tra body HTML: {e}")
            
            # Đợi .search_main_box xuất hiện (container chứa các story)
            try:
                safe_print("... Đang đợi .search_main_box xuất hiện...")
                self.page.wait_for_selector(".search_main_box", timeout=30000)
                safe_print("✅ Đã tìm thấy .search_main_box")
            except Exception as e:
                safe_print(f"⚠️ Không tìm thấy .search_main_box: {e}")
                # Thử đợi thêm một chút
                safe_print("... Thử đợi thêm 5 giây...")
                time.sleep(5)
            
            # Scroll xuống để load thêm nội dung nếu cần
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Thử nhiều selector khác nhau (ưu tiên selector chính xác nhất)
            fiction_links = []
            selectors_to_try = [
                ".search_main_box .search_title a[href*='/series/']",  # Selector chính xác nhất
                ".search_title a[href*='/series/']",  # Fallback 1
                ".search_main_box .search_title a",  # Fallback 2
                ".search_title a",  # Fallback 3
                "a[href*='/series/']",  # Fallback 4 (tất cả links có /series/)
                ".toc_ol a",
                ".wi_fic_table a"
            ]
            
            for selector in selectors_to_try:
                try:
                    links = self.page.locator(selector).all()
                    if links and len(links) > 0:
                        safe_print(f"✅ Tìm thấy {len(links)} links với selector: {selector}")
                        fiction_links = links
                        break
                except Exception as e:
                    safe_print(f"⚠️ Lỗi với selector {selector}: {e}")
                    continue
            
            if not fiction_links:
                safe_print("⚠️ Không tìm thấy link nào với bất kỳ selector nào!")
                # Debug: Kiểm tra HTML
                try:
                    body_html = self.page.locator("body").inner_html()
                    safe_print(f"📄 Độ dài HTML body: {len(body_html)}")
                    
                    # Kiểm tra xem có .search_main_box không
                    search_boxes = self.page.locator(".search_main_box").count()
                    safe_print(f"📦 Số lượng .search_main_box: {search_boxes}")
                    
                    # Kiểm tra xem có .search_title không
                    search_titles = self.page.locator(".search_title").count()
                    safe_print(f"📝 Số lượng .search_title: {search_titles}")
                    
                    # Kiểm tra tất cả links có /series/
                    all_series_links = self.page.locator("a[href*='/series/']").count()
                    safe_print(f"🔗 Số lượng links có '/series/': {all_series_links}")
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi debug HTML: {e}")
                return []
            
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
                        
                        # Chỉ lấy link có chứa /series/ (link truyện từ series-ranking)
                        if "/series/" in full_url and full_url not in story_urls:
                            story_urls.append(full_url)
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi lấy URL truyện: {e}")
                    continue
            
            return story_urls
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy danh sách truyện từ series-ranking: {e}")
            return []
    
    def scrape_story_metadata(self, story_url, web_story_id):
        """
        Cào metadata của story (title, author, description, stats, scores, etc.)
        Trả về story_data dict và story_id
        """
        from src.handlers.mongo_handler import MongoHandler
        
        # Kiểm tra story đã được cào chưa
        story_id = None
        if web_story_id and self.mongo.is_story_scraped(web_story_id):
            safe_print(f"⏭️  Story {web_story_id} đã có trong DB, lấy story_id để tiếp tục scrape chapters...")
            # Lấy story_id đã có từ DB
            existing_story = self.mongo.get_story_by_web_id(web_story_id)
            if existing_story:
                story_id = existing_story.get("story_id")
                # Trả về story_data từ DB để có thể tiếp tục scrape chapters
                # Lấy author_profile_url nếu có
                author_profile_url = ""
                user_id = existing_story.get("user_id", "")
                if user_id:
                    # Lấy user_url từ user_id
                    try:
                        user_doc = self.mongo.mongo_collection_users.find_one({"user_id": user_id})
                        if user_doc:
                            author_profile_url = user_doc.get("user_url", "")
                    except:
                        pass
                return existing_story, story_id, author_profile_url
            else:
                story_id = generate_id()
                # Nếu không tìm thấy story trong DB, vẫn cần scrape metadata
                safe_print(f"⚠️ Story {web_story_id} không tìm thấy trong DB, sẽ scrape metadata mới...")
        
        # Story chưa có, tạo id mới và cào toàn bộ metadata
        story_id = generate_id()
        safe_print("... Đang lấy thông tin chung")
        
        # ========== SCRIBBLEHUB FORMAT ==========
        # Lấy title từ class fic_title
        title = ""
        try:
            title_elem = self.page.locator(".fic_title").first
            if title_elem.count() > 0:
                title = title_elem.inner_text().strip()
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy title: {e}")
        
        # Lấy URL ảnh bìa từ fic_image img
        img_url_raw = ""
        try:
            img_elem = self.page.locator(".fic_image img").first
            if img_elem.count() > 0:
                img_url_raw = img_elem.get_attribute("src") or ""
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy cover image URL: {e}")
        
        local_img_path = utils.download_image(img_url_raw, web_story_id)
        
        # Lấy author profile URL từ story page
        author_profile_url = ""
        try:
            safe_print("... Đang tìm author profile URL trên story page...")
            # Tìm author link - thử nhiều selector
            author_selectors = [
                "div[property='author'] a[href*='/profile/']",  # ✅ Selector chính xác từ HTML bạn gửi
                ".sb_content.author a[href*='/profile/']",  # ✅ Selector theo class parent
                "a[href*='/profile/'] span.auth_name_fic",  # ✅ Tìm link có span.auth_name_fic bên trong
                ".auth_name_fic",  # Lấy parent <a> của span.auth_name_fic
                ".fic_title ~ .auth_name_fic a[href*='/profile/']",
                ".wi_fic_author a[href*='/profile/']",
                ".fic_author a[href*='/profile/']",
                ".author a[href*='/profile/']",
                "a[href*='/profile/'][href*='/series/']",
                ".fic_title ~ a[href*='/profile/']",
            ]
            
            found = False
            for selector in author_selectors:
                try:
                    author_elem = self.page.locator(selector).first
                    count = author_elem.count()
                    if count > 0:
                        # Nếu selector trả về span.auth_name_fic, lấy parent <a>
                        href = ""
                        try:
                            tag_name = author_elem.evaluate("el => el.tagName.toLowerCase()")
                            if tag_name == "span":
                                # Lấy parent <a> của span bằng JavaScript
                                href = author_elem.evaluate("el => el.parentElement?.href || ''")
                            else:
                                href = author_elem.get_attribute("href") or ""
                        except:
                            # Fallback: thử lấy href trực tiếp
                            href = author_elem.get_attribute("href") or ""
                        if href and "/profile/" in href:
                            if href.startswith("/"):
                                from src import config
                                author_profile_url = config.BASE_URL + href
                            elif href.startswith("http"):
                                author_profile_url = href
                            else:
                                from src import config
                                author_profile_url = config.BASE_URL + "/" + href
                            safe_print(f"      ✅ Đã tìm thấy author profile URL: {author_profile_url} (selector: {selector})")
                            found = True
                            break
                except:
                    continue
            
            # Nếu không tìm thấy, thử tìm tất cả links có /profile/ và lấy link đầu tiên hợp lý
            if not found:
                try:
                    all_profile_links = self.page.locator("a[href*='/profile/']").all()
                    for link_elem in all_profile_links:
                        try:
                            href = link_elem.get_attribute("href") or ""
                            if href and "/profile/" in href:
                                # Bỏ qua links trong reviews, comments (có thể có cid, tab)
                                if "?tab=" not in href and "&cid=" not in href:
                                    if href.startswith("/"):
                                        from src import config
                                        author_profile_url = config.BASE_URL + href
                                    elif href.startswith("http"):
                                        author_profile_url = href
                                    safe_print(f"      ✅ Đã tìm thấy author profile URL (fallback): {author_profile_url}")
                                    found = True
                                    break
                        except:
                            continue
                except:
                    pass
            
            if not found:
                safe_print("      ⚠️ Không tìm thấy author profile URL trên story page")
                
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy author profile URL: {e}")
        
        # Lấy total_chapters từ Table of Contents (ưu tiên)
        # HTML: <span class="cnt_toc">253</span>
        total_chapters = ""
        try:
            # Thử nhiều selector để tìm .cnt_toc
            selectors = [
                "span.cnt_toc",  # Selector đơn giản nhất - trực tiếp tìm span.cnt_toc
                ".wi_novel_title.tags.toc .cnt_toc",  # Trong toc section
                ".toc .cnt_toc",  # Trong .toc
                ".wi_novel_title .cnt_toc",  # Trong wi_novel_title
                ".cnt_toc"  # Fallback: chỉ tìm .cnt_toc
            ]
            
            for selector in selectors:
                try:
                    cnt_toc_elem = self.page.locator(selector).first
                    if cnt_toc_elem.count() > 0:
                        total_chapters_text = cnt_toc_elem.inner_text().strip()
                        if total_chapters_text and total_chapters_text.isdigit():
                            total_chapters = total_chapters_text
                            safe_print(f"... ✅ Đã lấy total_chapters từ {selector}: {total_chapters}")
                            break
                except Exception as e:
                    continue
            
            # Nếu vẫn chưa có, thử tìm tất cả span.cnt_toc và lấy cái đầu tiên có số
            if not total_chapters:
                try:
                    all_cnt_toc = self.page.locator("span.cnt_toc").all()
                    for elem in all_cnt_toc:
                        try:
                            text = elem.inner_text().strip()
                            if text and text.isdigit():
                                total_chapters = text
                                safe_print(f"... ✅ Đã lấy total_chapters từ span.cnt_toc (tìm tất cả): {total_chapters}")
                                break
                        except:
                            continue
                except:
                    pass
                    
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy total_chapters từ Table of Contents: {e}")
        
        # Lấy stats từ fic_stats (total_views, favorites, release_rate, number_of_reader)
        # HTML: <div class="fic_stats">
        #   <span class="st_item"><i class="fa fa-eye"></i> 562.8k <span class="mb_stat">Views</span></span>
        #   <span class="st_item"><i class="fa fa-heart"></i> 1259 <span class="mb_stat">Favorites</span></span>
        #   ...
        # </div>
        total_views_from_stats = ""  # Lấy từ fic_stats (562.8k)
        favorites = ""
        release_rate = ""
        number_of_reader = ""
        
        try:
            stats_items = self.page.locator(".fic_stats .st_item, .st_item").all()
            for item in stats_items:
                try:
                    # Lấy toàn bộ text của item
                    text = item.inner_text()
                    
                    # Tìm icon để xác định loại stat
                    icon_elem = item.locator("i").first
                    if icon_elem.count() > 0:
                        icon_class = icon_elem.get_attribute("class") or ""
                        
                        if "fa-eye" in icon_class:
                            # ✅ Total Views
                            # HTML: <span class="st_item"><i class="fa fa-eye"></i> 563.1k <span class="mb_stat">Views</span></span>
                            # Cần lấy: "563.1k" (giữ nguyên format)
                            try:
                                # Lấy từ text: "563.1k Views"
                                # Pattern: số có thể có dấu chấm + k/M (ví dụ: 563.1k, 1.2M)
                                match = re.search(r'([\d.]+)\s*(k|K|m|M)', text)
                                if match:
                                    value = match.group(1)  # Giữ nguyên dấu chấm (ví dụ: "563.1")
                                    unit = match.group(2).lower()  # k hoặc m
                                    total_views_from_stats = f"{value}{unit}"  # Giữ nguyên format: "563.1k"
                                    safe_print(f"... ✅ Đã lấy total_views từ fic_stats: {total_views_from_stats}")
                                else:
                                    # Fallback: lấy từ innerHTML
                                    try:
                                        item_html = item.inner_html()
                                        # Pattern: </i> 563.1k <span> hoặc </i>\s*563.1k\s*<span>
                                        match = re.search(r'</i>\s*([\d.]+)\s*(k|K|m|M)\s*<', item_html)
                                        if match:
                                            value = match.group(1)
                                            unit = match.group(2).lower()
                                            total_views_from_stats = f"{value}{unit}"
                                            safe_print(f"... ✅ Đã lấy total_views từ HTML: {total_views_from_stats}")
                                    except Exception as e2:
                                        safe_print(f"        ⚠️ Lỗi khi lấy total_views từ HTML: {e2}")
                            except Exception as e:
                                safe_print(f"        ⚠️ Lỗi khi lấy total_views: {e}")
                        elif "fa-heart" in icon_class:
                            # ✅ Favorites
                            # HTML: <span class="st_item"><i class="fa fa-heart"></i> 1259 <span class="mb_stat">Favorites</span></span>
                            # Cần lấy: "1259"
                            try:
                                # Lấy từ text: "1259 Favorites"
                                # Pattern: số có thể có dấu phẩy (ví dụ: 1259 hoặc 1,259)
                                match = re.search(r'([\d,]+)\s+Favorites', text)
                                if match:
                                    favorites = match.group(1).replace(",", "")  # Loại bỏ dấu phẩy: "1259"
                                    safe_print(f"... ✅ Đã lấy favorites: {favorites}")
                                else:
                                    # Fallback: lấy số đầu tiên trong text
                                    numbers = re.findall(r'[\d,]+', text)
                                    if numbers:
                                        favorites = numbers[0].replace(",", "")
                                        safe_print(f"... ✅ Đã lấy favorites (fallback): {favorites}")
                                    else:
                                        # Fallback: thử lấy từ innerHTML
                                        try:
                                            item_html = item.inner_html()
                                            # Pattern: </i> 1259 <span> hoặc </i>\s*1259\s*<span>
                                            match = re.search(r'</i>\s*([\d,]+)\s*<', item_html)
                                            if match:
                                                favorites = match.group(1).replace(",", "")
                                                safe_print(f"... ✅ Đã lấy favorites (từ HTML): {favorites}")
                                        except Exception as e2:
                                            safe_print(f"        ⚠️ Lỗi khi lấy favorites từ HTML: {e2}")
                            except Exception as e:
                                safe_print(f"        ⚠️ Lỗi khi lấy favorites: {e}")
                        elif "fa-list-alt" in icon_class:
                            # Chapters (total_chapters) - fallback nếu chưa có
                            if not total_chapters:
                                numbers = re.findall(r'\d+', text)
                                if numbers:
                                    total_chapters = numbers[0]
                        elif "fa-calendar" in icon_class:
                            # Chapters/Week (release_rate)
                            numbers = re.findall(r'\d+', text)
                            if numbers:
                                release_rate = numbers[0]
                        elif "fa-user-o" in icon_class:
                            # ✅ Readers (number_of_reader)
                            # HTML: <span class="st_item"><i class="fa fa-user-o fic"></i> 1105 <span class="mb_stat">Readers</span></span>
                            # Cần lấy: "1105"
                            try:
                                # Lấy từ text: "1105 Readers"
                                # Pattern: số có thể có dấu phẩy (ví dụ: 1105 hoặc 1,105)
                                match = re.search(r'([\d,]+)\s+Readers', text)
                                if match:
                                    number_of_reader = match.group(1).replace(",", "")  # Loại bỏ dấu phẩy: "1105"
                                    safe_print(f"... ✅ Đã lấy number_of_reader (Readers): {number_of_reader}")
                                else:
                                    # Fallback: lấy số đầu tiên trong text
                                    numbers = re.findall(r'[\d,]+', text)
                                    if numbers:
                                        number_of_reader = numbers[0].replace(",", "")
                                        safe_print(f"... ✅ Đã lấy number_of_reader (fallback): {number_of_reader}")
                                    else:
                                        # Fallback: thử lấy từ innerHTML
                                        try:
                                            item_html = item.inner_html()
                                            # Pattern: </i> 1105 <span> hoặc </i>\s*1105\s*<span>
                                            match = re.search(r'</i>\s*([\d,]+)\s*<', item_html)
                                            if match:
                                                number_of_reader = match.group(1).replace(",", "")
                                                safe_print(f"... ✅ Đã lấy number_of_reader (từ HTML): {number_of_reader}")
                                        except Exception as e2:
                                            safe_print(f"        ⚠️ Lỗi khi lấy number_of_reader từ HTML: {e2}")
                            except Exception as e:
                                safe_print(f"        ⚠️ Lỗi khi lấy number_of_reader: {e}")
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse stat item: {e}")
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy stats từ fic_stats: {e}")
        
        # ✅ Ưu tiên total_views từ fic_stats, nếu không có thì lấy từ Statistics page
        # Khởi tạo total_views từ fic_stats (nếu đã lấy được) - GIỮ NGUYÊN FORMAT (ví dụ: "563.1k")
        total_views = total_views_from_stats if total_views_from_stats else ""
        if total_views_from_stats:
            safe_print(f"... ✅ Đã dùng total_views từ fic_stats (format gốc): {total_views}")
        # Nếu chưa có, sẽ lấy từ Statistics page (code phía dưới)
        
        # Lấy stats từ .table_pro_overview (cần truy cập trang Statistics trước)
        # HTML: <div class="n_fic_buttons">
        #   <a class="fic_nav-link" href=".../stats"><span class="nficbutton">Statistics</span></a>
        # </div>
        # Sau đó mới có: <table class="table_pro_overview">...</table>
        # Lưu ý: total_views có thể đã có từ fic_stats, nhưng vẫn cần lấy average_views, total_word, etc.
        average_views = ""
        total_word = ""
        average_words = ""
        pages = ""
        total_views_chapters = ""
        
        try:
            # 1. Tìm link Statistics từ trang chính
            stats_url = None
            try:
                stats_link = self.page.locator('.n_fic_buttons a.fic_nav-link:has-text("Statistics"), .n_fic_buttons a.fic_nav-link[href*="/stats"]').first
                if stats_link.count() > 0:
                    stats_href = stats_link.get_attribute("href")
                    if stats_href:
                        if stats_href.startswith("/"):
                            stats_url = config.BASE_URL + stats_href
                        elif stats_href.startswith("http"):
                            stats_url = stats_href
                        else:
                            stats_url = config.BASE_URL + "/" + stats_href
            except Exception as e:
                safe_print(f"      ⚠️ Không tìm thấy link Statistics: {e}")
            
            # 2. Nếu tìm thấy link Statistics, truy cập vào đó
            if stats_url:
                safe_print("      📊 Đang truy cập trang Statistics để lấy stats...")
                try:
                    self.page.goto(stats_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
                    time.sleep(2)  # Đợi page load
                    
                    # Đợi table load
                    try:
                        self.page.wait_for_selector(".table_pro_overview", timeout=10000)
                    except:
                        safe_print("      ⚠️ Không tìm thấy .table_pro_overview sau 10s")
                    
                    # 3. Lấy data từ table_pro_overview
                    table = self.page.locator(".table_pro_overview").first
                    if table.count() > 0:
                        rows = table.locator("tbody tr").all()
                        safe_print(f"      ✅ Tìm thấy {len(rows)} rows trong table_pro_overview")
                        
                        for row in rows:
                            try:
                                th_text = row.locator("th").first.inner_text().strip()
                                td_text = row.locator("td").first.inner_text().strip()
                                
                                if "Total Views (All):" in th_text:
                                    # Mapping: Total Views (All) → total_views (ví dụ: 10,136 → "10136")
                                    # Chỉ lấy nếu chưa có từ fic_stats
                                    if not total_views:
                                        total_views = td_text.replace(",", "")
                                        safe_print(f"      ✅ total_views (từ Statistics): {total_views}")
                                    else:
                                        safe_print(f"      ℹ️ Đã có total_views từ fic_stats ({total_views}), bỏ qua từ Statistics")
                                elif "Total Views (Chapters):" in th_text:
                                    # Mapping: Total Views (Chapters) → total_views_chapters (ví dụ: 8,074 → "8074")
                                    total_views_chapters = td_text.replace(",", "")
                                    safe_print(f"      ✅ total_views_chapters: {total_views_chapters}")
                                elif "Average Views:" in th_text:
                                    # Mapping: Average Views → average_views (ví dụ: 105 → "105")
                                    average_views = td_text.replace(",", "")
                                    safe_print(f"      ✅ average_views: {average_views}")
                                elif "Word Count:" in th_text:
                                    # Mapping: Word Count → total_word (ví dụ: 125,055 → "125055")
                                    total_word = td_text.replace(",", "")
                                    safe_print(f"      ✅ total_word: {total_word}")
                                elif "Average Words:" in th_text:
                                    # Mapping: Average Words → average_words (ví dụ: 1,624 → "1624")
                                    average_words = td_text.replace(",", "")
                                    safe_print(f"      ✅ average_words: {average_words}")
                                elif "Pages:" in th_text:
                                    # Mapping: Pages → page_views (ví dụ: 455 → "455")
                                    pages = td_text.replace(",", "")
                                    safe_print(f"      ✅ page_views: {pages}")
                            except Exception as row_error:
                                safe_print(f"      ⚠️ Lỗi khi parse row: {row_error}")
                                continue
                    else:
                        safe_print("      ⚠️ Không tìm thấy .table_pro_overview trong trang Statistics")
                    
                    # 4. Quay lại trang chính
                    safe_print("      🔄 Quay lại trang story chính...")
                    self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
                    time.sleep(2)
                    
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi truy cập trang Statistics: {e}")
                    # Quay lại trang chính nếu lỗi
                    try:
                        self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
                    except:
                        pass
            else:
                safe_print("      ⚠️ Không tìm thấy link Statistics, bỏ qua stats từ table_pro_overview")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy stats từ table_pro_overview: {e}")
        
        # Lấy overall_score và voted từ #ratefic_user
        # HTML: <span id="ratefic_user">...<span> <span>3.5</span> <span>...<span class="rate_more">42 ratings</span>...</span>
        # overall_score: số 3.5 trong <span>3.5</span> (span con trực tiếp, không có class/style)
        # voted: số 42 từ "42 ratings" trong <span class="rate_more">
        overall_score = ""
        voted = ""
        rating_total = ""  # Giữ lại để tương thích
        try:
            ratefic_user = self.page.locator("#ratefic_user").first
            if ratefic_user.count() > 0:
                # ✅ CÁCH ĐÚNG: Tìm span chứa số thập phân (3.5) - span con trực tiếp, không có class/style
                # Pattern: <span> <span>3.5</span> - tìm span con có text là số thập phân
                try:
                    # Tìm tất cả spans con trực tiếp (không có class/style)
                    all_spans = ratefic_user.locator("span > span").all()
                    for span in all_spans:
                        span_text = span.inner_text().strip()
                        # Tìm số thập phân (ví dụ: 3.5, 4.1, 4.3)
                        # Pattern: chỉ số thập phân, không có text khác
                        match = re.search(r'^(\d+\.\d+)$', span_text)  # Phải có dấu chấm thập phân
                        if match:
                            overall_score = match.group(1)
                            safe_print(f"... ✅ Đã lấy overall_score: {overall_score}")
                            break
                    
                    # Nếu chưa tìm thấy với pattern có dấu chấm, thử pattern không có dấu chấm
                    if not overall_score:
                        for span in all_spans:
                            span_text = span.inner_text().strip()
                            match = re.search(r'^(\d+)$', span_text)  # Chỉ số nguyên
                            if match:
                                # Kiểm tra không phải là số trong ngoặc hoặc có text "rating"
                                parent_text = span.evaluate("el => el.parentElement?.textContent || ''")
                                if "rating" not in parent_text.lower() and "(" not in parent_text:
                                    overall_score = match.group(1)
                                    safe_print(f"... ✅ Đã lấy overall_score (số nguyên): {overall_score}")
                                    break
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi tìm span con: {e}")
                
                # Fallback: Tìm từ HTML trực tiếp
                if not overall_score:
                    try:
                        ratefic_html = ratefic_user.inner_html()
                        # Pattern: <span> <span>3.5</span> hoặc <span>3.5</span>
                        # Tìm số thập phân trong span không có class/style
                        match = re.search(r'<span>\s*(\d+\.\d+)\s*</span>', ratefic_html)
                        if match:
                            overall_score = match.group(1)
                            safe_print(f"... ✅ Đã lấy overall_score (từ HTML): {overall_score}")
                        else:
                            # Thử pattern số nguyên
                            match = re.search(r'<span>\s*(\d+)\s*</span>', ratefic_html)
                            if match:
                                # Kiểm tra không phải trong ngoặc
                                context = ratefic_html[max(0, match.start()-50):match.end()+50]
                                if "rating" not in context.lower() and "(" not in context:
                                    overall_score = match.group(1)
                                    safe_print(f"... ✅ Đã lấy overall_score (từ HTML, số nguyên): {overall_score}")
                    except:
                        pass
                
                # ✅ Lấy voted từ .rate_more (ví dụ: "42 ratings" → "42")
                rate_more = ratefic_user.locator(".rate_more").first
                if rate_more.count() > 0:
                    rate_text = rate_more.inner_text().strip()
                    # Tìm số đầu tiên (ví dụ: "42 ratings" → "42")
                    numbers = re.findall(r'\d+', rate_text)
                    if numbers:
                        voted = numbers[0]
                        rating_total = numbers[0]  # Giữ tương thích
                        safe_print(f"... ✅ Đã lấy voted (total ratings): {voted}")
                else:
                    safe_print("      ⚠️ Không tìm thấy .rate_more")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy rating: {e}")
        
        # Lấy total_reviews từ phần Reviews
        # HTML: <div class="wi_novel_title tags pedit_body nreview">Reviews <span class="cnt_toc">0</span></div>
        total_reviews = ""
        try:
            reviews_section = self.page.locator(".wi_novel_title.tags.pedit_body.nreview").first
            if reviews_section.count() > 0:
                cnt_toc = reviews_section.locator(".cnt_toc").first
                if cnt_toc.count() > 0:
                    total_reviews = cnt_toc.inner_text().strip()
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy total_reviews: {e}")
        
        # Lấy user stats từ .statUser
        # HTML: <ul class="statUser">
        #   <li class="stat2">
        #     <span class="sucnt">54</span>
        #     <span class="sulabel">reading</span>
        #   </li>
        #   <li class="stat2">
        #     <span class="sucnt">15</span>
        #     <span class="sulabel">plan to read</span>
        #   </li>
        #   ...
        # </ul>
        user_reading = ""
        user_plan_to_read = ""
        user_completed = ""
        user_paused = ""
        user_dropped = ""
        
        try:
            stat_user = self.page.locator(".statUser").first
            if stat_user.count() > 0:
                stat_items = stat_user.locator("li").all()
                for item in stat_items:
                    try:
                        label = item.locator(".sulabel").first.inner_text().strip().lower()
                        count = item.locator(".sucnt").first.inner_text().strip()
                        
                        if "reading" in label:
                            user_reading = count
                        elif "plan to read" in label:
                            user_plan_to_read = count
                        elif "completed" in label:
                            user_completed = count
                        elif "paused" in label:
                            user_paused = count
                        elif "dropped" in label:
                            user_dropped = count
                    except:
                        continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy user stats: {e}")
        
        # Lấy description từ .wi_fic_desc (có property="description")
        # HTML: <div class="wi_fic_desc" property="description"><p>...</p></div>
        description = ""
        try:
            desc_container = self.page.locator(".wi_fic_desc[property='description'], .wi_fic_desc").first
            if desc_container.count() > 0:
                html_content = desc_container.inner_html()
                # convert_html_to_formatted_text sẽ giữ đúng format (xuống dòng, đoạn văn)
                description = convert_html_to_formatted_text(html_content)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
            description = ""
        
        # Lấy genres từ .wi_fic_genre .fic_genre
        # HTML: <span class="wi_fic_genre"><span property="genre"><a class="fic_genre" ...>Action</a></span>...</span>
        genres = []
        try:
            genre_links = self.page.locator(".wi_fic_genre .fic_genre").all()
            for link in genre_links:
                try:
                    genre_text = link.inner_text().strip()
                    if genre_text:
                        genres.append(genre_text)
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy genres: {e}")
        
        # Lấy tags từ .wi_fic_showtags a.stag
        # HTML: <span class="wi_fic_showtags"><span class="wi_fic_showtags_inner"><a class="stag odd" ...>Game Elements</a> <a class="stag" ...>...</a></span></span>
        tags = []
        try:
            tag_links = self.page.locator(".wi_fic_showtags a.stag").all()
            for link in tag_links:
                try:
                    tag_text = link.inner_text().strip()
                    if tag_text:
                        tags.append(tag_text)
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy tags: {e}")
        
        # Lấy status và last_updated từ widget_fic_similar
        status = ""
        last_updated = ""
        try:
            similar_widget = self.page.locator(".widget_fic_similar").first
            if similar_widget.count() > 0:
                # Lấy status (ví dụ: "Ongoing", "Completed", etc.)
                status_text = similar_widget.inner_text()
                # Tìm pattern như "Ongoing", "Completed", "Hiatus", etc.
                status_patterns = ["Ongoing", "Completed", "Hiatus", "Dropped", "Stubbed"]
                for pattern in status_patterns:
                    if pattern in status_text:
                        status = pattern
                        break
                
                # Lấy last_updated từ phần có title="Last updated: ..."
                # HTML: <span>Ongoing - Updated <span title="Last updated: 7 hours ago">7 hours ago</span></span>
                try:
                    date_elem = similar_widget.locator('span[title*="Last updated"]').first
                    if date_elem.count() > 0:
                        date_text = date_elem.inner_text().strip()
                        # Lấy text bên trong span (ví dụ: "7 hours ago" hoặc "Nov 28, 2025")
                        if date_text:
                            last_updated = date_text
                        else:
                            # Fallback: Lấy từ title attribute nếu inner_text rỗng
                            title_attr = date_elem.get_attribute("title") or ""
                            if "Last updated:" in title_attr:
                                last_updated = title_attr.split("Last updated:")[-1].strip()
                except:
                    pass
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy status và last_updated: {e}")
        
        # Lấy ranking data từ .rank-icon
        # HTML: <div class="rank-icon">
        #   <a class="rank-link" href="...">
        #     <i class="ranktype">Rankings</i>
        #     <span class="catname">#1 in Pokémon Elemental</span>
        #   </a>
        # </div>
        rankings_list = []
        try:
            rank_icons = self.page.locator(".rank-icon").all()
            for rank_icon in rank_icons:
                try:
                    catname_elem = rank_icon.locator(".catname").first
                    if catname_elem.count() > 0:
                        catname_text = catname_elem.inner_text().strip()
                        # Parse: "#1 in Pokémon Elemental" → rank_number="1", rank_name="Pokémon Elemental"
                        import re
                        match = re.match(r'#(\d+)\s+in\s+(.+)', catname_text)
                        if match:
                            rank_number = match.group(1)
                            rank_name = match.group(2).strip()
                            
                            # Tạo ranking data
                            rank_id = generate_id()
                            website_id = self.mongo.scribblehub_website_id if self.mongo.scribblehub_website_id else ""
                            
                            ranking_data = {
                                "rank_id": rank_id,
                                "rank_name": rank_name,
                                "rank_number": rank_number,
                                "website_id": website_id,
                                "story_id": story_id
                            }
                            
                            rankings_list.append(ranking_data)
                            # Lưu vào MongoDB
                            self.mongo.save_ranking(ranking_data)
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi parse ranking: {e}")
                    continue
            
            if rankings_list:
                safe_print(f"✅ Đã lấy được {len(rankings_list)} rankings")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy rankings: {e}")
        
        # Các field khác chưa có trong HTML này, để trống
        # author_id sẽ được lấy sau khi scrape user profile
        
        # Tạo story_data theo thứ tự và tên fields mới
        story_data = {
            "story_id": story_id,  # 1. story id
            "web_story_id": web_story_id,  # 2. web story id
            "story_name": title,  # 3. story name
            "story_url": story_url,  # 4. story url
            "cover_image": local_img_path,  # 5. cover image
            "category": "",  # 6. category (Để trống)
            "status": status,  # 7. status
            "genres": genres,  # 8. genres
            "tags": tags,  # 9. tags
            "description": description,  # 10. description
            "user_id": "",  # 11. user id (sẽ được cập nhật sau khi scrape author profile)
            "total_chapters": total_chapters if total_chapters else ""  # 12. total chapters
        }
        
        # Tạo story_info_data (tất cả các field stats và info)
        info_id = generate_id()
        # Lấy website_id của ScribbleHub từ mongo handler
        website_id = self.mongo.scribblehub_website_id if self.mongo.scribblehub_website_id else ""
        story_info_data = {
            "info_id": info_id,
            "story_id": story_id,
            "website_id": website_id,  # Reference đến websites collection
            "total_views": total_views,
            "average_views": average_views,
            "followers": "",  # Để null
            "favorites": favorites,
            "page_views": pages,
            "overall_score": overall_score,
            "style_score": None,  # ScribbleHub không có, để null
            "story_score": None,  # ScribbleHub không có, để null
            "grammar_score": None,  # ScribbleHub không có, để null
            "character_score": None,  # ScribbleHub không có, để null
            # "stability_of_updates" đã bị xóa theo yêu cầu
            "voted": voted,  # Số lượt vote từ "129 ratings"
            "freeChapter": "",  # Chưa có scraping
            "time": "",  # Chưa có scraping
            "release_rate": release_rate,
            "number_of_reader": number_of_reader,
            "rating_total": rating_total,
            "total_views_chapters": total_views_chapters,
            "total_word": total_word,
            "average_words": average_words,
            "last_updated": last_updated,
            "total_reviews": total_reviews,
            "user_reading": user_reading,
            "user_plan_to_read": user_plan_to_read,
            "user_completed": user_completed,
            "user_paused": user_paused,
            "user_dropped": user_dropped
        }
        
        # Lưu story và story_info ngay khi cào xong metadata
        # (Chưa có chapter 1 ở đây, sẽ được check sau khi có chapter_info_list)
        self.mongo.save_story(story_data, None, None)
        self.mongo.save_story_info(story_info_data)
        
        # Trả về author_profile_url để scraper_engine có thể scrape user profile
        return story_data, story_id, author_profile_url
    
    def get_all_chapters_from_pagination(self, story_url):
        """
        Lấy tất cả chapters từ tất cả các trang phân trang
        Pagination sử dụng JavaScript (AJAX), không đổi URL
        Trả về danh sách dict với url và published_time của tất cả chapters
        """
        all_chapter_info = []
        
        try:
            safe_print(f"    📄 Đang lấy chapters từ trang 1 (trang story chính)...")
            # Goto với xử lý Cloudflare
            # Note: StoryHandler không kế thừa BaseHandler, nên cần import hoặc dùng trực tiếp
            self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="networkidle")
            time.sleep(3)  # Delay để đợi Cloudflare
            
            # Kiểm tra Cloudflare challenge
            try:
                page_content = self.page.content()
                if "challenges.cloudflare.com" in page_content.lower():
                    safe_print("      ⏳ Phát hiện Cloudflare challenge, đợi...")
                    time.sleep(10)  # Đợi thêm để pass challenge
            except:
                pass
            
            # Đợi chapters table load (nếu có)
            try:
                # Thử đợi một trong các selector
                self.page.wait_for_selector("ol.toc_ol, .wi_fic_table.toc, li.toc_w", timeout=15000)
            except:
                # Nếu không tìm thấy, vẫn tiếp tục
                pass
            
            # ✅ QUAN TRỌNG: Click "Show All Chapters" hoặc set dropdown về 50 để hiển thị tất cả chapters
            safe_print("    🔄 Đang click 'Show All Chapters' để hiển thị tất cả chapters...")
            show_all_clicked = False
            try:
                # Cách 1: Gọi JavaScript function toc_fic_show_all() (cách đáng tin cậy nhất)
                try:
                    self.page.evaluate("""
                        () => {
                            if (typeof toc_fic_show_all === 'function') {
                                toc_fic_show_all();
                                return true;
                            }
                            return false;
                        }
                    """)
                    safe_print("    ✅ Đã gọi JavaScript function toc_fic_show_all()")
                    show_all_clicked = True
                    time.sleep(3)  # Đợi chapters load
                except Exception as e1:
                    safe_print(f"    ⚠️ Không thể gọi toc_fic_show_all(): {e1}")
                    
                    # Cách 2: Click nút "Show All Chapters" (icon fa-th-list chpnew)
                    try:
                        show_all_btn = self.page.locator("i.chpnew, i.fa-th-list.chpnew, .chpnew, #menu_icon_fic").first
                        if show_all_btn.count() > 0:
                            show_all_btn.click()
                            safe_print("    ✅ Đã click nút 'Show All Chapters'")
                            show_all_clicked = True
                            time.sleep(3)  # Đợi chapters load
                        else:
                            # Cách 3: Set dropdown về 50
                            try:
                                dropdown = self.page.locator("#show_chapters").first
                                if dropdown.count() > 0:
                                    current_value = dropdown.input_value()
                                    if current_value != "50":
                                        dropdown.select_option("50")
                                        safe_print(f"    ✅ Đã set dropdown từ {current_value} về 50 chapters")
                                        show_all_clicked = True
                                        time.sleep(3)
                                    else:
                                        safe_print("    ℹ️ Dropdown đã set ở 50 rồi")
                            except Exception as e2:
                                safe_print(f"    ⚠️ Không thể set dropdown: {e2}")
                    except Exception as e3:
                        safe_print(f"    ⚠️ Không thể click nút Show All: {e3}")
            except Exception as e:
                safe_print(f"    ⚠️ Lỗi khi click Show All Chapters: {e}")
            
            # Sau khi click Show All, scroll để đảm bảo tất cả chapters được load
            if show_all_clicked:
                safe_print("    🔄 Đang scroll để load tất cả chapters...")
                # Scroll nhiều lần để đảm bảo lazy load
                for i in range(3):
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                self.page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)
            
            # Scroll để đảm bảo lazy load
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            self.page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
            
            page_chapters = self.get_chapters_from_current_page()
            all_chapter_info.extend(page_chapters)
            safe_print(f"    ✅ Trang 1: Lấy được {len(page_chapters)} chapters")
            
            # Kiểm tra xem có dropdown không và đang set ở giá trị nào
            dropdown_value = None
            try:
                dropdown = self.page.locator("#show_chapters").first
                if dropdown.count() > 0:
                    dropdown_value = dropdown.input_value()
                    safe_print(f"    📊 Dropdown hiện tại: {dropdown_value} chapters")
            except:
                pass
            
            # Nếu chỉ lấy được 15 chapters và dropdown đang set ở 15, thử set về 50 và lấy lại
            if len(page_chapters) == 15 and dropdown_value == "15":
                safe_print(f"    ⚠️ Chỉ lấy được 15 chapters, dropdown đang set ở 15, thử set về 50...")
                try:
                    dropdown = self.page.locator("#show_chapters").first
                    if dropdown.count() > 0:
                        dropdown.select_option("50")
                        safe_print(f"    ✅ Đã set dropdown về 50")
                        time.sleep(3)  # Đợi chapters load
                        # Scroll lại
                        for i in range(3):
                            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1)
                        time.sleep(1)
                        # Lấy lại chapters
                        page_chapters = self.get_chapters_from_current_page()
                        all_chapter_info = page_chapters  # Thay thế bằng danh sách mới
                        safe_print(f"    ✅ Sau khi set dropdown về 50: Lấy được {len(page_chapters)} chapters")
                except Exception as e:
                    safe_print(f"    ⚠️ Không thể set dropdown về 50: {e}")
            
            # Sau khi click "Show All", kiểm tra lại pagination (có thể có nhiều trang hơn)
            max_page = self.get_max_chapter_page()
            
            if max_page <= 1:
                safe_print(f"    📚 Chỉ có 1 trang chapters (đã lấy {len(all_chapter_info)} chapters)")
                return all_chapter_info
            
            safe_print(f"    📚 Tìm thấy {max_page} trang chapters (trang 1 đã lấy, còn {max_page - 1} trang nữa)")
            
            for page_num in range(2, max_page + 1):
                safe_print(f"    📄 Đang lấy chapters từ trang {page_num}/{max_page}...")
                
                if not self.go_to_chapter_page(page_num):
                    safe_print(f"    ⚠️ Không thể chuyển đến trang {page_num}, dừng lại")
                    break
                
                time.sleep(2)
                page_chapters = self.get_chapters_from_current_page()
                all_chapter_info.extend(page_chapters)
                safe_print(f"    ✅ Trang {page_num}: Lấy được {len(page_chapters)} chapters")
                
                if page_num < max_page:
                    time.sleep(1)
            
            # Loại bỏ duplicate chapters (theo URL)
            unique_chapters = []
            seen_urls = set()
            for ch in all_chapter_info:
                url = ch.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_chapters.append(ch)
            
            if len(unique_chapters) < len(all_chapter_info):
                safe_print(f"    🔄 Đã loại bỏ {len(all_chapter_info) - len(unique_chapters)} chapters trùng lặp")
            
            safe_print(f"    📚 Tổng cộng: {len(unique_chapters)} chapters (sau khi loại bỏ trùng)")
            return unique_chapters
            
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi lấy chapters từ pagination: {e}")
            try:
                self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
                return self.get_chapters_from_current_page()
            except:
                return []
    
    def get_max_chapter_page(self):
        """Lấy số trang chapters tối đa từ pagination - CẢI THIỆN để tìm được tất cả trang"""
        try:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1
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
                page_numbers = []
                
                # Cách 1: Tìm từ data-page attribute
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
                
                # Cách 2: Tìm từ text của link (nếu không có data-page)
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                # Bỏ qua các text như "Next", "Previous", ">>", "<<" 
                                if link_text.isdigit():
                                    page_num = int(link_text)
                                    page_numbers.append(page_num)
                            except:
                                continue
                    except:
                        pass
                
                # Cách 3: Tìm từ href attribute (ví dụ: ?page=5)
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                href = link.get_attribute("href") or ""
                                # Tìm pattern ?page=5 hoặc &page=5
                                import re
                                match = re.search(r'[?&]page=(\d+)', href)
                                if match:
                                    page_num = int(match.group(1))
                                    page_numbers.append(page_num)
                            except:
                                continue
                    except:
                        pass
                
                # Cách 4: Nếu có nút "Last" hoặc ">>", thử click để xem trang cuối
                if page_numbers:
                    max_page = max(page_numbers)
                    # Nếu max_page nhỏ hơn 10, có thể còn nhiều trang hơn (pagination không hiển thị hết)
                    # Thử tìm nút "Last" hoặc ">>"
                    try:
                        last_button = pagination.locator('a:has-text("Last"), a:has-text(">>"), .nav-arrow:has-text(">>")').first
                        if last_button.count() > 0:
                            # Có nút Last, có thể có nhiều trang hơn
                            # Thử click để xem trang cuối
                            try:
                                last_button.click()
                                time.sleep(2)
                                # Kiểm tra lại trang hiện tại
                                active_page = pagination.locator("li.page-active a").first
                                if active_page.count() > 0:
                                    active_text = active_page.inner_text().strip()
                                    if active_text.isdigit():
                                        last_page = int(active_text)
                                        if last_page > max_page:
                                            max_page = last_page
                                            safe_print(f"        📄 Tìm thấy trang cuối: {max_page} (từ nút Last)")
                                # Quay lại trang 1
                                first_link = pagination.locator('a[data-page="1"], a:has-text("1")').first
                                if first_link.count() > 0:
                                    first_link.click()
                                    time.sleep(1)
                            except:
                                pass
                    except:
                        pass
                    
                    safe_print(f"        📄 Tìm thấy {max_page} trang chapters")
                else:
                    safe_print(f"        📄 Không tìm thấy pagination numbers, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang chapters: {e}")
            return 1
    
    def go_to_chapter_page(self, page_num):
        """
        Chuyển đến trang chapters cụ thể bằng cách click vào link hoặc nút Next
        Trả về True nếu thành công, False nếu thất bại
        """
        try:
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
            
            # Cách 2: Tìm link có text = page_num
            try:
                all_links = pagination.locator("a").all()
                for link in all_links:
                    try:
                        link_text = link.inner_text().strip()
                        if link_text.isdigit() and int(link_text) == page_num:
                            parent_class = link.evaluate("el => el.closest('li')?.className || ''")
                            if "nav-arrow" not in parent_class:
                                link.click()
                                time.sleep(2)
                                return True
                    except:
                        continue
            except:
                pass
            
            # Cách 3: Click nút "Next" nhiều lần (KHÔNG GIỚI HẠN SỐ TRANG)
            current_page = 1
            try:
                active_page = pagination.locator("li.page-active a").first
                if active_page.count() > 0:
                    active_text = active_page.inner_text().strip()
                    if active_text.isdigit():
                        current_page = int(active_text)
            except:
                pass
            
            # Click Next cho đến khi đến trang cần thiết (KHÔNG GIỚI HẠN)
            max_attempts = page_num * 2  # Giới hạn số lần thử để tránh vòng lặp vô hạn
            attempts = 0
            
            while current_page < page_num and attempts < max_attempts:
                attempts += 1
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
                        next_button = pagination.locator(selector).last
                        if next_button.count() > 0:
                            href = next_button.get_attribute("href") or ""
                            if "page" in href.lower() or "next" in href.lower() or not href:
                                break
                    except:
                        continue
                
                if next_button and next_button.count() > 0:
                    try:
                        # Kiểm tra xem button có disabled không
                        is_disabled = next_button.evaluate("el => el.closest('li')?.classList.contains('disabled') || el.hasAttribute('disabled')")
                        if is_disabled:
                            safe_print(f"        ⚠️ Nút Next bị disabled ở trang {current_page}")
                            return False
                        
                        next_button.click()
                        time.sleep(2)
                        
                        # Kiểm tra lại trang hiện tại sau khi click
                        try:
                            active_page = pagination.locator("li.page-active a").first
                            if active_page.count() > 0:
                                active_text = active_page.inner_text().strip()
                                if active_text.isdigit():
                                    new_page = int(active_text)
                                    if new_page > current_page:
                                        current_page = new_page
                                    else:
                                        # Trang không đổi, có thể đã đến cuối
                                        safe_print(f"        ⚠️ Trang không đổi sau khi click Next (trang {current_page})")
                                        return False
                        except:
                            current_page += 1  # Giả sử đã tăng lên 1
                    except Exception as e:
                        safe_print(f"        ⚠️ Lỗi khi click Next: {e}")
                        return False
                else:
                    safe_print(f"        ⚠️ Không tìm thấy nút Next ở trang {current_page}")
                    return False
            
            if current_page >= page_num:
                return True
            else:
                safe_print(f"        ⚠️ Không thể đến trang {page_num} (dừng ở trang {current_page} sau {attempts} lần thử)")
                return False
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi chuyển đến trang {page_num}: {e}")
            return False
    
    def get_chapters_from_current_page(self):
        """Lấy danh sách chapters từ trang hiện tại, trả về list dict với url, order và published_time"""
        chapter_info_list = []
        
        try:
            # Scroll xuống để đảm bảo chapters được load (lazy load)
            # Scroll nhiều lần để đảm bảo tất cả chapters được load
            for i in range(3):
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
            time.sleep(1)  # Đợi thêm sau khi scroll xong
            
            # Thử nhiều selector khác nhau (fallback)
            chapter_items = []
            selectors = [
                "ol.toc_ol li.toc_w",  # Selector đơn giản nhất
                ".wi_fic_table.toc ol.toc_ol li.toc_w",  # Selector đầy đủ
                "li.toc_w",  # Chỉ class toc_w
                ".toc_ol li",  # Chỉ toc_ol
            ]
            
            for selector in selectors:
                try:
                    items = self.page.locator(selector).all()
                    if items and len(items) > 0:
                        chapter_items = items
                        safe_print(f"        ✅ Tìm thấy {len(items)} chapters với selector: {selector}")
                        break
                except Exception as e:
                    continue
            
            if not chapter_items:
                safe_print(f"        ⚠️ Không tìm thấy chapters với bất kỳ selector nào!")
                # Debug: In ra HTML để xem cấu trúc
                try:
                    toc_html = self.page.locator("ol.toc_ol").first
                    if toc_html.count() > 0:
                        safe_print(f"        🔍 Tìm thấy ol.toc_ol nhưng không có li.toc_w")
                    else:
                        safe_print(f"        🔍 Không tìm thấy ol.toc_ol")
                except:
                    pass
                return chapter_info_list
            
            for item in chapter_items:
                try:
                    # Lấy order từ attribute order
                    order = ""
                    try:
                        order_attr = item.get_attribute("order")
                        if order_attr:
                            order = order_attr
                    except:
                        pass
                    
                    # Lấy URL và chapter_name từ a.toc_a
                    link_el = item.locator("a.toc_a").first
                    if link_el.count() > 0:
                        url = link_el.get_attribute("href")
                        if url:
                            if url.startswith("/"):
                                full_url = config.BASE_URL + url
                            elif url.startswith("http"):
                                full_url = url
                            else:
                                full_url = config.BASE_URL + "/" + url
                            
                            # Lấy chapter_name từ link text (ví dụ: "Chapter 134: A Glimpse of Myself")
                            chapter_name = ""
                            try:
                                chapter_name = link_el.inner_text().strip()
                            except:
                                pass
                            
                            # Lấy published_time từ span.fic_date_pub title attribute
                            published_time = ""
                            try:
                                time_elem = item.locator("span.fic_date_pub").first
                                if time_elem.count() > 0:
                                    # Lấy từ title attribute (ví dụ: "Nov 28, 2025 12:13 PM")
                                    title_attr = time_elem.get_attribute("title")
                                    if title_attr:
                                        published_time = title_attr
                                    else:
                                        # Fallback: lấy từ inner text
                                        published_time = time_elem.inner_text().strip()
                            except:
                                pass
                            
                            # Lấy web_chapter_id từ URL
                            web_chapter_id = ""
                            try:
                                import re
                                match = re.search(r'/chapter/(\d+)', full_url)
                                if match:
                                    web_chapter_id = match.group(1)
                                else:
                                    if "/chapter/" in full_url:
                                        web_chapter_id = full_url.split("/chapter/")[1].split("/")[0]
                            except:
                                pass
                            
                            # Chỉ thêm nếu chưa có trong list (tránh trùng)
                            if not any(ch["url"] == full_url for ch in chapter_info_list):
                                chapter_info_list.append({
                                    "url": full_url,
                                    "order": order,
                                    "published_time": published_time,
                                    "chapter_name": chapter_name,
                                    "web_chapter_id": web_chapter_id
                                })
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse chapter item: {e}")
                    continue
            
            return chapter_info_list
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapters từ trang hiện tại: {e}")
            return []

