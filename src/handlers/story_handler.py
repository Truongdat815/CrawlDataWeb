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
    
    def __init__(self, page, mongo_handler, user_handler):
        """
        Args:
            page: Playwright page object
            mongo_handler: MongoHandler instance
            user_handler: UserHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
        self.user_handler = user_handler
    
    def get_story_urls_from_best_rated(self, num_stories=10, start_from=0):
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
    
    def scrape_story_metadata(self, story_url, web_story_id):
        """
        Cào metadata của story (title, author, description, stats, scores, etc.)
        Trả về story_data dict và story_id
        """
        from src.handlers.mongo_handler import MongoHandler
        
        # BƯỚC 1: Check Level 1 - Check theo URL (cùng nền tảng - nhanh nhất)
        existing_story = self.mongo.find_story_by_url(story_url)
        if existing_story:
            story_id = existing_story.get("storyId")
            safe_print(f"⏭️  Story đã có trong DB (match theo URL), bỏ qua phần metadata...")
            return None, story_id, "url"  # Return match_type = "url"
        
        # Story chưa có theo URL, lấy metadata để check tiếp
        story_id = generate_id()
        safe_print("... Đang lấy thông tin chung")
        
        # Lấy title
        title = self.page.locator("h1").first.inner_text()
        
        # Lấy URL ảnh bìa rồi tải về luôn
        img_url_raw = self.page.locator(".cover-art-container img").get_attribute("src")
        local_img_path = utils.download_image(img_url_raw, web_story_id)
        
        # Lấy author (web_user_id từ profile URL)
        author_link = self.page.locator(".fic-title h4 a").first
        author_href = author_link.get_attribute("href")
        author_name = author_link.inner_text()
        
        # Lưu user (author) ngay vào MongoDB và lấy user_id (rr_{uuid}) để dùng làm FK
        # Truyền page vào để tự động scrape profile
        user_id = None
        if author_href and author_name:
            user_id = self.user_handler.scrape_and_save_user_from_href(author_href, author_name, self.page)
        
        # BƯỚC 2: Check Level 2 - Check theo hash (nền tảng khác)
        # Lấy danh sách chapters để lấy chapter 1
        hash_string = None
        try:
            chapter_info_list = self.get_chapters_from_current_page()
            if chapter_info_list:
                first_chapter_url = chapter_info_list[0]["url"]
                # Lưu URL hiện tại để quay lại sau
                current_url = self.page.url
                
                # Dùng self.page hiện có để vào chapter 1
                hash_string = self.get_first_chapter_hash(first_chapter_url)
                
                # Quay lại trang story sau khi lấy hash
                if current_url:
                    self.page.goto(current_url, timeout=config.TIMEOUT)
                    time.sleep(1)
                
                if hash_string:
                    # Check theo hash với fuzzy match (lệch không quá 3 bit)
                    existing_story = self.mongo.find_story_by_hash(hash_string, max_bit_diff=3)
                    if existing_story:
                        story_id = existing_story.get("storyId")
                        safe_print(f"⏭️  Story đã có trong DB (match theo hash - nền tảng khác), storyId: {story_id}")
                        # Đây là truyện cũ từ nền tảng khác, KHÔNG tạo story mới
                        # Return (None, story_id, "hash") để báo là match theo hash
                        return None, story_id, "hash"
                    # else:
                    #     # BƯỚC 3: Check Level 3 - Check theo title+author (fallback)
                    #     if title and user_id:
                    #         existing_story = self.mongo.find_story_by_name_and_author(title, user_id)
                    #         if existing_story:
                    #             story_id = existing_story.get("storyId")
                    #             safe_print(f"⏭️  Story đã có trong DB (match theo tên/tác giả), storyId: {story_id}")
                    #             # Truyện đã có, KHÔNG tạo story mới
                    #             return None, story_id
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi check hash: {e}")
            # Nếu lỗi, vẫn tiếp tục như truyện mới
        
        # Nếu đến đây nghĩa là truyện mới 100%, tiếp tục lấy metadata để lưu
        # Lấy category
        category = self.page.locator(".fiction-info span").first.inner_text()
        
        # Lấy status
        status = self.page.locator(".fiction-info span:nth-child(2)").first.inner_text()
        
        # Lấy tags
        tags = self.page.locator(".tags a").all_inner_texts()
        
        # Lấy description - giữ nguyên định dạng như trong UI
        description = None
        try:
            desc_container = self.page.locator(".description").first
            if desc_container.count() > 0:
                html_content = desc_container.inner_html()
                description = convert_html_to_formatted_text(html_content)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
            description = None
        
        # Lấy stats - Scores từ aria-label
        overall_score = None
        style_score = None
        story_score = None
        grammar_score = None
        character_score = None
        
        try:
            stats_col = self.page.locator(".stats-content .col-sm-6").first
            if stats_col.count() > 0:
                score_spans = stats_col.locator("ul.list-unstyled li.list-item span[aria-label*='stars']").all()
                
                if len(score_spans) >= 1:
                    try:
                        aria_label = score_spans[0].get_attribute("aria-label") or None
                        if aria_label:
                            numbers = re.findall(r'\d+\.?\d*', aria_label)
                            if numbers:
                                overall_score = numbers[0]
                    except:
                        pass
                
                if len(score_spans) >= 2:
                    try:
                        aria_label = score_spans[1].get_attribute("aria-label") or ""
                        if aria_label:
                            numbers = re.findall(r'\d+\.?\d*', aria_label)
                            if numbers:
                                style_score = numbers[0]
                    except:
                        pass
                
                if len(score_spans) >= 3:
                    try:
                        aria_label = score_spans[2].get_attribute("aria-label") or ""
                        if aria_label:
                            numbers = re.findall(r'\d+\.?\d*', aria_label)
                            if numbers:
                                story_score = numbers[0]
                    except:
                        pass
                
                if len(score_spans) >= 4:
                    try:
                        aria_label = score_spans[3].get_attribute("aria-label") or ""
                        if aria_label:
                            numbers = re.findall(r'\d+\.?\d*', aria_label)
                            if numbers:
                                grammar_score = numbers[0]
                    except:
                        pass
                
                if len(score_spans) >= 5:
                    try:
                        aria_label = score_spans[4].get_attribute("aria-label") or ""
                        if aria_label:
                            numbers = re.findall(r'\d+\.?\d*', aria_label)
                            if numbers:
                                character_score = numbers[0]
                    except:
                        pass
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy scores từ story: {e}")
        
        # Lấy stats values
        stats_values_locator = self.page.locator("div.col-sm-6 li.font-red-sunglo")
        total_views = stats_values_locator.nth(0).inner_text()
        average_views = stats_values_locator.nth(1).inner_text()
        followers = stats_values_locator.nth(2).inner_text()
        favorites = stats_values_locator.nth(3).inner_text()
        ratings = stats_values_locator.nth(4).inner_text()
        pages = stats_values_locator.nth(5).inner_text()
        
        # Lấy total chapters
        total_chapters = self.get_total_chapters_from_html()
        
        # Normalize URL trước khi lưu
        from src.utils import normalize_url
        normalized_story_url = normalize_url(story_url)
        
        # Tạo story_data (chỉ các fields cơ bản)
        story_data = {
            "storyId": story_id,
            "webStoryId": web_story_id,
            "storyName": title,
            "storyUrl": normalized_story_url,  # Lưu URL đã normalize
            "coverImage": local_img_path,
            "category": category,
            "status": status,
            "genres": tags,
            "tags": [], # list tags để trống
            "description": description,
            "userId": user_id,  # FK to users
            "totalChapters": total_chapters,  # Đảm bảo luôn có field
        }
        
        # Thêm hashString nếu có
        if hash_string:
            story_data["hashString"] = hash_string
        
        # Tạo story_info_data (các fields thống kê/metrics)
        info_id = generate_id()  # Tạo infoId mới
        website_id = self.mongo.royal_road_website_id if self.mongo.royal_road_website_id else None
        story_info_data = {
            "infoId": info_id,
            "storyId": story_id,  # FK to stories
            "websiteId": website_id,  # FK to websites
            "totalViews": total_views,
            "averageViews": average_views,
            "followers": followers,
            "favorites": favorites,
            "pageViews": pages,
            "overallScore": overall_score,
            "styleScore": style_score,
            "storyScore": story_score,
            "grammarScore": grammar_score,
            "characterScore": character_score,
            "voted": None,  # Tổng vote của chap - để trống
            "freeChapter": None,  # Để trống
            "timeToFinish": None,  # Thời gian đọc xong bộ - để trống
            "releaseRate": None,  # Để trống
            "numberOfReader": None,  # Để trống
            "ratingTotal": ratings,  # rating total
            "totalViewsChapters": None,  # Để trống
            "totalWord": None,  # Để trống
            "averageWords": None,  # Để trống
            "lastUpdated": None,  # Để trống
            "totalReviews": None,  # Để trống
            "userReading": None,  # Để trống
            "userPlanToRead": None,  # Để trống
            "userCompleted": None,  # Để trống
            "userPaused": None,  # Để trống
            "userDropped": None,  # Để trống
        }
        
        # Lưu story và story_info ngay khi cào xong metadata
        self.mongo.save_story(story_data)
        self.mongo.save_story_info(story_info_data)
        
        return story_data, story_id, "new"  # Return match_type = "new" cho truyện mới
    
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
                                href = next_button.get_attribute("href") or None
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
        """Lấy danh sách chapters từ trang hiện tại, trả về list dict với url và published_time"""
        chapter_info_list = []
        
        try:
            chapter_rows = self.page.locator("table#chapters tbody tr").all()
            
            for row in chapter_rows:
                try:
                    link_el = row.locator("td").first.locator("a")
                    if link_el.count() > 0:
                        url = link_el.get_attribute("href")
                        if url:
                            if url.startswith("/"):
                                full_url = config.BASE_URL + url
                            elif url.startswith("http"):
                                full_url = url
                            else:
                                full_url = config.BASE_URL + "/" + url
                            
                            published_time = None
                            try:
                                time_elem = row.locator("time[datetime]").first
                                if time_elem.count() > 0:
                                    published_time = time_elem.get_attribute("datetime") or None
                            except:
                                pass
                            
                            if not any(ch["url"] == full_url for ch in chapter_info_list):
                                chapter_info_list.append({
                                    "url": full_url,
                                    "published_time": published_time
                                })
                except:
                    continue
            
            return chapter_info_list
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapters từ trang hiện tại: {e}")
            return []
    
    def get_total_chapters_from_html(self):
        """
        Lấy total chapters từ HTML (selector: .portlet-title .actions span.label.label-default.pull-right)
        Returns: total_chapters (str hoặc None)
        """
        try:
            chapters_label = self.page.locator(".portlet-title .actions span.label.label-default.pull-right").first
            if chapters_label.count() > 0:
                chapters_text = chapters_label.inner_text().strip()
                numbers = re.findall(r'\d+', chapters_text)
                if numbers:
                    return numbers[0]
            return None
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy total chapters từ HTML: {e}")
            return None
    
    def get_first_chapter_hash(self, first_chapter_url):
        """
        Lấy hash từ chapter 1 để check trùng truyện từ nền tảng khác
        Lấy 500 từ đầu tiên của chapter 1 để tạo hash
        Dùng self.page hiện có thay vì tạo browser mới để tránh conflict với asyncio
        Args:
            first_chapter_url: URL của chapter đầu tiên
        Returns:
            hash_string: Hash string của chapter 1 content (500 từ đầu), None nếu lỗi
        """
        from src.utils import create_content_hash, convert_html_to_formatted_text
        
        try:
            safe_print("      🔍 Đang lấy hash từ chapter 1 (500 từ đầu) để check trùng...")
            
            # Dùng self.page hiện có để vào chapter 1
            self.page.goto(first_chapter_url, timeout=config.TIMEOUT)
            self.page.wait_for_selector(".chapter-inner", timeout=10000)
            time.sleep(2)
            
            # Lấy content
            content_container = self.page.locator(".chapter-inner").first
            if content_container.count() > 0:
                html_content = content_container.inner_html()
                content = convert_html_to_formatted_text(html_content)
                # Lấy 500 từ đầu tiên để tạo hash
                hash_string = create_content_hash(content, max_words=500)
                safe_print(f"      ✅ Đã lấy hash từ 500 từ đầu của chapter 1")
                return hash_string
            else:
                safe_print(f"      ⚠️ Không tìm thấy content trong chapter 1")
                return None
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy hash từ chapter 1: {e}")
            return None

