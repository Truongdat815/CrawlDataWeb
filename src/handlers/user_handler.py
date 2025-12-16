"""
User handler - xử lý user profile scraping
"""
import time
import re
from datetime import datetime
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text


class UserHandler:
    """Handler cho user profile scraping"""
    
    def __init__(self, page, mongo_handler):
        """
        Args:
            page: Playwright page object
            mongo_handler: MongoHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
    
    def scrape_user_profile(self, profile_url):
        """
        Cào thông tin user profile từ URL profile của ScribbleHub
        Args:
            profile_url: URL profile (ví dụ: https://www.scribblehub.com/profile/237813/ngodat05/)
        Returns:
            user_id: ID của user đã lưu vào MongoDB
        """
        try:
            safe_print(f"      👤 Đang cào user profile: {profile_url}")
            
            # Goto profile URL
            self.page.goto(profile_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            time.sleep(2)
            
            # ✅ Đợi phần tử quan trọng xuất hiện (khắc phục lỗi NULL)
            safe_print(f"      ⏳ Đang đợi .sb_box.pro_stat xuất hiện...")
            try:
                self.page.wait_for_selector(".sb_box.pro_stat", timeout=30000)  # Đợi tối đa 30 giây
                safe_print(f"      ✅ Đã tìm thấy .sb_box.pro_stat, trang đã load xong")
            except Exception as e:
                safe_print(f"      ⚠️ Không tìm thấy .sb_box.pro_stat sau 30 giây: {e}")
                # Vẫn tiếp tục, có thể trang có cấu trúc khác
            
            # Lấy web_user_id từ URL (ví dụ: từ https://www.scribblehub.com/profile/237813/ngodat05/ lấy 237813)
            web_user_id = ""
            try:
                match = re.search(r'/profile/(\d+)/', profile_url)
                if match:
                    web_user_id = match.group(1)
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy web_user_id từ URL: {e}")
            
            if not web_user_id:
                safe_print(f"      ❌ Không tìm thấy web_user_id từ URL")
                return None
            
            # Lấy username từ .auth_name_fic
            username = ""
            try:
                username_elem = self.page.locator(".auth_name_fic").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy username: {e}")
            
            if not username:
                safe_print(f"      ❌ Không tìm thấy username")
                return None
            
            # Helper function để convert empty string thành None
            def to_none_if_empty(value):
                if value == "" or (isinstance(value, str) and not value.strip()):
                    return None
                return value
            
            # ✅ Lấy thông tin từ sidebar bên trái (.wi-fic_profile_content.left)
            # Joined date, Followers, Following, Comments từ .sb_box.pro_stat
            created_date = None
            followers = None
            following = None
            comments = None
            
            try:
                # Lấy từ .sb_box.pro_stat
                pro_stat_box = self.page.locator(".sb_box.pro_stat").first
                safe_print(f"      🔍 DEBUG: Đang tìm .sb_box.pro_stat...")
                if pro_stat_box.count() > 0:
                    safe_print(f"      ✅ Tìm thấy .sb_box.pro_stat")
                    
                    # ✅ createdDate: Tìm bằng :has-text("Joined:")
                    try:
                        joined_item = pro_stat_box.locator('.pro_stat_item:has-text("Joined:")').first
                        if joined_item.count() > 0:
                            pro_right = joined_item.locator("span.pro_right").first
                            if pro_right.count() > 0:
                                date_str = pro_right.inner_text().strip()
                                if date_str:
                                    created_date = self._convert_date_to_custom_format(date_str)
                                    safe_print(f"        ✅ Đã lấy createdDate: {date_str} → {created_date}")
                    except Exception as e:
                        safe_print(f"        ⚠️ Lỗi khi lấy createdDate: {e}")
                    
                    # ✅ followers: Tìm bằng :has-text("Followers:")
                    try:
                        followers_item = pro_stat_box.locator('.pro_stat_item:has-text("Followers:")').first
                        if followers_item.count() > 0:
                            pro_right = followers_item.locator("span.pro_right").first
                            if pro_right.count() > 0:
                                # Thử lấy từ .sw_follow trước
                                sw_follow = pro_right.locator("span.sw_follow").first
                                if sw_follow.count() > 0:
                                    followers_text = sw_follow.inner_text().strip()
                                else:
                                    followers_text = pro_right.inner_text().strip()
                                
                                if followers_text:
                                    match = re.search(r'(\d+)', followers_text)
                                    if match:
                                        followers = int(match.group(1))
                                        safe_print(f"        ✅ Đã lấy followers: {followers}")
                    except Exception as e:
                        safe_print(f"        ⚠️ Lỗi khi lấy followers: {e}")
                    
                    # ✅ following: Tìm bằng :has-text("Following:")
                    try:
                        following_item = pro_stat_box.locator('.pro_stat_item:has-text("Following:")').first
                        if following_item.count() > 0:
                            pro_right = following_item.locator("span.pro_right").first
                            if pro_right.count() > 0:
                                sw_follow = pro_right.locator("span.sw_follow").first
                                if sw_follow.count() > 0:
                                    following_text = sw_follow.inner_text().strip()
                                else:
                                    following_text = pro_right.inner_text().strip()
                                
                                if following_text:
                                    match = re.search(r'(\d+)', following_text)
                                    if match:
                                        following = int(match.group(1))
                                        safe_print(f"        ✅ Đã lấy following: {following}")
                    except Exception as e:
                        safe_print(f"        ⚠️ Lỗi khi lấy following: {e}")
                    
                    # ✅ comments: Tìm bằng :has-text("Comments:")
                    try:
                        comments_item = pro_stat_box.locator('.pro_stat_item:has-text("Comments:")').first
                        if comments_item.count() > 0:
                            pro_right = comments_item.locator("span.pro_right").first
                            if pro_right.count() > 0:
                                comments_text = pro_right.inner_text().strip()
                                if comments_text:
                                    match = re.search(r'(\d+)', comments_text)
                                    if match:
                                        comments = int(match.group(1))
                                        safe_print(f"        ✅ Đã lấy comments: {comments}")
                    except Exception as e:
                        safe_print(f"        ⚠️ Lỗi khi lấy comments: {e}")
                else:
                    safe_print(f"      ⚠️ Không tìm thấy .sb_box.pro_stat")
                
                # ✅ Lấy bio từ .sb_box.pro_stat có chứa <p> (selector ổn định)
                try:
                    # Tìm .sb_box.pro_stat có chứa thẻ <p> (đây là bio box)
                    bio_box = self.page.locator('.sb_box.pro_stat:has(p)').first
                    if bio_box.count() > 0:
                        html_content = bio_box.inner_html()
                        bio_text = convert_html_to_formatted_text(html_content)
                        bio = bio_text if bio_text and bio_text.strip() else None
                        if bio:
                            safe_print(f"      ✅ Đã lấy bio từ .sb_box.pro_stat:has(p): {bio[:50]}..." if len(bio) > 50 else f"      ✅ Đã lấy bio: {bio}")
                    else:
                        safe_print(f"      ⚠️ Không tìm thấy .sb_box.pro_stat:has(p)")
                        # Fallback: thử tìm .sb_box.pro_stat cuối cùng
                        try:
                            all_pro_stat = self.page.locator(".sb_box.pro_stat").all()
                            if len(all_pro_stat) >= 2:
                                bio_box = all_pro_stat[-1]  # Lấy cái cuối cùng
                                html_content = bio_box.inner_html()
                                bio_text = convert_html_to_formatted_text(html_content)
                                bio = bio_text if bio_text and bio_text.strip() else None
                                if bio:
                                    safe_print(f"      ✅ Đã lấy bio từ .sb_box.pro_stat cuối cùng (fallback)")
                        except:
                            pass
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy bio: {e}")
                    import traceback
                    safe_print(f"      {traceback.format_exc()}")
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy stats từ sidebar: {e}")
                import traceback
                safe_print(f"      {traceback.format_exc()}")
            
            # Lấy thông tin từ phần Overview (bên phải)
            # Cần click vào tab Overview trước
            gender = None
            location = None
            last_active = None
            birthday = None
            homepage = None
            bio = None
            series = None
            total_words = None
            total_pageviews = None
            reviews_received = None
            readers = None
            
            try:
                # Click vào tab Overview
                safe_print(f"      🔍 DEBUG: Đang tìm tab Overview...")
                overview_tab = self.page.locator('input[type="radio"][id="profile_tab_6"]').first
                if overview_tab.count() > 0:
                    safe_print(f"      ✅ Tìm thấy tab Overview, đang click...")
                    try:
                        overview_tab.click(timeout=5000)  # 5 giây thay vì 30 giây
                        time.sleep(2)  # Đợi tab load (tăng từ 1s lên 2s)
                        safe_print(f"      ✅ Đã click tab Overview")
                    except Exception as click_error:
                        safe_print(f"      ⚠️ Không thể click tab Overview: {click_error}")
                        # Thử fallback: click vào label
                        try:
                            overview_label = self.page.locator('label[for="profile_tab_6"]').first
                            if overview_label.count() > 0:
                                overview_label.click(timeout=5000)
                                time.sleep(2)
                                safe_print(f"      ✅ Đã click tab Overview (fallback label)")
                            else:
                                raise click_error
                        except:
                            safe_print(f"      ⚠️ Không thể click tab Overview bằng cả 2 cách, bỏ qua phần này")
                            # Không raise, chỉ bỏ qua phần này và tiếp tục
                else:
                    safe_print(f"      ⚠️ Không tìm thấy tab Overview (profile_tab_6)")
                    # Thử fallback
                    overview_tab_alt = self.page.locator('input[type="radio"][value="overview"], label:has-text("Overview")').first
                    if overview_tab_alt.count() > 0:
                        safe_print(f"      ✅ Tìm thấy tab Overview (fallback), đang click...")
                        try:
                            overview_tab_alt.click(timeout=5000)
                            time.sleep(2)
                        except Exception as e:
                            safe_print(f"      ⚠️ Không thể click tab Overview (fallback): {e}, bỏ qua phần này")
                            # Không raise, chỉ bỏ qua phần này và tiếp tục
                    
                    # ✅ Lấy Author Information từ table_pro_overview theo index của TR
                    # TR 1: numberOfStories (Series)
                    # TR 2: totalWords
                    # TR 3: Total Pageviews (bỏ qua)
                    # TR 4: totalReviewsReceived (Reviews Received)
                    # TR 5: Readers (bỏ qua)
                    # TR 6: Followers
                    safe_print(f"      🔍 DEBUG: Đang tìm .table_pro_overview...")
                    author_tables = self.page.locator(".table_pro_overview").all()
                    if len(author_tables) == 0:
                        safe_print(f"      ⚠️ Không tìm thấy .table_pro_overview, thử fallback...")
                        # Thử fallback selectors
                        fallback_tables = self.page.locator("table, .author_info, .profile_info").all()
                        author_tables = fallback_tables
                        safe_print(f"      🔍 DEBUG: Tìm thấy {len(author_tables)} fallback tables")
                    
                    for table in author_tables:
                        try:
                            rows = table.locator("tbody tr, tr").all()
                            safe_print(f"      📊 Tìm thấy {len(rows)} rows trong table")
                            
                            for idx, row in enumerate(rows):
                                try:
                                    # Lấy th text để xác định field
                                    th_elem = row.locator("th").first
                                    th_text = th_elem.inner_text().strip().lower() if th_elem.count() > 0 else ""
                                    td_elem = row.locator("td").first
                                    td_text = td_elem.inner_text().strip() if td_elem.count() > 0 else ""
                                    
                                    safe_print(f"        🔍 DEBUG: TR[{idx}] th='{th_text}', td='{td_text}'")
                                    
                                    # TR 1 (index 0): numberOfStories (Series) - tìm theo text "series" hoặc index 0
                                    if idx == 0 or "series" in th_text:
                                        if td_text and td_text != "--":
                                            series = td_text.replace(",", "").strip()
                                            try:
                                                series = int(series) if series.isdigit() else series
                                                safe_print(f"        ✅ TR 1: numberOfStories = {series}")
                                            except:
                                                pass
                                        else:
                                            series = None
                                    
                                    # TR 2 (index 1): totalWords - tìm theo text "words" hoặc index 1
                                    elif idx == 1 or "words" in th_text or "word" in th_text:
                                        if td_text and td_text != "--":
                                            total_words = td_text.replace(",", "").strip()
                                            try:
                                                total_words = int(total_words) if total_words.isdigit() else total_words
                                                safe_print(f"        ✅ TR 2: totalWords = {total_words}")
                                            except:
                                                pass
                                        else:
                                            total_words = None
                                    
                                    # TR 3 (index 2): Total Pageviews (bỏ qua)
                                    # TR 4 (index 3): totalReviewsReceived (Reviews Received) - tìm theo text "reviews received" hoặc index 3
                                    elif idx == 3 or "reviews received" in th_text or "review" in th_text:
                                        if td_text and td_text != "--":
                                            reviews_received = td_text.replace(",", "").strip()
                                            try:
                                                reviews_received = int(reviews_received) if reviews_received.isdigit() else reviews_received
                                                safe_print(f"        ✅ TR 4: totalReviewsReceived = {reviews_received}")
                                            except:
                                                pass
                                        else:
                                            reviews_received = None
                                    
                                    # TR 5 (index 4): Readers (bỏ qua)
                                    # TR 6 (index 5): Followers - tìm theo text "followers" hoặc index 5
                                    elif idx == 5 or ("followers" in th_text and idx > 3):
                                        if td_text and td_text != "--":
                                            followers_from_table = td_text.replace(",", "").strip()
                                            # Chỉ update nếu chưa có followers từ sidebar
                                            if followers is None:
                                                try:
                                                    followers = int(followers_from_table) if followers_from_table.isdigit() else followers_from_table
                                                    safe_print(f"        ✅ TR 6: followers = {followers}")
                                                except:
                                                    pass
                                        # Không cần else vì đã có từ sidebar
                                    
                                    # Các TR khác: Personal Information (Last Active, Birthday, Gender, Location, Homepage)
                                    else:
                                        th_text = row.locator("th").first.inner_text().strip() if row.locator("th").first.count() > 0 else ""
                                        
                                        if "Last Active:" in th_text:
                                            last_active = td_text if td_text and td_text != "--" else None
                                        elif "Birthday:" in th_text:
                                            birthday = td_text if td_text and td_text != "--" else None
                                        elif "Gender:" in th_text:
                                            gender = td_text if td_text and td_text != "--" else None
                                        elif "Location:" in th_text:
                                            location = td_text if td_text and td_text != "--" else None
                                        elif "Homepage:" in th_text:
                                            # Lấy href từ link trong td
                                            try:
                                                link_elem = td_elem.locator("a.externalLink").first
                                                if link_elem.count() > 0:
                                                    homepage = link_elem.get_attribute("href") or None
                                                else:
                                                    homepage = td_text if td_text and td_text != "--" else None
                                            except:
                                                homepage = td_text if td_text and td_text != "--" else None
                                except Exception as e:
                                    safe_print(f"        ⚠️ Lỗi khi parse TR[{idx}]: {e}")
                                    continue
                        except Exception as e:
                            safe_print(f"      ⚠️ Lỗi khi parse table: {e}")
                            continue
                    
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy thông tin Overview: {e}")
            
            # ✅ Tính totalFavoritesReceived và totalReviewsReceived từ tab Series
            # Cộng tất cả favorites và reviews từ các stories của user
            total_favorites_received = 0
            total_reviews_received = 0
            
            try:
                # Click vào tab Series
                safe_print(f"      🔍 DEBUG: Đang tìm tab Series...")
                series_tab = self.page.locator('input[type="radio"][id="profile_tab_2"]').first
                series_tab_clicked = False
                if series_tab.count() > 0:
                    safe_print(f"      ✅ Tìm thấy tab Series, đang click...")
                    try:
                        # Thử click với timeout ngắn hơn
                        series_tab.click(timeout=5000)  # 5 giây thay vì 30 giây
                        time.sleep(2)  # Đợi tab load và AJAX load stories
                        safe_print(f"      ✅ Đã click tab Series")
                        series_tab_clicked = True
                    except Exception as click_error:
                        safe_print(f"      ⚠️ Không thể click tab Series: {click_error}")
                        # Thử fallback: click vào label
                        try:
                            series_label = self.page.locator('label[for="profile_tab_2"]').first
                            if series_label.count() > 0:
                                series_label.click(timeout=5000)
                                time.sleep(2)
                                safe_print(f"      ✅ Đã click tab Series (fallback label)")
                                series_tab_clicked = True
                            else:
                                safe_print(f"      ⚠️ Không tìm thấy label cho tab Series, bỏ qua")
                        except Exception as e2:
                            safe_print(f"      ⚠️ Không thể click tab Series bằng cả 2 cách: {e2}")
                else:
                    safe_print(f"      ⚠️ Không tìm thấy tab Series (profile_tab_2), bỏ qua phần này")
                
                # Chỉ scrape stories nếu đã click được tab Series
                if series_tab_clicked:
                    # Lấy tất cả stories từ .p_load_series .search_main_box
                    story_boxes = self.page.locator(".p_load_series .search_main_box").all()
                    safe_print(f"      📚 Tìm thấy {len(story_boxes)} stories trong tab Series")
                    
                    for story_box in story_boxes:
                        try:
                            # Lấy favorites từ <span class="nl_stat destp"><i class="fa fa-heart pad"></i> 45 Favorites</span>
                            favorites_elem = story_box.locator('span.nl_stat:has(i.fa-heart)').first
                            if favorites_elem.count() > 0:
                                favorites_text = favorites_elem.inner_text().strip()
                                # Parse: "45 Favorites" → 45
                                match = re.search(r'([\d,]+)\s*Favorites?', favorites_text, re.IGNORECASE)
                                if match:
                                    favorites_num_str = match.group(1).replace(",", "").strip()
                                    try:
                                        favorites_num = int(favorites_num_str)
                                        total_favorites_received += favorites_num
                                        safe_print(f"        ✅ Đã lấy {favorites_num} favorites từ story")
                                    except:
                                        pass
                            
                            # Lấy reviews từ <span class="nl_stat destp"><i class="fa fa-pencil-square-o pad"></i> 0 Reviews</span>
                            reviews_elem = story_box.locator('span.nl_stat:has(i.fa-pencil-square-o)').first
                            if reviews_elem.count() > 0:
                                reviews_text = reviews_elem.inner_text().strip()
                                # Parse: "0 Reviews" → 0, "10 Reviews" → 10
                                match = re.search(r'([\d,]+)\s*Reviews?', reviews_text, re.IGNORECASE)
                                if match:
                                    reviews_num_str = match.group(1).replace(",", "").strip()
                                    try:
                                        reviews_num = int(reviews_num_str)
                                        total_reviews_received += reviews_num
                                        safe_print(f"        ✅ Đã lấy {reviews_num} reviews từ story")
                                    except:
                                        pass
                        except Exception as e:
                            safe_print(f"        ⚠️ Lỗi khi parse story stats: {e}")
                            continue
                    
                    # Kiểm tra xem có pagination không (nếu có nhiều trang stories)
                    try:
                        pagination = self.page.locator("#pagination-profile-series").first
                        if pagination.count() > 0:
                            # Lấy số trang từ pagination
                            page_items = pagination.locator("li").all()
                            max_page = 1
                            for item in page_items:
                                try:
                                    text = item.inner_text().strip()
                                    if text.isdigit():
                                        page_num = int(text)
                                        if page_num > max_page:
                                            max_page = page_num
                                except:
                                    pass
                            
                            # Nếu có nhiều trang, load từng trang và cộng thêm
                            if max_page > 1:
                                safe_print(f"      📄 Có {max_page} trang stories, đang load từng trang...")
                                for page_num in range(2, max_page + 1):
                                    try:
                                        # Click vào số trang
                                        page_link = pagination.locator(f"li:has-text('{page_num}')").first
                                        if page_link.count() > 0:
                                            try:
                                                page_link.click(timeout=5000)
                                                time.sleep(2)  # Đợi AJAX load
                                            except Exception as e:
                                                safe_print(f"      ⚠️ Không thể click pagination trang {page_num}: {e}")
                                                continue
                                            
                                            # Lấy stories từ trang này
                                            story_boxes_page = self.page.locator(".p_load_series .search_main_box").all()
                                            safe_print(f"      📚 Trang {page_num}: Tìm thấy {len(story_boxes_page)} stories")
                                            
                                            for story_box in story_boxes_page:
                                                try:
                                                    # Lấy favorites
                                                    favorites_elem = story_box.locator('span.nl_stat:has(i.fa-heart)').first
                                                    if favorites_elem.count() > 0:
                                                        favorites_text = favorites_elem.inner_text().strip()
                                                        match = re.search(r'([\d,]+)\s*Favorites?', favorites_text, re.IGNORECASE)
                                                        if match:
                                                            favorites_num_str = match.group(1).replace(",", "").strip()
                                                            try:
                                                                favorites_num = int(favorites_num_str)
                                                                total_favorites_received += favorites_num
                                                            except:
                                                                pass
                                                    
                                                    # Lấy reviews
                                                    reviews_elem = story_box.locator('span.nl_stat:has(i.fa-pencil-square-o)').first
                                                    if reviews_elem.count() > 0:
                                                        reviews_text = reviews_elem.inner_text().strip()
                                                        match = re.search(r'([\d,]+)\s*Reviews?', reviews_text, re.IGNORECASE)
                                                        if match:
                                                            reviews_num_str = match.group(1).replace(",", "").strip()
                                                            try:
                                                                reviews_num = int(reviews_num_str)
                                                                total_reviews_received += reviews_num
                                                            except:
                                                                pass
                                                except:
                                                    continue
                                    except Exception as e:
                                        safe_print(f"      ⚠️ Lỗi khi load trang {page_num}: {e}")
                                        continue
                    except:
                        pass  # Không có pagination hoặc lỗi
                    
                    safe_print(f"      ✅ Tổng totalFavoritesReceived: {total_favorites_received}")
                    safe_print(f"      ✅ Tổng totalReviewsReceived (từ Series tab): {total_reviews_received}")
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy stats từ tab Series: {e}")
                import traceback
                safe_print(f"      {traceback.format_exc()}")
            
            # Nếu đã có reviews_received từ Overview, ưu tiên dùng giá trị đó (có thể chính xác hơn)
            # Nếu không có, dùng giá trị từ Series tab
            if reviews_received is None and total_reviews_received > 0:
                reviews_received = total_reviews_received
            
            # ✅ Đếm số reviews mà user đã viết từ tab Reviews
            # Đây là field `reviews` (khác với `reviews_received` là số reviews nhận được)
            reviews_written = 0
            total_ratings_received = 0  # ✅ Tổng số sao được tô màu từ tất cả reviews
            try:
                # Click vào tab Reviews
                safe_print(f"      🔍 DEBUG: Đang tìm tab Reviews...")
                reviews_tab = self.page.locator('input[type="radio"][id="profile_tab_3"]').first
                if reviews_tab.count() > 0:
                    safe_print(f"      ✅ Tìm thấy tab Reviews, đang click...")
                    try:
                        reviews_tab.click(timeout=5000)  # 5 giây thay vì 30 giây
                        time.sleep(2)  # Đợi tab load và AJAX load reviews
                        safe_print(f"      ✅ Đã click tab Reviews")
                    except Exception as click_error:
                        safe_print(f"      ⚠️ Không thể click tab Reviews: {click_error}")
                        # Thử fallback: click vào label
                        try:
                            reviews_label = self.page.locator('label[for="profile_tab_3"]').first
                            if reviews_label.count() > 0:
                                reviews_label.click(timeout=5000)
                                time.sleep(2)
                                safe_print(f"      ✅ Đã click tab Reviews (fallback label)")
                            else:
                                raise click_error
                        except:
                            safe_print(f"      ⚠️ Không thể click tab Reviews bằng cả 2 cách, bỏ qua phần này")
                            # Không raise, chỉ bỏ qua phần này và tiếp tục
                else:
                    safe_print(f"      ⚠️ Không tìm thấy tab Reviews (profile_tab_3), bỏ qua phần này")
                    # Không raise, chỉ bỏ qua phần này và tiếp tục
                
                # Chỉ scrape reviews nếu đã click được tab Reviews
                reviews_tab_clicked = False
                if reviews_tab.count() > 0:
                    # Kiểm tra xem tab đã được click chưa bằng cách check xem có reviews không
                    try:
                        review_items_check = self.page.locator(".p_load_reviews .w-comments-item").all()
                        if len(review_items_check) > 0 or self.page.locator(".p_load_reviews").count() > 0:
                            reviews_tab_clicked = True
                    except:
                        pass
                
                if reviews_tab_clicked or reviews_tab.count() > 0:
                    # Đếm số reviews từ .p_load_reviews .w-comments-item
                    review_items = self.page.locator(".p_load_reviews .w-comments-item").all()
                    reviews_written = len(review_items)
                    safe_print(f"      📝 Trang 1: Tìm thấy {reviews_written} reviews")
                    
                    # Kiểm tra xem có pagination không
                    try:
                        pagination = self.page.locator("#pagination-profile-reviews").first
                        if pagination.count() > 0:
                            # Lấy số trang từ pagination
                            page_items = pagination.locator("li").all()
                            max_page = 1
                            for item in page_items:
                                try:
                                    text = item.inner_text().strip()
                                    if text.isdigit():
                                        page_num = int(text)
                                        if page_num > max_page:
                                            max_page = page_num
                                except:
                                    pass
                            
                            # Nếu có nhiều trang, load từng trang và đếm thêm
                            if max_page > 1:
                                safe_print(f"      📄 Có {max_page} trang reviews, đang load từng trang...")
                                for page_num in range(2, max_page + 1):
                                    try:
                                        # Click vào số trang
                                        page_link = pagination.locator(f"li:has-text('{page_num}')").first
                                        if page_link.count() > 0:
                                            try:
                                                page_link.click(timeout=5000)
                                                time.sleep(2)  # Đợi AJAX load
                                            except Exception as e:
                                                safe_print(f"      ⚠️ Không thể click pagination trang {page_num}: {e}")
                                                continue
                                            
                                            # Đếm reviews từ trang này
                                            review_items_page = self.page.locator(".p_load_reviews .w-comments-item").all()
                                            page_count = len(review_items_page)
                                            reviews_written += page_count
                                            safe_print(f"      📝 Trang {page_num}: Tìm thấy {page_count} reviews (Tổng: {reviews_written})")
                                    except Exception as e:
                                        safe_print(f"      ⚠️ Lỗi khi load trang {page_num}: {e}")
                                        continue
                    except:
                        pass  # Không có pagination hoặc lỗi
                    
                    safe_print(f"      ✅ Tổng số reviews đã viết: {reviews_written}")
                    
                    # ✅ Tính totalRatingsReceived bằng cách đếm số sao được tô màu từ tất cả reviews
                    total_ratings_received = 0
                    try:
                        # Lấy tất cả review items (đã có từ trên)
                        review_items_all = self.page.locator(".p_load_reviews .w-comments-item").all()
                        safe_print(f"      ⭐ Đang đếm sao từ {len(review_items_all)} reviews (trang 1)...")
                        
                        for review_item in review_items_all:
                            try:
                                # Đếm số sao được tô màu
                                # HTML: <span class="fic_pro_rate">...<i class="fa fa-star userreview" data-rating="1"></i>...</span>
                                # Stars được tô màu là những cái không có class "fa-star-o"
                                filled_stars = review_item.locator('span.fic_pro_rate i.fa-star:not(.fa-star-o)').all()
                                total_ratings_received += len(filled_stars)
                                if len(filled_stars) > 0:
                                    safe_print(f"        ✅ Đã đếm {len(filled_stars)} sao được tô màu từ review")
                            except Exception as e:
                                safe_print(f"        ⚠️ Lỗi khi đếm sao từ review: {e}")
                                continue
                        
                        # Xử lý pagination cho reviews (nếu có nhiều trang)
                        try:
                            pagination = self.page.locator("#pagination-profile-reviews").first
                            if pagination.count() > 0:
                                page_items = pagination.locator("li").all()
                                max_page = 1
                                for item in page_items:
                                    try:
                                        text = item.inner_text().strip()
                                        if text.isdigit():
                                            page_num = int(text)
                                            if page_num > max_page:
                                                max_page = page_num
                                    except:
                                        pass
                                
                                if max_page > 1:
                                    safe_print(f"      📄 Có {max_page} trang reviews, đang đếm sao từng trang...")
                                    for page_num in range(2, max_page + 1):
                                        try:
                                            page_link = pagination.locator(f"li:has-text('{page_num}')").first
                                            if page_link.count() > 0:
                                                try:
                                                    page_link.click(timeout=5000)
                                                    time.sleep(2)  # Đợi AJAX load
                                                except Exception as e:
                                                    safe_print(f"      ⚠️ Không thể click pagination trang {page_num}: {e}")
                                                    continue
                                                review_items_page = self.page.locator(".p_load_reviews .w-comments-item").all()
                                                safe_print(f"      ⭐ Trang {page_num}: Tìm thấy {len(review_items_page)} reviews")
                                                for review_item in review_items_page:
                                                    try:
                                                        filled_stars = review_item.locator('span.fic_pro_rate i.fa-star:not(.fa-star-o)').all()
                                                        total_ratings_received += len(filled_stars)
                                                    except:
                                                        continue
                                        except Exception as e:
                                            safe_print(f"      ⚠️ Lỗi khi load trang reviews {page_num}: {e}")
                                            continue
                        except Exception as e:
                            safe_print(f"      ⚠️ Lỗi khi xử lý pagination cho ratings: {e}")
                            pass
                        
                        safe_print(f"      ✅ Tổng totalRatingsReceived (từ Reviews tab): {total_ratings_received}")
                    except Exception as e:
                        safe_print(f"      ⚠️ Lỗi khi tính totalRatingsReceived từ tab Reviews: {e}")
                        import traceback
                        safe_print(f"      {traceback.format_exc()}")
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi đếm reviews từ tab Reviews: {e}")
                import traceback
                safe_print(f"      {traceback.format_exc()}")
                total_ratings_received = 0
            
            # ✅ Lấy userUrl từ HTML (ưu tiên selector ổn định)
            user_url_final = None
            safe_print(f"      🔍 DEBUG: Đang tìm userUrl...")
            try:
                # ✅ Ưu tiên: Lấy từ .sb_content.author a (selector ổn định nhất)
                author_link = self.page.locator('.sb_content.author a').first
                if author_link.count() > 0:
                    user_url_final = author_link.get_attribute("href")
                    if user_url_final:
                        safe_print(f"      ✅ Đã lấy userUrl từ .sb_content.author a: {user_url_final}")
                
                # Fallback: dùng profile_url parameter nếu không tìm thấy
                if not user_url_final:
                    user_url_final = profile_url
                    safe_print(f"      ✅ Đã lấy userUrl từ parameter: {user_url_final}")
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy userUrl: {e}")
                user_url_final = profile_url
            
            # Convert empty strings thành None trước khi lưu
            user_url_final = to_none_if_empty(user_url_final) if user_url_final else None
            created_date_final = to_none_if_empty(created_date) if created_date else None
            # followers, following, comments đã là int hoặc None từ code scrape, giữ nguyên
            followers_final = followers  # Có thể là int hoặc None
            following_final = following  # Có thể là int hoặc None
            comments_final = comments  # Có thể là int hoặc None
            # bio có thể là string hoặc None
            bio_final = to_none_if_empty(bio) if bio else None
            
            # Debug: In tất cả giá trị trước khi lưu
            safe_print(f"      📋 DEBUG: Giá trị trước khi lưu vào MongoDB:")
            safe_print(f"         - userUrl: {user_url_final}")
            safe_print(f"         - createdDate: {created_date_final}")
            safe_print(f"         - followers: {followers_final} (type: {type(followers_final).__name__})")
            safe_print(f"         - following: {following_final} (type: {type(following_final).__name__})")
            safe_print(f"         - comments: {comments_final} (type: {type(comments_final).__name__})")
            safe_print(f"         - gender: {gender}")
            safe_print(f"         - location: {location}")
            safe_print(f"         - bio: {bio_final[:50] + '...' if bio_final and len(bio_final) > 50 else bio_final} (type: {type(bio_final).__name__})")
            safe_print(f"         - numberOfStories: {series}")
            safe_print(f"         - totalWords: {total_words}")
            safe_print(f"         - totalReviewsReceived: {reviews_received}")
            safe_print(f"         - totalRatingsReceived: {total_ratings_received}")
            safe_print(f"         - totalFavoritesReceived: {total_favorites_received}")
            safe_print(f"         - reviews (written): {reviews_written}")
            
            # Lưu user vào MongoDB (chỉ các field được yêu cầu)
            user_id = self.mongo.save_user(
                web_user_id=web_user_id,
                username=username,
                user_url=user_url_final,
                created_date=created_date_final,
                gender=gender,
                location=location,
                followers=followers_final,
                following=following_final,
                comments=comments_final,
                bio=bio_final,
                favorites=total_favorites_received if total_favorites_received > 0 else None,  # ✅ Tổng favorites từ tất cả stories
                ratings=total_ratings_received if total_ratings_received > 0 else None,  # ✅ Tổng ratings từ tất cả reviews (số sao được tô màu)
                reviews=reviews_written if reviews_written > 0 else None,  # ✅ Số reviews user đã viết (từ tab Reviews)
                series=series,  # Sẽ map thành numberOfStories
                total_words=total_words,
                reviews_received=reviews_received  # Sẽ map thành totalReviewsReceived (số reviews nhận được trên stories)
            )
            
            if user_id:
                safe_print(f"      ✅ Đã lưu user profile: {username} (web_user_id: {web_user_id})")
                safe_print(f"         - Joined: {created_date}")
                safe_print(f"         - Followers: {followers}, Following: {following}, Comments: {comments}")
                if bio:
                    safe_print(f"         - Bio: {bio[:50]}..." if len(bio) > 50 else f"         - Bio: {bio}")
            
            return user_id
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi scrape user profile: {e}")
            return None
    
    def _convert_date_format(self, date_str):
        """
        Convert date từ "Nov 30, 2025" sang "30/11/2025"
        Args:
            date_str: Date string (ví dụ: "Nov 30, 2025")
        Returns:
            Formatted date string (ví dụ: "30/11/2025")
        """
        try:
            # Parse date string
            # Format: "Nov 30, 2025" hoặc "November 30, 2025"
            date_str = date_str.strip()
            
            # Thử parse với format "Nov 30, 2025"
            try:
                dt = datetime.strptime(date_str, "%b %d, %Y")
            except:
                # Thử format "November 30, 2025"
                try:
                    dt = datetime.strptime(date_str, "%B %d, %Y")
                except:
                    # Nếu không parse được, trả về nguyên bản
                    return date_str
            
            # Format lại thành "DD/MM/YYYY"
            return dt.strftime("%d/%m/%Y")
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi convert date format: {e}")
            return date_str  # Trả về nguyên bản nếu lỗi
    
    def _convert_date_to_custom_format(self, date_str):
        """
        Convert date từ "Mar 8, 2020" sang "8/3/2020, 12:00 AM"
        Args:
            date_str: Date string (ví dụ: "Mar 8, 2020")
        Returns:
            Formatted date string (ví dụ: "8/3/2020, 12:00 AM") - không có leading zero cho day và month
        """
        try:
            date_str = date_str.strip()
            
            # Thử parse với format "Mar 8, 2020" (không có leading zero)
            try:
                dt = datetime.strptime(date_str, "%b %d, %Y")
            except:
                # Thử format "March 8, 2020" (full month name)
                try:
                    dt = datetime.strptime(date_str, "%B %d, %Y")
                except:
                    safe_print(f"      ⚠️ Không thể parse date: {date_str}")
                    return None
            
            # Format lại thành "d/M/yyyy, h:mm AM/PM" (không có leading zero cho day và month)
            # Ví dụ: "8/3/2020, 12:00 AM"
            day = dt.day  # Không có leading zero
            month = dt.month  # Không có leading zero
            year = dt.year
            # Set time là 12:00 AM (midnight)
            formatted = f"{day}/{month}/{year}, 12:00 AM"
            return formatted
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi convert date to custom format: {e}")
            return None

