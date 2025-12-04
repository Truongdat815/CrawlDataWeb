"""
Comment handler - xử lý comment scraping
"""
import time
from src import config
from src.utils import safe_print, generate_id


class CommentHandler:
    """Handler cho comment scraping"""
    
    def __init__(self, page, mongo_handler, user_handler):
        """
        Args:
            page: Playwright page object (có thể là None nếu chỉ dùng worker methods)
            mongo_handler: MongoHandler instance
            user_handler: UserHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
        self.user_handler = user_handler
    
    def get_max_comment_page(self, url):
        """Lấy số trang comments tối đa từ pagination"""
        try:
            base_url = url.split('?')[0]
            current_url = self.page.url.split('?')[0] if self.page else ""
            
            if base_url not in current_url:
                self.page.goto(base_url, timeout=config.TIMEOUT)
                time.sleep(2)
            
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
    
    def scrape_comments_from_page(self, page_url, chapter_id=""):
        """Lấy comments từ một trang cụ thể, trả về danh sách phẳng (flat)"""
        comments = []
        
        try:
            self.page.goto(page_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            all_comments = self.page.locator("div.comment").all()
            
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
                    
                    comment_list = self.scrape_single_comment_recursive(comment_elem, chapter_id, parent_id=None, page=self.page)
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
                self.page.goto(url, timeout=config.TIMEOUT)
                time.sleep(2)
            
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
                page.goto(url, timeout=config.TIMEOUT)
                time.sleep(2)
            
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
    
    def scrape_single_comment_recursive(self, comment_elem, chapter_id="", parent_id=None, parent_user_id=None, page=None):
        """
        Hàm đệ quy để lấy một comment và tất cả replies của nó, trả về danh sách phẳng (flat)
        
        Args:
            comment_elem: Element của comment
            chapter_id: ID của chapter
            parent_id: ID của parent comment (comment_id mà nó reply, None nếu là comment gốc)
            parent_user_id: User ID của parent comment (dùng để tạo reply_to_user_id)
            page: Playwright page object (từ worker thread, nếu None thì dùng self.page)
        """
        result_list = []
        
        try:
            media_elem = comment_elem.locator("div.media.media-v2").first
            if media_elem.count() == 0:
                return []
            
            web_comment_id = media_elem.get_attribute("id") or ""
            if web_comment_id.startswith("comment-container-"):
                web_comment_id = web_comment_id.replace("comment-container-", "")
            
            if web_comment_id and self.mongo.is_comment_scraped(web_comment_id):
                try:
                    subcomments_list = comment_elem.locator("ul.subcomments").first
                    if subcomments_list.count() > 0:
                        reply_comments = subcomments_list.locator("div.comment").all()
                        existing_comment = self.mongo.get_comment_by_web_id(web_comment_id)
                        existing_comment_id = existing_comment.get("comment_id") if existing_comment else None
                        for reply_elem in reply_comments:
                            reply_list = self.scrape_single_comment_recursive(reply_elem, chapter_id, parent_id=existing_comment_id, parent_user_id=None, page=page)
                            if reply_list:
                                result_list.extend(reply_list)
                except:
                    pass
                return result_list
            
            comment_id = generate_id()
            
            # Lấy user từ comment element
            web_user_id, username, user_url = self.user_handler.scrape_user_from_element(media_elem)
            user_id = None
            if web_user_id and username:
                # Lưu user cơ bản trước (không scrape profile ngay - sẽ scrape sau khi xong tất cả comments)
                user_id = self.user_handler.save_user(web_user_id, username, user_url, page=None)
            
            comment_text = ""
            try:
                media_body = media_elem.locator(".media-body").first
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
            
            timestamp = ""
            try:
                time_elem = media_elem.locator("time, .timestamp, [class*='time'], [class*='date']").first
                if time_elem.count() > 0:
                    timestamp = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            reply_to_user_id = parent_user_id if parent_user_id else None
            is_root = (parent_id is None or parent_id == "")
            
            # lấy website_id của Royal Road
            website_id = self.mongo.royal_road_website_id if self.mongo.royal_road_website_id else ""

            comment_data = {
                "comment_id": comment_id,
                "web_comment_id": web_comment_id,
                "comment_text": comment_text,
                "time": timestamp,
                "chapter_id": chapter_id,
                "user_id": user_id,
                "reply_to_user_id": reply_to_user_id if reply_to_user_id else None,
                "parent_id": parent_id if parent_id else None,
                "is_root": is_root,
                "react": "",
                "website_id": website_id
            }
            
            self.mongo.save_comment(comment_data)
            result_list.append(comment_data)
            
            try:
                subcomments_list = comment_elem.locator("ul.subcomments").first
                if subcomments_list.count() > 0:
                    reply_comments = subcomments_list.locator("div.comment").all()
                    
                    for reply_elem in reply_comments:
                        reply_list = self.scrape_single_comment_recursive(reply_elem, chapter_id, parent_id=comment_id, parent_user_id=user_id, page=page)
                        if reply_list:
                            result_list.extend(reply_list)
            except Exception as e:
                pass
            
            return result_list
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse comment: {e}")
            return []

