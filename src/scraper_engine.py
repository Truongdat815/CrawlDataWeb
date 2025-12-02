import time
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from src import config, utils

# Import MongoDB
try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

# Helper function để print an toàn với encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        # Thử print bình thường
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Nếu lỗi encoding, encode lại thành ASCII-safe
        message = ' '.join(str(arg) for arg in args)
        # Thay thế emoji và ký tự đặc biệt
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

class RoyalRoadScraper:
    def __init__(self, max_workers=None):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.max_workers = max_workers or config.MAX_WORKERS
        
        # Khởi tạo MongoDB client nếu được bật
        self.mongo_client = None
        self.mongo_db = None
        # Khởi tạo các collections riêng biệt
        self.mongo_collections = {}
        if config.MONGODB_ENABLED and MONGODB_AVAILABLE:
            try:
                self.mongo_client = MongoClient(config.MONGODB_URI)
                self.mongo_db = self.mongo_client[config.MONGODB_DB_NAME]
                # Khởi tạo tất cả các collections
                self.mongo_collections = {
                    "stories": self.mongo_db[config.MONGODB_COLLECTION_STORIES],
                    "chapters": self.mongo_db[config.MONGODB_COLLECTION_CHAPTERS],
                    "comments": self.mongo_db[config.MONGODB_COLLECTION_COMMENTS],
                    "reviews": self.mongo_db[config.MONGODB_COLLECTION_REVIEWS],
                    "scores": self.mongo_db[config.MONGODB_COLLECTION_SCORES],
                    "users": self.mongo_db[config.MONGODB_COLLECTION_USERS],
                }
                # Giữ lại collection cũ để tương thích
                self.mongo_collection = self.mongo_db[config.MONGODB_COLLECTION_FICTIONS]
                safe_print("✅ Đã kết nối MongoDB với các collections: stories, chapters, comments, reviews, scores, users")
            except Exception as e:
                safe_print(f"⚠️ Không thể kết nối MongoDB: {e}")
                safe_print("   Tiếp tục lưu vào file JSON...")
                self.mongo_client = None

    def start(self):
        """Khởi động trình duyệt"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=config.HEADLESS)
        # Thêm user agent và viewport để tránh bị chặn
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        self.page = self.context.new_page()
        safe_print("✅ Bot đã khởi động!")

    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.mongo_client:
            self.mongo_client.close()
            safe_print("✅ Đã đóng kết nối MongoDB")
        safe_print("zzz Bot đã tắt.")

    def scrape_webnovel_fiction(self, fiction_url, max_chapters=None):
        """
        Cào một bộ truyện Webnovel (single book URL)
        Args:
            fiction_url: URL của bộ truyện trên Webnovel
            max_chapters: Số chương tối đa muốn cào (None = lấy hết)
        """
        safe_print(f"🌍 Đang truy cập truyện Webnovel: {fiction_url}")
        self.page.goto(fiction_url, timeout=config.TIMEOUT)
        # Đợi page load xong (wait cho networkidle)
        self.page.wait_for_load_state("networkidle")
        time.sleep(3)
        safe_print(f"    ✅ Page đã load xong, title: {self.page.title()}")
        
        # Lấy ID truyện từ URL (ví dụ: _34078380808505505)
        fiction_id = ""
        try:
            match = re.search(r"_(\d{10,})$", fiction_url)
            if match:
                fiction_id = match.group(1)
            else:
                match = re.search(r"(\d{10,})", fiction_url)
                if match:
                    fiction_id = match.group(1)
        except:
            fiction_id = "unknown"
        
        safe_print("... Đang lấy thông tin chung")
        
        # Lấy title (Webnovel dùng h1 hoặc h2 trong meta hoặc page title)
        title = ""
        try:
            # Thử nhiều selector
            title_el = self.page.locator("h1").first
            if title_el.count() > 0:
                title = title_el.inner_text().strip()
            if not title:
                # Fallback: lấy từ page title
                title = self.page.title().split('|')[0].strip()
            safe_print(f"    ✅ Title: {title}")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy title: {e}")
            title = "Unknown Title"
        
        # Lấy author (Webnovel có link author với class/href profile)
        author = ""
        try:
            # Tìm trong phần tử chứa "Author:"
            author_el = self.page.locator("a[href*='/profile/']").first
            if author_el.count() > 0:
                author = author_el.inner_text().strip()
            safe_print(f"    ✅ Author: {author}")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy author: {e}")
            author = "Unknown Author"
        
        # Lấy cover image (Webnovel: img có src chứa 'bookcover' hoặc 'book-pic')
        img_url_raw = None
        try:
            img_el = self.page.locator("img[src*='bookcover'], img[src*='book-pic'], img.book-cover").first
            if img_el.count() > 0:
                img_url_raw = img_el.get_attribute("src")
                # Thêm https: nếu URL bắt đầu bằng //
                if img_url_raw and img_url_raw.startswith("//"):
                    img_url_raw = "https:" + img_url_raw
                safe_print(f"    ✅ Cover: {img_url_raw[:80]}...")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy cover: {e}")
        
        local_img_path = None
        if img_url_raw:
            local_img_path = utils.download_image(img_url_raw, fiction_id)
            if local_img_path:
                safe_print(f"    ✅ Đã tải cover về: {local_img_path}")
        
        # Lấy genre (từ link category như "Anime & Comics")
        genre = ""
        try:
            # Tìm trong span có icon book (thường bên cạnh chapter count)
            # Pattern: <span>📕 Anime & Comics</span> hoặc link <a>Anime & Comics</a>
            genre_candidates = [
                "span._ml a",  # Link trong span._ml
                "a[href*='/category/']",  # Link có /category/ trong href
                "span:has-text('Anime') a",  # Span chứa text "Anime" và có link bên trong
                ".det-info a[href*='/']"  # Fallback: link trong det-info
            ]
            
            for selector in genre_candidates:
                genre_el = self.page.locator(selector).first
                if genre_el.count() > 0:
                    genre_text = genre_el.inner_text().strip()
                    # Kiểm tra xem có phải genre hợp lệ không (không phải number hoặc quá ngắn)
                    if genre_text and len(genre_text) > 2 and not genre_text.isdigit():
                        genre = genre_text
                        break
            
            if not genre:
                # Fallback: tìm text pattern "XXX Chapters" gần đó và lấy text trước đó
                page_text = self.page.locator("body").inner_text()
                genre_match = re.search(r"([A-Za-z &]+)\s+\d+\s+Chapters", page_text)
                if genre_match:
                    genre = genre_match.group(1).strip()
            
            safe_print(f"    ✅ Genre: {genre}")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy genre: {e}")
        
        # Lấy tags từ div.m-tags > p.m-tag (Webnovel structure)
        tags = []
        try:
            # Tìm div.m-tags container
            tags_container = self.page.locator("div.m-tags").first
            if tags_container.count() > 0:
                # Lấy tất cả p.m-tag trong container
                tag_elements = tags_container.locator("p.m-tag").all()
                for tag_el in tag_elements:
                    tag_text = tag_el.inner_text().strip()
                    # Clean tag text (bỏ # prefix nếu có)
                    if tag_text:
                        clean_tag = tag_text.lstrip('#').strip()
                        if clean_tag and clean_tag not in tags:
                            tags.append(clean_tag)
            safe_print(f"    ✅ Tags: {tags}")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy tags: {e}")
        
        # Lấy description/synopsis (Webnovel: thường trong section hoặc div có text "Synopsis")
        description = ""
        try:
            # Tìm các paragraph trong phần synopsis (thường có class _synopsis hoặc nằm trong section.j_synopsis)
            desc_paras = self.page.locator("div._synopsis p, section.j_synopsis p").all()
            if desc_paras:
                description = "\n".join([p.inner_text().strip() for p in desc_paras if p.inner_text().strip()])
                safe_print(f"    ✅ Description: {description[:100]}...")
            else:
                # Fallback: tìm phần Synopsis
                desc_container = self.page.locator("text=Synopsis").locator('..').first
                if desc_container.count() > 0:
                    desc_text = desc_container.inner_text()
                    # Loại bỏ chữ "Synopsis" và lấy chỉ phần đầu (trước Tags/Fans)
                    lines = [line.strip() for line in desc_text.split('\n') if line.strip()]
                    # Lọc bỏ "Synopsis" và dừng ở "Tags", "Fans", "General Audiences", etc.
                    filtered_lines = []
                    for line in lines:
                        if line.lower() in ['synopsis', 'tags', 'fans', 'see all', 'general audiences', 'weekly power status']:
                            continue
                        if line.startswith('#') or 'Contributed' in line or 'Power' in line:
                            break
                        filtered_lines.append(line)
                    description = "\n".join(filtered_lines).strip()
                    safe_print(f"    ✅ Description: {description[:100]}...")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy description: {e}")
        
        # Lấy stats (views, chapters count, etc.)
        views_text = ""
        chapters_count_text = ""
        try:
            # Tìm text chứa "Views" hoặc số lượt xem
            page_text = self.page.locator("body").inner_text()
            view_match = re.search(r"([\d,\.KMkm]+)\s*Views?", page_text, re.I)
            if view_match:
                views_text = view_match.group(1)
            
            # Tìm text chứa "Chapters" hoặc số chương
            chap_match = re.search(r"(\d+[\d,\.]*)\s*Chapters?", page_text, re.I)
            if chap_match:
                chapters_count_text = chap_match.group(1)
        except:
            pass
        
        # Lấy total reviews và ratings
        total_reviews = 0
        total_rating = 0.0
        try:
            # Tìm rating chính (4.87) - thường hiển thị với stars gần title
            # Pattern 1: Tìm số thập phân có 1-2 chữ số sau dấu phẩy, theo sau bởi "(XXX ratings)"
            rating_match = re.search(r"(\d+\.\d{1,2})\s*\((\d+)\s*ratings?\)", page_text, re.I)
            if rating_match:
                total_rating = float(rating_match.group(1))
                total_reviews = int(rating_match.group(2))  # XXX ratings
            else:
                # Pattern 2: Fallback - tìm "XXX Reviews" riêng
                reviews_match = re.search(r"(\d+)\s*Reviews?", page_text, re.I)
                if reviews_match:
                    total_reviews = int(reviews_match.group(1))
                
                # Tìm rating (số thập phân)
                rating_match2 = re.search(r"(\d+\.\d+)", page_text)
                if rating_match2:
                    total_rating = float(rating_match2.group(1))
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy rating: {e}")
        
        # Lấy scores chi tiết (5 categories) từ review section
        scores = {
            "writing_quality": "",
            "stability_of_updates": "",
            "story_development": "",
            "character_design": "",
            "world_background": ""
        }
        try:
            # Tìm review section có 5 score categories
            score_items = self.page.locator("li:has(strong)").all()
            for item in score_items:
                try:
                    label = item.locator("strong").inner_text().strip().lower()
                    # Đếm số sao (svg với class _on)
                    stars = item.locator("svg.g_star._on, span.g_star svg._on").count()
                    
                    if "writing quality" in label:
                        scores["writing_quality"] = str(stars)
                    elif "stability" in label:
                        scores["stability_of_updates"] = str(stars)
                    elif "story" in label:
                        scores["story_development"] = str(stars)
                    elif "character" in label:
                        scores["character_design"] = str(stars)
                    elif "world" in label or "background" in label:
                        scores["world_background"] = str(stars)
                except:
                    continue
            safe_print(f"    ✅ Scores: {scores}")
            safe_print(f"    ✅ Reviews: {total_reviews}, Rating: {total_rating}")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy scores: {e}")
        
        # Lấy story-level comments (reviews/paragraphs từ trang fiction)
        story_comments = []
        try:
            safe_print("    💬 Đang lấy story-level comments...")
            
            # Webnovel có thể có tab "Reviews" cần click để show
            try:
                # Tìm và click vào tab/button Reviews
                review_tab = self.page.locator("button:has-text('Review'), a:has-text('Review'), div:has-text('Reviews')").first
                if review_tab.count() > 0:
                    safe_print("    🔘 Clicking Reviews tab...")
                    review_tab.click()
                    time.sleep(2)
            except:
                pass
            
            # Scroll xuống review section
            try:
                reviews_heading = self.page.locator("h3:has-text('Review'), h2:has-text('Review')").first
                if reviews_heading.count() > 0:
                    reviews_heading.scroll_into_view_if_needed()
                    time.sleep(2)
            except:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)
            
            # Scroll nhiều lần để load TẤT CẢ reviews (infinite scroll)
            safe_print("    ⏳ Đang scroll để load TẤT CẢ reviews...")
            previous_height = 0
            no_change_count = 0
            max_scrolls = 50  # Giới hạn tối đa để tránh vòng lặp vô hạn
            
            for scroll_attempt in range(max_scrolls):
                # Scroll xuống
                self.page.evaluate("window.scrollBy(0, 500)")
                time.sleep(1.2)
                
                # Kiểm tra xem page có tăng chiều cao không
                current_height = self.page.evaluate("document.body.scrollHeight")
                if current_height == previous_height:
                    no_change_count += 1
                    if no_change_count >= 3:  # Nếu 3 lần liên tiếp không thay đổi -> đã hết
                        safe_print(f"    ✅ Đã scroll hết reviews (sau {scroll_attempt + 1} lần scroll)")
                        break
                else:
                    no_change_count = 0  # Reset nếu có thay đổi
                    previous_height = current_height
                    safe_print(f"    📜 Scroll lần {scroll_attempt + 1}: Phát hiện thêm content...")
            
            if scroll_attempt >= max_scrolls - 1:
                safe_print(f"    ⚠️ Đã scroll {max_scrolls} lần, có thể vẫn còn reviews nhưng dừng để tránh timeout")
            
            # Đợi reviews render
            safe_print("    ⏳ Đợi reviews render...")
            time.sleep(5)
            
            # Lấy reviews - approach đơn giản: tìm text "Attention please" để xác định review đầu tiên
            # Sau đó tìm pattern: profile link + content
            
            # Debug: In ra page content để xem có reviews không
            page_text = self.page.locator("body").inner_text()
            if "Attention please" in page_text:
                safe_print("    ✅ Tìm thấy text 'Attention please' trong page")
            else:
                safe_print("    ⚠️ KHÔNG tìm thấy 'Attention please' - reviews chưa load")
            
            # Tìm tất cả text nodes chứa "Attention" hoặc reviews dài
            test_phrases = ["Attention please", "Its just peak", "Without a doubt", "HOOOOOOLY"]
            review_items = []
            
            for phrase in test_phrases:
                try:
                    # Thử nhiều selector khác nhau
                    selectors_with_phrase = [
                        f"p:has-text('{phrase}')",
                        f"div:has-text('{phrase}')",
                        f"li:has-text('{phrase}')",
                        f"*:has-text('{phrase}')"
                    ]
                    
                    for sel in selectors_with_phrase:
                        phrase_el = self.page.locator(sel).first
                        if phrase_el.count() > 0:
                            safe_print(f"    🔍 Tìm thấy element với selector: {sel}")
                            # Thử nhiều loại ancestor
                            ancestor = None
                            ancestor_selectors = [
                                "xpath=ancestor::li[1]",
                                "xpath=ancestor::div[@class][1]",
                                "xpath=parent::*[1]",
                            ]
                            
                            for anc_sel in ancestor_selectors:
                                test_anc = phrase_el.locator(anc_sel).first
                                if test_anc.count() > 0:
                                    ancestor = test_anc
                                    safe_print(f"    ✅ Tìm được ancestor với: {anc_sel}")
                                    break
                            
                            if ancestor:
                                review_items.append(ancestor)
                                safe_print(f"    ✅ Tìm thấy review chứa: '{phrase[:30]}...'")
                                break
                            else:
                                safe_print(f"    ⚠️ Không tìm được ancestor")
                except Exception as ex:
                    safe_print(f"    ⚠️ Error: {ex}")
                    continue
            
            if not review_items:
                safe_print(f"    ⚠️ Không tìm thấy reviews, skip comments")
                story_comments = []
            else:
                safe_print(f"    ✅ Tìm được {len(review_items)} review items, bắt đầu parse...")
                
                for review_item in review_items:
                    try:
                        # Lấy toàn bộ text từ item để debug
                        full_item_text = review_item.inner_text().strip()
                        
                        # Lấy username từ link profile
                        username = ""
                        username_el = review_item.locator("a[href*='/profile/']").first
                        if username_el.count() > 0:
                            username = username_el.inner_text().strip()
                            # Loại bỏ "LV X" prefix nếu có
                            username = re.sub(r'^LV\s*\d+\s*', '', username).strip()
                        
                        # Lấy comment content
                        # Strategy: Lấy tất cả paragraphs, filter ra những cái không phải metadata
                        all_paragraphs = review_item.locator("p").all()
                        content_lines = []
                        
                        for p in all_paragraphs:
                            p_text = p.inner_text().strip()
                            # Skip metadata lines (LV, VIEW, short single words, numbers only)
                            if p_text and len(p_text) > 3:
                                # Skip nếu chỉ là metadata
                                if re.match(r'^(LV\s*\d+|VIEW|LIKE|\d+\s*(mth|d|h|m)|\d+$|Prev|Next)', p_text, re.I):
                                    continue
                                # Skip nếu chỉ là username
                                if p_text == username:
                                    continue
                                # Valid content
                                content_lines.append(p_text)
                        
                        content_text = "\n".join(content_lines).strip()
                        
                        # Fallback: nếu không có content từ <p>, lấy toàn bộ và filter
                        if not content_text:
                            lines = full_item_text.split('\n')
                            filtered = []
                            for line in lines:
                                line = line.strip()
                                if not line or len(line) < 5:
                                    continue
                                # Skip metadata
                                if re.match(r'^(LV\s*\d+|VIEW|LIKE|\d+\s*(mth|d|h|m)|Prev|Next)', line, re.I):
                                    continue
                                if line == username:
                                    continue
                                filtered.append(line)
                            content_text = "\n".join(filtered[:20])  # Lấy tối đa 20 dòng đầu
                        
                        # Bắt buộc phải có content
                        if not content_text or len(content_text) < 15:
                            continue
                        
                        # Kiểm tra GIF images trong review
                        gif_imgs = review_item.locator("img[src*='.gif'], img[src*='giphy'], img[src*='tenor'], img[data-src*='.gif']").all()
                        gif_urls = []
                        for gif_el in gif_imgs:
                            gif_url = gif_el.get_attribute("src") or gif_el.get_attribute("data-src")
                            if gif_url:
                                if gif_url.startswith("//"):
                                    gif_url = "https:" + gif_url
                                gif_urls.append(gif_url)
                        
                        # Thêm GIF URLs vào content
                        if gif_urls:
                            for gif_url in gif_urls:
                                content_text += f"\n[GIF: {gif_url}]"
                        
                        # Lấy time (1mth, 24d, etc.)
                        time_text = ""
                        time_patterns = [r'(\d+mth)', r'(\d+d)', r'(\d+h)', r'(\d+m)']
                        review_text = review_item.inner_text()
                        for pattern in time_patterns:
                            match = re.search(pattern, review_text)
                            if match:
                                time_text = match.group(1)
                                break
                        
                        # Lấy comment_id từ nhiều attributes
                        comment_id = (
                            review_item.get_attribute("id") or 
                            review_item.get_attribute("data-id") or 
                            review_item.get_attribute("data-comment-id") or
                            review_item.get_attribute("data-cid") or
                            ""
                        )
                        # Nếu vẫn không có, generate từ username + time
                        if not comment_id:
                            import hashlib
                            comment_id = hashlib.md5(f"{username}_{time_text}_{content_text[:20]}".encode()).hexdigest()[:12]
                        
                        # Tạo comment object theo schema mới
                        comment_data = {
                            "comment_id": comment_id,
                            "content_id": fiction_id,  # Story ID cho story-level comments
                            "comment_text": content_text,  # Đổi content → comment_text
                            "time": time_text,
                            "user_id": username,
                            "parent_id": "",
                            "is_root": True,  # Story-level comments là root
                            "react": 0,  # TODO: scrape reactions/likes
                            "replies": []
                        }
                        
                        story_comments.append(comment_data)
                        
                    except Exception as ex:
                        safe_print(f"    ⚠️ Lỗi parse review item: {ex}")
                        continue
            
            safe_print(f"    ✅ Lấy được {len(story_comments)} story comments")
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi lấy story comments: {e}")
        
        # Convert chapters count to integer
        total_chapters_int = 0
        try:
            total_chapters_int = int(chapters_count_text.replace(',', '').replace('.', ''))
        except:
            total_chapters_int = 0
        
        # Tạo fiction_data theo schema HOÀN CHỈNH
        fiction_data = {
            "story_id": fiction_id,
            "story_name": title,
            "story_url": fiction_url,
            "cover_image": local_img_path,
            "author_id": author,  # Sẽ link với Users collection
            "genre": genre,
            "status": "Unknown",  # TODO: scrape (Ongoing/Completed/Hiatus)
            "tags": tags,
            "description": description,
            "total_chapters": total_chapters_int,
            "total_views": views_text,
            "followers": 0,  # TODO: scrape
            "favorites": 0,  # TODO: scrape
            "ratings": total_reviews,
            "overall_score": total_rating,
            "style_score": float(scores.get("writing_quality", 0)) if scores.get("writing_quality") else 0,
            "story_score": float(scores.get("story_development", 0)) if scores.get("story_development") else 0,
            "character_score": float(scores.get("character_design", 0)) if scores.get("character_design") else 0,
            "world_background_score": float(scores.get("world_background", 0)) if scores.get("world_background") else 0,
            "stability_score": float(scores.get("stability_of_updates", 0)) if scores.get("stability_of_updates") else 0,
            "voted": 0,  # TODO: scrape power stones
            "time": "",  # TODO: scrape publish date
            "comments": story_comments,
            "chapter_list": []
        }
        
        # Lấy danh sách chapters từ catalog
        safe_print("... Đang tìm danh sách chương")
        chapter_urls = self._get_webnovel_chapter_urls(fiction_url, fiction_id)
        
        if not chapter_urls:
            safe_print("⚠️ Không tìm thấy chương nào!")
        else:
            if max_chapters:
                chapter_urls = chapter_urls[:max_chapters]
            safe_print(f"--> Tìm thấy {len(chapter_urls)} chương")
            
            # Cào chapters song song
            safe_print(f"🚀 Bắt đầu cào {len(chapter_urls)} chương với {self.max_workers} thread...")
            chapter_results = [None] * len(chapter_urls)
            future_to_index = {}
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for index, chap_url in enumerate(chapter_urls):
                    future = executor.submit(self._scrape_single_chapter_worker, chap_url, index)
                    future_to_index[future] = index
                
                completed = 0
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        chapter_data = future.result()
                        chapter_results[index] = chapter_data
                        completed += 1
                        status = "✅" if chapter_data else "⚠️"
                        safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_urls)} (đã xong {completed}/{len(chapter_urls)})")
                    except Exception as e:
                        safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                        chapter_results[index] = None
            
            # Thêm vào fiction_data theo đúng thứ tự
            for index in range(len(chapter_results)):
                chapter_data = chapter_results[index]
                if chapter_data:
                    fiction_data["chapter_list"].append(chapter_data)
        
        safe_print(f"✅ Đã hoàn thành {len(fiction_data['chapter_list'])} chương")
        
        # Lưu kết quả
        self._save_to_json(fiction_data)

    def _get_webnovel_chapter_urls(self, fiction_url, fiction_id):
        """Lấy danh sách URL chapters từ Webnovel (workaround: lấy first chapter rồi navigate)"""
        chapter_urls = []
        
        # Chiến lược mới: tìm nút READ hoặc first chapter link trên trang book
        safe_print(f"    📖 Tìm first chapter từ trang book...")
        first_chapter_url = None
        
        try:
            # Tìm nút "READ" hoặc link chapter đầu tiên
            read_button = self.page.locator("a:has-text('READ'), a.j_read_btn, a[class*='read']").first
            if read_button.count() > 0:
                first_chapter_url = read_button.get_attribute("href")
                if first_chapter_url:
                    if not first_chapter_url.startswith("http"):
                        first_chapter_url = "https://www.webnovel.com" + first_chapter_url
                    safe_print(f"    ✅ Tìm thấy first chapter: {first_chapter_url[:80]}...")
        except Exception as e:
            safe_print(f"    ⚠️ Không tìm thấy nút READ: {e}")
        
        # Nếu không tìm được, thử build first chapter URL (Webnovel format)
        if not first_chapter_url:
            # Webnovel first chapter thường có format: /book/<id>/<slug>_<chapter-id>
            # Ta có thể thử guess hoặc lấy từ API
            safe_print(f"    ⚠️ Không tìm thấy first chapter link")
            safe_print(f"    💡 Workaround: Webnovel yêu cầu login hoặc block bot để xem catalog")
            safe_print(f"    💡 Bạn có thể:")
            safe_print(f"        1. Chạy với HEADLESS=False trong config.py để xem browser")
            safe_print(f"        2. Thêm cookies/login vào browser context")
            safe_print(f"        3. Dùng API Webnovel (nếu có)")
            return []
        
        # Nếu tìm được first chapter, ta có thể navigate qua chapters (prev/next)
        # Nhưng giới hạn để demo
        chapter_urls.append(first_chapter_url)
        safe_print(f"    ✅ Lấy được 1 chapter URL (demo mode)")
        
        return chapter_urls

    def scrape_best_rated_fictions(self, best_rated_url, num_fictions=10, start_from=0):
        """
        Cào nhiều bộ truyện từ trang web-novel
        Args:
            best_rated_url: URL trang web-novel
            num_fictions: Số lượng bộ truyện muốn cào (mặc định 10)
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên, 5 = bỏ qua 5 bộ đầu)
        """
        safe_print(f"📚 Đang truy cập trang web-novel: {best_rated_url}")
        self.page.goto(best_rated_url, timeout=config.TIMEOUT)
        time.sleep(2)
        
        # Lấy danh sách các bộ truyện từ trang web-novel
        if start_from > 0:
            safe_print(f"🔍 Đang lấy danh sách {num_fictions} bộ truyện (bắt đầu từ vị trí {start_from + 1})...")
        else:
            safe_print(f"🔍 Đang lấy danh sách {num_fictions} bộ truyện đầu tiên...")
        fiction_urls = self._get_fiction_urls_from_best_rated(num_fictions, start_from)
        
        if not fiction_urls:
            safe_print("❌ Không tìm thấy bộ truyện nào!")
            return
        
        safe_print(f"✅ Đã tìm thấy {len(fiction_urls)} bộ truyện:")
        for i, url in enumerate(fiction_urls, 1):
            safe_print(f"   {i}. {url}")
        
        # Cào từng bộ truyện tuần tự
        for index, fiction_url in enumerate(fiction_urls, 1):
            safe_print(f"\n{'='*60}")
            safe_print(f"📖 Bắt đầu cào bộ truyện {index}/{len(fiction_urls)}")
            safe_print(f"{'='*60}")
            try:
                self.scrape_fiction(fiction_url)
                safe_print(f"✅ Hoàn thành bộ truyện {index}/{len(fiction_urls)}")
            except Exception as e:
                safe_print(f"❌ Lỗi khi cào bộ truyện {index}: {e}")
                continue
            
            # Delay giữa các bộ truyện
            if index < len(fiction_urls):
                safe_print(f"⏳ Nghỉ {config.DELAY_BETWEEN_CHAPTERS * 2} giây trước khi cào bộ tiếp theo...")
                time.sleep(config.DELAY_BETWEEN_CHAPTERS * 2)
        
        safe_print(f"\n{'='*60}")
        safe_print(f"🎉 Đã hoàn thành cào {len(fiction_urls)} bộ truyện!")
        safe_print(f"{'='*60}")

    def _get_fiction_urls_from_best_rated(self, num_fictions=10, start_from=0):
        """
        Lấy danh sách URL của các bộ truyện từ trang web-novel
        Selector: h2.fiction-title a
        Args:
            num_fictions: Số lượng bộ truyện muốn lấy
            start_from: Bắt đầu từ vị trí thứ mấy (0 = bộ đầu tiên)
        """
        fiction_urls = []
        
        try:
            # Scroll xuống để load thêm nội dung nếu cần
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Lấy tất cả các link truyện từ thẻ h2.fiction-title a
            fiction_links = self.page.locator("h2.fiction-title a").all()
            
            # Tính toán vị trí bắt đầu và kết thúc
            start_index = start_from
            end_index = start_from + num_fictions
            
            # Lấy các link từ vị trí start_from đến end_index
            for link in fiction_links[start_index:end_index]:
                try:
                    href = link.get_attribute("href")
                    if href:
                        # Tạo full URL
                        if href.startswith("/"):
                            full_url = config.BASE_URL + href
                        elif href.startswith("http"):
                            full_url = href
                        else:
                            full_url = config.BASE_URL + "/" + href
                        
                        if full_url not in fiction_urls:
                            fiction_urls.append(full_url)
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi lấy URL truyện: {e}")
                    continue
            
            return fiction_urls
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy danh sách truyện từ web-novel: {e}")
            return []

    def scrape_fiction(self, fiction_url):
        """
        Hàm chính để cào toàn bộ 1 bộ truyện.
        Luồng đi: Vào trang truyện -> Lấy Info -> Lấy List Chapter -> Vào từng Chapter -> Lấy Content.
        """
        safe_print(f"🌍 Đang truy cập truyện: {fiction_url}")
        self.page.goto(fiction_url, timeout=config.TIMEOUT)

        # 1. Lấy ID truyện từ URL (Ví dụ: 21220)
        fiction_id = fiction_url.split("/")[4]

        # 2. Lấy thông tin tổng quan (Metadata)
        safe_print("... Đang lấy thông tin chung")
        
        # Lấy title
        title = self.page.locator("h1").first.inner_text()
        
        # Lấy URL ảnh bìa rồi tải về luôn
        img_url_raw = self.page.locator(".cover-art-container img").get_attribute("src")
        local_img_path = utils.download_image(img_url_raw, fiction_id)

        # Lấy author
        author = self.page.locator(".fic-title h4 a").first.inner_text()

        # Lấy category
        category = self.page.locator(".fiction-info span").first.inner_text()

        # Lấy status
        status = self.page.locator(".fiction-info span:nth-child(2)").first.inner_text()

        #Lấy tags
        tags = self.page.locator(".tags a").all_inner_texts()

        #Lấy description - giữ nguyên định dạng như trong UI
        description = ""
        try:
            desc_container = self.page.locator(".description").first
            if desc_container.count() > 0:
                # Lấy HTML để giữ định dạng
                html_content = desc_container.inner_html()
                # Chuyển HTML sang text với định dạng đúng
                description = self._convert_html_to_formatted_text(html_content)
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lấy description: {e}")
            description = ""

        #Lấy stats
        # stats = self.page.locator(".stats-content .list-item").all()
        # Container chính: .stats-content ul.list-unstyled
        base_locator = ".stats-content ul.list-unstyled li:nth-child({}) span"

        # 1. Overall Score (Nằm ở vị trí con thứ 2)
        overall_score = self.page.locator(base_locator.format(2)).inner_text()

        # 2. Style Score (Vị trí con thứ 4)
        style_score = self.page.locator(base_locator.format(4)).inner_text()

        # 3. Story Score (Vị trí con thứ 6)
        story_score = self.page.locator(base_locator.format(6)).inner_text()

        # 4. Grammar Score (Vị trí con thứ 8)
        grammar_score = self.page.locator(base_locator.format(8)).inner_text()

        # 5. Character Score (Vị trí con thứ 10)
        character_score = self.page.locator(base_locator.format(10)).inner_text()

        # 1. Định vị tất cả các thẻ <li> chứa GIÁ TRỊ số liệu
        # Sử dụng class đặc trưng (.font-red-sunglo) và giới hạn trong khối stats bên phải (.col-sm-6)
        stats_values_locator = self.page.locator("div.col-sm-6 li.font-red-sunglo")
        
        # 2. Lấy giá trị bằng cách dùng chỉ mục (index)
        
        # Lấy total_views (Index 0)
        total_views = stats_values_locator.nth(0).inner_text()
        
        # Lấy average_views (Index 1)
        average_views = stats_values_locator.nth(1).inner_text()
        
        # Lấy followers (Index 2)
        followers = stats_values_locator.nth(2).inner_text()
        
        # Lấy favorites (Index 3)
        favorites = stats_values_locator.nth(3).inner_text()
        
        # Lấy ratings (Index 4)
        ratings = stats_values_locator.nth(4).inner_text()
        
        # Lấy pages/words (Index 5 - Giá trị cuối cùng)
        pages = stats_values_locator.nth(5).inner_text()

        # Tạo cấu trúc dữ liệu tổng quan sau khi đã lấy hết các biến
        # Theo scheme: fiction id, fiction name, fiction url, cover image, author, category, status, tags, description
        fiction_data = {
            "id": fiction_id,
            "name": title,  # Scheme: fiction name
            "url": fiction_url,  # Scheme: fiction url
            "cover_image": local_img_path,  # Scheme: cover image
            "author": author,
            "category": category,
            "status": status,
            "tags": tags,
            "description": description,
            "stats": {
                "score": {
                    "overall_score": overall_score,
                    "style_score": style_score,
                    "story_score": story_score,
                    "grammar_score": grammar_score,
                    "character_score": character_score,
                },
                "views": {
                    "total_views": total_views,
                    "average_views": average_views,
                    "followers": followers,
                    "favorites": favorites,
                    "ratings": ratings,
                    "page_views": pages,
                }
            },
            "reviews": [],  # Sẽ được điền sau
            "chapters": []     # Chuẩn bị cái mảng rỗng để chứa các chương
        }

        # 3. Lấy danh sách link chương từ TẤT CẢ các trang phân trang
        safe_print("... Đang lấy danh sách chương từ tất cả các trang")
        chapter_urls = self._get_all_chapters_from_pagination(fiction_url)
        
        safe_print(f"--> Tổng cộng tìm thấy {len(chapter_urls)} chương từ tất cả các trang.")

        # 3.5. Lấy reviews cho toàn bộ truyện
        safe_print("... Đang lấy reviews cho toàn bộ truyện")
        reviews = self._scrape_reviews(fiction_url)
        fiction_data["reviews"] = reviews
        safe_print(f"✅ Đã lấy được {len(reviews)} reviews")

        # 4. Cào các chương song song với ThreadPoolExecutor (GIỮ ĐÚNG THỨ TỰ)
        safe_print(f"🚀 Bắt đầu cào {len(chapter_urls)} chương với {self.max_workers} thread...")
        
        # Tạo list kết quả cố định theo index - mỗi index = 1 chương
        chapter_results = [None] * len(chapter_urls)
        
        # Dictionary để map future -> index để biết chương nào
        future_to_index = {}
        
        # Sử dụng ThreadPoolExecutor - NÓ TỰ ĐỘNG PHÂN PHỐI công việc!
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit TẤT CẢ chapters vào pool - mỗi chương chỉ submit 1 LẦN
            for index, chap_url in enumerate(chapter_urls):
                future = executor.submit(self._scrape_single_chapter_worker, chap_url, index)
                future_to_index[future] = index
            
            # Thu thập kết quả - các thread có thể hoàn thành bất kỳ lúc nào
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]  # Lấy index của chương này
                try:
                    chapter_data = future.result()
                    # LƯU VÀO ĐÚNG VỊ TRÍ INDEX - không phải append!
                    chapter_results[index] = chapter_data
                    completed += 1
                    status = "✅" if chapter_data else "⚠️"
                    safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_urls)} (đã xong {completed}/{len(chapter_urls)})")
                except Exception as e:
                    safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                    chapter_results[index] = None

        # SAU KHI TẤT CẢ XONG: Thêm vào fiction_data THEO ĐÚNG THỨ TỰ
        safe_print(f"📝 Sắp xếp kết quả theo đúng thứ tự...")
        for index in range(len(chapter_results)):
            chapter_data = chapter_results[index]
            if chapter_data:
                fiction_data["chapters"].append(chapter_data)
            else:
                safe_print(f"    ⚠️ Bỏ qua chương {index + 1} (lỗi hoặc không có dữ liệu)")

        safe_print(f"✅ Đã hoàn thành {len(fiction_data['chapters'])}/{len(chapter_urls)} chương (theo đúng thứ tự)")

        # 5. Lưu kết quả ra JSON
        self._save_to_json(fiction_data)

    def _get_all_chapters_from_pagination(self, fiction_url):
        """
        Lấy tất cả chapters từ tất cả các trang phân trang
        Pagination sử dụng JavaScript (AJAX), không đổi URL
        Trả về danh sách URL của tất cả chapters
        """
        all_chapter_urls = []
        
        try:
            # Trang đầu tiên: Lấy từ trang fiction chính
            safe_print(f"    📄 Đang lấy chapters từ trang 1 (trang fiction chính)...")
            self.page.goto(fiction_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Lấy chapters từ trang fiction chính
            page_chapters = self._get_chapters_from_current_page()
            all_chapter_urls.extend(page_chapters)
            safe_print(f"    ✅ Trang 1: Lấy được {len(page_chapters)} chapters")
            
            # Tìm số trang tối đa cho chapters từ pagination trên trang fiction chính
            max_page = self._get_max_chapter_page()
            
            # Nếu chỉ có 1 trang, return luôn
            if max_page <= 1:
                safe_print(f"    📚 Chỉ có 1 trang chapters")
                return all_chapter_urls
            
            safe_print(f"    📚 Tìm thấy {max_page} trang chapters (trang 1 đã lấy, còn {max_page - 1} trang nữa)")
            
            # Loop qua từng trang còn lại (từ trang 2 trở đi)
            # Sử dụng click vào pagination để load thêm chapters (AJAX, không đổi URL)
            for page_num in range(2, max_page + 1):
                safe_print(f"    📄 Đang lấy chapters từ trang {page_num}/{max_page}...")
                
                # Click vào nút pagination để chuyển trang (AJAX load, không đổi URL)
                if not self._go_to_chapter_page(page_num):
                    safe_print(f"    ⚠️ Không thể chuyển đến trang {page_num}, dừng lại")
                    break
                
                # Đợi AJAX load xong
                time.sleep(2)
                
                # Lấy chapters từ trang hiện tại
                page_chapters = self._get_chapters_from_current_page()
                all_chapter_urls.extend(page_chapters)
                
                safe_print(f"    ✅ Trang {page_num}: Lấy được {len(page_chapters)} chapters")
                
                # Delay giữa các trang
                if page_num < max_page:
                    time.sleep(1)
            
            return all_chapter_urls
            
        except Exception as e:
            safe_print(f"    ⚠️ Lỗi khi lấy chapters từ pagination: {e}")
            # Fallback: Lấy từ trang đầu tiên (trang fiction chính)
            try:
                self.page.goto(fiction_url, timeout=config.TIMEOUT)
                time.sleep(2)
                return self._get_chapters_from_current_page()
            except:
                return []

    def _get_max_chapter_page(self):
        """Lấy số trang chapters tối đa từ pagination"""
        try:
            # Scroll xuống để load pagination
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1  # Mặc định là 1 trang
            
            # Tìm pagination element - có thể là pagination-small hoặc pagination
            pagination_selectors = [
                "ul.pagination-small",
                "ul.pagination",
                ".pagination-small",
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
                # Lấy tất cả các link có data-page attribute
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
                
                # Nếu không có data-page, thử lấy từ text content
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                # Bỏ qua các nút navigation (Next, Previous) và icon
                                if link_text.isdigit():
                                    page_num = int(link_text)
                                    page_numbers.append(page_num)
                            except:
                                continue
                    except:
                        pass
                
                if page_numbers:
                    max_page = max(page_numbers)
                    safe_print(f"        📄 Tìm thấy {max_page} trang chapters")
                else:
                    # Nếu không tìm thấy số trang, có thể chỉ có 1 trang
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang chapters: {e}")
            return 1

    def _get_chapter_page_urls(self, base_url, max_page):
        """Lấy tất cả URL của các trang chapters từ pagination"""
        page_urls = [base_url]  # Trang 1 là base_url
        
        try:
            # Tìm pagination
            pagination_selectors = [
                "ul.pagination-small",
                "ul.pagination",
                ".pagination-small",
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
                # Lấy tất cả các link có data-page attribute
                page_links = pagination.locator("a[data-page]").all()
                
                url_map = {}  # {page_num: url}
                for link in page_links:
                    try:
                        page_num_str = link.get_attribute("data-page")
                        if page_num_str:
                            page_num = int(page_num_str)
                            href = link.get_attribute("href")
                            if href:
                                # Tạo full URL
                                if href.startswith("/"):
                                    full_url = config.BASE_URL + href
                                elif href.startswith("http"):
                                    full_url = href
                                else:
                                    full_url = config.BASE_URL + "/" + href
                                url_map[page_num] = full_url
                    except:
                        continue
                
                # Sắp xếp và thêm vào list
                for page_num in sorted(url_map.keys()):
                    if page_num <= max_page:
                        page_urls.append(url_map[page_num])
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy URLs từ pagination: {e}")
        
        return page_urls

    def _go_to_chapter_page(self, page_num):
        """
        Chuyển đến trang chapters cụ thể bằng cách click vào link hoặc nút Next
        Trả về True nếu thành công, False nếu thất bại
        """
        try:
            # Tìm pagination
            pagination_selectors = [
                "ul.pagination-small",
                "ul.pagination",
                ".pagination-small",
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
            
            if not pagination or pagination.count() == 0:
                return False
            
            # Cách 1: Thử tìm link có data-page = page_num
            try:
                page_link = pagination.locator(f'a[data-page="{page_num}"]').first
                if page_link.count() > 0:
                    page_link.click()
                    time.sleep(2)
                    return True
            except:
                pass
            
            # Cách 2: Nếu không có data-page, thử tìm link có text = page_num
            # Lấy tất cả các link trong pagination và tìm link có text = page_num
            try:
                all_links = pagination.locator("a").all()
                for link in all_links:
                    try:
                        link_text = link.inner_text().strip()
                        # Kiểm tra xem text có phải là số và bằng page_num không
                        if link_text.isdigit() and int(link_text) == page_num:
                            # Kiểm tra xem không phải là nút navigation (không có class nav-arrow)
                            parent_class = link.evaluate("el => el.closest('li')?.className || ''")
                            if "nav-arrow" not in parent_class:
                                link.click()
                                time.sleep(2)
                                return True
                    except:
                        continue
            except:
                pass
            
            # Cách 3: Click nút "Next" nhiều lần (chỉ dùng nếu page_num nhỏ)
            # Tìm nút Next (có class nav-arrow hoặc chứa icon chevron-right)
            if page_num <= 10:  # Giới hạn để tránh click quá nhiều
                # Tìm trang hiện tại
                current_page = 1
                try:
                    active_page = pagination.locator("li.page-active a").first
                    if active_page.count() > 0:
                        active_text = active_page.inner_text().strip()
                        if active_text.isdigit():
                            current_page = int(active_text)
                except:
                    pass
                
                # Click Next cho đến khi đến trang cần
                while current_page < page_num:
                    # Tìm nút Next (có thể là .nav-arrow với icon chevron-right)
                    next_selectors = [
                        'a.pagination-button:has(i.fa-chevron-right)',
                        '.nav-arrow a:has(i.fa-chevron-right)',
                        'a:has(i.fa-chevron-right)',
                        '.nav-arrow a',
                        'a.pagination-button'
                    ]
                    
                    next_button = None
                    for selector in next_selectors:
                        try:
                            next_button = pagination.locator(selector).last  # Lấy nút cuối (Next)
                            if next_button.count() > 0:
                                # Kiểm tra xem có phải nút Next không (không phải Previous)
                                href = next_button.get_attribute("href") or ""
                                if "page" in href.lower() or "next" in href.lower() or not href:
                                    break
                        except:
                            continue
                    
                    if next_button and next_button.count() > 0:
                        try:
                            next_button.click()
                            time.sleep(2)
                            current_page += 1
                        except:
                            return False
                    else:
                        return False
                
                return True
            
            return False
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi chuyển đến trang {page_num}: {e}")
            return False

    def _get_chapters_from_current_page(self):
        """Lấy danh sách chapters từ trang hiện tại"""
        chapter_urls = []
        
        try:
            # Lấy tất cả các rows trong table chapters
            chapter_rows = self.page.locator("table#chapters tbody tr").all()
            
            for row in chapter_rows:
                try:
                    link_el = row.locator("td").first.locator("a")
                    if link_el.count() > 0:
                        url = link_el.get_attribute("href")
                        if url:
                            # Tạo full URL
                            if url.startswith("/"):
                                full_url = config.BASE_URL + url
                            elif url.startswith("http"):
                                full_url = url
                            else:
                                full_url = config.BASE_URL + "/" + url
                            
                            # Tránh duplicate
                            if full_url not in chapter_urls:
                                chapter_urls.append(full_url)
                except:
                    continue
            
            return chapter_urls
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapters từ trang hiện tại: {e}")
            return []

    def _convert_html_to_formatted_text(self, html_content):
        """
        Chuyển đổi HTML sang text với định dạng đúng (giữ nguyên xuống dòng như trong UI)
        - Mỗi thẻ <p> = một đoạn văn, các đoạn cách nhau bằng một dòng trống
        - Thẻ <br> = xuống dòng
        - Giữ nguyên cấu trúc như trong UI
        """
        if not html_content:
            return ""
        
        import html as html_module
        
        # Decode HTML entities trước
        html_content = html_module.unescape(html_content)
        
        # Xử lý theo thứ tự để đảm bảo định dạng đúng
        text = html_content
        
        # 1. Xử lý <br> và <br/> trước - xuống dòng ngay lập tức
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        # 2. Xử lý các thẻ block: <p> - mỗi đoạn văn cách nhau 1 dòng trống
        # Thay thế </p> thành dấu phân cách đoạn (2 dòng xuống)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        # Xóa thẻ mở <p>
        text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)
        
        # 3. Xử lý các thẻ block khác: <div> - xuống dòng
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<div[^>]*>', '', text, flags=re.IGNORECASE)
        
        # 4. Xử lý các thẻ heading (h1, h2, h3, ...) - xuống dòng trước và sau
        text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
        
        # 5. Xóa tất cả các thẻ HTML còn lại (giữ lại text)
        text = re.sub(r'<[^>]+>', '', text)
        
        # 6. Làm sạch: xử lý các dòng trống và khoảng trắng thừa
        lines = text.split('\n')
        cleaned_lines = []
        
        prev_empty = False
        for line in lines:
            # Strip cả 2 bên để loại bỏ khoảng trắng thừa (từ HTML indentation)
            stripped_line = line.strip()
            
            # Xử lý dòng trống
            if not stripped_line:
                # Chỉ thêm 1 dòng trống giữa các đoạn (không thêm nhiều dòng trống liên tiếp)
                if not prev_empty:
                    cleaned_lines.append('')
                prev_empty = True
            else:
                # Giữ nguyên dòng có nội dung (đã strip khoảng trắng thừa)
                cleaned_lines.append(stripped_line)
                prev_empty = False
        
        # Loại bỏ dòng trống ở đầu và cuối (nhưng giữ dòng trống giữa các đoạn)
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        result = '\n'.join(cleaned_lines)
        
        # Loại bỏ khoảng trắng thừa ở đầu và cuối toàn bộ text
        # Nhưng vẫn giữ nguyên cấu trúc bên trong (các dòng trống giữa đoạn)
        result = result.strip()
        
        # Đảm bảo không có khoảng trắng thừa ở đầu mỗi dòng (từ HTML indentation)
        # Normalize lại để chắc chắn
        if result:
            lines = result.split('\n')
            final_lines = []
            for line in lines:
                # Strip từng dòng để loại bỏ khoảng trắng thừa
                clean_line = line.strip()
                # Giữ dòng trống nếu là dòng trống thật
                if not clean_line:
                    final_lines.append('')
                else:
                    final_lines.append(clean_line)
            result = '\n'.join(final_lines).strip()
        
        return result

    def _scrape_single_chapter(self, url):
        """Hàm con: Chỉ chịu trách nhiệm vào 1 link chương và trả về cục data của chương đó"""
        try:
            self.page.goto(url, timeout=config.TIMEOUT)
            self.page.wait_for_selector(".chapter-inner", timeout=10000)

            title = self.page.locator("h1").first.inner_text()
            
            # Lấy content với định dạng đúng (giữ nguyên xuống dòng như trong UI)
            content = ""
            try:
                content_container = self.page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    # Lấy HTML để giữ định dạng
                    html_content = content_container.inner_html()
                    # Chuyển HTML sang text với định dạng đúng
                    content = self._convert_html_to_formatted_text(html_content)
                else:
                    # Fallback: dùng inner_text nếu không tìm thấy
                    content = self.page.locator(".chapter-inner").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi lấy content: {e}")
                content = self.page.locator(".chapter-inner").inner_text()

            # Lấy comments cho chapter này
            safe_print(f"      ... Đang lấy comments cho chương")
            chapter_comments = self._scrape_comments(url, "chapter")
            
            # Lấy chapter_id từ URL (ví dụ: /chapter/123456/ -> 123456)
            chapter_id = ""
            try:
                url_parts = url.split("/chapter/")
                if len(url_parts) > 1:
                    chapter_id = url_parts[1].split("/")[0]
            except:
                chapter_id = ""

            # Transform chapter comments theo schema mới
            transformed_comments = []
            for comment in chapter_comments:
                transformed_comment = {
                    "comment_id": comment.get("comment_id", ""),
                    "content_id": chapter_id,  # Chapter ID cho chapter comments
                    "comment_text": comment.get("content", ""),  # Đổi content → comment_text
                    "time": comment.get("time", ""),
                    "user_id": comment.get("user_id", ""),
                    "parent_id": comment.get("parent_id", ""),
                    "is_root": not comment.get("parent_id"),  # Root nếu không có parent
                    "react": 0,  # TODO: scrape
                    "replies": comment.get("replies", [])
                }
                transformed_comments.append(transformed_comment)

            return {
                "chapter_id": chapter_id,
                "story_id": "",  # TODO: pass fiction_id
                "order": 0,  # TODO: pass index
                "chapter_name": title,
                "chapter_url": url,
                "content": content,
                "published_time": "",  # TODO: scrape
                "last_updated": "",  # TODO: scrape
                "voted": 0,  # TODO: scrape
                "views": "",  # TODO: scrape
                "comments": transformed_comments
            }
        except Exception as e:
            safe_print(f"⚠️ Lỗi cào chương {url}: {e}")
            return None

    def _scrape_single_chapter_worker(self, url, index):
        """
        Worker function để cào MỘT chương - mỗi worker có browser instance riêng
        Thread-safe: Mỗi worker có browser instance riêng
        
        Args:
            url: URL của chương cần cào (DUY NHẤT - không trùng lặp)
            index: Thứ tự chương trong list (DUY NHẤT - không trùng lặp)
        """
        worker_playwright = None
        worker_browser = None
        
        try:
            # Delay để stagger các thread - tránh tất cả thread bắt đầu cùng lúc
            time.sleep(index * config.DELAY_THREAD_START)
            
            # Tạo browser instance riêng cho worker này
            worker_playwright = sync_playwright().start()
            worker_browser = worker_playwright.chromium.launch(headless=config.HEADLESS)
            worker_context = worker_browser.new_context()
            worker_page = worker_context.new_page()
            
            safe_print(f"    🔄 Thread-{index}: Đang cào chương {index + 1}")
            
            # Delay trước khi request để tránh ban IP
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Cào chương
            worker_page.goto(url, timeout=config.TIMEOUT)
            worker_page.wait_for_selector(".chapter-inner", timeout=10000)
            
            # Delay sau khi load page
            time.sleep(config.DELAY_BETWEEN_REQUESTS)

            title = worker_page.locator("h1").first.inner_text()
            
            # Lấy content với định dạng đúng
            content = ""
            try:
                content_container = worker_page.locator(".chapter-inner").first
                if content_container.count() > 0:
                    html_content = content_container.inner_html()
                    content = self._convert_html_to_formatted_text(html_content)
                else:
                    content = worker_page.locator(".chapter-inner").inner_text()
            except Exception as e:
                safe_print(f"      ⚠️ Thread-{index}: Lỗi khi lấy content: {e}")
                content = worker_page.locator(".chapter-inner").inner_text()

            # Delay trước khi lấy comments
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Lấy comments cho chapter này
            safe_print(f"      💬 Thread-{index}: Đang lấy comments cho chương")
            # Kiểm tra xem có phải Webnovel không
            if "webnovel.com" in url:
                chapter_comments = self._scrape_webnovel_chapter_comments(worker_page, url)
            else:
                chapter_comments = self._scrape_comments_worker(worker_page, url, "chapter")

            # Delay sau khi hoàn thành chương
            time.sleep(config.DELAY_BETWEEN_CHAPTERS)
            
            # Lấy chapter_id từ URL (ví dụ: /chapter/123456/ -> 123456)
            chapter_id = ""
            try:
                url_parts = url.split("/chapter/")
                if len(url_parts) > 1:
                    chapter_id = url_parts[1].split("/")[0]
            except:
                chapter_id = ""

            # Transform chapter comments theo schema mới (worker)
            transformed_comments = []
            for comment in chapter_comments:
                transformed_comment = {
                    "comment_id": comment.get("comment_id", ""),
                    "content_id": chapter_id,  # Chapter ID
                    "comment_text": comment.get("content", ""),
                    "time": comment.get("time", ""),
                    "user_id": comment.get("user_id", ""),
                    "parent_id": comment.get("parent_id", ""),
                    "is_root": not comment.get("parent_id"),
                    "react": 0,  # TODO: scrape
                    "replies": comment.get("replies", [])
                }
                transformed_comments.append(transformed_comment)

            return {
                "chapter_id": chapter_id,
                "story_id": "",  # TODO: pass fiction_id
                "order": index + 1,  # Thứ tự chapter
                "chapter_name": title,
                "chapter_url": url,
                "content": content,
                "published_time": "",  # TODO: scrape
                "last_updated": "",  # TODO: scrape
                "voted": 0,  # TODO: scrape
                "views": "",  # TODO: scrape
                "comments": transformed_comments
            }
            
        except Exception as e:
            safe_print(f"⚠️ Thread-{index}: Lỗi cào chương {index + 1}: {e}")
            return None
        finally:
            # Đóng browser của worker
            if worker_browser:
                worker_browser.close()
            if worker_playwright:
                worker_playwright.stop()

    def _get_max_comment_page(self, url):
        """Lấy số trang comments tối đa từ pagination"""
        try:
            # Đảm bảo đang ở đúng trang (trang 1 - không có query comments)
            base_url = url.split('?')[0]
            current_url = self.page.url.split('?')[0]
            
            if base_url not in current_url:
                self.page.goto(base_url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            # Scroll xuống để load pagination
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            max_page = 1  # Mặc định là 1 trang
            
            # Tìm pagination element - có thể trong .chapter-nav hoặc trực tiếp
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
                # Lấy tất cả các link có data-page attribute
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
                
                # Cũng thử lấy từ text content (nếu không có data-page)
                if not page_numbers:
                    try:
                        all_links = pagination.locator("a").all()
                        for link in all_links:
                            try:
                                link_text = link.inner_text().strip()
                                # Thử parse số từ text (ví dụ: "31", "Next >" sẽ bị skip)
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
                    # Nếu không tìm thấy số trang, có thể chỉ có 1 trang hoặc chưa load
                    safe_print(f"        📄 Không tìm thấy pagination, giả sử có 1 trang")
            
            return max_page
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy số trang: {e}")
            return 1  # Nếu lỗi, mặc định chỉ có 1 trang

    def _scrape_comments_from_page(self, page_url):
        """Lấy comments từ một trang cụ thể"""
        comments = []
        
        try:
            self.page.goto(page_url, timeout=config.TIMEOUT)
            time.sleep(2)  # Chờ page load
            
            # Scroll xuống để load comments (lazy load)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Lấy tất cả div.comment và filter những cái không nằm trong ul.subcomments
            all_comments = self.page.locator("div.comment").all()
            
            for comment_elem in all_comments:
                try:
                    # Kiểm tra xem comment này có nằm trong ul.subcomments không
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
                    
                    # Nếu nằm trong subcomments thì skip (đây là reply, sẽ được lấy đệ quy)
                    if is_in_subcomments:
                        continue
                    
                    # Đây là comment gốc, lấy nó và tất cả replies
                    comment_data = self._scrape_single_comment_recursive(comment_elem)
                    if comment_data:
                        comments.append(comment_data)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []

    def _scrape_comments(self, url, comment_type="chapter"):
        """
        Lấy tất cả comments từ TẤT CẢ các trang phân trang
        Trả về danh sách comments với threading (comment gốc + replies)
        """
        try:
            # Đảm bảo đang ở đúng trang để kiểm tra pagination
            current_url = self.page.url
            if url not in current_url:
                self.page.goto(url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            # Bước 1: Tìm số trang tối đa
            max_page = self._get_max_comment_page(url)
            
            all_comments = []
            
            # Bước 2: Lấy comments từ tất cả các trang
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang {page_num}/{max_page}...")
                
                # Tạo URL cho trang này
                if page_num == 1:
                    # Trang 1: Loại bỏ query parameter comments nếu có
                    base_url = url.split('?')[0]  # Lấy URL gốc không có query
                    page_url = base_url
                else:
                    # Trang khác: Thêm query parameter comments=N
                    base_url = url.split('?')[0]  # Lấy URL gốc
                    # Tìm các query parameter hiện có (trừ comments)
                    if '?' in url:
                        existing_params = url.split('?', 1)[1]
                        # Loại bỏ comments parameter nếu có
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
                
                # Lấy comments từ trang này
                page_comments = self._scrape_comments_from_page(page_url)
                all_comments.extend(page_comments)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_comments)} comments")
                
                # Delay giữa các trang để tránh bị ban
                if page_num < max_page:
                    time.sleep(1)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_comments)} comments từ {max_page} trang ({comment_type}-level)")
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []

    def _scrape_comments_worker(self, page, url, comment_type="chapter"):
        """
        Worker function để lấy comments - dùng page từ worker thay vì self.page
        """
        try:
            current_url = page.url
            if url not in current_url:
                # Delay trước khi request comments
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
                page.goto(url, timeout=config.TIMEOUT)
                time.sleep(2)
            
            safe_print(f"      💬 Đang lấy comments ({comment_type}-level)...")
            
            # Delay trước khi lấy số trang
            time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            # Tìm số trang tối đa
            max_page = self._get_max_comment_page_worker(page, url)
            
            all_comments = []
            
            # Lấy comments từ tất cả các trang
            for page_num in range(1, max_page + 1):
                safe_print(f"        📄 Đang lấy trang {page_num}/{max_page}...")
                
                # Tạo URL cho trang này
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
                
                # Delay trước khi request trang comments
                if page_num > 1:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                
                # Lấy comments từ trang này
                page_comments = self._scrape_comments_from_page_worker(page, page_url)
                all_comments.extend(page_comments)
                
                safe_print(f"        ✅ Trang {page_num}: Lấy được {len(page_comments)} comments")
                
                # Delay giữa các trang comments
                if page_num < max_page:
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
            
            safe_print(f"      ✅ Tổng cộng lấy được {len(all_comments)} comments từ {max_page} trang ({comment_type}-level)")
            return all_comments
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy comments: {e}")
            return []

    def _get_max_comment_page_worker(self, page, url):
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

    def _scrape_comments_from_page_worker(self, page, page_url):
        """Lấy comments từ một trang cụ thể - dùng page từ worker"""
        comments = []
        
        try:
            # Delay trước khi request
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
                    
                    comment_data = self._scrape_single_comment_recursive(comment_elem)
                    if comment_data:
                        comments.append(comment_data)
                except Exception as e:
                    continue
            
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy comments từ trang: {e}")
            return []

    def _scrape_webnovel_chapter_comments(self, page, chapter_url):
        """
        Scrape TẤT CẢ comments của một chapter trên Webnovel
        Webnovel dùng infinite scroll và có nút comment để mở comment section
        """
        comments = []
        try:
            safe_print(f"        💬 Đang lấy Webnovel chapter comments...")
            
            # Bước 1: Tìm và click nút comment
            try:
                comment_button_selectors = [
                    "button:has-text('Comment')",
                    "button:has-text('comment')",
                    "a:has-text('Comment')",
                    ".comment-btn",
                    "button[class*='comment']",
                    "div[class*='comment-button']"
                ]
                
                comment_button = None
                for selector in comment_button_selectors:
                    try:
                        btn = page.locator(selector).first
                        if btn.count() > 0:
                            comment_button = btn
                            safe_print(f"        🔘 Tìm thấy comment button: {selector}")
                            break
                    except:
                        continue
                
                if comment_button:
                    # Scroll đến button và click
                    comment_button.scroll_into_view_if_needed()
                    time.sleep(1)
                    comment_button.click()
                    safe_print(f"        ✅ Đã click comment button")
                    time.sleep(3)  # Đợi comment section load
                else:
                    safe_print(f"        ⚠️ Không tìm thấy comment button, thử scroll xuống")
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
            except Exception as e:
                safe_print(f"        ⚠️ Lỗi khi click comment button: {e}")
            
            # Bước 2: Scroll infinite để load TẤT CẢ comments
            safe_print(f"        📜 Đang scroll để load TẤT CẢ chapter comments...")
            previous_height = 0
            no_change_count = 0
            max_scrolls = 30  # Giới hạn cho chapter comments (ít hơn story comments)
            
            for scroll_attempt in range(max_scrolls):
                # Scroll xuống
                page.evaluate("window.scrollBy(0, 500)")
                time.sleep(1)
                
                # Kiểm tra xem page có tăng chiều cao không
                current_height = page.evaluate("document.body.scrollHeight")
                if current_height == previous_height:
                    no_change_count += 1
                    if no_change_count >= 3:  # 3 lần liên tiếp không thay đổi -> đã hết
                        safe_print(f"        ✅ Đã scroll hết chapter comments (sau {scroll_attempt + 1} lần)")
                        break
                else:
                    no_change_count = 0
                    previous_height = current_height
            
            # Bước 3: Parse comments giống như story comments
            # Tìm các comment items
            page_text = page.locator("body").inner_text()
            safe_print(f"        🔍 Đang tìm chapter comments...")
            
            # Thử tìm comment containers với nhiều selectors
            comment_containers = []
            comment_selectors = [
                "div[class*='comment']",
                "li[class*='comment']",
                "div[class*='review']",
                ".j_comment_list li",
                "div.comment-item"
            ]
            
            for selector in comment_selectors:
                try:
                    items = page.locator(selector).all()
                    if len(items) > 0:
                        safe_print(f"        ✅ Tìm thấy {len(items)} items với selector: {selector}")
                        comment_containers = items
                        break
                except:
                    continue
            
            if not comment_containers:
                safe_print(f"        ⚠️ Không tìm thấy comment containers")
                return []
            
            # Parse từng comment
            import hashlib
            for idx, container in enumerate(comment_containers):
                try:
                    # Lấy toàn bộ text
                    full_text = container.inner_text().strip()
                    if not full_text or len(full_text) < 5:
                        continue
                    
                    # Tìm username (thường có link profile)
                    username = ""
                    try:
                        username_links = container.locator("a[href*='/profile'], a[href*='/user']").all()
                        if username_links:
                            username = username_links[0].inner_text().strip()
                    except:
                        pass
                    
                    if not username:
                        username = f"User_{idx}"
                    
                    # Lấy comment content
                    content_text = full_text
                    
                    # Filter out metadata (LV, time, etc.)
                    lines = content_text.split('\n')
                    filtered_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Skip metadata lines
                        if re.match(r'^LV\s+\d+', line):
                            continue
                        if line == username:
                            continue
                        if re.match(r'^\d+(s|m|h|d|w|mth|yr)$', line):
                            continue
                        filtered_lines.append(line)
                    
                    content_text = '\n'.join(filtered_lines)
                    
                    if not content_text:
                        continue
                    
                    # Tìm GIF nếu có
                    try:
                        gif_imgs = container.locator("img[src*='.gif']").all()
                        for gif_img in gif_imgs:
                            gif_url = gif_img.get_attribute("src")
                            if gif_url and not gif_url.startswith("http"):
                                gif_url = "https:" + gif_url
                            content_text += f"\n[GIF: {gif_url}]"
                    except:
                        pass
                    
                    # Lấy time
                    time_text = ""
                    try:
                        time_patterns = [r'\d+s', r'\d+m', r'\d+h', r'\d+d', r'\d+w', r'\d+mth', r'\d+yr']
                        for pattern in time_patterns:
                            matches = re.findall(pattern, full_text)
                            if matches:
                                time_text = matches[0]
                                break
                    except:
                        pass
                    
                    # Generate comment_id
                    comment_id = (
                        container.get_attribute("id") or 
                        container.get_attribute("data-id") or 
                        container.get_attribute("data-comment-id") or
                        ""
                    )
                    if not comment_id:
                        comment_id = hashlib.md5(f"{username}_{time_text}_{content_text[:20]}".encode()).hexdigest()[:12]
                    
                    # Tạo comment object
                    comment_data = {
                        "comment_id": comment_id,
                        "content": content_text,
                        "time": time_text,
                        "user_id": username,
                        "parent_id": "",
                        "replies": []
                    }
                    
                    comments.append(comment_data)
                    
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi parse comment {idx}: {e}")
                    continue
            
            safe_print(f"        ✅ Đã lấy {len(comments)} chapter comments")
            return comments
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi lấy chapter comments: {e}")
            return []

    def _scrape_single_comment_recursive(self, comment_elem):
        """
        Hàm đệ quy để lấy một comment và tất cả replies của nó
        Cấu trúc HTML:
        - div.comment
          - div.media.media-v2 (nội dung comment chính)
          - ul.subcomments (chứa các replies)
            - div.comment (reply, có thể có ul.subcomments riêng)
        """
        try:
            # Lấy comment container (div.media.media-v2)
            media_elem = comment_elem.locator("div.media.media-v2").first
            if media_elem.count() == 0:
                return None
            
            # Lấy comment ID từ id attribute
            comment_id = media_elem.get_attribute("id") or ""
            if comment_id.startswith("comment-container-"):
                comment_id = comment_id.replace("comment-container-", "")
            
            # Lấy username - theo cấu trúc HTML: h4.media-heading > span.name > strong > a
            username = ""
            try:
                # Cấu trúc: h4.media-heading > span.name > a[href*='/profile/']
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
                        username_elem = media_elem.locator(selector).first
                        if username_elem.count() > 0:
                            username = username_elem.inner_text().strip()
                            if username:
                                break
                    except:
                        continue
                
                # Nếu vẫn không tìm thấy, thử lấy từ bất kỳ link profile nào trong media-heading
                if not username:
                    try:
                        username_elem = media_elem.locator(".media-heading a[href*='/profile/']").first
                        if username_elem.count() > 0:
                            username = username_elem.inner_text().strip()
                    except:
                        pass
                        
                if not username:
                    username = "[Unknown]"
            except:
                username = "[Unknown]"
            
            # Lấy comment text/content - lấy tất cả các đoạn văn để giữ format
            comment_text = ""
            try:
                media_body = media_elem.locator(".media-body").first
                if media_body.count() > 0:
                    # Lấy tất cả các đoạn văn trong comment
                    paragraphs = media_body.locator("p").all()
                    
                    if paragraphs:
                        # Nếu có nhiều đoạn văn, nối lại với xuống dòng
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
                        # Nếu không có thẻ p, lấy toàn bộ text từ media-body
                        full_text = media_body.inner_text().strip()
                        
                        # Loại bỏ username nếu có ở đầu
                        if username and full_text.startswith(username):
                            comment_text = full_text[len(username):].strip()
                        else:
                            comment_text = full_text
                        
                        # Loại bỏ các phần không phải nội dung (như timestamp, rep count)
                        # Các phần này thường ở cuối, có thể có format như "7 years ago" hoặc "Rep (63)"
                        lines = comment_text.split('\n')
                        cleaned_lines = []
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            # Bỏ qua dòng chứa "years ago", "Rep (", "Reply", "Report"
                            if any(x in line.lower() for x in ['years ago', 'months ago', 'days ago', 'hours ago', 
                                                                'rep (', 'reply', 'report']):
                                continue
                            cleaned_lines.append(line)
                        comment_text = '\n'.join(cleaned_lines).strip()
            except Exception as e:
                comment_text = ""
            
            # Lấy timestamp
            timestamp = ""
            try:
                time_elem = media_elem.locator("time, .timestamp, [class*='time'], [class*='date']").first
                if time_elem.count() > 0:
                    timestamp = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # Tạo cấu trúc comment theo schema mới
            comment_data = {
                "comment_id": comment_id,
                "time": timestamp,
                "content": comment_text,
                "user_id": "",  # TODO: extract if available
                "story_id": "",  # Will be filled by parent
                "chapter_id": "",  # Will be filled if chapter comment
                "parent_id": "",  # Will be filled if reply
                "replies": []
            }
            
            # Lấy replies (subcomments) - ĐỆ QUY
            try:
                subcomments_list = comment_elem.locator("ul.subcomments").first
                if subcomments_list.count() > 0:
                    # Lấy tất cả các comment con trong ul.subcomments
                    reply_comments = subcomments_list.locator("div.comment").all()
                    
                    for reply_elem in reply_comments:
                        reply_data = self._scrape_single_comment_recursive(reply_elem)
                        if reply_data:
                            comment_data["replies"].append(reply_data)
            except Exception as e:
                # Không có replies hoặc lỗi khi lấy
                pass
            
            return comment_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse comment: {e}")
            return None

    def _scrape_reviews(self, fiction_url):
        """
        Lấy tất cả reviews từ trang fiction
        Theo scheme: review id, title, username, at chapter, time, content, score (overall, style, story, grammar, character)
        """
        reviews = []
        try:
            safe_print("      📝 Đang lấy reviews từ trang fiction...")
            
            # Đảm bảo đang ở trang fiction
            self.page.goto(fiction_url, timeout=config.TIMEOUT)
            time.sleep(2)
            
            # Scroll xuống để load reviews section
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Tìm reviews section - có thể là tab "Reviews" hoặc section riêng
            # Thử tìm các selector phổ biến cho reviews
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
            
            # Nếu không tìm thấy với selector thông thường, thử tìm trong tabs
            if not review_elements:
                try:
                    # Thử click vào tab "Reviews" nếu có
                    reviews_tab = self.page.locator("a[href*='reviews'], button:has-text('Reviews'), .nav-tabs a:has-text('Reviews')").first
                    if reviews_tab.count() > 0:
                        reviews_tab.click()
                        time.sleep(3)
                        # Thử lại với các selector
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
            
            # Parse từng review
            for review_elem in review_elements:
                try:
                    review_data = self._parse_single_review(review_elem)
                    if review_data:
                        reviews.append(review_data)
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
                    continue
            
            safe_print(f"      ✅ Đã lấy được {len(reviews)} reviews")
            return reviews
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi lấy reviews: {e}")
            return []

    def _parse_single_review(self, review_elem):
        """
        Parse một review element thành dictionary theo scheme
        """
        try:
            # Lấy review ID
            review_id = ""
            try:
                review_id = review_elem.get_attribute("id") or review_elem.get_attribute("data-id") or ""
                if review_id.startswith("review-"):
                    review_id = review_id.replace("review-", "")
            except:
                pass
            
            # Lấy title
            title = ""
            try:
                title_elem = review_elem.locator("h3, h4, .review-title, [class*='title']").first
                if title_elem.count() > 0:
                    title = title_elem.inner_text().strip()
            except:
                pass
            
            # Lấy username
            username = ""
            try:
                username_elem = review_elem.locator("a[href*='/profile/'], .username, .reviewer-name, [class*='username']").first
                if username_elem.count() > 0:
                    username = username_elem.inner_text().strip()
            except:
                username = "[Unknown]"
            
            # Lấy "at chapter" - chapter mà review được viết
            at_chapter = ""
            try:
                chapter_elem = review_elem.locator("a[href*='/chapter/'], .chapter-link, [class*='chapter']").first
                if chapter_elem.count() > 0:
                    at_chapter = chapter_elem.inner_text().strip()
                    # Hoặc lấy từ href
                    if not at_chapter:
                        href = chapter_elem.get_attribute("href") or ""
                        if "/chapter/" in href:
                            at_chapter = href.split("/chapter/")[1].split("/")[0]
            except:
                pass
            
            # Lấy time
            time_str = ""
            try:
                time_elem = review_elem.locator("time, .timestamp, [class*='time'], [class*='date']").first
                if time_elem.count() > 0:
                    time_str = time_elem.get_attribute("datetime") or time_elem.inner_text().strip()
            except:
                pass
            
            # Lấy content
            content = ""
            try:
                content_elem = review_elem.locator(".review-content, .review-text, [class*='content'], [class*='text']").first
                if content_elem.count() > 0:
                    content = content_elem.inner_text().strip()
            except:
                pass
            
            # Lấy scores (overall, style, story, grammar, character)
            scores = {
                "overall": "",
                "style": "",
                "story": "",
                "grammar": "",
                "character": ""
            }
            
            try:
                # Tìm các score elements
                score_elements = review_elem.locator(".score, .rating, [class*='score'], [class*='rating']").all()
                for score_elem in score_elements:
                    try:
                        score_text = score_elem.inner_text().strip()
                        score_label = score_elem.get_attribute("data-label") or ""
                        # Có thể parse từ text hoặc từ data attributes
                        if "overall" in score_label.lower() or "overall" in score_text.lower():
                            scores["overall"] = score_text
                        elif "style" in score_label.lower() or "style" in score_text.lower():
                            scores["style"] = score_text
                        elif "story" in score_label.lower() or "story" in score_text.lower():
                            scores["story"] = score_text
                        elif "grammar" in score_label.lower() or "grammar" in score_text.lower():
                            scores["grammar"] = score_text
                        elif "character" in score_label.lower() or "character" in score_text.lower():
                            scores["character"] = score_text
                    except:
                        continue
            except:
                pass
            
            # Tạo review data theo scheme
            review_data = {
                "review_id": review_id,
                "title": title,
                "username": username,
                "at_chapter": at_chapter,
                "time": time_str,
                "content": content,
                "score": scores
            }
            
            return review_data
            
        except Exception as e:
            safe_print(f"        ⚠️ Lỗi khi parse review: {e}")
            return None

    def _save_to_json(self, data):
        """
        Lưu dữ liệu vào cả file JSON và MongoDB (nếu được bật)
        Tách dữ liệu thành nhiều collections: stories, chapters, comments, reviews, scores, users
        """
        # 1. Lưu vào file JSON (luôn luôn)
        # Sanitize filename for Windows (remove colons, replace spaces with underscores)
        title = utils.clean_text(data.get('name', data.get('title', 'unknown')))
        title = re.sub(r'[<>:"/\\|?*]', '', title)  # Remove Windows-illegal chars
        title = re.sub(r'\s+', '_', title)  # Replace spaces with underscores
        filename = f"{data['id']}_{title}.json"
        save_path = os.path.join(config.JSON_DIR, filename)
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        safe_print(f"💾 Đã lưu dữ liệu vào file: {save_path}")
        
        # 2. Lưu vào MongoDB - tách thành nhiều collections
        if self.mongo_collections:
            try:
                story_id = data['id']
                
                # 2.1. Lưu STORY vào collection "stories"
                story_data = {
                    "id": story_id,
                    "name": data.get("name", ""),
                    "url": data.get("url", ""),
                    "cover_image": data.get("cover_image", ""),
                    "author": data.get("author", ""),
                    "category": data.get("category", ""),
                    "status": data.get("status", ""),
                    "tags": data.get("tags", []),
                    "description": data.get("description", ""),
                    "stats": {
                        "views": data.get("stats", {}).get("views", {})
                    }
                }
                
                stories_col = self.mongo_collections["stories"]
                existing_story = stories_col.find_one({"id": story_id})
                if existing_story:
                    stories_col.update_one({"id": story_id}, {"$set": story_data})
                    safe_print(f"🔄 Đã cập nhật story trong MongoDB (ID: {story_id})")
                else:
                    stories_col.insert_one(story_data)
                    safe_print(f"✅ Đã lưu story vào MongoDB (ID: {story_id})")
                
                # 2.2. Lưu SCORES vào collection "scores"
                if "stats" in data and "score" in data["stats"]:
                    score_data = {
                        "story_id": story_id,
                        "overall_score": data["stats"]["score"].get("overall_score", ""),
                        "style_score": data["stats"]["score"].get("style_score", ""),
                        "story_score": data["stats"]["score"].get("story_score", ""),
                        "grammar_score": data["stats"]["score"].get("grammar_score", ""),
                        "character_score": data["stats"]["score"].get("character_score", "")
                    }
                    
                    scores_col = self.mongo_collections["scores"]
                    existing_score = scores_col.find_one({"story_id": story_id})
                    if existing_score:
                        scores_col.update_one({"story_id": story_id}, {"$set": score_data})
                    else:
                        scores_col.insert_one(score_data)
                    safe_print(f"✅ Đã lưu scores vào MongoDB (story_id: {story_id})")
                
                # 2.3. Lưu CHAPTERS vào collection "chapters"
                chapters_col = self.mongo_collections["chapters"]
                chapters = data.get("chapters", [])
                chapters_saved = 0
                for chapter in chapters:
                    chapter_data = {
                        "id": chapter.get("id", ""),
                        "story_id": story_id,
                        "name": chapter.get("name", ""),
                        "url": chapter.get("url", ""),
                        "content": chapter.get("content", "")
                    }
                    
                    chapter_id = chapter_data["id"]
                    if chapter_id:
                        existing_chapter = chapters_col.find_one({"id": chapter_id, "story_id": story_id})
                        if existing_chapter:
                            chapters_col.update_one(
                                {"id": chapter_id, "story_id": story_id},
                                {"$set": chapter_data}
                            )
                        else:
                            chapters_col.insert_one(chapter_data)
                        chapters_saved += 1
                        
                        # 2.4. Lưu COMMENTS của chapter vào collection "comments"
                        chapter_comments = chapter.get("comments", [])
                        if chapter_comments:
                            self._save_comments_to_mongo(chapter_comments, story_id, chapter_id, "chapter")
                
                safe_print(f"✅ Đã lưu {chapters_saved} chapters vào MongoDB (story_id: {story_id})")
                
                # 2.5. Lưu REVIEWS vào collection "reviews"
                reviews_col = self.mongo_collections["reviews"]
                reviews = data.get("reviews", [])
                reviews_saved = 0
                for review in reviews:
                    review_data = {
                        "review_id": review.get("review_id", ""),
                        "story_id": story_id,
                        "title": review.get("title", ""),
                        "username": review.get("username", ""),
                        "at_chapter": review.get("at_chapter", ""),
                        "time": review.get("time", ""),
                        "content": review.get("content", ""),
                        "score": review.get("score", {})
                    }
                    
                    review_id = review_data["review_id"]
                    if review_id:
                        existing_review = reviews_col.find_one({"review_id": review_id, "story_id": story_id})
                        if existing_review:
                            reviews_col.update_one(
                                {"review_id": review_id, "story_id": story_id},
                                {"$set": review_data}
                            )
                        else:
                            reviews_col.insert_one(review_data)
                        reviews_saved += 1
                        
                        # Lưu user từ review
                        username = review_data.get("username", "")
                        if username:
                            self._save_user_to_mongo(username)
                
                safe_print(f"✅ Đã lưu {reviews_saved} reviews vào MongoDB (story_id: {story_id})")
                
                # 2.6. Lưu vào collection cũ để tương thích (nếu cần)
                if self.mongo_collection:
                    existing = self.mongo_collection.find_one({"id": story_id})
                    if existing:
                        self.mongo_collection.update_one({"id": story_id}, {"$set": data})
                    else:
                        self.mongo_collection.insert_one(data)
                
                safe_print(f"🎉 Đã hoàn thành lưu tất cả dữ liệu vào MongoDB!")
                
            except Exception as e:
                safe_print(f"⚠️ Lỗi khi lưu vào MongoDB: {e}")
                safe_print("   Dữ liệu vẫn được lưu vào file JSON")
                import traceback
                safe_print(traceback.format_exc())
    
    def _save_comments_to_mongo(self, comments, story_id, parent_id, parent_type="chapter"):
        """
        Lưu comments vào MongoDB (đệ quy để lưu cả replies)
        parent_type: "chapter" hoặc "story"
        """
        if not self.mongo_collections:
            return
        
        comments_col = self.mongo_collections["comments"]
        
        for comment in comments:
            comment_data = {
                "comment_id": comment.get("comment_id", ""),
                "story_id": story_id,
                "parent_id": parent_id,
                "parent_type": parent_type,
                "username": comment.get("username", ""),
                "comment_text": comment.get("comment_text", ""),
                "time": comment.get("time", "")
            }
            
            comment_id = comment_data["comment_id"]
            if comment_id:
                # Kiểm tra xem đã có comment này chưa (thêm parent_type để chắc chắn)
                existing = comments_col.find_one({
                    "comment_id": comment_id,
                    "story_id": story_id,
                    "parent_id": parent_id,
                    "parent_type": parent_type
                })
                
                if existing:
                    comments_col.update_one(
                        {"comment_id": comment_id, "story_id": story_id, "parent_id": parent_id, "parent_type": parent_type},
                        {"$set": comment_data}
                    )
                else:
                    comments_col.insert_one(comment_data)
                
                # Lưu user từ comment
                username = comment_data.get("username", "")
                if username:
                    self._save_user_to_mongo(username)
                
                # Lưu replies (đệ quy)
                replies = comment.get("replies", [])
                if replies:
                    self._save_comments_to_mongo(replies, story_id, comment_id, "comment")
    
    def _save_user_to_mongo(self, username):
        """
        Lưu user vào collection "users" (chỉ lưu username, có thể mở rộng sau)
        """
        if not self.mongo_collections or not username or username == "[Unknown]":
            return
        
        users_col = self.mongo_collections["users"]
        
        # Kiểm tra xem user đã tồn tại chưa
        existing_user = users_col.find_one({"username": username})
        if not existing_user:
            user_data = {
                "username": username,
                "created_at": time.time()  # Timestamp khi tạo
            }
            users_col.insert_one(user_data)