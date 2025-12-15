"""
Chapter handler - xử lý chapter content scraping
✅ CÁCH TỐI ƯU: Dùng browser chính đã mở (đã vượt Cloudflare) thay vì tạo mới
"""
import time
import random
import re
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text
from src.utils.requests_helper import get_session_from_context, scrape_chapter_with_requests


class ChapterHandler:
    """Handler cho chapter content scraping"""
    
    def __init__(self, mongo_handler, comment_handler, context=None):
        """
        Args:
            mongo_handler: MongoHandler instance
            comment_handler: CommentHandler instance
            context: Playwright context (để lấy cookies cho requests)
        """
        self.mongo = mongo_handler
        self.comment_handler = comment_handler
        self.context = context  # Lưu context để dùng cho requests
    
    def scrape_single_chapter_using_browser(self, page, url, index, story_id, order, published_time_from_table, chapter_name_from_table=""):
        """
        ✅ CÁCH TỐI ƯU: Scrape chapter bằng browser chính đã mở (đã vượt Cloudflare)
        → Không bị 403 Forbidden (vì dùng browser đã verify)
        → Không bị lỗi Playwright Sync API (vì không tạo browser mới)
        → Ổn định nhất, reliable nhất
        
        Args:
            page: Playwright page object (browser chính đã mở)
            url: URL của chương cần cào
            index: Thứ tự chương trong list
            story_id: ID của story (FK)
            order: Số thứ tự của chapter (từ 1)
            published_time_from_table: published_time lấy từ table row
            chapter_name_from_table: chapter_name lấy từ table of contents
        """
        try:
            safe_print(f"    🔄 Đang cào chương {index + 1} bằng Browser chính...")
            
            # 1. Goto URL bằng browser đang mở (đã vượt Cloudflare)
            page.goto(url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            
            # 2. Random delay để giống người thật
            time.sleep(random.uniform(2.0, 4.0))
            
            # 3. Xử lý Cloudflare nếu vô tình gặp lại (Scroll nhẹ)
            page_content = page.content().lower()
            if any(x in page_content for x in ["challenges.cloudflare.com", "please unblock", "checking your browser"]):
                safe_print("      ⚠️ Gặp lại Cloudflare, đợi 5s...")
                time.sleep(5)
            
            # 4. Lấy nội dung từ div.chp_raw (giữ đúng format như UI)
            try:
                # Thử lấy từ #chp_raw hoặc .chp_raw
                page.wait_for_selector("#chp_raw, .chp_raw", timeout=10000)
            except:
                safe_print(f"      ⚠️ Không tìm thấy #chp_raw/.chp_raw (Timeout), thử fallback...")
            
            # Lấy chapter_name (ưu tiên từ table of contents, fallback từ page)
            chapter_name = chapter_name_from_table
            if not chapter_name:
                try:
                    # Thử lấy từ .chapter-title
                    title_elem = page.locator(".chapter-title").first
                    if title_elem.count() > 0:
                        chapter_name = title_elem.inner_text().strip()
                    else:
                        # Fallback: thử h1
                        title_elem = page.locator("h1").first
                        if title_elem.count() > 0:
                            chapter_name = title_elem.inner_text().strip()
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi lấy chapter_name: {e}")
            
            content = ""
            try:
                # ✅ Ưu tiên lấy toàn bộ HTML trong #chp_raw/.chp_raw
                # và loại bỏ phần author notes (.wi_authornotes) bên trong
                content_container = page.locator("#chp_raw, .chp_raw").first
                if content_container.count() > 0:
                    try:
                        # Xóa tất cả .wi_authornotes bên trong chp_raw (Patreon, lời tác giả, v.v.)
                        page.evaluate(
                            """
                            (el) => {
                                if (!el) return;
                                const notes = el.querySelectorAll('.wi_authornotes');
                                notes.forEach(n => n.remove());
                            }
                            """,
                            content_container,
                        )
                    except Exception as _e:
                        # Nếu có lỗi khi evaluate JS thì bỏ qua, tiếp tục dùng HTML hiện tại
                        pass

                    # Lấy lại HTML sau khi đã loại bỏ author notes
                    html_content = content_container.inner_html()
                    content = convert_html_to_formatted_text(html_content)
                    safe_print(f"      ✅ Đã lấy content từ #chp_raw/.chp_raw ({len(content)} ký tự, đã bỏ author notes)")
                else:
                    # Fallback 1: Thử .chapter-inner với helper convert_html_to_formatted_text
                    try:
                        content_container = page.locator(".chapter-inner").first
                        if content_container.count() > 0:
                            html_content = content_container.inner_html()
                            content = convert_html_to_formatted_text(html_content)
                            safe_print("      ⚠️ Dùng fallback .chapter-inner")
                        else:
                            # Fallback 2: Lấy text thô toàn trang
                            content = page.locator("body").inner_text()
                            safe_print("      ⚠️ Dùng fallback body text")
                    except Exception:
                        pass
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi lấy content: {e}")
                try:
                    # Fallback cuối cùng
                    content = page.locator("body").inner_text()
                except Exception:
                    pass
            
            # 5. Lấy published_time (ưu tiên từ table, fallback từ page)
            # HTML: <span class="fic_date_pub" title="Dec 12, 2025 04:12 PM">Dec 12, 2025</span>
            published_time = published_time_from_table
            if not published_time:
                try:
                    # Thử lấy từ span.fic_date_pub title attribute
                    time_elem = page.locator("span.fic_date_pub").first
                    if time_elem.count() > 0:
                        title_attr = time_elem.get_attribute("title")
                        if title_attr:
                            published_time = title_attr
                        else:
                            published_time = time_elem.inner_text().strip()
                    else:
                        # Fallback: thử time[datetime]
                        time_elem = page.locator("time[datetime]").first
                        if time_elem.count() > 0:
                            published_time = time_elem.get_attribute("datetime") or ""
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi lấy published_time: {e}")
            
            # 6. Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    if "/chapter/" in url:
                        web_chapter_id = url.split("/chapter/")[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy web_chapter_id: {e}")
            
            # 7. Kiểm tra chapter đã có trong DB chưa (có thể chỉ có metadata từ table of contents)
            chapter_id = None
            existing_chapter = None
            if web_chapter_id and self.mongo.mongo_collection_chapters:
                try:
                    existing_chapter = self.mongo.mongo_collection_chapters.find_one({"webChapterId": web_chapter_id})
                    if existing_chapter:
                        chapter_id = existing_chapter.get("chapterId")
                        # Kiểm tra xem đã có content chưa
                        if chapter_id and self.mongo.mongo_collection_chapter_contents:
                            content_doc = self.mongo.mongo_collection_chapter_contents.find_one({"chapterId": chapter_id})
                            if content_doc and content_doc.get("content"):
                                safe_print(f"      ⏭️  Bỏ qua (Đã có content): {web_chapter_id}")
                                return None
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi kiểm tra chapter trong DB: {e}")
            
            # Nếu chưa có chapter_id, tạo mới
            if not chapter_id:
                chapter_id = generate_id()
            
            # 8. Lưu Content (chỉ nếu chưa có)
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
            
            # 9. Lấy views, total_comments, và voted từ chapter page
            # HTML views: <span class="chp_stats_feature" title="Total Pageviews"><i class="fa fa-eye chp"></i> 335</span>
            # HTML comments: <span class="chp_stats_feature" title="Total Comments"><i class="fa fa-comments-o chp"></i> <a href="#comments">7</a></span>
            # HTML voted: <span class="chp_stats_feature" title="Favorite This Chapter"><i class="fa fa-heart chp"></i> <span id="heart_cnt">14</span></span>
            views = None
            voted = None
            
            try:
                # Lấy views từ .chp_stats_feature có fa-eye chp
                stats_features = page.locator("span.chp_stats_feature").all()
                for feature in stats_features:
                    try:
                        icon = feature.locator("i").first
                        if icon.count() > 0:
                            icon_classes = icon.get_attribute("class") or ""
                            
                            # Lấy views từ fa-eye chp
                            if "fa-eye" in icon_classes and "chp" in icon_classes:
                                # Lấy text sau icon (số views)
                                feature_text = feature.inner_text().strip()
                                # Parse số từ text (ví dụ: "335" từ "335" hoặc "1.2k" từ "1.2k")
                                view_match = re.search(r'([\d,]+\.?\d*[kKmM]?)', feature_text)
                                if view_match:
                                    views = view_match.group(1).strip()
                            
                            # Lấy voted từ fa-heart chp
                            elif "fa-heart" in icon_classes and "chp" in icon_classes:
                                # Lấy từ span#heart_cnt
                                heart_cnt = feature.locator("span#heart_cnt").first
                                if heart_cnt.count() > 0:
                                    voted = heart_cnt.inner_text().strip()
                                else:
                                    # Fallback: lấy số từ text
                                    feature_text = feature.inner_text().strip()
                                    vote_match = re.search(r'(\d+)', feature_text)
                                    if vote_match:
                                        voted = vote_match.group(1).strip()
                    except:
                        continue
                
                # Fallback: Thử cách cũ nếu không tìm thấy
                if not views or not voted:
                    # Lấy views từ .fic_stats .st_item có fa fa-eye
                    fic_stats = page.locator(".fic_stats").first
                    if fic_stats.count() > 0:
                        stats_items = fic_stats.locator(".st_item").all()
                        for item in stats_items:
                            try:
                                icon = item.locator("i").first
                                if icon.count() > 0:
                                    icon_classes = icon.get_attribute("class") or ""
                                    item_text = item.inner_text().strip()
                                    
                                    # Lấy views từ fa-eye
                                    if "fa-eye" in icon_classes and not views:
                                        view_match = re.search(r'([\d,]+\.?\d*[kKmM]?)\s*Views?', item_text, re.IGNORECASE)
                                        if view_match:
                                            views = view_match.group(1).strip()
                                        else:
                                            numbers = re.findall(r'[\d,]+\.?\d*[kKmM]?', item_text)
                                            if numbers:
                                                views = numbers[0].strip()
                            except:
                                continue
                    
                    # Lấy voted từ .rate_more
                    if not voted:
                        try:
                            rate_more = page.locator(".rate_more").first
                            if rate_more.count() > 0:
                                rate_text = rate_more.inner_text().strip()
                                vote_match = re.search(r'(\d+)', rate_text)
                                if vote_match:
                                    voted = vote_match.group(1).strip()
                        except:
                            pass
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy views/voted: {e}")
            
            # 10. Lấy total_comments từ page (ưu tiên) hoặc scrape comments
            # HTML mới: <div class="cnt_counter">Comments (4)<div class="comments_options">...</div></div>
            # HTML cũ: <span class="chp_stats_feature" title="Total Comments"><i class="fa fa-comments-o chp"></i> <a href="#comments">7</a></span>
            total_comments = 0
            try:
                # ✅ Ưu tiên: Thử lấy từ div.cnt_counter với text "Comments (4)"
                # HTML: <div class="cnt_counter">Comments (4)<div class="comments_options">...</div></div>
                cnt_counter = page.locator("div.cnt_counter").first
                if cnt_counter.count() > 0:
                    try:
                        # Lấy text node đầu tiên (trước div.comments_options) để tránh lấy text từ select bên trong
                        counter_text = cnt_counter.evaluate("""
                            el => {
                                // Lấy text node đầu tiên (trước div.comments_options)
                                let text = '';
                                for (let node of el.childNodes) {
                                    if (node.nodeType === 3) { // Text node
                                        text += node.textContent;
                                    } else if (node.nodeType === 1 && !node.classList.contains('comments_options')) {
                                        // Nếu là element nhưng không phải comments_options, lấy text
                                        text += node.textContent;
                                        break; // Dừng khi gặp comments_options
                                    }
                                    if (node.classList && node.classList.contains('comments_options')) {
                                        break; // Dừng khi gặp comments_options
                                    }
                                }
                                return text.trim();
                            }
                        """)
                        
                        # Fallback: Nếu không lấy được, dùng inner_text và lấy phần trước "Newest" hoặc "Most Liked"
                        if not counter_text or not counter_text.strip():
                            full_text = cnt_counter.inner_text().strip()
                            # Lấy phần trước "Newest" hoặc "Most Liked" (text trong select)
                            if "Newest" in full_text:
                                counter_text = full_text.split("Newest")[0].strip()
                            elif "Most Liked" in full_text:
                                counter_text = full_text.split("Most Liked")[0].strip()
                            else:
                                counter_text = full_text
                        
                        # Parse: "Comments (4)" → 4
                        comment_match = re.search(r'Comments\s*\((\d+)\)', counter_text, re.IGNORECASE)
                        if comment_match:
                            total_comments = int(comment_match.group(1))
                            safe_print(f"      ✅ Đã lấy totalComments từ div.cnt_counter: {total_comments}")
                        else:
                            safe_print(f"      🔍 DEBUG: Không parse được từ text: '{counter_text}'")
                    except Exception as e:
                        safe_print(f"      ⚠️ Lỗi khi parse div.cnt_counter: {e}")
                        import traceback
                        safe_print(f"      {traceback.format_exc()}")
                
                # Fallback: Thử lấy từ .chp_stats_feature có fa-comments-o chp
                if total_comments == 0:
                    stats_features = page.locator("span.chp_stats_feature").all()
                    for feature in stats_features:
                        try:
                            icon = feature.locator("i").first
                            if icon.count() > 0:
                                icon_classes = icon.get_attribute("class") or ""
                                
                                # Lấy total_comments từ fa-comments-o chp
                                if "fa-comments-o" in icon_classes and "chp" in icon_classes:
                                    # Lấy từ thẻ <a> bên trong
                                    link_elem = feature.locator("a").first
                                    if link_elem.count() > 0:
                                        total_comments = link_elem.inner_text().strip()
                                        # Parse số từ text
                                        comment_match = re.search(r'(\d+)', total_comments)
                                    if comment_match:
                                        total_comments = int(comment_match.group(1))
                                    else:
                                        total_comments = 0
                                else:
                                    # Fallback: lấy số từ text
                                    feature_text = feature.inner_text().strip()
                                    comment_match = re.search(r'(\d+)', feature_text)
                                    if comment_match:
                                        total_comments = int(comment_match.group(1))
                                    else:
                                        total_comments = 0
                                break  # Tìm thấy rồi thì break
                        except:
                            pass
                
                # ✅ LUÔN scrape comments để lưu vào DB (không chỉ khi total_comments == 0)
                # Comments sẽ được lưu tự động trong scrape_comments_worker -> scrape_single_comment_recursive -> save_comment
                try:
                    safe_print(f"      💬 Đang scrape comments cho chapter...")
                    comments_list = self.comment_handler.scrape_comments_worker(page, url, "chapter", chapter_id)
                    # Nếu chưa có total_comments từ stats, dùng số lượng comments đã scrape
                    if total_comments == 0 and comments_list:
                        total_comments = len(comments_list)
                        safe_print(f"      ✅ Đã scrape và lưu {len(comments_list)} comments vào MongoDB")
                    elif comments_list:
                        safe_print(f"      ✅ Đã scrape và lưu {len(comments_list)} comments vào MongoDB (total_comments từ stats: {total_comments})")
                    elif not comments_list:
                        safe_print(f"      ℹ️ Không tìm thấy comments cho chapter này")
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi scrape comments: {e}")
                    import traceback
                    safe_print(f"      {traceback.format_exc()}")
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy total_comments: {e}")
                # Fallback: LUÔN scrape comments
                try:
                    safe_print(f"      💬 Fallback: Đang scrape comments cho chapter...")
                    comments_list = self.comment_handler.scrape_comments_worker(page, url, "chapter", chapter_id)
                    if comments_list:
                        total_comments = len(comments_list)
                        safe_print(f"      ✅ Đã scrape và lưu {len(comments_list)} comments vào MongoDB (fallback)")
                    else:
                        safe_print(f"      ℹ️ Không tìm thấy comments cho chapter này (fallback)")
                except Exception as e2:
                    safe_print(f"      ⚠️ Lỗi khi scrape comments (fallback): {e2}")
                    import traceback
                    safe_print(f"      {traceback.format_exc()}")
            
            # 11. Lưu/Update Info (update nếu đã có metadata, insert nếu chưa có)
            chapter_data = {
                "chapterId": chapter_id,
                "webChapterId": web_chapter_id,
                "order": order,
                "chapterName": chapter_name,
                "chapterUrl": url,
                "publishedTime": published_time,
                "storyId": story_id,
                "voted": voted,
                "views": views,
                "totalComments": str(total_comments)
            }
            
            self.mongo.save_chapter(chapter_data)
            safe_print(f"      ✅ Đã cào chương {index + 1} bằng Browser chính!")
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"❌ Lỗi cào chương {index + 1}: {e}")
            return None
    
    def scrape_single_chapter_with_requests(self, url, index, story_id, order, published_time_from_table, session=None):
        """
        ✅ CÁCH 5: Scrape chapter bằng requests (không dùng Playwright)
        → Không bị detect như bot headless
        → Nhanh hơn, ổn định hơn
        
        Args:
            url: URL của chương cần cào
            index: Thứ tự chương trong list
            story_id: ID của story (FK)
            order: Số thứ tự của chapter (từ 1)
            published_time_from_table: published_time lấy từ table row
            session: requests.Session (nếu None thì tạo mới từ context)
        """
        try:
            safe_print(f"    📄 Đang cào chương {index + 1} bằng requests...")
            
            # ✅ CÁCH 4: Random delay như người thật
            delay = random.uniform(2.5, 6.0)  # Random 2.5-6 giây
            time.sleep(delay)
            
            # Tạo session từ context nếu chưa có
            if session is None and self.context:
                # Lấy user_agent từ context options (không phải dict)
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                session = get_session_from_context(self.context, user_agent)
            
            if session is None:
                safe_print(f"      ⚠️ Không có session, dùng Playwright fallback...")
                return self.scrape_single_chapter_worker(url, index, story_id, order, published_time_from_table)
            
            # Scrape bằng requests
            chapter_data = scrape_chapter_with_requests(session, url)
            
            if not chapter_data:
                safe_print(f"      ⚠️ Requests failed, dùng Playwright fallback...")
                return self.scrape_single_chapter_worker(url, index, story_id, order, published_time_from_table)
            
            # Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    url_parts = url.split("/chapter/")
                    if len(url_parts) > 1:
                        web_chapter_id = url_parts[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy web_chapter_id: {e}")
            
            # Kiểm tra đã có chưa
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"      ⏭️  Bỏ qua chapter {web_chapter_id} (đã có trong DB)")
                return None
            
            chapter_id = generate_id()
            title = chapter_data.get('title', '')
            content = chapter_data.get('content', '')
            published_time = published_time_from_table or chapter_data.get('publishedTime', '')
            
            # Lưu content
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
            
            # Lấy totalComments, views và voted từ requests (cần parse HTML)
            total_comments = 0
            views = None
            voted = None
            
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(session.get(url).text, 'html.parser')
                
                # ✅ Lấy totalComments từ div.cnt_counter với text "Comments (4)"
                # HTML: <div class="cnt_counter">Comments (4)<div class="comments_options">...</div></div>
                cnt_counter = soup.select_one("div.cnt_counter")
                if cnt_counter:
                    try:
                        # Lấy text node đầu tiên (trước div.comments_options)
                        # BeautifulSoup: lấy text trực tiếp từ element, bỏ qua children
                        counter_text = ""
                        # Lấy text từ element chính (không bao gồm children)
                        for child in cnt_counter.children:
                            if hasattr(child, 'name') and child.name == 'div' and 'comments_options' in child.get('class', []):
                                break  # Dừng khi gặp div.comments_options
                            if isinstance(child, str):
                                counter_text += child.strip()
                        
                        # Fallback: Nếu không lấy được, dùng get_text và split
                        if not counter_text or not counter_text.strip():
                            full_text = cnt_counter.get_text(strip=True)
                            # Lấy phần trước "Newest" hoặc "Most Liked"
                            if "Newest" in full_text:
                                counter_text = full_text.split("Newest")[0].strip()
                            elif "Most Liked" in full_text:
                                counter_text = full_text.split("Most Liked")[0].strip()
                            else:
                                counter_text = full_text
                        
                        # Parse: "Comments (4)" → 4
                        comment_match = re.search(r'Comments\s*\((\d+)\)', counter_text, re.IGNORECASE)
                        if comment_match:
                            total_comments = int(comment_match.group(1))
                            safe_print(f"      ✅ Đã lấy totalComments từ div.cnt_counter: {total_comments}")
                        else:
                            safe_print(f"      🔍 DEBUG: Không parse được từ text: '{counter_text}'")
                    except Exception as e:
                        safe_print(f"      ⚠️ Lỗi khi parse div.cnt_counter: {e}")
                
                # Lấy views từ .fic_stats .st_item có fa-eye
                fic_stats = soup.select_one(".fic_stats")
                if fic_stats:
                    stats_items = fic_stats.select(".st_item")
                    for item in stats_items:
                        icon = item.select_one("i")
                        if icon:
                            icon_classes = icon.get("class", [])
                            item_text = item.get_text(strip=True)
                            
                            # Lấy views từ fa-eye
                            if "fa-eye" in icon_classes:
                                # Parse: "27k Views" hoặc "27 Views" → "27k" hoặc "27"
                                view_match = re.search(r'([\d,]+\.?\d*[kKmM]?)\s*Views?', item_text, re.IGNORECASE)
                                if view_match:
                                    views = view_match.group(1).strip()
                                else:
                                    # Fallback: lấy số đầu tiên
                                    numbers = re.findall(r'[\d,]+\.?\d*[kKmM]?', item_text)
                                    if numbers:
                                        views = numbers[0].strip()
                
                # Lấy voted từ .rate_more
                rate_more = soup.select_one(".rate_more")
                if rate_more:
                    rate_text = rate_more.get_text(strip=True)
                    # Parse: "42 ratings" hoặc "42" → "42"
                    vote_match = re.search(r'(\d+)', rate_text)
                    if vote_match:
                        voted = vote_match.group(1).strip()
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy views/voted/totalComments bằng requests: {e}")
            
            chapter_data_dict = {
                "chapterId": chapter_id,  # Khóa chính (không phải "id")
                "webChapterId": web_chapter_id,
                "order": order,
                "chapterName": title,  # Không phải "name"
                "chapterUrl": url,  # Không phải "url"
                "publishedTime": published_time,
                "storyId": story_id,
                "voted": voted,
                "views": views,
                "totalComments": str(total_comments)
            }
            
            self.mongo.save_chapter(chapter_data_dict)
            safe_print(f"      ✅ Đã cào chương {index + 1} bằng requests!")
            
            return chapter_data_dict
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi scrape chapter bằng requests: {e}")
            # Fallback về Playwright
            return self.scrape_single_chapter_worker(url, index, story_id, order, published_time_from_table)
    
    def scrape_single_chapter_worker(self, url, index, story_id, order, published_time_from_table):
        """
        Worker function để cào MỘT chương bằng Playwright (fallback)
        """
        worker_playwright = None
        worker_browser = None
        
        try:
            # ✅ CÁCH 4: Random delay
            delay = random.uniform(2.5, 6.0)
            time.sleep(delay)
            
            worker_playwright = sync_playwright().start()
            worker_browser = worker_playwright.chromium.launch(headless=config.HEADLESS)
            worker_context = worker_browser.new_context()
            worker_page = worker_context.new_page()
            
            safe_print(f"    🔄 Thread-{index}: Đang cào chương {index + 1} (Playwright fallback)")
            
            worker_page.goto(url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            
            # ✅ CÁCH 4: Random delay
            time.sleep(random.uniform(1.0, 3.0))
            
            # ✅ Lấy từ div.chp_raw (giữ đúng format như UI)
            worker_page.wait_for_selector("#chp_raw, .chp_raw", timeout=15000)
            
            title = worker_page.locator("h1").first.inner_text()
            
            published_time = published_time_from_table
            if not published_time:
                try:
                    time_elem = worker_page.locator("time[datetime]").first
                    if time_elem.count() > 0:
                        published_time = time_elem.get_attribute("datetime") or ""
                except:
                    pass
            
            content = ""
            try:
                # ✅ Lấy từ div.chp_raw (có nhiều thẻ p, giữ đúng format như UI)
                content_container = worker_page.locator("#chp_raw, .chp_raw").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content = convert_html_to_formatted_text(html_content)
                else:
                    # Fallback: Thử .chapter-inner
                    try:
                        content_container = worker_page.locator(".chapter-inner").first
                        if content_container.count() > 0:
                            html_content = content_container.inner_html()
                            content = convert_html_to_formatted_text(html_content)
                        else:
                            content = worker_page.locator("body").inner_text()
                    except:
                        content = worker_page.locator("body").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy content: {e}")
                try:
                    content = worker_page.locator("#chp_raw, .chp_raw").inner_text()
                except:
                    content = worker_page.locator("body").inner_text()
            
            # ✅ CÁCH 4: Random delay
            time.sleep(random.uniform(1.0, 3.0))
            
            # Lấy web_chapter_id từ URL
            web_chapter_id = ""
            try:
                match = re.search(r'/chapter/(\d+)', url)
                if match:
                    web_chapter_id = match.group(1)
                else:
                    url_parts = url.split("/chapter/")
                    if len(url_parts) > 1:
                        web_chapter_id = url_parts[1].split("/")[0]
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy web_chapter_id từ URL: {e}")
                web_chapter_id = ""
            
            if web_chapter_id and self.mongo.is_chapter_scraped(web_chapter_id):
                safe_print(f"      ⏭️  Thread-{index}: Bỏ qua chapter {web_chapter_id} (đã có trong DB)")
                return None
            
            chapter_id = generate_id()
            
            # Lấy views và voted (favorites) từ chapter page
            # HTML: 
            # Views: <span class="st_item"><i class="fa fa-eye" aria-hidden="true"></i> 151k <span class="mb_stat">Views</span></span>
            # Voted (Favorites): <span class="st_item"><i class="fa fa-heart" aria-hidden="true"></i> 5792 <span class="mb_stat">Favorites</span></span>
            views = ""
            voted = ""
            
            try:
                # Tìm tất cả .st_item (có thể trong .fic_stats hoặc ở đâu đó trên page)
                stats_items = worker_page.locator(".st_item").all()
                for item in stats_items:
                    try:
                        icon = item.locator("i").first
                        if icon.count() > 0:
                            icon_classes = icon.get_attribute("class") or ""
                            item_text = item.inner_text().strip()
                            
                            # Lấy views từ fa-eye
                            if "fa-eye" in icon_classes:
                                # Parse: "151k Views" hoặc "335 Views" → "151k" hoặc "335"
                                view_match = re.search(r'([\d,]+\.?\d*[kKmM]?)\s*Views?', item_text, re.IGNORECASE)
                                if view_match:
                                    views = view_match.group(1).strip()
                                else:
                                    # Fallback: lấy số đầu tiên (có thể có dấu phẩy, k, M)
                                    numbers = re.findall(r'[\d,]+\.?\d*[kKmM]?', item_text)
                                    if numbers:
                                        views = numbers[0].strip()
                            
                            # Lấy voted (favorites) từ fa-heart
                            elif "fa-heart" in icon_classes:
                                # Parse: "5792 Favorites" hoặc "14 Favorites" → "5792" hoặc "14"
                                favorites_match = re.search(r'([\d,]+)\s+Favorites?', item_text, re.IGNORECASE)
                                if favorites_match:
                                    voted = favorites_match.group(1).replace(",", "").strip()
                                else:
                                    # Fallback: lấy số đầu tiên
                                    numbers = re.findall(r'[\d,]+', item_text)
                                    if numbers:
                                        voted = numbers[0].replace(",", "").strip()
                    except:
                        continue
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy views/voted: {e}")
            
            # Lấy totalComments từ HTML
            # HTML mới: <div class="cnt_counter">Comments (4)<div class="comments_options">...</div></div>
            # HTML cũ: <div class="wi_novel_title tags pedit_body nreview">Comments <span class="cnt_toc">9</span></div>
            # Hoặc: <div class="wi_novel_title tags pedit_body nreview">Reviews <span class="cnt_toc">9</span></div>
            total_comments = 0
            try:
                # ✅ Ưu tiên: Thử lấy từ div.cnt_counter với text "Comments (4)"
                # HTML: <div class="cnt_counter">Comments (4)<div class="comments_options">...</div></div>
                cnt_counter = worker_page.locator("div.cnt_counter").first
                if cnt_counter.count() > 0:
                    try:
                        # Lấy text node đầu tiên (trước div.comments_options) để tránh lấy text từ select bên trong
                        counter_text = cnt_counter.evaluate("""
                            el => {
                                // Lấy text node đầu tiên (trước div.comments_options)
                                let text = '';
                                for (let node of el.childNodes) {
                                    if (node.nodeType === 3) { // Text node
                                        text += node.textContent;
                                    } else if (node.nodeType === 1 && !node.classList.contains('comments_options')) {
                                        // Nếu là element nhưng không phải comments_options, lấy text
                                        text += node.textContent;
                                        break; // Dừng khi gặp comments_options
                                    }
                                    if (node.classList && node.classList.contains('comments_options')) {
                                        break; // Dừng khi gặp comments_options
                                    }
                                }
                                return text.trim();
                            }
                        """)
                        
                        # Fallback: Nếu không lấy được, dùng inner_text và lấy phần trước "Newest" hoặc "Most Liked"
                        if not counter_text or not counter_text.strip():
                            full_text = cnt_counter.inner_text().strip()
                            # Lấy phần trước "Newest" hoặc "Most Liked" (text trong select)
                            if "Newest" in full_text:
                                counter_text = full_text.split("Newest")[0].strip()
                            elif "Most Liked" in full_text:
                                counter_text = full_text.split("Most Liked")[0].strip()
                            else:
                                counter_text = full_text
                        
                        # Parse: "Comments (4)" → 4
                        comment_match = re.search(r'Comments\s*\((\d+)\)', counter_text, re.IGNORECASE)
                        if comment_match:
                            total_comments = int(comment_match.group(1))
                            safe_print(f"      ✅ Thread-{index}: Đã lấy totalComments từ div.cnt_counter: {total_comments}")
                        else:
                            safe_print(f"      🔍 DEBUG Thread-{index}: Không parse được từ text: '{counter_text}'")
                    except Exception as e:
                        safe_print(f"      ⚠️ Thread-{index}: Lỗi khi parse div.cnt_counter: {e}")
                        import traceback
                        safe_print(f"      {traceback.format_exc()}")
                
                # Fallback 1: Tìm trong .wi_novel_title có chứa "Comments" với .cnt_toc bên trong
                if total_comments == 0:
                    comment_sections = worker_page.locator(".wi_novel_title.tags.pedit_body").all()
                    for section in comment_sections:
                        try:
                            section_text = section.inner_text().lower()
                            # Tìm section có chứa "Comments" (không phải "Reviews")
                            if "comment" in section_text and "review" not in section_text:
                                # Tìm .cnt_toc trong section này
                                cnt_toc = section.locator(".cnt_toc").first
                                if cnt_toc.count() > 0:
                                    comment_text = cnt_toc.inner_text().strip()
                                    if comment_text and comment_text.isdigit():
                                        total_comments = int(comment_text)
                                        safe_print(f"      ✅ Thread-{index}: Đã lấy totalComments từ HTML: {total_comments}")
                                        break
                        except:
                            continue
                
                # Fallback 2: Nếu chưa tìm thấy, thử tìm tất cả .cnt_toc và kiểm tra context
                if total_comments == 0:
                    all_cnt_toc = worker_page.locator(".wi_novel_title .cnt_toc").all()
                    for elem in all_cnt_toc:
                        try:
                            # Lấy parent element
                            parent_text = elem.evaluate("el => el.parentElement?.textContent || ''")
                            # Nếu parent text có chứa "Comment" nhưng không phải "Chapter" hay "Review" trong context khác
                            if "comment" in parent_text.lower() and "chapter" not in parent_text.lower() and "review" not in parent_text.lower():
                                comment_text = elem.inner_text().strip()
                                if comment_text and comment_text.isdigit():
                                    total_comments = int(comment_text)
                                    safe_print(f"      ✅ Thread-{index}: Đã lấy totalComments từ HTML (fallback): {total_comments}")
                                    break
                        except:
                            continue
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy totalComments từ HTML: {e}")
            
            # Luôn scrape comments để lưu vào DB
            # Nếu chưa có totalComments từ HTML, sẽ đếm từ scraping
            comments_list = []
            try:
                safe_print(f"      💬 Thread-{index}: Đang scrape comments cho chapter {index + 1}...")
                comments_list = self.comment_handler.scrape_comments_worker(worker_page, url, "chapter", chapter_id)
                
                if total_comments == 0:
                    # Nếu chưa có từ HTML, dùng số lượng từ scraping
                    total_comments = len(comments_list) if comments_list else 0
                    if total_comments > 0:
                        safe_print(f"      ✅ Thread-{index}: Đã lấy totalComments từ scraping: {total_comments}")
                else:
                    # Đã có từ HTML, nhưng vẫn scrape để lưu vào DB
                    safe_print(f"      ✅ Thread-{index}: Đã scrape {len(comments_list) if comments_list else 0} comments (totalComments từ HTML: {total_comments})")
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi scrape comments: {e}")
                # Nếu lỗi, vẫn đếm số comments đã scrape được (nếu có)
                if total_comments == 0:
                    total_comments = len(comments_list) if comments_list else 0
            
            if content and chapter_id:
                if not self.mongo.is_chapter_content_scraped(chapter_id):
                    content_id = generate_id()
                    self.mongo.save_chapter_content(content_id, content, chapter_id)
            
            chapter_data = {
                "chapterId": chapter_id,
                "webChapterId": web_chapter_id,
                "order": order,
                "chapterName": title,
                "chapterUrl": url,
                "publishedTime": published_time,
                "storyId": story_id,
                "voted": voted,
                "views": views,
                "totalComments": str(total_comments)
            }
            
            self.mongo.save_chapter(chapter_data)
            
            return chapter_data
            
        except Exception as e:
            safe_print(f"⚠️ Thread-{index}: Lỗi cào chương {index + 1}: {e}")
            return None
        finally:
            if worker_browser:
                worker_browser.close()
            if worker_playwright:
                worker_playwright.stop()
