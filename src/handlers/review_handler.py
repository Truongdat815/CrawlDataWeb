"""
Review handler - xử lý review scraping
"""
import time
import re
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text, goto_with_retry


class ReviewHandler:
    """Handler cho review scraping"""
    
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
    
    def get_max_review_page(self, story_url):
        """Lấy số trang reviews tối đa từ pagination"""
        try:
            base_url = story_url.split('?')[0]
            current_url = self.page.url.split('?')[0] if self.page else ""
            
            if base_url not in current_url:
                goto_with_retry(self.page, base_url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name="Review")
                time.sleep(2)
            
            # Click vào tab Reviews nếu cần
            try:
                reviews_tab = self.page.locator("a[href*='reviews'], button:has-text('Reviews'), .nav-tabs a:has-text('Reviews')").first
                if reviews_tab.count() > 0:
                    reviews_tab.click()
                    time.sleep(3)
            except:
                pass
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1
            pagination_selectors = [
                "ul.pagination",
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
                    safe_print(f"        📄 Tìm thấy {max_page} trang reviews")
                else:
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang reviews: {e}")
            return 1
    
    def scrape_reviews_from_page(self, page_url, story_id):
        """
        Lấy reviews từ một trang cụ thể
        """
        reviews = []
        try:
            goto_with_retry(self.page, page_url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name="Review")
            time.sleep(2)
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Click vào tab Reviews nếu cần (cho trang đầu tiên)
            if "reviews=" not in page_url or "reviews=1" in page_url:
                try:
                    reviews_tab = self.page.locator("a[href*='reviews'], button:has-text('Reviews'), .nav-tabs a:has-text('Reviews')").first
                    if reviews_tab.count() > 0:
                        reviews_tab.click()
                        time.sleep(3)
                except:
                    pass
            
            review_selectors = [
                ".review",
                ".review-item",
                ".review-container",
                "[class*='review']",
                ".rating-review"
            ]
            
            review_elements = []
            for selector in review_selectors:
                try:
                    elements = self.page.locator(selector).all()
                    if elements:
                        review_elements = elements
                        break
                except:
                    continue
            
            for review_elem in review_elements:
                try:
                    review_id_attr = review_elem.get_attribute("id") or None
                    web_review_id = None
                    if review_id_attr and review_id_attr.startswith("review-"):
                        web_review_id = review_id_attr.replace("review-", "")
                    
                    # Check review đã có chưa theo cặp (webReviewId, storyId)
                    if web_review_id and story_id and self.mongo.is_review_scraped(web_review_id, story_id):
                        continue
                    
                    review_data = self.parse_single_review(review_elem, story_id)
                    if review_data:
                        reviews.append(review_data)
                        self.mongo.save_review(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    continue
            
            return reviews
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy reviews từ trang: {e}")
            return []
    
    def scrape_reviews(self, story_url, story_id):
        """
        Lấy tất cả reviews từ TẤT CẢ các trang phân trang
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        try:
            safe_print("      📝 Đang lấy reviews từ trang story...")
            
            goto_with_retry(self.page, story_url, config.TIMEOUT, max_retries=3, retry_delay=5, context_name="Review")
            time.sleep(2)
            
            # Click vào tab Reviews
            try:
                reviews_tab = self.page.locator("a[href*='reviews'], button:has-text('Reviews'), .nav-tabs a:has-text('Reviews')").first
                if reviews_tab.count() > 0:
                    reviews_tab.click()
                    time.sleep(3)
            except:
                pass
            
            max_page = self.get_max_review_page(story_url)
            all_reviews = []
            
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang reviews {page_num}/{max_page}...")
                
                if page_num == 1:
                    base_url = story_url.split('?')[0]
                    # Thêm sorting=top&reviews=1 cho trang đầu
                    if '?' in story_url:
                        existing_params = story_url.split('?', 1)[1]
                        params_list = []
                        for param in existing_params.split('&'):
                            if not param.startswith('reviews=') and not param.startswith('sorting='):
                                params_list.append(param)
                        if params_list:
                            other_params = '&'.join(params_list)
                            page_url = f"{base_url}?{other_params}&sorting=top&reviews={page_num}"
                        else:
                            page_url = f"{base_url}?sorting=top&reviews={page_num}"
                    else:
                        page_url = f"{base_url}?sorting=top&reviews={page_num}"
                else:
                    base_url = story_url.split('?')[0]
                    if '?' in story_url:
                        existing_params = story_url.split('?', 1)[1]
                        params_list = []
                        for param in existing_params.split('&'):
                            if not param.startswith('reviews=') and not param.startswith('sorting='):
                                params_list.append(param)
                        if params_list:
                            other_params = '&'.join(params_list)
                            page_url = f"{base_url}?{other_params}&sorting=top&reviews={page_num}"
                        else:
                            page_url = f"{base_url}?sorting=top&reviews={page_num}"
                    else:
                        page_url = f"{base_url}?sorting=top&reviews={page_num}"
                
                if page_num > 1:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                
                page_reviews = self.scrape_reviews_from_page(page_url, story_id)
                all_reviews.extend(page_reviews)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_reviews)} reviews")
                
                if page_num < max_page:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_reviews)} reviews từ {max_page} trang")
            return all_reviews
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy reviews: {e}")
            return []
    
    def parse_single_review(self, review_elem, story_id):
        """
        Parse một review element thành dictionary theo schema
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        try:
            web_review_id = None
            try:
                review_id_attr = review_elem.get_attribute("id") or None
                if review_id_attr and review_id_attr.startswith("review-"):
                    web_review_id = review_id_attr.replace("review-", "")
            except:
                pass
            
            review_id = generate_id()
            
            title = None
            try:
                title_elem = review_elem.locator("h3, h4, .review-title, [class*='title']").first
                if title_elem.count() > 0:
                    title = title_elem.inner_text().strip()
            except:
                pass
            
            # Lấy user từ review element
            # Truyền page vào để tự động scrape profile
            user_id = self.user_handler.scrape_and_save_user_from_element(
                review_elem,
                selectors=["a[href*='/profile/']", ".username", ".reviewer-name", "[class*='username']"],
                page=self.page
            )
            
            chapter_url = None
            try:
                # Lấy chapter link từ review header - theo HTML mẫu: <a href="/fiction/chapter/371224">100. Sacrifice</a>
                chapter_elem = review_elem.locator("h5.bold.font-red-sunglo a[href*='/chapter/']").first
                if chapter_elem.count() == 0:
                    # Fallback: thử các selector khác
                    chapter_elem = review_elem.locator("a[href*='/chapter/'], .chapter-link, [class*='chapter']").first
                
                if chapter_elem.count() > 0:
                    href = chapter_elem.get_attribute("href") or None
                    if href and "/chapter/" in href:
                        # Tạo full URL từ href
                        from src import config
                        if href.startswith("/"):
                            chapter_url = config.BASE_URL + href
                        elif href.startswith("http"):
                            chapter_url = href
                        else:
                            chapter_url = config.BASE_URL + "/" + href
            except:
                pass
            
            chapter_id = None
            if chapter_url:
                existing_chapter = self.mongo.get_chapter_by_url(chapter_url)
                if existing_chapter:
                    # Sửa: Dùng "chapterId" thay vì "id" (đây là khóa chính trong DB)
                    chapter_id = existing_chapter.get("chapterId")
            
            time_str = None
            try:
                # Tìm time element trong review-meta hoặc trực tiếp trong review
                time_elem = review_elem.locator(".review-meta time, time").first
                if time_elem.count() > 0:
                    datetime_attr = time_elem.get_attribute("datetime")
                    if datetime_attr:
                        from src.utils import parse_and_format_datetime
                        time_str = parse_and_format_datetime(datetime_attr)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi parse review time: {e}")
                pass
            
            content = None
            try:
                review_inner = review_elem.locator(".review-inner").first
                if review_inner.count() > 0:
                    html_content = review_inner.inner_html()
                    content = convert_html_to_formatted_text(html_content)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy review content: {e}")
                pass
            
            scores = {
                "overall_score": "",
                "style_score": "",
                "story_score": "",
                "grammar_score": "",
                "character_score": ""
            }
            
            try:
                try:
                    overall_container = review_elem.locator(".overall-score-container").first
                    if overall_container.count() > 0:
                        overall_score_elem = overall_container.locator("div[aria-label*='stars']").first
                        if overall_score_elem.count() > 0:
                            aria_label = overall_score_elem.get_attribute("aria-label") or None
                            if aria_label:
                                numbers = re.findall(r'\d+\.?\d*', aria_label)
                                if numbers:
                                    scores["overall_score"] = numbers[0]
                except:
                    pass
                
                try:
                    advanced_scores = review_elem.locator(".advanced-score").all()
                    for advanced_score in advanced_scores:
                        try:
                            label_elem = advanced_score.locator("div[aria-label*='Score']").first
                            if label_elem.count() > 0:
                                label_text = label_elem.get_attribute("aria-label") or None
                                if label_text:
                                    label_lower = label_text.lower()
                                    
                                    value_elem = advanced_score.locator("div[aria-label*='stars']").first
                                    if value_elem.count() > 0:
                                        aria_label = value_elem.get_attribute("aria-label") or None
                                        if aria_label:
                                            numbers = re.findall(r'\d+\.?\d*', aria_label)
                                            if numbers:
                                                score_value = numbers[0]
                                                
                                                if "style" in label_lower:
                                                    scores["style_score"] = score_value
                                                elif "story" in label_lower:
                                                    scores["story_score"] = score_value
                                                elif "grammar" in label_lower:
                                                    scores["grammar_score"] = score_value
                                                elif "character" in label_lower:
                                                    scores["character_score"] = score_value
                        except:
                            continue
                except:
                    pass
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi lấy scores từ aria-label: {e}")
                pass
            
            score_id = generate_id()
            
            is_review_swap = False
            try:
                swap_icon = review_elem.locator("i[data-title='Review Swap']").first
                if swap_icon.count() > 0:
                    is_review_swap = True
            except:
                pass
            
            # lấy website_id của Royal Road
            website_id = self.mongo.royal_road_website_id if self.mongo.royal_road_website_id else None
            
            review_data = {
                "reviewId": review_id,
                "webReviewId": web_review_id,
                "title": title,
                "time": time_str,
                "content": content,
                "userId": user_id,
                "chapterId": chapter_id,
                "storyId": story_id,
                "scoreId": score_id,
                "isReviewSwap": is_review_swap,
                "websiteId": website_id,
                "isDeleted": False
            }
            
            if score_id:
                self.mongo.save_score(
                    score_id=score_id,
                    overall_score=scores.get("overall_score") or None,
                    style_score=scores.get("style_score") or None,
                    story_score=scores.get("story_score") or None,
                    grammar_score=scores.get("grammar_score") or None,
                    character_score=scores.get("character_score") or None,
                    review_id=review_id
                )
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None

