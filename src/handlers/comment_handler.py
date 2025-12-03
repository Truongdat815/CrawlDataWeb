"""
Comment handler - xử lý comment scraping
"""
import time
from src import config
from src.utils import safe_print, generate_id


class CommentHandler:
    """Handler cho comment scraping"""
    
    def __init__(self, page, mongo_handler):
        """
        Args:
            page: Playwright page object (có thể là None nếu chỉ dùng worker methods)
            mongo_handler: MongoHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
    
    def get_max_comment_page(self, url):
        """Lấy số trang comments tối đa từ pagination"""
        try:
            base_url = url.split('?')[0]
            current_url = self.page.url.split('?')[0] if self.page else ""
            
            if base_url not in current_url:
                self.page.goto(base_url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
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
                    safe_print(f"        📄 Tìm thấy {max_page} trang comments")
                else:
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang: {e}")
            return 1
    
    def get_max_comment_page_worker(self, page, url):
        """Lấy số trang comments tối đa từ pagination - dùng page từ worker"""
        try:
            base_url = url.split('?')[0]
            current_url = page.url.split('?')[0]
            
            if base_url not in current_url:
                page.goto(base_url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
            
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
    
    def scrape_comments_from_page(self, page_url, chapter_id=""):
        """Lấy comments từ một trang cụ thể, trả về danh sách phẳng (flat)"""
        comments = []
        
        try:
            self.page.goto(page_url, timeout=config.TIMEOUT, wait_until="networkidle")
            time.sleep(3)
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ✅ Selector mới: tìm tất cả li có id bắt đầu bằng "comment-"
            all_comments = self.page.locator("ol.comment-list li[id^='comment-'], ul.comment-list li[id^='comment-']").all()
            
            # Nếu không tìm thấy, thử selector cũ
            if not all_comments:
                all_comments = self.page.locator("div.comment").all()
            
            for comment_elem in all_comments:
                try:
                    # Kiểm tra xem có phải comment trong children không (để tránh duplicate)
                    is_in_children = comment_elem.evaluate("""
                        el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.tagName === 'UL' && (parent.classList.contains('children') || parent.classList.contains('subcomments'))) {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        }
                    """)
                    
                    if is_in_children:
                        continue
                    
                    comment_list = self.scrape_single_comment_recursive(comment_elem, chapter_id, parent_id=None)
                    if comment_list:
                        comments.extend(comment_list)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []
    
    def scrape_comments_from_page_worker(self, page, page_url, chapter_id=""):
        """Lấy comments từ một trang cụ thể - dùng page từ worker, trả về danh sách phẳng"""
        comments = []
        
        try:
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            page.goto(page_url, timeout=config.TIMEOUT, wait_until="networkidle")
            time.sleep(3)
            
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ✅ Selector mới: tìm tất cả li có id bắt đầu bằng "comment-"
            all_comments = page.locator("ol.comment-list li[id^='comment-'], ul.comment-list li[id^='comment-']").all()
            
            # Nếu không tìm thấy, thử selector cũ
            if not all_comments:
                all_comments = page.locator("div.comment").all()
            
            for comment_elem in all_comments:
                try:
                    # Kiểm tra xem có phải comment trong children không (để tránh duplicate)
                    is_in_children = comment_elem.evaluate("""
                        el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.tagName === 'UL' && (parent.classList.contains('children') || parent.classList.contains('subcomments'))) {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        }
                    """)
                    
                    if is_in_children:
                        continue
                    
                    comment_list = self.scrape_single_comment_recursive(comment_elem, chapter_id, parent_id=None)
                    if comment_list:
                        comments.extend(comment_list)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []
    
    def scrape_comments(self, url, comment_type="chapter", chapter_id=""):
        """
        Lấy tất cả comments từ TẤT CẢ các trang phân trang
        Trả về danh sách comments phẳng (flat) với parent_id thay vì nested
        """
        try:
            current_url = self.page.url if self.page else ""
            if url not in current_url:
                self.page.goto(url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            max_page = self.get_max_comment_page(url)
            all_comments = []
            
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang {page_num}/{max_page}...")
                
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
                
                page_comments = self.scrape_comments_from_page(page_url, chapter_id)
                all_comments.extend(page_comments)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_comments)} comments")
                
                if page_num < max_page:
                    time.sleep(1)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_comments)} comments từ {max_page} trang ({comment_type}-level)")
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []
    
    def scrape_comments_worker(self, page, url, comment_type="chapter", chapter_id=""):
        """
        Worker function để lấy comments - dùng page từ worker thay vì self.page
        """
        try:
            current_url = page.url
            if url not in current_url:
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
                page.goto(url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            max_page = self.get_max_comment_page_worker(page, url)
            all_comments = []
            
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang {page_num}/{max_page}...")
                
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
                
                if page_num > 1:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                
                page_comments = self.scrape_comments_from_page_worker(page, page_url, chapter_id)
                all_comments.extend(page_comments)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_comments)} comments")
                
                if page_num < max_page:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_comments)} comments từ {max_page} trang ({comment_type}-level)")
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []
    
    def scrape_single_comment_recursive(self, comment_elem, chapter_id="", parent_id=None, parent_user_id=None):
        """
        Hàm đệ quy để lấy một comment và tất cả replies của nó, trả về danh sách phẳng (flat)
        
        Args:
            comment_elem: Element của comment (li[id^='comment-'] hoặc div.comment)
            chapter_id: ID của chapter
            parent_id: ID của parent comment (comment_id mà nó reply, None nếu là comment gốc)
            parent_user_id: User ID của parent comment (dùng để tạo reply_to_user_id)
        """
        result_list = []
        
        try:
            # ✅ Lấy web_comment_id từ id attribute của li hoặc div
            web_comment_id = comment_elem.get_attribute("id") or ""
            if web_comment_id.startswith("comment-"):
                web_comment_id = web_comment_id.replace("comment-", "")
            elif web_comment_id.startswith("comment-container-"):
                web_comment_id = web_comment_id.replace("comment-container-", "")
            
            if not web_comment_id:
                return []
            
            # ✅ Tìm comment body (có thể là div.comment-body hoặc div.media.media-v2)
            comment_body = comment_elem.locator("div.comment-body").first
            if comment_body.count() == 0:
                comment_body = comment_elem.locator("div.media.media-v2").first
                if comment_body.count() == 0:
                    return []
            
            if web_comment_id and self.mongo.is_comment_scraped(web_comment_id):
                try:
                    # Tìm children comments (replies)
                    children_list = comment_elem.locator("ul.children, ul.subcomments").first
                    if children_list.count() > 0:
                        reply_comments = children_list.locator("li[id^='comment-']").all()
                        if not reply_comments:
                            reply_comments = children_list.locator("div.comment").all()
                        existing_comment = self.mongo.get_comment_by_web_id(web_comment_id)
                        existing_comment_id = existing_comment.get("comment_id") if existing_comment else None
                        for reply_elem in reply_comments:
                            reply_list = self.scrape_single_comment_recursive(reply_elem, chapter_id, parent_id=existing_comment_id, parent_user_id=None)
                            if reply_list:
                                result_list.extend(reply_list)
                except:
                    pass
                return result_list
            
            comment_id = generate_id()
            
            # ✅ Lấy username và web_user_id từ HTML mới
            # Selector: .fn a hoặc .comment-author a[href*='/profile/']
            web_user_id = ""
            username = ""
            try:
                # Thử selector mới trước
                username_elem = comment_body.locator(".fn a, .comment-author a[href*='/profile/']").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
                    href = username_elem.get_attribute("href") or ""
                    if "/profile/" in href:
                        web_user_id = href.split("/profile/")[1].split("/")[0]
                else:
                    # Fallback: thử selector cũ
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
                            username_elem = comment_body.locator(selector).first
                            if username_elem.count() > 0:
                                username = username_elem.inner_text().strip()
                                href = username_elem.get_attribute("href") or ""
                                if "/profile/" in href:
                                    web_user_id = href.split("/profile/")[1].split("/")[0]
                                if username:
                                    break
                        except:
                            continue
                        
                if not username:
                    username = "[Unknown]"
            except:
                username = "[Unknown]"
            
            user_id = None
            if web_user_id and username:
                user_id = self.mongo.save_user(web_user_id, username)
            
            # ✅ Lấy comment text từ HTML mới
            # Selector: .user-comment.comment hoặc .media-body
            comment_text = ""
            try:
                # Thử selector mới trước
                comment_text_elem = comment_body.locator(".user-comment.comment").first
                if comment_text_elem.count() > 0:
                    # Lấy HTML và convert để giữ format
                    from src.utils import convert_html_to_formatted_text
                    html_content = comment_text_elem.inner_html()
                    comment_text = convert_html_to_formatted_text(html_content)
                else:
                    # Fallback: thử .media-body
                    media_body = comment_body.locator(".media-body").first
                    if media_body.count() > 0:
                        paragraphs = media_body.locator("p").all()
                        if paragraphs:
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
                            full_text = media_body.inner_text().strip()
                            if username and full_text.startswith(username):
                                comment_text = full_text[len(username):].strip()
                            else:
                                comment_text = full_text
                            
                            lines = comment_text.split('\n')
                            cleaned_lines = []
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue
                                if any(x in line.lower() for x in ['years ago', 'months ago', 'days ago', 'hours ago', 
                                                                    'rep (', 'reply', 'report']):
                                    continue
                                cleaned_lines.append(line)
                            comment_text = '\n'.join(cleaned_lines).strip()
            except Exception as e:
                comment_text = ""
            
            # ✅ Lấy timestamp từ HTML mới
            # Selector: .com_date (có title attribute)
            timestamp = ""
            try:
                time_elem = comment_body.locator(".com_date").first
                if time_elem.count() > 0:
                    # Ưu tiên lấy từ title attribute
                    timestamp = time_elem.get_attribute("title") or time_elem.inner_text().strip()
                else:
                    # Fallback: thử selector cũ
                    time_elem = comment_body.locator("time, .timestamp, [class*='time'], [class*='date']").first
                    if time_elem.count() > 0:
                        timestamp = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # ✅ Xác định parent_id từ rid attribute (nếu là reply)
            # HTML: <div class="reply user 3903578" rid="3900834">
            if not parent_id:
                try:
                    reply_div = comment_body.locator("div.reply[rid]").first
                    if reply_div.count() > 0:
                        parent_rid = reply_div.get_attribute("rid")
                        if parent_rid:
                            # Tìm parent comment để lấy parent_id
                            parent_comment = self.mongo.get_comment_by_web_id(parent_rid)
                            if parent_comment:
                                parent_id = parent_comment.get("comment_id")
                                parent_user_id = parent_comment.get("user_id")
                except:
                    pass
            
            # ✅ Xác định is_root từ class depth
            # depth_1 = root, depth_2+ = reply
            is_root = True
            try:
                comment_body_class = comment_body.get_attribute("class") or ""
                if "depth_2" in comment_body_class or "depth_3" in comment_body_class or "depth_4" in comment_body_class:
                    is_root = False
                elif parent_id is not None:
                    is_root = False
            except:
                is_root = (parent_id is None or parent_id == "")
            
            reply_to_user_id = parent_user_id if parent_user_id else None
            
            # ✅ Lấy react (số lượng likes) từ HTML mới
            # Selector: #helpful_{web_comment_id} hoặc .cmt_counter.up
            react = ""
            try:
                import re
                # Thử lấy từ #helpful_{web_comment_id}
                helpful_elem = comment_body.locator(f"#helpful_{web_comment_id}").first
                if helpful_elem.count() > 0:
                    react = helpful_elem.inner_text().strip()
                else:
                    # Thử lấy từ .cmt_counter.up
                    up_counter = comment_body.locator(f".cmt_counter.up.{web_comment_id}").first
                    if up_counter.count() > 0:
                        react = up_counter.inner_text().strip()
                    else:
                        # Fallback: thử selector cũ
                        react_selectors = [
                            ".react-count",
                            ".like-count",
                            ".heart-count",
                            "[class*='react']",
                            "[class*='like']"
                        ]
                        for selector in react_selectors:
                            try:
                                react_elem = comment_body.locator(selector).first
                                if react_elem.count() > 0:
                                    react_text = react_elem.inner_text().strip()
                                    numbers = re.findall(r'\d+', react_text)
                                    if numbers:
                                        react = numbers[0]
                                        break
                            except:
                                continue
            except:
                pass
            
            # Lấy website_id từ mongo handler
            website_id = self.mongo.scribblehub_website_id if self.mongo.scribblehub_website_id else ""
            
            comment_data = {
                "comment_id": comment_id,  # Khóa chính (không phải "id")
                "web_comment_id": web_comment_id,
                "comment_text": comment_text,
                "time": timestamp,
                "chapter_id": chapter_id,
                "user_id": user_id,
                "reply_to_user_id": reply_to_user_id if reply_to_user_id else None,
                "parent_id": parent_id if parent_id else None,
                "is_root": is_root,
                "react": react,
                "website_id": website_id
            }
            
            self.mongo.save_comment(comment_data)
            result_list.append(comment_data)
            
            # ✅ Tìm children comments (replies) từ HTML mới
            try:
                children_list = comment_elem.locator("ul.children, ul.subcomments").first
                if children_list.count() > 0:
                    reply_comments = children_list.locator("li[id^='comment-']").all()
                    if not reply_comments:
                        reply_comments = children_list.locator("div.comment").all()
                    
                    for reply_elem in reply_comments:
                        reply_list = self.scrape_single_comment_recursive(reply_elem, chapter_id, parent_id=comment_id, parent_user_id=user_id)
                        if reply_list:
                            result_list.extend(reply_list)
            except Exception as e:
                pass
            
            return result_list
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse comment: {e}")
            return []

