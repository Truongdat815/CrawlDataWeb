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
    
    def get_story_urls_from_best_rated(self, num_stories=10, start_from=0):
        """
        Lấy danh sách URL của các bộ truyện từ trang series-ranking của ScribbleHub
        Args:
            num_stories: Số lượng bộ truyện muốn lấy
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên)
        """
        story_urls = []
        
        try:
            # Đợi trang load xong
            self.page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(3)
            
            # Scroll xuống để load thêm nội dung nếu cần
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Thử nhiều selector khác nhau
            fiction_links = []
            selectors_to_try = [
                ".search_title a",
                ".search_title a[href*='/series/']",
                "a[href*='/series/']",
                ".search_title",
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
                except:
                    continue
            
            if not fiction_links:
                safe_print("⚠️ Không tìm thấy link nào với bất kỳ selector nào!")
                # Debug: In ra HTML để kiểm tra
                try:
                    body_html = self.page.locator("body").inner_html()
                    safe_print(f"📄 Độ dài HTML body: {len(body_html)}")
                except:
                    pass
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
            safe_print(f"⏭️  Story {web_story_id} đã có trong DB, bỏ qua phần metadata...")
            # Lấy story_id đã có từ DB
            existing_story = self.mongo.get_story_by_web_id(web_story_id)
            if existing_story:
                story_id = existing_story.get("id")
            else:
                story_id = generate_id()
            return None, story_id  # Không cần cào metadata nữa
        
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
        
        # Lấy stats từ fic_stats (favorites, total_chapters, release_rate, number_of_reader)
        favorites = ""
        total_chapters = ""
        release_rate = ""
        number_of_reader = ""
        
        try:
            stats_items = self.page.locator(".fic_stats .st_item").all()
            for item in stats_items:
                try:
                    text = item.inner_text()
                    # Tìm icon để xác định loại stat
                    icon_elem = item.locator("i").first
                    if icon_elem.count() > 0:
                        icon_class = icon_elem.get_attribute("class") or ""
                        
                        if "fa-heart" in icon_class:
                            # Favorites
                            numbers = re.findall(r'[\d.]+[kmKM]?', text)
                            if numbers:
                                favorites = numbers[0]
                        elif "fa-list-alt" in icon_class:
                            # Chapters
                            numbers = re.findall(r'\d+', text)
                            if numbers:
                                total_chapters = numbers[0]
                        elif "fa-calendar" in icon_class:
                            # Chapters/Week (release_rate)
                            numbers = re.findall(r'\d+', text)
                            if numbers:
                                release_rate = numbers[0]
                        elif "fa-user-o" in icon_class:
                            # Readers
                            numbers = re.findall(r'[\d.]+[kmKM]?', text)
                            if numbers:
                                number_of_reader = numbers[0]
                except:
                    continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy stats từ fic_stats: {e}")
        
        # Lấy stats từ table_pro_overview (total_views, average_views, total_word, average_words, page_views, total_views_chapters)
        total_views = ""
        average_views = ""
        total_word = ""
        average_words = ""
        pages = ""
        total_views_chapters = ""
        
        try:
            table = self.page.locator(".table_pro_overview").first
            if table.count() > 0:
                rows = table.locator("tbody tr").all()
                for row in rows:
                    try:
                        th_text = row.locator("th").first.inner_text().strip()
                        td_text = row.locator("td").first.inner_text().strip()
                        
                        if "Total Views (All):" in th_text:
                            # Xóa dấu phẩy và lấy số
                            total_views = td_text.replace(",", "")
                        elif "Total Views (Chapters):" in th_text:
                            # Xóa dấu phẩy và lấy số
                            total_views_chapters = td_text.replace(",", "")
                        elif "Average Views:" in th_text:
                            average_views = td_text.replace(",", "")
                        elif "Word Count:" in th_text:
                            total_word = td_text.replace(",", "")
                        elif "Average Words:" in th_text:
                            average_words = td_text.replace(",", "")
                        elif "Pages:" in th_text:
                            pages = td_text.replace(",", "")
                    except:
                        continue
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy stats từ table_pro_overview: {e}")
        
        # Lấy overall_score (từ rating_average) và rating_total từ fic_rate
        overall_score = ""
        rating_total = ""
        try:
            fic_rate = self.page.locator(".fic_rate").first
            if fic_rate.count() > 0:
                # Lấy overall_score từ số cạnh phần sao (rating_average)
                rating_span = fic_rate.locator("span span").first
                if rating_span.count() > 0:
                    rating_text = rating_span.inner_text().strip()
                    numbers = re.findall(r'\d+\.?\d*', rating_text)
                    if numbers:
                        overall_score = numbers[0]
                
                # Lấy rating_total (số trong ngoặc, ví dụ "81 ratings")
                rate_more = fic_rate.locator(".rate_more").first
                if rate_more.count() > 0:
                    rate_text = rate_more.inner_text().strip()
                    numbers = re.findall(r'\d+', rate_text)
                    if numbers:
                        rating_total = numbers[0]
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy rating: {e}")
        
        # Lấy total_reviews từ phần Reviews
        total_reviews = ""
        try:
            reviews_section = self.page.locator(".wi_novel_title.tags.pedit_body.nreview").first
            if reviews_section.count() > 0:
                cnt_toc = reviews_section.locator(".cnt_toc").first
                if cnt_toc.count() > 0:
                    total_reviews = cnt_toc.inner_text().strip()
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy total_reviews: {e}")
        
        # Lấy user stats từ statUser
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
        
        # Lấy description từ wi_fic_desc
        description = ""
        try:
            desc_container = self.page.locator(".wi_fic_desc").first
            if desc_container.count() > 0:
                html_content = desc_container.inner_html()
                description = convert_html_to_formatted_text(html_content)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
            description = ""
        
        # Lấy genres từ wi_fic_genre
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
        
        # Lấy tags từ wi_fic_showtags
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
                try:
                    date_elem = similar_widget.locator('span[title*="Last updated"]').first
                    if date_elem.count() > 0:
                        date_text = date_elem.inner_text().strip()
                        # Extract date từ text như "Nov 28, 2025"
                        date_match = re.search(r'([A-Za-z]+ \d{1,2}, \d{4})', date_text)
                        if date_match:
                            last_updated = date_match.group(1)
                except:
                    pass
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy status và last_updated: {e}")
        
        # Các field khác chưa có trong HTML này, để trống
        author_id = None
        
        # Tạo story_data (chỉ các field cơ bản)
        story_data = {
            "id": story_id,
            "web_story_id": web_story_id,
            "name": title,
            "url": story_url,
            "cover_image": local_img_path,
            "category": "",  # Để trống
            "status": status,
            "genres": genres,
            "tags": tags,
            "description": description
        }
        
        if author_id:
            story_data["user_id"] = author_id
        
        if total_chapters:
            story_data["total_chapters"] = total_chapters
        
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
            "style_score": "",  # Để null
            "story_score": "",  # Để null
            "grammar_score": "",  # Để null
            "character_score": "",  # Để null
            "stability_of_updates": "",  # Chưa có scraping
            "voted": "",  # Chưa có scraping
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
        self.mongo.save_story(story_data)
        self.mongo.save_story_info(story_info_data)
        
        return story_data, story_id
    
    def get_all_chapters_from_pagination(self, story_url):
        """
        Lấy tất cả chapters từ tất cả các trang phân trang
        Pagination sử dụng JavaScript (AJAX), không đổi URL
        Trả về danh sách dict với url và published_time của tất cả chapters
        """
        all_chapter_info = []
        
        try:
            safe_print(f"    📄 Đang lấy chapters từ trang 1 (trang story chính)...")
            self.page.goto(story_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            page_chapters = self.get_chapters_from_current_page()
            all_chapter_info.extend(page_chapters)
            safe_print(f"    ✅ Trang 1: Lấy được {len(page_chapters)} chapters")
            
            max_page = self.get_max_chapter_page()
            
            if max_page <= 1:
                safe_print(f"    📚 Chỉ có 1 trang chapters")
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
            
            return all_chapter_info
            
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi lấy chapters từ pagination: {e}")
            try:
                self.page.goto(story_url, timeout=config.TIMEOUT)
                time.sleep(2)
                return self.get_chapters_from_current_page()
            except:
                return []
    
    def get_max_chapter_page(self):
        """Lấy số trang chapters tối đa từ pagination"""
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
                    safe_print(f"        📄 Tìm thấy {max_page} trang chapters")
                else:
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
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
            
            # Cách 3: Click nút "Next" nhiều lần
            if page_num <= 10:
                current_page = 1
                try:
                    active_page = pagination.locator("li.page-active a").first
                    if active_page.count() > 0:
                        active_text = active_page.inner_text().strip()
                        if active_text.isdigit():
                            current_page = int(active_text)
                except:
                    pass
                
                while current_page < page_num:
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
    
    def get_chapters_from_current_page(self):
        """Lấy danh sách chapters từ trang hiện tại, trả về list dict với url, order và published_time"""
        chapter_info_list = []
        
        try:
            # Lấy chapters từ HTML mới: .wi_fic_table.toc ol.toc_ol li.toc_w
            chapter_items = self.page.locator(".wi_fic_table.toc ol.toc_ol li.toc_w").all()
            
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
                    
                    # Lấy URL từ a.toc_a
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
                            
                            # Chỉ thêm nếu chưa có trong list (tránh trùng)
                            if not any(ch["url"] == full_url for ch in chapter_info_list):
                                chapter_info_list.append({
                                    "url": full_url,
                                    "order": order,
                                    "published_time": published_time
                                })
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse chapter item: {e}")
                    continue
            
            return chapter_info_list
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapters từ trang hiện tại: {e}")
            return []

