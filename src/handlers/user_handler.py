"""
User handler - xử lý user scraping và lưu trữ
"""
import time
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print, generate_id


class UserHandler:
    """Handler cho user scraping và lưu trữ"""
    
    def __init__(self, mongo_handler):
        """
        Args:
            mongo_handler: MongoHandler instance
        """
        self.mongo = mongo_handler
    
    def create_user_data(self, user_id, web_user_id, username, user_url=""):
        """
        Tạo user_data dict với tất cả các fields theo schema
        Args:
            user_id: ID được gen (rr_{uuid})
            web_user_id: User ID lấy từ web (URL)
            username: Tên người dùng
            user_url: URL của user profile (optional)
        Returns:
            dict: user_data với tất cả các fields
        """
        # Tạo full URL nếu chỉ có relative path
        if user_url and not user_url.startswith("http"):
            if user_url.startswith("/"):
                user_url = config.BASE_URL + user_url
            else:
                user_url = config.BASE_URL + "/" + user_url
        
        user_data = {
            "user_id": user_id,  # Schema: user_id (khóa chính, format rr_{uuid})
            "web_user_id": web_user_id,  # Schema: web_user_id (lấy từ URL)
            "username": username,  # Schema: username
            "user_url": user_url if user_url else "",  # Schema: user_url
            "created_date": "",  # Để trống
            "gender": "",  # Để trống
            "location": "",  # Để trống
            "followers": "",  # Để trống
            "following": "",  # Để trống
            "comments": "",  # Để trống
            "bio": "",  # Để trống
            "favorites": "",  # Để trống
            "ratings": "",  # Để trống
            "reviews": "",  # Để trống
            "number_of_stories": "",  # Để trống
            "total_words": "",  # Để trống
            "total_reviews_received": "",  # Để trống
            "total_ratings_received": "",  # Để trống
            "total_favorites_received": "",  # Để trống
        }
        return user_data
    
    def scrape_user_from_element(self, element, selectors=None):
        """
        Lấy user từ một element với các selector
        Args:
            element: Playwright locator element
            selectors: List các selector để tìm user link (optional)
        Returns:
            tuple: (web_user_id, username, user_url) hoặc (None, None, None) nếu không tìm thấy
        """
        if selectors is None:
            # Selector mặc định cho comment
            selectors = [
                "h4.media-heading span.name a[href*='/profile/']",
                "h4.media-heading .name a[href*='/profile/']",
                "h4.media-heading span.name a",
                "h4.media-heading .name a",
                ".media-heading span.name a[href*='/profile/']",
                ".media-heading .name a[href*='/profile/']",
                "h4.media-heading a[href*='/profile/']",
                ".media-heading a[href*='/profile/']",
                "span.name a[href*='/profile/']",
                ".name a[href*='/profile/']"
            ]
        
        web_user_id = ""
        username = ""
        user_url = ""
        
        try:
            for selector in selectors:
                try:
                    username_elem = element.locator(selector).first
                    if username_elem.count() > 0:
                        username = username_elem.inner_text().strip()
                        href = username_elem.get_attribute("href") or ""
                        if "/profile/" in href:
                            web_user_id = href.split("/profile/")[1].split("/")[0] if "/profile/" in href else ""
                            # Tạo full URL từ href
                            if href.startswith("/"):
                                user_url = config.BASE_URL + href
                            elif href.startswith("http"):
                                user_url = href
                            else:
                                user_url = config.BASE_URL + "/" + href
                        if username:
                            break
                except:
                    continue
            
            # Fallback: Thử selector đơn giản hơn
            if not username:
                try:
                    username_elem = element.locator("a[href*='/profile/']").first
                    if username_elem.count() > 0:
                        username = username_elem.inner_text().strip()
                        href = username_elem.get_attribute("href") or ""
                        if "/profile/" in href:
                            web_user_id = href.split("/profile/")[1].split("/")[0] if "/profile/" in href else ""
                            # Tạo full URL từ href
                            if href.startswith("/"):
                                user_url = config.BASE_URL + href
                            elif href.startswith("http"):
                                user_url = href
                            else:
                                user_url = config.BASE_URL + "/" + href
                except:
                    pass
            
            if not username:
                username = "[Unknown]"
            
            if web_user_id and username:
                return (web_user_id, username, user_url)
            else:
                return (None, None, None)
                
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy user từ element: {e}")
            return (None, None, None)
    
    def scrape_user_from_href(self, href, username=""):
        """
        Lấy user từ href và username
        Args:
            href: URL của user profile (có thể là relative hoặc absolute)
            username: Tên người dùng (optional, có thể lấy từ element)
        Returns:
            tuple: (web_user_id, username, user_url) hoặc (None, None, None) nếu không hợp lệ
        """
        if not href:
            return (None, None, None)
        
        web_user_id = ""
        user_url = ""
        
        try:
            if "/profile/" in href:
                web_user_id = href.split("/profile/")[1].split("/")[0] if "/profile/" in href else ""
                # Tạo full URL từ href
                if href.startswith("/"):
                    user_url = config.BASE_URL + href
                elif href.startswith("http"):
                    user_url = href
                else:
                    user_url = config.BASE_URL + "/" + href
            
            if web_user_id:
                if not username:
                    username = "[Unknown]"
                return (web_user_id, username, user_url)
            else:
                return (None, None, None)
                
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy user từ href: {e}")
            return (None, None, None)
    
    def save_user(self, web_user_id, username, user_url="", page=None):
        """
        Lưu user vào MongoDB và tự động scrape profile nếu có page và user_url
        Args:
            web_user_id: User ID lấy từ web (URL)
            username: Tên người dùng
            user_url: URL của user profile (optional)
            page: Playwright page object (optional, để scrape profile)
        Returns:
            user_id: ID được gen (rr_{uuid}) để dùng làm FK, hoặc None nếu lỗi
        """
        if not web_user_id or not username or not self.mongo.mongo_collection_users:
            return None
        
        try:
            # Tạo full URL nếu chỉ có relative path
            if user_url and not user_url.startswith("http"):
                if user_url.startswith("/"):
                    user_url = config.BASE_URL + user_url
                else:
                    user_url = config.BASE_URL + "/" + user_url
            
            # Tìm user theo web_user_id
            existing = self.mongo.mongo_collection_users.find_one({"web_user_id": web_user_id})
            
            if existing:
                # Update các fields nếu có thay đổi
                update_data = {}
                if existing.get("username") != username:
                    update_data["username"] = username
                if user_url and existing.get("user_url") != user_url:
                    update_data["user_url"] = user_url
                
                if update_data:
                    self.mongo.mongo_collection_users.update_one(
                        {"web_user_id": web_user_id},
                        {"$set": update_data}
                    )
                
                user_id = existing.get("user_id")
                
                # Kiểm tra xem user đã có đầy đủ thông tin chưa (có created_date hoặc followers)
                # Nếu chưa có thì mới scrape profile
                has_full_info = existing.get("created_date") or existing.get("followers")
                
                # Nếu có page và user_url và chưa có đầy đủ thông tin, scrape profile
                if page and user_url and not has_full_info:
                    try:
                        self.scrape_user_profile(page, user_url)
                    except Exception as e:
                        safe_print(f"        ⚠️ Không thể scrape profile cho user {web_user_id}: {e}")
                
                return user_id  # Trả về user_id đã có
            else:
                # Tạo id mới và user_data
                user_id = generate_id()
                user_data = self.create_user_data(user_id, web_user_id, username, user_url)
                self.mongo.mongo_collection_users.insert_one(user_data)
                
                # Nếu có page và user_url, scrape profile để lấy thông tin chi tiết
                if page and user_url:
                    try:
                        self.scrape_user_profile(page, user_url)
                    except Exception as e:
                        safe_print(f"        ⚠️ Không thể scrape profile cho user {web_user_id}: {e}")
                
                return user_id  # Trả về id mới để dùng làm FK
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lưu user vào MongoDB: {e}")
            return None
    
    def scrape_and_save_user_from_element(self, element, selectors=None, page=None):
        """
        Lấy user từ element và lưu vào MongoDB trong một bước
        Args:
            element: Playwright locator element
            selectors: List các selector để tìm user link (optional)
            page: Playwright page object (optional, để scrape profile)
        Returns:
            user_id: ID được gen (rr_{uuid}) để dùng làm FK, hoặc None nếu không tìm thấy
        """
        web_user_id, username, user_url = self.scrape_user_from_element(element, selectors)
        if web_user_id and username:
            return self.save_user(web_user_id, username, user_url, page)
        return None
    
    def scrape_and_save_user_from_href(self, href, username="", page=None):
        """
        Lấy user từ href và lưu vào MongoDB trong một bước
        Args:
            href: URL của user profile (có thể là relative hoặc absolute)
            username: Tên người dùng (optional)
            page: Playwright page object (optional, để scrape profile)
        Returns:
            user_id: ID được gen (rr_{uuid}) để dùng làm FK, hoặc None nếu không hợp lệ
        """
        web_user_id, username, user_url = self.scrape_user_from_href(href, username)
        if web_user_id and username:
            return self.save_user(web_user_id, username, user_url, page)
        return None
    
    def scrape_user_profile(self, page, user_url):
        """
        Scrape thông tin chi tiết từ user profile page và cập nhật vào MongoDB
        Args:
            page: Playwright page object
            user_url: URL của user profile
        Returns:
            user_id: ID của user đã được cập nhật, hoặc None nếu lỗi
        """
        if not page or not user_url:
            return None
        
        try:
            # Lấy web_user_id từ URL
            if "/profile/" in user_url:
                web_user_id = user_url.split("/profile/")[1].split("/")[0] if "/profile/" in user_url else ""
            else:
                return None
            
            if not web_user_id:
                return None
            
            # Tìm user hiện có trong DB
            existing_user = self.mongo.mongo_collection_users.find_one({"web_user_id": web_user_id})
            if not existing_user:
                safe_print(f"        ⚠️ User {web_user_id} chưa có trong DB, cần tạo trước")
                return None
            
            # Kiểm tra xem user đã có đầy đủ thông tin chưa
            has_full_info = existing_user.get("created_date") or existing_user.get("followers")
            if has_full_info:
                safe_print(f"        ⏭️  User {web_user_id} đã có đầy đủ thông tin, bỏ qua scrape profile")
                return existing_user.get("user_id")
            
            user_id = existing_user.get("user_id")
            
            # Lưu URL hiện tại để quay lại sau
            current_url = page.url
            
            # Navigate to profile page - đảm bảo chạy trong cùng thread context
            try:
                # Navigate trong cùng worker thread - mỗi worker thread có playwright instance riêng
                # Page object thuộc về thread đó, nên page.goto() nên hoạt động được
                page.goto(user_url, timeout=60000)
                import time
                time.sleep(2)
            except Exception as e:
                error_msg = str(e)
                # Kiểm tra nếu là lỗi thread switching
                if "Cannot switch to a different thread" in error_msg or "greenlet" in error_msg.lower():
                    # Nếu vẫn lỗi, có thể do cách Playwright xử lý với ThreadPoolExecutor
                    # Bỏ qua scrape profile trong trường hợp này
                    safe_print(f"        ⚠️ Không thể navigate trong thread này (thread context issue), sẽ bỏ qua scrape profile")
                    return user_id
                else:
                    # Nếu là lỗi khác (network, timeout, etc.), raise lại để xử lý ở ngoài
                    raise
            
            # Scope vào các tables cụ thể
            personal_info_table = page.locator("div.portlet:has-text('Personal Information') table").first
            activity_table = page.locator("div.portlet:has-text('Activity') table").first
            author_info_table = page.locator("div.portlet:has-text('Author Information') table").first
            
            # ========== Personal Information ==========
            # Lấy created_date từ Personal Information table
            created_date = ""
            try:
                if personal_info_table.count() > 0:
                    joined_time = personal_info_table.locator("tbody tr:has-text('Joined:') time[datetime]").first
                    if joined_time.count() > 0:
                        created_date = joined_time.get_attribute("datetime") or ""
            except:
                pass
            
            # Lấy gender từ Personal Information table
            gender = ""
            try:
                if personal_info_table.count() > 0:
                    gender_row = personal_info_table.locator("tbody tr:has-text('Gender:')").first
                    if gender_row.count() > 0:
                        gender_td = gender_row.locator("td").last
                        if gender_td.count() > 0:
                            gender = gender_td.inner_text().strip()
            except:
                pass
            
            # Lấy location từ Personal Information table
            location = ""
            try:
                if personal_info_table.count() > 0:
                    location_row = personal_info_table.locator("tbody tr:has-text('Location:')").first
                    if location_row.count() > 0:
                        location_td = location_row.locator("td").last
                        if location_td.count() > 0:
                            location = location_td.inner_text().strip()
            except:
                pass
            
            # Lấy bio từ Personal Information table
            bio = ""
            try:
                if personal_info_table.count() > 0:
                    bio_row = personal_info_table.locator("tbody tr:has-text('Bio:')").first
                    if bio_row.count() > 0:
                        bio_td = bio_row.locator("td.bio").first
                        if bio_td.count() > 0:
                            bio = bio_td.inner_text().strip()
            except:
                pass
            
            # ========== Activity ==========
            # Lấy following từ Activity table (Follows)
            following = ""
            try:
                if activity_table.count() > 0:
                    follows_row = activity_table.locator("tbody tr:has-text('Follows')").first
                    if follows_row.count() > 0:
                        follows_td = follows_row.locator("td").last
                        if follows_td.count() > 0:
                            following = follows_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy comments từ Activity table
            comments = ""
            try:
                if activity_table.count() > 0:
                    comments_row = activity_table.locator("tbody tr:has-text('Comments')").first
                    if comments_row.count() > 0:
                        comments_td = comments_row.locator("td").last
                        if comments_td.count() > 0:
                            comments = comments_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy ratings từ Activity table
            ratings = ""
            try:
                if activity_table.count() > 0:
                    ratings_row = activity_table.locator("tbody tr:has-text('Ratings')").first
                    if ratings_row.count() > 0:
                        ratings_td = ratings_row.locator("td").last
                        if ratings_td.count() > 0:
                            ratings = ratings_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy reviews từ Activity table
            reviews = ""
            try:
                if activity_table.count() > 0:
                    reviews_row = activity_table.locator("tbody tr:has-text('Reviews')").first
                    if reviews_row.count() > 0:
                        reviews_td = reviews_row.locator("td").last
                        if reviews_td.count() > 0:
                            reviews = reviews_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # ========== Author Information ==========
            # Lấy number_of_stories từ Author Information table (Fictions)
            number_of_stories = ""
            try:
                if author_info_table.count() > 0:
                    fictions_row = author_info_table.locator("tbody tr:has-text('Fictions:')").first
                    if fictions_row.count() > 0:
                        fictions_td = fictions_row.locator("td").last
                        if fictions_td.count() > 0:
                            number_of_stories = fictions_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_words từ Author Information table
            total_words = ""
            try:
                if author_info_table.count() > 0:
                    total_words_row = author_info_table.locator("tbody tr:has-text('Total Words:')").first
                    if total_words_row.count() > 0:
                        total_words_td = total_words_row.locator("td").last
                        if total_words_td.count() > 0:
                            total_words = total_words_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_reviews_received từ Author Information table
            total_reviews_received = ""
            try:
                if author_info_table.count() > 0:
                    total_reviews_row = author_info_table.locator("tbody tr:has-text('Total Reviews Received:')").first
                    if total_reviews_row.count() > 0:
                        total_reviews_td = total_reviews_row.locator("td").last
                        if total_reviews_td.count() > 0:
                            total_reviews_received = total_reviews_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_ratings_received từ Author Information table
            total_ratings_received = ""
            try:
                if author_info_table.count() > 0:
                    total_ratings_row = author_info_table.locator("tbody tr:has-text('Total Ratings Received:')").first
                    if total_ratings_row.count() > 0:
                        total_ratings_td = total_ratings_row.locator("td").last
                        if total_ratings_td.count() > 0:
                            total_ratings_received = total_ratings_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy followers từ Author Information table
            followers = ""
            try:
                if author_info_table.count() > 0:
                    followers_row = author_info_table.locator("tbody tr:has-text('Followers:')").first
                    if followers_row.count() > 0:
                        followers_td = followers_row.locator("td").last
                        if followers_td.count() > 0:
                            followers = followers_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy favorites từ Author Information table
            favorites = ""
            try:
                if author_info_table.count() > 0:
                    favorites_row = author_info_table.locator("tbody tr:has-text('Favorites:')").first
                    if favorites_row.count() > 0:
                        favorites_td = favorites_row.locator("td").last
                        if favorites_td.count() > 0:
                            favorites = favorites_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_favorites_received (cùng với favorites từ Author Information)
            total_favorites_received = favorites
            
            # Cập nhật user_data với các fields mới
            update_data = {}
            if created_date:
                update_data["created_date"] = created_date
            if gender:
                update_data["gender"] = gender
            if location is not None:  # Có thể là empty string
                update_data["location"] = location
            if bio is not None:  # Có thể là empty string
                update_data["bio"] = bio
            if followers:
                update_data["followers"] = followers
            if following:
                update_data["following"] = following
            if comments:
                update_data["comments"] = comments
            if favorites:
                update_data["favorites"] = favorites
            if ratings:
                update_data["ratings"] = ratings
            if reviews:
                update_data["reviews"] = reviews
            if number_of_stories:
                update_data["number_of_stories"] = number_of_stories
            if total_words:
                update_data["total_words"] = total_words
            if total_reviews_received:
                update_data["total_reviews_received"] = total_reviews_received
            if total_ratings_received:
                update_data["total_ratings_received"] = total_ratings_received
            if total_favorites_received:
                update_data["total_favorites_received"] = total_favorites_received
            
            # Cập nhật vào MongoDB
            if update_data:
                self.mongo.mongo_collection_users.update_one(
                    {"web_user_id": web_user_id},
                    {"$set": update_data}
                )
                safe_print(f"        ✅ Đã cập nhật profile cho user {web_user_id}")
            
            # Quay lại trang trước (URL của truyện)
            if current_url:
                try:
                    page.goto(current_url, timeout=60000)
                    time.sleep(1)  # Đợi một chút để trang load
                except Exception as e:
                    safe_print(f"        ⚠️ Không thể quay lại trang trước: {e}")
            
            return user_id
            
        except Exception as e:
            error_msg = str(e)
            # Kiểm tra nếu là lỗi thread switching
            if "Cannot switch to a different thread" in error_msg or "greenlet" in error_msg.lower():
                safe_print(f"        ⚠️ Không thể scrape profile trong thread này (thread context issue), sẽ bỏ qua")
            else:
                safe_print(f"        ⚠️ Lỗi khi scrape user profile: {e}")
            
            # Vẫn cố gắng quay lại trang trước nếu có lỗi và có current_url
            try:
                if 'current_url' in locals() and current_url:
                    page.goto(current_url, timeout=60000)
            except:
                pass
            return user_id if 'user_id' in locals() else None
    
    def scrape_user_profile_data(self, page, user_url, web_user_id):
        """
        Scrape thông tin chi tiết từ user profile page (page đã được navigate sẵn)
        Method này được gọi sau khi page đã navigate đến profile URL trong cùng thread
        Args:
            page: Playwright page object (đã ở profile page)
            user_url: URL của user profile
            web_user_id: Web user ID
        Returns:
            user_id: ID của user đã được cập nhật, hoặc None nếu lỗi
        """
        if not page or not user_url or not web_user_id:
            return None
        
        try:
            # Tìm user hiện có trong DB
            existing_user = self.mongo.mongo_collection_users.find_one({"web_user_id": web_user_id})
            if not existing_user:
                return None
            
            user_id = existing_user.get("user_id")
            
            # Scope vào các tables cụ thể
            personal_info_table = page.locator("div.portlet:has-text('Personal Information') table").first
            activity_table = page.locator("div.portlet:has-text('Activity') table").first
            author_info_table = page.locator("div.portlet:has-text('Author Information') table").first
            
            # ========== Personal Information ==========
            # Lấy created_date từ Personal Information table
            created_date = ""
            try:
                if personal_info_table.count() > 0:
                    joined_time = personal_info_table.locator("tbody tr:has-text('Joined:') time[datetime]").first
                    if joined_time.count() > 0:
                        created_date = joined_time.get_attribute("datetime") or ""
            except:
                pass
            
            # Lấy gender từ Personal Information table
            gender = ""
            try:
                if personal_info_table.count() > 0:
                    gender_row = personal_info_table.locator("tbody tr:has-text('Gender:')").first
                    if gender_row.count() > 0:
                        gender_td = gender_row.locator("td").last
                        if gender_td.count() > 0:
                            gender = gender_td.inner_text().strip()
            except:
                pass
            
            # Lấy location từ Personal Information table
            location = ""
            try:
                if personal_info_table.count() > 0:
                    location_row = personal_info_table.locator("tbody tr:has-text('Location:')").first
                    if location_row.count() > 0:
                        location_td = location_row.locator("td").last
                        if location_td.count() > 0:
                            location = location_td.inner_text().strip()
            except:
                pass
            
            # Lấy bio từ Personal Information table
            bio = ""
            try:
                if personal_info_table.count() > 0:
                    bio_row = personal_info_table.locator("tbody tr:has-text('Bio:')").first
                    if bio_row.count() > 0:
                        bio_td = bio_row.locator("td.bio").first
                        if bio_td.count() > 0:
                            bio = bio_td.inner_text().strip()
            except:
                pass
            
            # ========== Activity ==========
            # Lấy following từ Activity table (Follows)
            following = ""
            try:
                if activity_table.count() > 0:
                    follows_row = activity_table.locator("tbody tr:has-text('Follows')").first
                    if follows_row.count() > 0:
                        follows_td = follows_row.locator("td").last
                        if follows_td.count() > 0:
                            following = follows_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy comments từ Activity table
            comments = ""
            try:
                if activity_table.count() > 0:
                    comments_row = activity_table.locator("tbody tr:has-text('Comments')").first
                    if comments_row.count() > 0:
                        comments_td = comments_row.locator("td").last
                        if comments_td.count() > 0:
                            comments = comments_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy ratings từ Activity table
            ratings = ""
            try:
                if activity_table.count() > 0:
                    ratings_row = activity_table.locator("tbody tr:has-text('Ratings')").first
                    if ratings_row.count() > 0:
                        ratings_td = ratings_row.locator("td").last
                        if ratings_td.count() > 0:
                            ratings = ratings_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy reviews từ Activity table
            reviews = ""
            try:
                if activity_table.count() > 0:
                    reviews_row = activity_table.locator("tbody tr:has-text('Reviews')").first
                    if reviews_row.count() > 0:
                        reviews_td = reviews_row.locator("td").last
                        if reviews_td.count() > 0:
                            reviews = reviews_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # ========== Author Information ==========
            # Lấy number_of_stories từ Author Information table (Fictions)
            number_of_stories = ""
            try:
                if author_info_table.count() > 0:
                    fictions_row = author_info_table.locator("tbody tr:has-text('Fictions:')").first
                    if fictions_row.count() > 0:
                        fictions_td = fictions_row.locator("td").last
                        if fictions_td.count() > 0:
                            number_of_stories = fictions_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_words từ Author Information table
            total_words = ""
            try:
                if author_info_table.count() > 0:
                    total_words_row = author_info_table.locator("tbody tr:has-text('Total Words:')").first
                    if total_words_row.count() > 0:
                        total_words_td = total_words_row.locator("td").last
                        if total_words_td.count() > 0:
                            total_words = total_words_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_reviews_received từ Author Information table
            total_reviews_received = ""
            try:
                if author_info_table.count() > 0:
                    total_reviews_row = author_info_table.locator("tbody tr:has-text('Total Reviews Received:')").first
                    if total_reviews_row.count() > 0:
                        total_reviews_td = total_reviews_row.locator("td").last
                        if total_reviews_td.count() > 0:
                            total_reviews_received = total_reviews_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_ratings_received từ Author Information table
            total_ratings_received = ""
            try:
                if author_info_table.count() > 0:
                    total_ratings_row = author_info_table.locator("tbody tr:has-text('Total Ratings Received:')").first
                    if total_ratings_row.count() > 0:
                        total_ratings_td = total_ratings_row.locator("td").last
                        if total_ratings_td.count() > 0:
                            total_ratings_received = total_ratings_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy followers từ Author Information table
            followers = ""
            try:
                if author_info_table.count() > 0:
                    followers_row = author_info_table.locator("tbody tr:has-text('Followers:')").first
                    if followers_row.count() > 0:
                        followers_td = followers_row.locator("td").last
                        if followers_td.count() > 0:
                            followers = followers_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy favorites từ Author Information table
            favorites = ""
            try:
                if author_info_table.count() > 0:
                    favorites_row = author_info_table.locator("tbody tr:has-text('Favorites:')").first
                    if favorites_row.count() > 0:
                        favorites_td = favorites_row.locator("td").last
                        if favorites_td.count() > 0:
                            favorites = favorites_td.inner_text().strip().replace(",", "")
            except:
                pass
            
            # Lấy total_favorites_received (cùng với favorites từ Author Information)
            total_favorites_received = favorites
            
            # Cập nhật user_data với các fields mới
            update_data = {}
            if created_date:
                update_data["created_date"] = created_date
            if gender:
                update_data["gender"] = gender
            if location is not None:  # Có thể là empty string
                update_data["location"] = location
            if bio is not None:  # Có thể là empty string
                update_data["bio"] = bio
            if followers:
                update_data["followers"] = followers
            if following:
                update_data["following"] = following
            if comments:
                update_data["comments"] = comments
            if favorites:
                update_data["favorites"] = favorites
            if ratings:
                update_data["ratings"] = ratings
            if reviews:
                update_data["reviews"] = reviews
            if number_of_stories:
                update_data["number_of_stories"] = number_of_stories
            if total_words:
                update_data["total_words"] = total_words
            if total_reviews_received:
                update_data["total_reviews_received"] = total_reviews_received
            if total_ratings_received:
                update_data["total_ratings_received"] = total_ratings_received
            if total_favorites_received:
                update_data["total_favorites_received"] = total_favorites_received
            
            # Cập nhật vào MongoDB
            if update_data:
                self.mongo.mongo_collection_users.update_one(
                    {"web_user_id": web_user_id},
                    {"$set": update_data}
                )
                safe_print(f"        ✅ Đã cập nhật profile cho user {web_user_id}")
            
            return user_id
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi scrape user profile data: {e}")
            return None
    
    def scrape_user_profile_worker(self, user_url, web_user_id, index):
        """
        Worker function để scrape profile của MỘT user - mỗi worker có browser instance riêng
        Thread-safe: Mỗi worker có browser instance riêng
        
        Args:
            user_url: URL của user profile
            web_user_id: Web user ID
            index: Thứ tự user trong list (để delay)
        Returns:
            user_id: ID của user đã được cập nhật, hoặc None nếu lỗi
        """
        worker_playwright = None
        worker_browser = None
        
        try:
            time.sleep(index * config.DELAY_THREAD_START)
            
            worker_playwright = sync_playwright().start()
            worker_browser = worker_playwright.chromium.launch(headless=config.HEADLESS)
            worker_context = worker_browser.new_context()
            worker_page = worker_context.new_page()
            
            safe_print(f"    🔄 Thread-{index}: Đang scrape profile user {web_user_id}")
            
            # Navigate đến profile page
            worker_page.goto(user_url, timeout=60000)
            time.sleep(2)
            
            # Scrape profile data (chỉ extract data, không navigate)
            user_id = self.scrape_user_profile_data(worker_page, user_url, web_user_id)
            
            safe_print(f"      ✅ Thread-{index}: Đã scrape xong profile user {web_user_id}")
            return user_id
            
        except Exception as e:
            safe_print(f"      ❌ Thread-{index}: Lỗi khi scrape profile user {web_user_id}: {e}")
            return None
        finally:
            if worker_browser:
                worker_browser.close()
            if worker_playwright:
                worker_playwright.stop()

