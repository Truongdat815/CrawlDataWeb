"""
Review handler - xử lý review scraping
"""
import time
import re
from datetime import datetime
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text


class ReviewHandler:
    """Handler cho review scraping"""
    
    def __init__(self, page, mongo_handler):
        """
        Args:
            page: Playwright page object
            mongo_handler: MongoHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
        self.mongo = mongo_handler
    
    def scrape_reviews(self, story_url, story_id):
        """
        Lấy tất cả reviews từ trang story
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        reviews = []
        try:
            safe_print("      📝 Đang lấy reviews từ trang story...")
            
            # Truy cập vào tab Reviews (reviews nằm trong tab riêng)
            # URL format: story_url + "?tab=review" hoặc story_url + "?tab=review_helpful"
            review_url = story_url
            if "?tab=" not in story_url and "#comments" not in story_url:
                # Thêm tab=review vào URL
                if "?" in story_url:
                    review_url = story_url + "&tab=review"
                else:
                    review_url = story_url + "?tab=review"
            
            self.page.goto(review_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Kiểm tra Cloudflare challenge
            try:
                page_content = self.page.content()
                if "challenges.cloudflare.com" in page_content.lower():
                    safe_print("      ⏳ Phát hiện Cloudflare challenge, đợi...")
                    time.sleep(10)
            except:
                pass
            
            # Scroll để load reviews
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # ✅ Tìm reviews trong div#comments hoặc .comments-area
            # HTML mới: <div class="w-comments-item-text 3986405"> hoặc <div class="w-comments-item">
            review_elements = []
            
            # Thử các selector khác nhau
            selectors = [
                "div.w-comments-item",  # Selector chính
                "div.w-comments-item-text",  # ✅ HTML mới: w-comments-item-text với ID trong class
                "div#comments .w-comments-item",
                ".comments-area .w-comments-item",
                "div[class*='w-comments-item']"  # Fallback
            ]
            
            for selector in selectors:
                try:
                    found_reviews = self.page.locator(selector).all()
                    if found_reviews:
                        review_elements = found_reviews
                        safe_print(f"      ✅ Tìm thấy {len(review_elements)} reviews với selector: {selector}")
                        break
                except:
                    continue
            
            if not review_elements:
                safe_print("      ℹ️ Không tìm thấy reviews với các selector mặc định, thử scroll...")
                # Thử scroll thêm để load
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)
                for selector in selectors:
                    try:
                        found_reviews = self.page.locator(selector).all()
                        if found_reviews:
                            review_elements = found_reviews
                            safe_print(f"      ✅ Tìm thấy {len(review_elements)} reviews sau khi scroll với selector: {selector}")
                            break
                    except:
                        continue
                
            if not review_elements:
                safe_print("      ⚠️ Vẫn không tìm thấy reviews, có thể chưa có reviews hoặc cần truy cập tab khác")
                return []
            
            safe_print(f"      ✅ Tìm thấy {len(review_elements)} reviews")
            
            # Lấy rating distribution (bar chart) - có thể lưu vào story_info sau
            rating_distribution = self._scrape_rating_distribution()
            if rating_distribution:
                safe_print(f"      📊 Rating distribution: {rating_distribution}")
            
            for review_elem in review_elements:
                try:
                    # ✅ Lấy web_review_id từ nhiều nguồn khác nhau
                    # HTML: <div class="w-comments-item" id="comment-2853508">
                    web_review_id = ""
                    
                    # ✅ Ưu tiên: Lấy từ id="comment-{id}"
                    review_id_attr = review_elem.get_attribute("id") or ""
                    if review_id_attr.startswith("comment-"):
                        web_review_id = review_id_attr.replace("comment-", "")
                        safe_print(f"        ✅ Đã lấy web_review_id từ id: {web_review_id}")
                    elif review_id_attr and review_id_attr.isdigit():
                        web_review_id = review_id_attr
                        safe_print(f"        ✅ Đã lấy web_review_id từ id (số thuần): {web_review_id}")
                    
                    # Fallback: Thử lấy từ class (HTML mới)
                    if not web_review_id:
                        class_attr = review_elem.get_attribute("class") or ""
                        # Tìm số trong class: "w-comments-item-text 3986405" → "3986405"
                        import re
                        match = re.search(r'w-comments-item-text\s+(\d+)', class_attr)
                        if match:
                            web_review_id = match.group(1)
                            safe_print(f"        ✅ Đã lấy web_review_id từ class: {web_review_id}")
                        else:
                            # Thử tìm số bất kỳ trong class
                            numbers = re.findall(r'\b(\d{6,})\b', class_attr)  # Tìm số có ít nhất 6 chữ số
                            if numbers:
                                web_review_id = numbers[0]
                                safe_print(f"        ✅ Đã lấy web_review_id từ class (fallback): {web_review_id}")
                    
                    if not web_review_id:
                        safe_print(f"        ⚠️ Không thể lấy web_review_id từ review element, bỏ qua")
                        continue
                    
                    # ✅ LUÔN parse review để update title và time nếu đã có trong DB nhưng thiếu data
                    # Kiểm tra xem review đã có trong DB chưa và có thiếu title/time không
                    should_skip = False
                    if web_review_id and self.mongo.is_review_scraped(web_review_id):
                        # Kiểm tra xem review trong DB có thiếu title hoặc time không
                        existing_review = self.mongo.mongo_collection_reviews.find_one({"webReviewId": web_review_id})
                        if existing_review:
                            # Nếu đã có title và time thì skip, nếu không thì update
                            if existing_review.get("title") and existing_review.get("time"):
                                should_skip = True
                    
                    if should_skip:
                        continue
                    
                    review_data = self.parse_single_review(review_elem, story_id, web_review_id)
                    if review_data:
                        reviews.append(review_data)
                        # ✅ Chỉ lưu review nếu có dữ liệu hợp lệ
                        self.mongo.save_review(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    import traceback
                    safe_print(f"        {traceback.format_exc()}")
                    continue
            
            # ✅ Chỉ in log nếu có reviews
            if reviews:
                safe_print(f"      ✅ Đã lấy được {len(reviews)} reviews")
            else:
                safe_print(f"      ℹ️ Không có reviews để lưu")
            
            # ✅ So sánh với DB và cập nhật isDeleted cho reviews không còn trên web
            if story_id:
                web_review_ids = [review.get("webReviewId") for review in reviews if review.get("webReviewId")]
                self.mongo.update_deleted_reviews(story_id, web_review_ids)
            
            return reviews
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy reviews: {e}")
            return []
    
    def _scrape_rating_distribution(self):
        """
        Lấy rating distribution từ bar chart
        Returns: dict với {1: count, 2: count, 3: count, 4: count, 5: count}
        """
        distribution = {}
        try:
            bar_rows = self.page.locator(".bar_box_main .bar_chart .bar_row").all()
            for row in bar_rows:
                try:
                    ratebar = row.get_attribute("ratebar")  # "1", "2", "3", "4", "5"
                    count_text = row.locator(".bar_count").first.inner_text().strip()
                    # Parse: "100% (1)" → count = 1
                    match = re.search(r'\((\d+)\)', count_text)
                    if match and ratebar:
                        count = int(match.group(1))
                        distribution[int(ratebar)] = count
                except:
                    continue
        except:
            pass
        return distribution
    
    def parse_single_review(self, review_elem, story_id, web_review_id=""):
        """
        Parse một review element thành dictionary theo schema
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK), likes, status
        
        Args:
            review_elem: Element của review
            story_id: ID của story
            web_review_id: Web review ID (optional, sẽ parse nếu không có)
        """
        try:
            safe_print(f"        🔍 DEBUG parse_single_review: web_review_id={web_review_id}")
            
            # Lấy web_review_id nếu chưa có
            if not web_review_id:
                try:
                    review_id_attr = review_elem.get_attribute("id") or ""
                    if review_id_attr.startswith("comment-"):
                        web_review_id = review_id_attr.replace("comment-", "")
                    elif review_id_attr and review_id_attr.isdigit():
                        web_review_id = review_id_attr
                    else:
                        # Thử lấy từ class
                        class_attr = review_elem.get_attribute("class") or ""
                        match = re.search(r'w-comments-item-text\s+(\d+)', class_attr)
                        if match:
                            web_review_id = match.group(1)
                except:
                    pass
            
            review_id = generate_id()
            
            # Lấy username và web_user_id từ .revname hoặc a#revname
            web_user_id = ""
            username = ""
            try:
                # Thử selector mới: a#revname hoặc a.revname{id}
                username_elem = review_elem.locator("a#revname, a[class^='revname'], a[href*='/profile/']").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
                    href = username_elem.get_attribute("href") or ""
                    if "/profile/" in href:
                        # Parse: /profile/186518/mooseebae/ → 186518
                        match = re.search(r'/profile/(\d+)/', href)
                        if match:
                            web_user_id = match.group(1)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy username: {e}")
            
            user_id = None
            if web_user_id and username:
                user_id = self.mongo.save_user(web_user_id, username)
            
            # Lấy overall_score từ stars (đếm số .fa-star được filled/highlighted)
            # HTML: <i class="fa fa-star userreview" data-rating="1"></i> ... (5 stars)
            # Cần kiểm tra xem star nào được filled (có thể có style, class khác, hoặc chỉ đếm theo thứ tự)
            overall_score = ""
            try:
                # Tìm tất cả stars trong review
                star_icons = review_elem.locator("i.fa-star.userreview, i.userreview.fa-star").all()
                filled_count = 0
                
                for star in star_icons:
                    try:
                        # Kiểm tra xem star có được filled không
                        # Có thể kiểm tra qua style (color), class, hoặc thuộc tính khác
                        classes = star.get_attribute("class") or ""
                        style = star.get_attribute("style") or ""
                        
                        # Nếu có class "fa-star" và không có "fa-star-o" (outline), coi như filled
                        # Hoặc kiểm tra style có màu (filled stars thường có màu)
                        if "fa-star-o" not in classes:
                            # Kiểm tra thêm: nếu có style với color, hoặc data-rating
                            # Trong HTML mẫu, tất cả stars đều có, nên cần cách khác
                            # Có thể đếm tất cả và giả sử đều filled, hoặc kiểm tra parent element
                            filled_count += 1
                    except:
                        continue
                
                # Nếu không tìm thấy cách khác, thử đếm theo data-rating
                if filled_count == 0:
                    # Thử cách khác: đếm số stars có data-rating và được filled
                    # Thông thường stars được filled sẽ có class hoặc style khác
                    # Hoặc có thể kiểm tra trong parent span
                    try:
                        # Kiểm tra xem có parent span với stars không
                        parent_span = review_elem.locator("span:has(i.fa-star.userreview)").first
                        if parent_span.count() > 0:
                            # Đếm số stars có class không phải outline
                            all_stars = parent_span.locator("i.fa-star:not(.fa-star-o)").all()
                            filled_count = len(all_stars)
                        
                        # Nếu vẫn không có, đếm tất cả stars (fallback - có thể không chính xác)
                        if filled_count == 0:
                            filled_count = len(star_icons)
                    except:
                        filled_count = len(star_icons)
                
                if filled_count > 0:
                    overall_score = str(filled_count)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy overall_score: {e}")
                pass
            
            # Lấy các score breakdown từ HTML (Style, Story, Grammar, Character)
            style_score = ""
            story_score = ""
            grammar_score = ""
            character_score = ""
            try:
                # Tìm trong review content hoặc các phần tử chứa score breakdown
                # Pattern có thể là: "Style: 4.5" hoặc "Style Score: 4.5" hoặc trong các thẻ HTML cụ thể
                review_text = review_elem.inner_text().lower()
                
                # Tìm Style Score
                style_match = re.search(r'style\s*(?:score)?\s*:?\s*(\d+\.?\d*)', review_text, re.IGNORECASE)
                if style_match:
                    style_score = style_match.group(1)
                
                # Tìm Story Score
                story_match = re.search(r'story\s*(?:score)?\s*:?\s*(\d+\.?\d*)', review_text, re.IGNORECASE)
                if story_match:
                    story_score = story_match.group(1)
                
                # Tìm Grammar Score
                grammar_match = re.search(r'grammar\s*(?:score)?\s*:?\s*(\d+\.?\d*)', review_text, re.IGNORECASE)
                if grammar_match:
                    grammar_score = grammar_match.group(1)
                
                # Tìm Character Score
                character_match = re.search(r'character\s*(?:score)?\s*:?\s*(\d+\.?\d*)', review_text, re.IGNORECASE)
                if character_match:
                    character_score = character_match.group(1)
                
                # Nếu không tìm thấy bằng text, thử tìm trong các phần tử HTML cụ thể
                # Có thể có các thẻ như <span class="score-style">, <div class="score-breakdown">, etc.
                if not style_score or not story_score or not grammar_score or not character_score:
                    # Tìm trong các phần tử có class chứa "score"
                    score_elements = review_elem.locator("[class*='score'], [class*='rating'], [class*='breakdown']").all()
                    for elem in score_elements:
                        elem_text = elem.inner_text().lower()
                        # Tìm các score trong element này
                        if not style_score:
                            style_match = re.search(r'style\s*:?\s*(\d+\.?\d*)', elem_text, re.IGNORECASE)
                            if style_match:
                                style_score = style_match.group(1)
                        if not story_score:
                            story_match = re.search(r'story\s*:?\s*(\d+\.?\d*)', elem_text, re.IGNORECASE)
                            if story_match:
                                story_score = story_match.group(1)
                        if not grammar_score:
                            grammar_match = re.search(r'grammar\s*:?\s*(\d+\.?\d*)', elem_text, re.IGNORECASE)
                            if grammar_match:
                                grammar_score = grammar_match.group(1)
                        if not character_score:
                            character_match = re.search(r'character\s*:?\s*(\d+\.?\d*)', elem_text, re.IGNORECASE)
                            if character_match:
                                character_score = character_match.group(1)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy score breakdown: {e}")
            
            # Lấy status từ .status_cmt hoặc .fic_r_stats
            status = ""
            try:
                status_elem = review_elem.locator(".status_cmt .fic_r_stats, .fic_r_stats").first
                if status_elem.count() > 0:
                    status = status_elem.inner_text().strip()
            except:
                pass
            
            # Lấy web_chapter_id từ status (ví dụ: "chapter 57: the echo of shadows" → tìm chapter 57)
            web_chapter_id = ""
            chapter_id = None
            if status:
                try:
                    # Tìm pattern "chapter 57" hoặc "ch. 57"
                    match = re.search(r'chapter\s+(\d+)|ch\.\s*(\d+)', status, re.IGNORECASE)
                    if match:
                        chapter_num = match.group(1) or match.group(2)
                        # Tìm chapter trong DB theo story_id và order
                        if self.mongo.mongo_collection_chapters:
                            chapter = self.mongo.mongo_collection_chapters.find_one({
                                "storyId": story_id,
                                "order": chapter_num
                            })
                            if chapter:
                                chapter_id = chapter.get("chapterId") or chapter.get("id")
                                web_chapter_id = chapter.get("webChapterId", "")
                except:
                    pass
            
            # Lấy date từ div.td_top_second div.pro_item_al a
            # HTML: <div class="td_top_second"><div class="pro_item_al"><a href="...">Jul 22, 2024</a></div></div>
            time_str = None
            try:
                # ✅ Tìm div.td_top_second trước, rồi tìm div.pro_item_al a bên trong
                td_top_second = review_elem.locator("div.td_top_second").first
                if td_top_second.count() > 0:
                    pro_item_al = td_top_second.locator("div.pro_item_al").first
                    if pro_item_al.count() > 0:
                        date_elem = pro_item_al.locator("a").first
                        if date_elem.count() > 0:
                            time_str_raw = date_elem.inner_text().strip()
                            # Convert sang format: "Jul 22, 2024" → "22/7/2024, 12:00 AM"
                            if time_str_raw:
                                time_str = self._parse_review_time_to_custom_format(time_str_raw)
                                safe_print(f"        ✅ Đã lấy time từ div.td_top_second div.pro_item_al a: {time_str}")
                else:
                    safe_print(f"        🔍 DEBUG: Không tìm thấy div.td_top_second, thử fallback...")
                    # Fallback 1: thử tìm trực tiếp div.pro_item_al a
                    date_elem = review_elem.locator("div.pro_item_al a").first
                    if date_elem.count() > 0:
                        time_str_raw = date_elem.inner_text().strip()
                        if time_str_raw:
                            time_str = self._parse_review_time_to_custom_format(time_str_raw)
                            safe_print(f"        ✅ Đã lấy time từ div.pro_item_al a (fallback 1): {time_str}")
                    else:
                        # Fallback 2: Tìm tất cả a có href chứa "tab=review"
                        all_links = review_elem.locator("a[href*='tab=review']").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                # Kiểm tra xem có phải date không (có pattern tháng/ngày/năm)
                                if re.search(r'[A-Za-z]{3}\s+\d{1,2},\s+\d{4}', link_text):
                                    time_str = self._parse_review_time_to_custom_format(link_text)
                                    safe_print(f"        ✅ Đã lấy time từ a[href*='tab=review'] (fallback 2): {time_str}")
                                    break
                            except:
                                continue
                
                if not time_str:
                    safe_print(f"        ⚠️ DEBUG: Không tìm thấy time cho review {web_review_id}")
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy time: {e}")
                import traceback
                safe_print(f"        {traceback.format_exc()}")
                pass
            
            # ✅ Lấy content từ .w-comments-item-text (HTML mới)
            # HTML: <div class="w-comments-item-text 3986405"><p>...</p><p>...</p></div>
            content = ""
            try:
                # Kiểm tra xem element chính có phải là .w-comments-item-text không
                class_attr = review_elem.get_attribute("class") or ""
                if "w-comments-item-text" in class_attr:
                    content_elem = review_elem
                else:
                    content_elem = review_elem.locator(".w-comments-item-text").first
                    if content_elem.count() == 0:
                        content_elem = None
                
                if content_elem:
                    # Lấy tất cả các <p> tags bên trong
                    paragraphs = content_elem.locator("p").all()
                    if paragraphs:
                        text_parts = []
                        for para in paragraphs:
                            try:
                                para_text = para.inner_text().strip()
                                # Bỏ qua "Read More" paragraph
                                if para_text and "read more" not in para_text.lower() and para_text:
                                    text_parts.append(para_text)
                            except:
                                continue
                        if text_parts:
                            content = "\n\n".join(text_parts)
                    
                    # Nếu không có paragraphs hoặc không lấy được, thử lấy HTML và convert
                    if not content:
                        # Xóa phần "Read More" nếu có
                        read_more = content_elem.locator(".read-more-review").first
                        if read_more.count() > 0:
                            # Lấy HTML trước phần Read More
                            html_content = content_elem.evaluate("""
                                el => {
                                    const readMore = el.querySelector('.read-more-review');
                                    if (readMore) {
                                        readMore.remove();
                                    }
                                    return el.innerHTML;
                                }
                            """)
                        else:
                            html_content = content_elem.inner_html()
                        
                        from src.utils import convert_html_to_formatted_text
                        content = convert_html_to_formatted_text(html_content)
                else:
                    # Fallback: thử selector cũ
                    content_elem = review_elem.locator(".revtext, .review-content").first
                    if content_elem.count() > 0:
                        from src.utils import convert_html_to_formatted_text
                        html_content = content_elem.inner_html()
                        content = convert_html_to_formatted_text(html_content)
                    else:
                        # Fallback cuối: lấy text thuần
                        content = review_elem.inner_text().strip()
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy review content: {e}")
                import traceback
                safe_print(f"        {traceback.format_exc()}")
            
            # Lấy likes từ .rev_bar (ví dụ: "3 Likes · Like" → "3")
            likes = ""
            try:
                likes_elem = review_elem.locator(".rev_bar").first
                if likes_elem.count() > 0:
                    likes_text = likes_elem.inner_text().strip()
                    # Parse: "3 Likes · Like" → "3"
                    match = re.search(r'(\d+)\s+Likes?', likes_text)
                    if match:
                        likes = match.group(1)
            except:
                pass
            
            # Tạo score_id và lưu score (luôn tạo score để link với review)
            score_id = None
            # Luôn tạo score_id để link với review, ngay cả khi không có overall_score
            score_id = generate_id()
            # Lưu score với reviewId để link đến review
            self.mongo.save_score(
                score_id=score_id,
                overall_score=overall_score if overall_score else "",
                style_score=style_score if style_score else "",
                story_score=story_score if story_score else "",
                grammar_score=grammar_score if grammar_score else "",
                character_score=character_score if character_score else "",
                review_id=review_id  # Link score đến review
            )
            
            # Lấy title từ div.status_cmt span.fic_r_stats#stat{web_review_id}
            # HTML: <div class="status_cmt" title="ch 40: scattered to the winds."><span class="fic_r_stats" id="stat2853508">ch 40: scattered to the winds.</span></div>
            title = ""
            try:
                if web_review_id:
                    # ✅ Ưu tiên: Tìm span#stat{web_review_id} trong div.status_cmt
                    status_cmt = review_elem.locator("div.status_cmt").first
                    if status_cmt.count() > 0:
                        title_elem = status_cmt.locator(f"span#stat{web_review_id}").first
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            safe_print(f"        ✅ Đã lấy title từ div.status_cmt span#stat{web_review_id}: {title}")
                    
                    # Fallback 1: Tìm trực tiếp span#stat{web_review_id}
                    if not title:
                        title_elem = review_elem.locator(f"span#stat{web_review_id}").first
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            safe_print(f"        ✅ Đã lấy title từ span#stat{web_review_id} (fallback 1): {title}")
                    
                    # Fallback 2: Tìm span.fic_r_stats#stat{web_review_id}
                    if not title:
                        title_elem = review_elem.locator(f"span.fic_r_stats#stat{web_review_id}").first
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            safe_print(f"        ✅ Đã lấy title từ span.fic_r_stats#stat{web_review_id} (fallback 2): {title}")
                
                # Fallback 3: Tìm span.fic_r_stats bất kỳ trong review element
                if not title:
                    title_elem = review_elem.locator("div.status_cmt span.fic_r_stats").first
                    if title_elem.count() > 0:
                        title = title_elem.inner_text().strip()
                        safe_print(f"        ✅ Đã lấy title từ div.status_cmt span.fic_r_stats (fallback 3): {title}")
                
                # Fallback 4: Tìm tất cả span có id bắt đầu bằng "stat"
                if not title:
                    all_stat_spans = review_elem.locator("span[id^='stat']").all()
                    for span in all_stat_spans:
                        try:
                            span_text = span.inner_text().strip()
                            if span_text:
                                title = span_text
                                safe_print(f"        ✅ Đã lấy title từ span[id^='stat'] (fallback 4): {title}")
                                break
                        except:
                            continue
                
                if not title:
                    safe_print(f"        ⚠️ DEBUG: Không tìm thấy title cho review {web_review_id}")
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy title: {e}")
                import traceback
                safe_print(f"        {traceback.format_exc()}")
                pass
            
            # Lấy website_id từ mongo handler
            website_id = self.mongo.scribblehub_website_id if self.mongo.scribblehub_website_id else ""
            
            review_data = {
                "reviewId": review_id,
                "webReviewId": web_review_id,
                "title": title if title else None,  # Set None nếu không có title
                "time": time_str,
                "content": content,
                "userId": user_id,
                "chapterId": chapter_id,
                "storyId": story_id,
                "scoreId": score_id if score_id else None,  # Set None thay vì empty string
                "isReviewSwap": False,
                "websiteId": website_id,
                "isDeleted": False  # Đảm bảo có field isDeleted
            }
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None
    
    def _parse_review_time_to_custom_format(self, time_str: str):
        """
        Parse time string từ format "Jul 22, 2024" sang format "22/7/2024, 4:47 AM"
        
        Args:
            time_str: Time string (ví dụ: "Jul 22, 2024" hoặc "May 9, 2023 09:41 AM")
        
        Returns:
            Custom format string (ví dụ: "22/7/2024, 4:47 AM") hoặc None nếu không parse được
        """
        if not time_str or not time_str.strip():
            return None
        
        try:
            time_str = time_str.strip()
            
            # Thử parse với format có giờ trước: "May 9, 2023 09:41 AM"
            formats_with_time = [
                "%b %d, %Y %I:%M %p",      # "May 9, 2023 09:41 AM"
                "%b %d, %Y %I:%M:%S %p",  # "May 9, 2023 09:41:00 AM"
                "%B %d, %Y %I:%M %p",     # "May 9, 2023 09:41 AM" (full month name)
                "%B %d, %Y %I:%M:%S %p",  # "May 9, 2023 09:41:00 AM" (full month name)
            ]
            
            # Thử parse với format chỉ có date: "Jul 22, 2024"
            formats_date_only = [
                "%b %d, %Y",      # "Jul 22, 2024"
                "%B %d, %Y",      # "July 22, 2024" (full month name)
            ]
            
            dt = None
            has_time = False
            
            # Thử parse với format có giờ trước
            for fmt in formats_with_time:
                try:
                    dt = datetime.strptime(time_str, fmt)
                    has_time = True
                    break
                except ValueError:
                    continue
            
            # Nếu không có giờ, thử parse chỉ date
            if not dt:
                for fmt in formats_date_only:
                    try:
                        dt = datetime.strptime(time_str, fmt)
                        has_time = False
                        break
                    except ValueError:
                        continue
            
            if not dt:
                # Nếu không parse được, trả về None
                safe_print(f"        ⚠️ Không thể parse time: {time_str}")
                return None
            
            # Convert sang format "d/M/yyyy, h:mm AM/PM" (không zero-padding)
            # Format: "22/7/2024, 4:47 AM" hoặc "25/5/2020, 4:47 AM"
            day = dt.day
            month = dt.month
            year = dt.year
            
            if has_time:
                # Có giờ: format "d/M/yyyy, h:mm AM/PM"
                hour = dt.hour
                minute = dt.minute
                am_pm = "AM" if hour < 12 else "PM"
                hour_12 = hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                custom_str = f"{day}/{month}/{year}, {hour_12}:{minute:02d} {am_pm}"
            else:
                # Không có giờ: format "d/M/yyyy, 12:00 AM" (giờ mặc định)
                custom_str = f"{day}/{month}/{year}, 12:00 AM"
            
            return custom_str
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review time: {e}")
            return None
    
    def _parse_review_time(self, time_str: str):
        """
        Parse time string từ format "May 9, 2023 09:41 AM" sang ISO format "2023-05-09T09:41:00.000Z"
        (Giữ lại hàm này để tương thích với code cũ nếu cần)
        
        Args:
            time_str: Time string (ví dụ: "May 9, 2023 09:41 AM")
        
        Returns:
            ISO format string (ví dụ: "2023-05-09T09:41:00.000Z") hoặc None nếu không parse được
        """
        if not time_str or not time_str.strip():
            return None
        
        try:
            time_str = time_str.strip()
            
            formats = [
                "%b %d, %Y %I:%M %p",      # "May 9, 2023 09:41 AM"
                "%b %d, %Y %I:%M:%S %p",  # "May 9, 2023 09:41:00 AM"
                "%B %d, %Y %I:%M %p",     # "May 9, 2023 09:41 AM" (full month name)
                "%B %d, %Y %I:%M:%S %p",  # "May 9, 2023 09:41:00 AM" (full month name)
            ]
            
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            
            if not dt:
                safe_print(f"        ⚠️ Không thể parse time: {time_str}")
                return None
            
            iso_str = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            return iso_str
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review time: {e}")
            return None

