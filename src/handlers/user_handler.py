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
            
            # Lấy thông tin từ sidebar bên trái (.wi-fic_profile_content.left)
            # Joined date, Followers, Following, Comments
            created_date = None
            followers = None
            following = None
            comments = None
            
            try:
                left_sidebar = self.page.locator(".wi-fic_profile_content.left").first
                if left_sidebar.count() > 0:
                    # Lấy các stat items
                    stat_items = left_sidebar.locator(".pro_stat_item").all()
                    for item in stat_items:
                        try:
                            text = item.inner_text().strip()
                            if "Joined:" in text:
                                # Parse: "Joined: Nov 30, 2025" → "Nov 30, 2025"
                                date_match = re.search(r'Joined:\s*(.+)', text)
                                if date_match:
                                    date_str = date_match.group(1).strip()
                                    # Convert từ "Nov 30, 2025" sang "30/11/2025"
                                    created_date = self._convert_date_format(date_str) if date_str else None
                            elif "Followers:" in text:
                                # Parse: "Followers: 0" → "0"
                                match = re.search(r'Followers:\s*(\d+)', text)
                                if match:
                                    followers = match.group(1)
                                else:
                                    followers = None
                            elif "Following:" in text:
                                # Parse: "Following: 0" → "0"
                                match = re.search(r'Following:\s*(\d+)', text)
                                if match:
                                    following = match.group(1)
                                else:
                                    following = None
                            elif "Comments:" in text:
                                # Parse: "Comments: 1" → "1"
                                match = re.search(r'Comments:\s*(\d+)', text)
                                if match:
                                    comments = match.group(1)
                                else:
                                    comments = None
                        except Exception as e:
                            continue
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy stats từ sidebar: {e}")
            
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
                overview_tab = self.page.locator('input[type="radio"][id="profile_tab_6"]').first
                if overview_tab.count() > 0:
                    overview_tab.click()
                    time.sleep(1)  # Đợi tab load
                    
                    # Lấy Personal Information từ table_pro_overview
                    personal_tables = self.page.locator(".table_pro_overview").all()
                    for table in personal_tables:
                        try:
                            rows = table.locator("tbody tr").all()
                            for row in rows:
                                try:
                                    th_text = row.locator("th").first.inner_text().strip()
                                    td_elem = row.locator("td").first
                                    
                                    if "Last Active:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        last_active = td_text if td_text and td_text != "--" else None
                                    elif "Birthday:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        birthday = td_text if td_text and td_text != "--" else None
                                    elif "Gender:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        gender = td_text if td_text and td_text != "--" else None
                                    elif "Location:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        location = td_text if td_text and td_text != "--" else None
                                    elif "Homepage:" in th_text:
                                        # Lấy href từ link trong td
                                        try:
                                            link_elem = td_elem.locator("a.externalLink").first
                                            if link_elem.count() > 0:
                                                homepage = link_elem.get_attribute("href") or None
                                            else:
                                                # Nếu không có link, lấy text
                                                td_text = td_elem.inner_text().strip()
                                                homepage = td_text if td_text and td_text != "--" else None
                                        except:
                                            td_text = td_elem.inner_text().strip()
                                            homepage = td_text if td_text and td_text != "--" else None
                                    elif "Series:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        # Parse số, loại bỏ dấu phẩy
                                        if td_text and td_text != "--":
                                            series = td_text.replace(",", "").strip()
                                            # Convert sang int nếu có thể
                                            try:
                                                series = int(series) if series.isdigit() else series
                                            except:
                                                pass
                                        else:
                                            series = None
                                    elif "Total Words:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        if td_text and td_text != "--":
                                            total_words = td_text.replace(",", "").strip()
                                            # Convert sang int nếu có thể
                                            try:
                                                total_words = int(total_words) if total_words.isdigit() else total_words
                                            except:
                                                pass
                                        else:
                                            total_words = None
                                    elif "Total Pageviews:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        if td_text and td_text != "--":
                                            total_pageviews = td_text.replace(",", "").strip()
                                            # Convert sang int nếu có thể
                                            try:
                                                total_pageviews = int(total_pageviews) if total_pageviews.isdigit() else total_pageviews
                                            except:
                                                pass
                                        else:
                                            total_pageviews = None
                                    elif "Reviews Received:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        if td_text and td_text != "--":
                                            reviews_received = td_text.replace(",", "").strip()
                                            # Convert sang int nếu có thể
                                            try:
                                                reviews_received = int(reviews_received) if reviews_received.isdigit() else reviews_received
                                            except:
                                                pass
                                        else:
                                            reviews_received = None
                                    elif "Readers:" in th_text:
                                        td_text = td_elem.inner_text().strip()
                                        if td_text and td_text != "--":
                                            readers = td_text.replace(",", "").strip()
                                            # Convert sang int nếu có thể
                                            try:
                                                readers = int(readers) if readers.isdigit() else readers
                                            except:
                                                pass
                                        else:
                                            readers = None
                                    elif "Followers:" in th_text:
                                        # Có thể có followers ở đây nữa (nếu chưa lấy được từ sidebar)
                                        if followers is None:
                                            td_text = td_elem.inner_text().strip()
                                            if td_text and td_text != "--":
                                                followers = td_text.replace(",", "").strip()
                                            else:
                                                followers = None
                                except:
                                    continue
                        except:
                            continue
                    
                    # Lấy bio từ .user_bio_profile
                    try:
                        bio_elem = self.page.locator(".user_bio_profile").first
                        if bio_elem.count() > 0:
                            html_content = bio_elem.inner_html()
                            bio_text = convert_html_to_formatted_text(html_content)
                            bio = bio_text if bio_text and bio_text.strip() else None
                    except:
                        pass
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy thông tin Overview: {e}")
            
            # Convert empty strings thành None trước khi lưu
            user_url_final = to_none_if_empty(profile_url) if profile_url else None
            created_date_final = to_none_if_empty(created_date) if created_date else None
            followers_final = to_none_if_empty(followers) if followers else None
            following_final = to_none_if_empty(following) if following else None
            comments_final = to_none_if_empty(comments) if comments else None
            
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
                bio=bio,
                favorites=None,  # Không có trong profile này
                ratings=None,  # Không có trong profile này
                series=series,  # Sẽ map thành numberOfStories
                total_words=total_words,
                reviews_received=reviews_received  # Sẽ map thành totalReviewsReceived và reviews
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

