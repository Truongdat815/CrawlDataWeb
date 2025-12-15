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
            
            # ✅ Selector mới: tìm tất cả comments với các format khác nhau
            # HTML mới: <div class="comment_list_main"><ol class="comment-list chapters"><li id="comment-3985144" class="cmt_li_chp_1">...</li></ol></div>
            # HTML cũ: <li id="comment-3979748">
            # HTML cũ khác: <div id="div-comment-3857398" class="comment-body user depth_1">
            all_comments = []
            
            # Thử các selector khác nhau (ưu tiên selector cụ thể nhất trước)
            selectors = [
                "div.comment_list_main ol.comment-list li[id^='comment-']",  # ✅ HTML mới: cụ thể nhất
                "ol.comment-list li[id^='comment-']",  # ✅ HTML mới: ol.comment-list
                "ol.comment-list.chapters li[id^='comment-']",  # ✅ HTML mới: với class chapters
                "li[id^='comment-']",  # ✅ HTML mới: li là container chính (fallback)
                "div.comment_list_main li[id^='comment-']",  # Fallback
                "ul.comment-list li[id^='comment-']",  # HTML cũ
                "div[id^='div-comment-']",  # ✅ HTML mới: div-comment-3985144 (nếu không có li)
                "div.comment-body",  # Fallback
                "div.comment"  # Fallback cuối cùng
            ]
            
            for selector in selectors:
                try:
                    found_comments = self.page.locator(selector).all()
                    if found_comments:
                        all_comments = found_comments
                        safe_print(f"        ✅ Tìm thấy {len(all_comments)} comments với selector: {selector}")
                        break
                except:
                    continue
            
            for comment_elem in all_comments:
                try:
                    # Chỉ xử lý root comments (không phải trong ul.children)
                    is_in_children = comment_elem.evaluate("""
                        el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.tagName === 'UL' && (parent.classList.contains('children') || parent.classList.contains('subcomments') || parent.classList.contains('chp'))) {
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
            # Kiểm tra xem page đã ở đúng URL chưa
            current_url = page.url.split('?')[0] if page.url else ""
            target_url = page_url.split('?')[0]
            
            if target_url not in current_url:
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
                page.goto(page_url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
            
            # Scroll để load comments (có thể comments load lazy)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Scroll lên một chút để trigger load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ✅ Selector mới: tìm tất cả comments với các format khác nhau
            # HTML mới: <div class="comment_list_main"><ol class="comment-list chapters"><li id="comment-3985144" class="cmt_li_chp_1">...</li></ol></div>
            # HTML cũ: <ol class="comment-list chapters"><li id="comment-3979748">
            all_comments = []
            
            # Thử các selector khác nhau (ưu tiên selector cụ thể nhất trước)
            selectors = [
                "div.comment_list_main ol.comment-list li[id^='comment-']",  # ✅ HTML mới: cụ thể nhất
                "ol.comment-list li[id^='comment-']",  # ✅ HTML mới: ol.comment-list
                "ol.comment-list.chapters li[id^='comment-']",  # ✅ HTML mới: với class chapters
                "li[id^='comment-']",  # ✅ HTML mới: li là container chính (fallback)
                "div.comment_list_main li[id^='comment-']",  # Fallback
                "ul.comment-list li[id^='comment-']",  # HTML cũ
                "div[id^='div-comment-']",  # ✅ HTML mới: div-comment-3985144 (nếu không có li)
                "div.comment-body",  # Fallback
                "div.comment"  # Fallback cuối cùng
            ]
            
            for selector in selectors:
                try:
                    found_comments = page.locator(selector).all()
                    if found_comments and len(found_comments) > 0:
                        all_comments = found_comments
                        safe_print(f"        ✅ Tìm thấy {len(all_comments)} comments với selector: {selector}")
                        break
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi thử selector {selector}: {e}")
                    continue
            
            # Nếu không tìm thấy, thử debug
            if not all_comments:
                safe_print(f"        ⚠️ Không tìm thấy comments với bất kỳ selector nào")
                safe_print(f"        🔍 DEBUG: Đang kiểm tra HTML structure...")
                # Debug: Kiểm tra xem có comment_list_main không
                try:
                    comment_list_main = page.locator("div.comment_list_main").first
                    if comment_list_main.count() > 0:
                        safe_print(f"        🔍 DEBUG: ✅ Tìm thấy div.comment_list_main")
                        # Kiểm tra xem có ol.comment-list không
                        ol_comment_list = comment_list_main.locator("ol.comment-list").first
                        if ol_comment_list.count() > 0:
                            safe_print(f"        🔍 DEBUG: ✅ Tìm thấy ol.comment-list")
                            # Đếm số li
                            li_count = ol_comment_list.locator("li").count()
                            safe_print(f"        🔍 DEBUG: Có {li_count} thẻ <li> trong ol.comment-list")
                            
                            # Thử lấy tất cả li có id bắt đầu bằng "comment-"
                            li_with_comment_id = ol_comment_list.locator("li[id^='comment-']").all()
                            safe_print(f"        🔍 DEBUG: Có {len(li_with_comment_id)} thẻ <li> với id^='comment-'")
                            
                            # Nếu có li nhưng không match selector, thử lấy trực tiếp
                            if li_count > 0 and len(li_with_comment_id) == 0:
                                safe_print(f"        🔍 DEBUG: ⚠️ Có {li_count} <li> nhưng không có id^='comment-', thử lấy tất cả <li>")
                                all_li = ol_comment_list.locator("li").all()
                                all_comments = all_li
                                safe_print(f"        🔍 DEBUG: ✅ Đã lấy {len(all_comments)} <li> làm comments")
                        else:
                            safe_print(f"        🔍 DEBUG: ❌ KHÔNG tìm thấy ol.comment-list trong div.comment_list_main")
                    else:
                        safe_print(f"        🔍 DEBUG: ❌ KHÔNG tìm thấy div.comment_list_main")
                        # Thử tìm ol.comment-list trực tiếp
                        ol_direct = page.locator("ol.comment-list").first
                        if ol_direct.count() > 0:
                            safe_print(f"        🔍 DEBUG: ✅ Tìm thấy ol.comment-list (không có div.comment_list_main)")
                            li_count = ol_direct.locator("li[id^='comment-']").count()
                            safe_print(f"        🔍 DEBUG: Có {li_count} thẻ <li> với id^='comment-' trong ol.comment-list")
                except Exception as e:
                    safe_print(f"        🔍 DEBUG: ❌ Lỗi khi debug: {e}")
                    import traceback
                    safe_print(f"        🔍 DEBUG: {traceback.format_exc()}")
            
            for comment_elem in all_comments:
                try:
                    # Chỉ xử lý root comments (không phải trong ul.children)
                    is_in_children = comment_elem.evaluate("""
                        el => {
                            let parent = el.parentElement;
                            while (parent) {
                                if (parent.tagName === 'UL' && (parent.classList.contains('children') || parent.classList.contains('subcomments') || parent.classList.contains('chp'))) {
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
            
            # ✅ So sánh với DB và cập nhật isDeleted cho comments không còn trên web
            if chapter_id:
                web_comment_ids = [comment.get("webCommentId") for comment in all_comments if comment.get("webCommentId")]
                self.mongo.update_deleted_comments(chapter_id, web_comment_ids)
            
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []
    
    def scrape_comments_worker(self, page, url, comment_type="chapter", chapter_id=""):
        """
        Worker function để lấy comments - dùng page từ worker thay vì self.page
        """
        try:
            current_url = page.url.split('?')[0] if page.url else ""
            target_url = url.split('?')[0]
            
            # Chỉ goto nếu URL khác nhau
            if target_url not in current_url:
                safe_print(f"      🔄 Đang navigate đến chapter URL để scrape comments...")
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
                page.goto(url, timeout=config.TIMEOUT, wait_until="networkidle")
                time.sleep(3)
            else:
                safe_print(f"      ✅ Page đã ở đúng URL, không cần navigate lại")
                # Đảm bảo page đã load xong
                time.sleep(2)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            # Scroll để đảm bảo comments được load (lazy load)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
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
            
            # ✅ So sánh với DB và cập nhật isDeleted cho comments không còn trên web
            if chapter_id:
                web_comment_ids = [comment.get("webCommentId") for comment in all_comments if comment.get("webCommentId")]
                self.mongo.update_deleted_comments(chapter_id, web_comment_ids)
            
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
            # HTML mới: <div id="div-comment-3857398"> → web_comment_id = "3857398"
            # HTML cũ: <li id="comment-3979748"> → web_comment_id = "3979748"
            web_comment_id = comment_elem.get_attribute("id") or ""
            if web_comment_id.startswith("div-comment-"):
                web_comment_id = web_comment_id.replace("div-comment-", "")
            elif web_comment_id.startswith("comment-"):
                web_comment_id = web_comment_id.replace("comment-", "")
            elif web_comment_id.startswith("comment-container-"):
                web_comment_id = web_comment_id.replace("comment-container-", "")
            
            if not web_comment_id:
                return []
            
            # ✅ Tìm comment body
            # HTML mới: <li id="comment-3985144"><div id="div-comment-3985144" class="comment-body user depth_1">...</div></li>
            # Hoặc: <div id="div-comment-3985144" class="comment-body user depth_1"> (nếu không có li wrapper)
            # HTML cũ: <li id="comment-3979748"><div class="comment-body">...</div>
            comment_body = None
            # Kiểm tra xem element hiện tại có phải là comment-body không
            elem_class = comment_elem.get_attribute("class") or ""
            if "comment-body" in elem_class:
                comment_body = comment_elem
            else:
                # Tìm div.comment-body bên trong (khi comment_elem là <li>)
                comment_body = comment_elem.locator("div.comment-body").first
                if comment_body.count() == 0:
                    # Fallback: thử div.media.media-v2 (HTML cũ)
                    comment_body = comment_elem.locator("div.media.media-v2").first
                    if comment_body.count() == 0:
                        # Fallback cuối: dùng element chính
                        comment_body = comment_elem
            
            if not comment_body or (hasattr(comment_body, 'count') and comment_body.count() == 0):
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
                        existing_comment_id = existing_comment.get("commentId") if existing_comment else None
                        for reply_elem in reply_comments:
                            reply_list = self.scrape_single_comment_recursive(reply_elem, chapter_id, parent_id=existing_comment_id, parent_user_id=None)
                            if reply_list:
                                result_list.extend(reply_list)
                except:
                    pass
                return result_list
            
            comment_id = generate_id()
            
            # ✅ Lấy username và web_user_id từ HTML
            # HTML: <span class="fn 3979748"><a href="https://www.scribblehub.com/profile/212501/l1aei/">L1aei</a></span>
            web_user_id = ""
            username = ""
            try:
                # Selector: .fn a hoặc .comment-author a[href*='/profile/']
                username_elem = comment_body.locator(".fn a, .comment-author.chapter a[href*='/profile/']").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
                    href = username_elem.get_attribute("href") or ""
                    if "/profile/" in href:
                        # Parse: /profile/212501/l1aei/ → 212501
                        import re
                        match = re.search(r'/profile/(\d+)/', href)
                        if match:
                            web_user_id = match.group(1)
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
                                    import re
                                    match = re.search(r'/profile/(\d+)/', href)
                                    if match:
                                        web_user_id = match.group(1)
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
            # HTML: <div class="reply user 3979748" rid="3979748">
            # Hoặc từ onclick="hl_cmt('3979967')" trong span.rpy_cmt_fa
            if not parent_id:
                try:
                    # Thử lấy từ rid attribute
                    reply_div = comment_body.locator("div.reply[rid]").first
                    if reply_div.count() > 0:
                        parent_rid = reply_div.get_attribute("rid")
                        if parent_rid and parent_rid != web_comment_id:
                            # Tìm parent comment để lấy parent_id
                            parent_comment = self.mongo.get_comment_by_web_id(parent_rid)
                            if parent_comment:
                                parent_id = parent_comment.get("commentId")
                                parent_user_id = parent_comment.get("userId")
                    
                    # Nếu chưa có, thử lấy từ onclick="hl_cmt('3979967')"
                    if not parent_id:
                        reply_span = comment_body.locator("span.rpy_cmt_fa[onclick]").first
                        if reply_span.count() > 0:
                            onclick_attr = reply_span.get_attribute("onclick") or ""
                            import re
                            match = re.search(r"hl_cmt\(['\"]?(\d+)['\"]?\)", onclick_attr)
                            if match:
                                parent_rid = match.group(1)
                                if parent_rid != web_comment_id:
                                    parent_comment = self.mongo.get_comment_by_web_id(parent_rid)
                                    if parent_comment:
                                        parent_id = parent_comment.get("commentId")
                                        parent_user_id = parent_comment.get("userId")
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
            
            # ✅ Lấy react (số lượng likes) từ HTML
            # HTML: <span id="helpful_3979748">3</span> Likes
            # Hoặc: <span class="cmt_counter up 3979748">3</span>
            react = ""
            try:
                import re
                # Thử lấy từ #helpful_{web_comment_id}
                helpful_elem = comment_body.locator(f"#helpful_{web_comment_id}").first
                if helpful_elem.count() > 0:
                    react_text = helpful_elem.inner_text().strip()
                    numbers = re.findall(r'\d+', react_text)
                    if numbers:
                        react = numbers[0]
                
                # Nếu chưa có, thử lấy từ .cmt_counter.up
                if not react:
                    up_counter = comment_body.locator(f".cmt_counter.up.{web_comment_id}").first
                    if up_counter.count() > 0:
                        react = up_counter.inner_text().strip()
                        if not react:
                            # Thử lấy từ parent span
                            parent_span = up_counter.evaluate("el => el.parentElement")
                            if parent_span:
                                react_text = up_counter.evaluate("el => el.parentElement?.textContent || ''")
                                numbers = re.findall(r'\d+', react_text)
                                if numbers:
                                    react = numbers[0]
                
                # Fallback: thử selector cũ
                if not react:
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
            
            # ✅ Convert react từ "" thành None để phù hợp với MongoDB schema
            react_final = react if react and react.strip() else None
            
            # ✅ Đảm bảo tất cả fields khớp với MongoDB schema (theo hình ảnh):
            # _id: ObjectId (tự động tạo bởi MongoDB) - KHÔNG CẦN SET
            # commentId: string (PK) - ID duy nhất của comment trong hệ thống
            # webCommentId: string - ID từ website gốc (ví dụ: "3985144")
            # commentText: string - Nội dung comment (ví dụ: "Huh, MoL on RR?")
            # time: string - Thời gian comment (ví dụ: "Dec 13, 2025 04:19 PM")
            # chapterId: string - ID của chapter mà comment thuộc về
            # userId: string hoặc None - ID của user đã comment
            # replyToUserId: string hoặc None - ID của user mà comment này reply (null nếu không phải reply)
            # parentId: string hoặc None - ID của parent comment (null nếu là root comment)
            # isRoot: boolean - Có phải là root comment không (true = root, false = reply)
            # react: string hoặc None - Số lượng likes/reacts (null nếu không có)
            # websiteId: string - ID của website (ví dụ: ScribbleHub)
            # isDeleted: boolean - Đã bị xóa chưa (false = chưa xóa, true = đã xóa)
            comment_data = {
                "commentId": comment_id,  # ✅ string - Khóa chính (tự động generate)
                "webCommentId": web_comment_id,  # ✅ string - ID từ web (ví dụ: "3985144")
                "commentText": comment_text,  # ✅ string - Nội dung comment
                "time": timestamp,  # ✅ string - Thời gian (ví dụ: "Dec 13, 2025 04:19 PM")
                "chapterId": chapter_id,  # ✅ string - ID của chapter
                "userId": user_id,  # ✅ string hoặc None - ID của user
                "replyToUserId": reply_to_user_id if reply_to_user_id else None,  # ✅ string hoặc None
                "parentId": parent_id if parent_id else None,  # ✅ string hoặc None
                "isRoot": is_root,  # ✅ boolean - true nếu là root comment
                "react": react_final,  # ✅ string hoặc None - Số likes (ví dụ: "5" hoặc null)
                "websiteId": website_id,  # ✅ string - ID của website
                "isDeleted": False  # ✅ boolean - false khi comment được tìm thấy trên web
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

