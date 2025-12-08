"""
Review handler - xử lý review scraping
"""
import time
import re
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text


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
    
    def scrape_reviews(self, story_url, story_id):
        """
        Lấy tất cả reviews từ trang story
        Schema: review id, title, time, content, user id (FK), chapter id (FK), story id (FK), score id (FK)
        """
        reviews = []
        try:
            safe_print("      📝 Đang lấy reviews từ trang story...")
            
            self.page.goto(story_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
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
                        safe_print(f"      ✅ Tìm thấy {len(elements)} reviews với selector: {selector}")
                        break
                except:
                    continue
            
            if not review_elements:
                try:
                    reviews_tab = self.page.locator("a[href*='reviews'], button:has-text('Reviews'), .nav-tabs a:has-text('Reviews')").first
                    if reviews_tab.count() > 0:
                        reviews_tab.click()
                        time.sleep(3)
                        for selector in review_selectors:
                            try:
                                elements = self.page.locator(selector).all()
                                if elements:
                                    review_elements = elements
                                    break
                            except:
                                continue
                except:
                    pass
            
            for review_elem in review_elements:
                try:
                    review_id_attr = review_elem.get_attribute("id") or None
                    web_review_id = None
                    if review_id_attr and review_id_attr.startswith("review-"):
                        web_review_id = review_id_attr.replace("review-", "")
                    
                    if web_review_id and self.mongo.is_review_scraped(web_review_id):
                        continue
                    
                    review_data = self.parse_single_review(review_elem, story_id)
                    if review_data:
                        reviews.append(review_data)
                        self.mongo.save_review(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    continue
            
            safe_print(f"      ✅ Đã lấy được {len(reviews)} reviews")
            return reviews
            
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
            
            web_chapter_id = None
            try:
                # Lấy chapter link từ review header - theo HTML mẫu: <a href="/fiction/chapter/371224">100. Sacrifice</a>
                chapter_elem = review_elem.locator("h5.bold.font-red-sunglo a[href*='/chapter/']").first
                if chapter_elem.count() == 0:
                    # Fallback: thử các selector khác
                    chapter_elem = review_elem.locator("a[href*='/chapter/'], .chapter-link, [class*='chapter']").first
                
                if chapter_elem.count() > 0:
                    href = chapter_elem.get_attribute("href") or None
                    if href and "/chapter/" in href:
                        web_chapter_id = href.split("/chapter/")[1].split("/")[0]
            except:
                pass
            
            chapter_id = None
            if web_chapter_id:
                existing_chapter = self.mongo.get_chapter_by_web_id(web_chapter_id)
                if existing_chapter:
                    # Sửa: Dùng "chapterId" thay vì "id" (đây là khóa chính trong DB)
                    chapter_id = existing_chapter.get("chapterId")
            
            time_str = None
            try:
                time_elem = review_elem.locator("time, .timestamp, [class*='time'], [class*='date']").first
                if time_elem.count() > 0:
                    time_str = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
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
                "websiteId": website_id
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

