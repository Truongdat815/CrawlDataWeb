"""
Review handler - xử lý review scraping
"""
import time
import re
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
    
    def scrape_reviews(self, story_url, story_id):
        """
        Lấy tất cả reviews từ trang story
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        reviews = []
        try:
            safe_print("      📝 Đang lấy reviews từ trang story...")
            
            self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            time.sleep(2)
            
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
            
            # ✅ Tìm reviews theo selector mới: .w-comments-item
            review_elements = self.page.locator(".w-comments-item").all()
            
            if not review_elements:
                safe_print("      ℹ️ Không tìm thấy reviews với selector .w-comments-item")
                return []
            
            safe_print(f"      ✅ Tìm thấy {len(review_elements)} reviews")
            
            # Lấy rating distribution (bar chart) - có thể lưu vào story_info sau
            rating_distribution = self._scrape_rating_distribution()
            if rating_distribution:
                safe_print(f"      📊 Rating distribution: {rating_distribution}")
            
            for review_elem in review_elements:
                try:
                    # Lấy web_review_id từ id attribute (ví dụ: id="comment-3879341" → "3879341")
                    review_id_attr = review_elem.get_attribute("id") or ""
                    web_review_id = ""
                    if review_id_attr.startswith("comment-"):
                        web_review_id = review_id_attr.replace("comment-", "")
                    elif review_id_attr:
                        web_review_id = review_id_attr
                    
                    if web_review_id and self.mongo.is_review_scraped(web_review_id):
                        continue
                    
                    review_data = self.parse_single_review(review_elem, story_id)
                    if review_data:
                        reviews.append(review_data)
                        # ✅ Chỉ lưu review nếu có dữ liệu hợp lệ
                        self.mongo.save_review(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    continue
            
            # ✅ Chỉ in log nếu có reviews
            if reviews:
                safe_print(f"      ✅ Đã lấy được {len(reviews)} reviews")
            else:
                safe_print(f"      ℹ️ Không có reviews để lưu")
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
    
    def parse_single_review(self, review_elem, story_id):
        """
        Parse một review element thành dictionary theo schema
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK), likes, status
        """
        try:
            # Lấy web_review_id từ id attribute (ví dụ: id="comment-3879341" → "3879341")
            web_review_id = ""
            try:
                review_id_attr = review_elem.get_attribute("id") or ""
                if review_id_attr.startswith("comment-"):
                    web_review_id = review_id_attr.replace("comment-", "")
                elif review_id_attr:
                    web_review_id = review_id_attr
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
            
            # Lấy overall_score từ stars (đếm số .fa-star filled)
            overall_score = ""
            try:
                star_icons = review_elem.locator("i.userreview.fa-star").all()
                filled_stars = len(star_icons)
                if filled_stars > 0:
                    overall_score = str(filled_stars)
            except:
                pass
            
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
                                "story_id": story_id,
                                "order": chapter_num
                            })
                            if chapter:
                                chapter_id = chapter.get("chapter_id") or chapter.get("id")
                                web_chapter_id = chapter.get("web_chapter_id", "")
                except:
                    pass
            
            # Lấy date từ .pro_item_al a
            time_str = ""
            try:
                date_elem = review_elem.locator(".pro_item_al a").first
                if date_elem.count() > 0:
                    time_str = date_elem.inner_text().strip()
            except:
                pass
            
            # Lấy content từ .w-comments-item-text
            content = ""
            try:
                content_elem = review_elem.locator(".w-comments-item-text").first
                if content_elem.count() > 0:
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
                    
                    content = convert_html_to_formatted_text(html_content)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy review content: {e}")
            
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
            
            # Tạo score_id và lưu score
            score_id = None
            if overall_score:
                score_id = generate_id()
                self.mongo.save_score(
                    score_id=score_id,
                    overall_score=overall_score,
                    style_score="",
                    story_score="",
                    grammar_score="",
                    character_score=""
                )
            
            # Lấy website_id từ mongo handler
            website_id = self.mongo.scribblehub_website_id if self.mongo.scribblehub_website_id else ""
            
            review_data = {
                "review_id": review_id,
                "web_review_id": web_review_id,
                "title": "",  # Không có title trong cấu trúc mới
                "time": time_str,
                "content": content,
                "user_id": user_id,
                "chapter_id": chapter_id,
                "story_id": story_id,
                "score_id": score_id if score_id else "",
                "is_review_swap": False,
                "website_id": website_id,
                "status": status,  # Thêm status
                "likes": likes  # Thêm likes
            }
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None

